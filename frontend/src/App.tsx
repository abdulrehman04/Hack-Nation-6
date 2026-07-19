import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import LoginPage from './components/LoginPage'
import UploadForm from './components/UploadForm'
import ConfirmView from './components/ConfirmView'
import UnderstandView from './components/UnderstandView'
import PrepareView from './components/PrepareView'
import DiscoverView from './components/DiscoverView'
import {
  deleteMyData,
  extractDocuments,
  fetchDiscover,
  fetchPrepare,
  fetchUnderstand,
  listMyProfiles,
} from './api'
import { getIdToken, logOut, onAuth } from './firebase'
import type { Account } from './firebase'
import type { AuditEvent, Doc, DiscoverData, EnrichedProfile, PrepareData } from './types'

type Screen = 'login' | 'flow' | 'discover'

const STEPS = ['Upload documents', 'Review & confirm', 'Understand & confirm', 'Prepare packet']

// Documents are named hh-XXX_... in this challenge's synthetic dataset;
// the household_id is that prefix, uppercased.
function householdIdFromFileName(fileName: string): string | null {
  const match = fileName.match(/^(hh-\d+)/i)
  return match ? match[1].toUpperCase() : null
}

// Rebuild editable docs from a saved packet, so returning users can correct fields
// even with nothing uploaded this session.
function reconstructDocs(data: PrepareData): Doc[] {
  return data.documents.map((d) => ({
    file_name: d.file_name,
    document_type: d.document_type,
    detected: true,
    method: 'text_layer',
    injected_instruction: null,
    page_image: '',
    page_size_points: [612, 792],
    fields: d.fields.map((f) => ({
      name: f.field,
      value: f.value,
      confidence: f.confidence,
      source_method: null,
      source_bbox: f.bbox,
      status: f.status,
      reason: null,
    })),
  }))
}

function LockIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="11" width="18" height="11" rx="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  )
}

function ChevronIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m6 9 6 6 6-6" />
    </svg>
  )
}

export default function App() {
  const [account, setAccount] = useState<Account | null>(null)
  const [ready, setReady] = useState(false)
  const [screen, setScreen] = useState<Screen>('login')
  const [documents, setDocuments] = useState<Doc[]>([])
  const [audit, setAudit] = useState<AuditEvent[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [enrichedProfile, setEnrichedProfile] = useState<EnrichedProfile | null>(null)
  const [householdId, setHouseholdId] = useState<string | null>(null)
  const [prepareData, setPrepareData] = useState<PrepareData | null>(null)
  const [resultsLoading, setResultsLoading] = useState(false)
  const [discoverData, setDiscoverData] = useState<DiscoverData | null>(null)
  const [discoverLoading, setDiscoverLoading] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [activeStage, setActiveStage] = useState(0)
  const [expanded, setExpanded] = useState<number>(0) // only one section open at a time
  const initialized = useRef(false)

  const uploadRef = useRef<HTMLDivElement>(null)
  const reviewRef = useRef<HTMLDivElement>(null)
  const understandRef = useRef<HTMLDivElement>(null)
  const prepareRef = useRef<HTMLDivElement>(null)
  const sectionRefs = [uploadRef, reviewRef, understandRef, prepareRef]

  // Derived gate state: each stage unlocks only once the prior one has produced data.
  const reviewUnlocked = documents.length > 0
  const resultsUnlocked = !!enrichedProfile && !!prepareData
  const stageUnlocked = [true, reviewUnlocked, resultsUnlocked, resultsUnlocked]

  // Open one section (accordion) and scroll to it once its body has committed.
  function goToStage(index: number) {
    setExpanded(index)
    setTimeout(() => sectionRefs[index].current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 90)
  }

  function toggleStage(index: number) {
    setExpanded((prev) => (prev === index ? -1 : index))
  }

  // Fetch dashboard + packet together, both computed from the saved profile.
  async function loadResults(hhId: string, token: string): Promise<PrepareData> {
    const [understand, prepare] = await Promise.all([
      fetchUnderstand(hhId, token),
      fetchPrepare(hhId, token),
    ])
    setHouseholdId(hhId)
    setEnrichedProfile(understand)
    setPrepareData(prepare)
    return prepare
  }

  // Load the signed-in user's saved profile into the single-page flow.
  async function enterDashboard() {
    setError(null)
    try {
      const token = await getIdToken()
      const profiles = token ? await listMyProfiles(token) : []
      const hhId = profiles.map((p) => p.household_id).find((id): id is string => !!id)
      setScreen('flow')
      if (hhId && token) {
        setResultsLoading(true)
        const prepare = await loadResults(hhId, token)
        setDocuments(reconstructDocs(prepare)) // populate Review for returning users
        goToStage(2) // returning users land on Understand
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setScreen('flow')
    } finally {
      setResultsLoading(false)
      setReady(true)
    }
  }

  // Track sign-in state. The first callback decides the landing screen.
  useEffect(() => onAuth((next) => {
    setAccount(next)
    if (!initialized.current) {
      initialized.current = true
      if (next) {
        enterDashboard()
      } else {
        setScreen('login')
        setReady(true)
      }
    }
  }), [])

  // Scroll-spy: highlight whichever stage sits under a line ~45% down the viewport.
  useEffect(() => {
    if (screen !== 'flow' || !ready) return
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((e) => e.isIntersecting)
      if (visible.length === 0) return
      const top = visible.reduce((a, b) => (a.boundingClientRect.top < b.boundingClientRect.top ? a : b))
      const idx = sectionRefs.findIndex((r) => r.current === top.target)
      if (idx >= 0) setActiveStage(idx)
    }, { rootMargin: '-45% 0px -50% 0px', threshold: 0 })
    sectionRefs.forEach((r) => r.current && observer.observe(r.current))
    return () => observer.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screen, ready])

  async function addFiles(files: File[]) {
    if (files.length === 0) return
    setError(null)
    setBusy(true)
    try {
      const res = await extractDocuments(files)
      setDocuments((prev) => [...prev, ...res.documents])
      const n = res.documents.length
      setAudit((prev) => [
        ...prev,
        { action: 'uploaded', detail: `${n} document${n === 1 ? '' : 's'}`, at: new Date().toISOString() },
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  function startNew() {
    setDocuments([])
    setAudit([])
    setEnrichedProfile(null)
    setHouseholdId(null)
    setPrepareData(null)
    setError(null)
    setScreen('flow')
    goToStage(0)
  }

  function removeDoc(index: number) {
    setDocuments((prev) => prev.filter((_, i) => i !== index))
  }

  async function signOut() {
    await logOut()
    setDocuments([])
    setAudit([])
    setEnrichedProfile(null)
    setHouseholdId(null)
    setPrepareData(null)
    setExpanded(0)
    setScreen('login')
  }

  async function confirmDelete() {
    setDeleting(true)
    setDeleteError(null)
    try {
      const token = await getIdToken()
      if (token) await deleteMyData(token)
      setShowDelete(false)
      await signOut()
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : String(e))
    } finally {
      setDeleting(false)
    }
  }

  // After a save (or edit re-save), refresh dashboard + packet and reveal them.
  async function afterSaved(confirmedDocuments: Doc[]) {
    const hhId = confirmedDocuments
      .map((d) => householdIdFromFileName(d.file_name))
      .find((id): id is string => id !== null)
    if (!hhId) {
      setError('Could not determine which household this application belongs to.')
      return
    }
    setDocuments(confirmedDocuments)
    setError(null)
    setResultsLoading(true)
    try {
      const token = await getIdToken()
      if (!token) throw new Error('Please sign in again to view your dashboard.')
      await loadResults(hhId, token)
      goToStage(2)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setResultsLoading(false)
    }
  }

  // Stretch: browse public LIHTC properties. Loaded lazily; no household data leaves the client.
  async function onDiscover() {
    setError(null)
    if (discoverData) {
      setScreen('discover')
      return
    }
    setDiscoverLoading(true)
    try {
      const result = await fetchDiscover()
      setDiscoverData(result)
      setScreen('discover')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setDiscoverLoading(false)
    }
  }

  if (!ready) {
    return (
      <div className="page">
        <main className="content"><p className="status">Loading…</p></main>
      </div>
    )
  }

  if (screen === 'login') {
    return (
      <div className="page">
        <header className="masthead">
          <div className="masthead-inner">
            <span className="brand-mark">RealDoor</span>
            <span className="brand-sub">Affordable Housing Application Readiness</span>
          </div>
        </header>
        <main className="content">
          {error && <p role="alert" className="notice notice-error">{error}</p>}
          <LoginPage onLoggedIn={enterDashboard} onStartNew={startNew} />
        </main>
      </div>
    )
  }

  if (screen === 'discover') {
    return (
      <div className="page">
        <Masthead account={account} onDelete={() => { setDeleteError(null); setShowDelete(true) }} onSignOut={signOut} />
        <main className="content">
          {discoverLoading && <p role="status" className="status">Loading properties…</p>}
          {discoverData && <DiscoverView data={discoverData} onBack={() => setScreen('flow')} />}
        </main>
        <DeleteModal
          show={showDelete} deleting={deleting} error={deleteError}
          onCancel={() => setShowDelete(false)} onConfirm={confirmDelete}
        />
      </div>
    )
  }

  return (
    <div className="page">
      <p className="gov-banner">
        An application-readiness tool. It organizes your documents; a housing officer decides eligibility.
      </p>

      <Masthead account={account} onDelete={() => { setDeleteError(null); setShowDelete(true) }} onSignOut={signOut} />

      <nav className="steps steps-sticky" aria-label="Progress">
        <ol className="steps-list">
          {STEPS.map((label, i) => {
            const unlocked = stageUnlocked[i]
            const done = unlocked && i < activeStage
            const cls = `step${i === activeStage ? ' step-current' : ''}${done ? ' step-done' : ''}`
              + `${!unlocked ? ' step-locked' : ''}`
            return (
              <li key={label} className={cls} aria-current={i === activeStage ? 'step' : undefined}>
                <button type="button" className="step-btn" disabled={!unlocked} onClick={() => goToStage(i)}>
                  <span className="step-num">
                    {!unlocked ? <LockIcon /> : done ? <CheckIcon /> : i + 1}
                  </span>
                  <span className="step-label">{label}</span>
                </button>
              </li>
            )
          })}
        </ol>
      </nav>

      <main className="content flow">
        {error && <p role="alert" className="notice notice-error">{error}</p>}

        <StageSection
          index={1} title="Upload documents" sectionRef={uploadRef}
          locked={false} expanded={expanded === 0} onToggle={() => toggleStage(0)}
        >
          <UploadForm
            documents={documents}
            busy={busy}
            onAddFiles={addFiles}
            onRemove={removeDoc}
            onContinue={() => goToStage(1)}
          />
        </StageSection>

        <StageSection
          index={2} title="Review & confirm" sectionRef={reviewRef}
          locked={!reviewUnlocked} hint="Upload your documents above to unlock."
          expanded={expanded === 1} onToggle={() => toggleStage(1)}
        >
          <ConfirmView
            documents={documents}
            audit={audit}
            onBack={() => goToStage(0)}
            onSaved={afterSaved}
          />
        </StageSection>

        <StageSection
          index={3} title="Understand & confirm" sectionRef={understandRef}
          locked={!resultsUnlocked} hint="Confirm your details in Review to unlock."
          expanded={expanded === 2} onToggle={() => toggleStage(2)}
        >
          {resultsLoading ? (
            <p role="status" className="status">Loading your dashboard…</p>
          ) : enrichedProfile && householdId ? (
            <UnderstandView
              profile={enrichedProfile}
              householdId={householdId}
              onContinue={() => goToStage(3)}
              onDiscover={onDiscover}
            />
          ) : null}
        </StageSection>

        <StageSection
          index={4} title="Prepare packet" sectionRef={prepareRef}
          locked={!resultsUnlocked} hint="Confirm your details in Review to unlock."
          expanded={expanded === 3} onToggle={() => toggleStage(3)}
        >
          {prepareData && householdId ? (
            <PrepareView
              data={prepareData}
              householdId={householdId}
              onBack={() => goToStage(2)}
              onEdit={() => goToStage(1)}
              onStartOver={startNew}
            />
          ) : null}
        </StageSection>
      </main>

      <DeleteModal
        show={showDelete} deleting={deleting} error={deleteError}
        onCancel={() => setShowDelete(false)} onConfirm={confirmDelete}
      />
    </div>
  )
}

function StageSection({ index, title, locked, expanded, hint, onToggle, sectionRef, children }: {
  index: number
  title: string
  locked: boolean
  expanded: boolean
  hint?: string
  onToggle: () => void
  sectionRef: React.RefObject<HTMLDivElement>
  children: ReactNode
}) {
  return (
    <div ref={sectionRef} className={`flow-section${expanded && !locked ? ' flow-section-open' : ''}`}>
      <button
        type="button"
        className="stage-header"
        disabled={locked}
        aria-expanded={locked ? undefined : expanded}
        onClick={onToggle}
      >
        <span className="stage-num">{locked ? <LockIcon /> : index}</span>
        <span className="stage-title">{title}</span>
        {locked
          ? <span className="stage-lock"><LockIcon /></span>
          : <span className={`stage-chevron${expanded ? ' open' : ''}`}><ChevronIcon /></span>}
      </button>
      {locked ? (
        <p className="stage-hint muted">{hint}</p>
      ) : (
        <div className="stage-body" hidden={!expanded}>{children}</div>
      )}
    </div>
  )
}

function Masthead({ account, onDelete, onSignOut }: {
  account: Account | null; onDelete: () => void; onSignOut: () => void
}) {
  return (
    <header className="masthead">
      <div className="masthead-inner">
        <span className="brand-mark">RealDoor</span>
        <span className="brand-sub">Affordable Housing Application Readiness</span>
        {account && (
          <div className="masthead-account">
            <span className="muted">{account.email}</span>
            <button type="button" className="btn-secondary btn-sm btn-danger" onClick={onDelete}>
              Delete my data
            </button>
            <button type="button" className="btn-secondary btn-sm" onClick={onSignOut}>Sign out</button>
          </div>
        )}
      </div>
    </header>
  )
}

function DeleteModal({ show, deleting, error, onCancel, onConfirm }: {
  show: boolean; deleting: boolean; error: string | null; onCancel: () => void; onConfirm: () => void
}) {
  if (!show) return null
  return (
    <div className="modal-overlay" onClick={() => !deleting && onCancel()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="delete-title" onClick={(e) => e.stopPropagation()}>
        <h2 id="delete-title">Delete your data?</h2>
        <p className="modal-lede">
          This permanently removes your saved profile and its documents. This cannot be undone.
        </p>
        {error && <p role="alert" className="notice notice-error">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onCancel} disabled={deleting}>Cancel</button>
          <button type="button" className="btn-primary btn-danger" onClick={onConfirm} disabled={deleting}>
            {deleting ? 'Deleting…' : 'Delete my data'}
          </button>
        </div>
      </div>
    </div>
  )
}
