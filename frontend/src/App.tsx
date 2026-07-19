import { useEffect, useRef, useState } from 'react'
import LoginPage from './components/LoginPage'
import AccountView from './components/AccountView'
import UploadForm from './components/UploadForm'
import ConfirmView from './components/ConfirmView'
import UnderstandView from './components/UnderstandView'
import PrepareView from './components/PrepareView'
import { deleteMyData, extractDocuments, fetchPrepare, fetchUnderstand, listMyProfiles } from './api'
import { getIdToken, logOut, onAuth } from './firebase'
import type { Account } from './firebase'
import type { AuditEvent, Doc, EnrichedProfile, PrepareData } from './types'

type View = 'login' | 'upload' | 'review' | 'understand' | 'prepare' | 'account'

const STEPS = ['Upload documents', 'Review & confirm', 'Understand & confirm', 'Prepare packet']

// Documents are named hh-XXX_... in this challenge's synthetic dataset;
// the household_id is that prefix, uppercased.
function householdIdFromFileName(fileName: string): string | null {
  const match = fileName.match(/^(hh-\d+)/i)
  return match ? match[1].toUpperCase() : null
}

export default function App() {
  const [account, setAccount] = useState<Account | null>(null)
  const [ready, setReady] = useState(false)
  const [view, setView] = useState<View>('login')
  const [documents, setDocuments] = useState<Doc[]>([])
  const [audit, setAudit] = useState<AuditEvent[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [enrichedProfile, setEnrichedProfile] = useState<EnrichedProfile | null>(null)
  const [householdId, setHouseholdId] = useState<string | null>(null)
  const [understandLoading, setUnderstandLoading] = useState(false)
  const [prepareData, setPrepareData] = useState<PrepareData | null>(null)
  const [prepareLoading, setPrepareLoading] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const initialized = useRef(false)

  // Load the signed-in user's saved profile and open their dashboard.
  async function enterDashboard() {
    setUnderstandLoading(true)
    setError(null)
    try {
      const token = await getIdToken()
      const profiles = token ? await listMyProfiles(token) : []
      const hhId = profiles.map((p) => p.household_id).find((id): id is string => !!id)
      if (!hhId) {
        setView('account') // signed in, but no dashboard data yet
        return
      }
      const result = await fetchUnderstand(hhId, token!)
      setHouseholdId(hhId)
      setEnrichedProfile(result)
      setView('understand')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setView('account')
    } finally {
      setUnderstandLoading(false)
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
        setView('login')
        setReady(true)
      }
    }
  }), [])

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
    setView('upload')
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
    setView('login')
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

  // After a save (or edit re-save), keep the confirmed values and open the dashboard.
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
    setUnderstandLoading(true)
    try {
      const token = await getIdToken()
      if (!token) throw new Error('Please sign in again to view your dashboard.')
      const result = await fetchUnderstand(hhId, token)
      setHouseholdId(hhId)
      setEnrichedProfile(result)
      setView('understand')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setUnderstandLoading(false)
    }
  }

  function editFromPrepare() {
    setError(null)
    if (documents.length > 0) {
      setView('review')
      return
    }
    // Returning user: no uploads in memory, so rebuild editable docs from the packet.
    if (!prepareData) return
    const reconstructed: Doc[] = prepareData.documents.map((d) => ({
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
    setDocuments(reconstructed)
    setView('review')
  }

  async function onContinueToPrepare() {
    if (!householdId) return
    setError(null)
    setPrepareLoading(true)
    try {
      const token = await getIdToken()
      if (!token) throw new Error('Please sign in again to prepare your packet.')
      const result = await fetchPrepare(householdId, token)
      setPrepareData(result)
      setView('prepare')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setPrepareLoading(false)
    }
  }

  const inFlow = view === 'upload' || view === 'review' || view === 'understand' || view === 'prepare'
  const stepIndex = view === 'upload' ? 0 : view === 'review' ? 1 : view === 'understand' ? 2 : 3
  const anyLoading = understandLoading || prepareLoading

  return (
    <div className="page">
      <p className="gov-banner">
        An application-readiness tool. It organizes your documents; a housing officer decides eligibility.
      </p>

      <header className="masthead">
        <div className="masthead-inner">
          <span className="brand-mark">RealDoor</span>
          <span className="brand-sub">Affordable Housing Application Readiness</span>
          {account && (
            <div className="masthead-account">
              <span className="muted">{account.email}</span>
              <button
                type="button"
                className="btn-secondary btn-sm btn-danger"
                onClick={() => { setDeleteError(null); setShowDelete(true) }}
              >
                Delete my data
              </button>
              <button type="button" className="btn-secondary btn-sm" onClick={signOut}>Sign out</button>
            </div>
          )}
        </div>
      </header>

      {inFlow && !anyLoading && (
        <nav className="steps" aria-label="Progress">
          <ol className="steps-list">
            {STEPS.map((label, i) => (
              <li
                key={label}
                className={`step${i === stepIndex ? ' step-current' : ''}${i < stepIndex ? ' step-done' : ''}`}
                aria-current={i === stepIndex ? 'step' : undefined}
              >
                <span className="step-num">{i + 1}</span>
                <span className="step-label">{label}</span>
              </li>
            ))}
          </ol>
        </nav>
      )}

      <main className="content">
        {!ready && <p className="status">Loading…</p>}
        {error && <p role="alert" className="notice notice-error">{error}</p>}
        {ready && understandLoading && <p role="status" className="status">Loading your dashboard…</p>}
        {ready && prepareLoading && <p role="status" className="status">Loading your packet…</p>}

        {ready && !anyLoading && (
          <>
            {view === 'login' && (
              <LoginPage onLoggedIn={enterDashboard} onStartNew={startNew} />
            )}

            {view === 'account' && account && (
              <AccountView account={account} onSignOut={signOut} />
            )}

            {view === 'upload' && (
              <UploadForm
                documents={documents}
                busy={busy}
                onAddFiles={addFiles}
                onRemove={removeDoc}
                onContinue={() => setView('review')}
              />
            )}

            {view === 'review' && (
              <ConfirmView
                documents={documents}
                audit={audit}
                onBack={() => setView('upload')}
                onSaved={afterSaved}
              />
            )}

            {view === 'understand' && enrichedProfile && householdId && (
              <UnderstandView
                profile={enrichedProfile}
                householdId={householdId}
                onContinue={onContinueToPrepare}
              />
            )}

            {view === 'prepare' && prepareData && householdId && (
              <PrepareView
                data={prepareData}
                householdId={householdId}
                onBack={() => setView('understand')}
                onEdit={editFromPrepare}
                onStartOver={startNew}
              />
            )}
          </>
        )}
      </main>

      {showDelete && (
        <div className="modal-overlay" onClick={() => !deleting && setShowDelete(false)}>
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="delete-title">Delete your data?</h2>
            <p className="modal-lede">
              This permanently removes your saved profile and its documents. This cannot be undone.
            </p>
            {deleteError && <p role="alert" className="notice notice-error">{deleteError}</p>}
            <div className="modal-actions">
              <button type="button" className="btn-secondary" onClick={() => setShowDelete(false)} disabled={deleting}>
                Cancel
              </button>
              <button type="button" className="btn-primary btn-danger" onClick={confirmDelete} disabled={deleting}>
                {deleting ? 'Deleting…' : 'Delete my data'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
