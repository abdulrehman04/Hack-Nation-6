import { useEffect, useRef, useState } from 'react'
import LoginPage from './components/LoginPage'
import AccountView from './components/AccountView'
import UploadForm from './components/UploadForm'
import ConfirmView from './components/ConfirmView'
import UnderstandView from './components/UnderstandView'
import { extractDocuments, fetchUnderstand } from './api'
import { logOut, onAuth } from './firebase'
import type { Account } from './firebase'
import type { Doc, EnrichedProfile } from './types'

type View = 'login' | 'upload' | 'review' | 'understand' | 'account'

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
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [enrichedProfile, setEnrichedProfile] = useState<EnrichedProfile | null>(null)
  const [householdId, setHouseholdId] = useState<string | null>(null)
  const [understandLoading, setUnderstandLoading] = useState(false)
  const initialized = useRef(false)

  // Track sign-in state. Only the first callback picks the initial landing;
  // later changes (sign-up mid-flow, sign-out) are handled by explicit nav.
  useEffect(() => onAuth((next) => {
    setAccount(next)
    if (!initialized.current) {
      initialized.current = true
      setView(next ? 'account' : 'login')
      setReady(true)
    }
  }), [])

  async function addFiles(files: File[]) {
    if (files.length === 0) return
    setError(null)
    setBusy(true)
    try {
      const res = await extractDocuments(files)
      setDocuments((prev) => [...prev, ...res.documents])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  function removeDoc(index: number) {
    setDocuments((prev) => prev.filter((_, i) => i !== index))
  }

  async function signOut() {
    await logOut()
    setDocuments([])
    setEnrichedProfile(null)
    setHouseholdId(null)
    setView('login')
  }

  // After the profile is saved to the account, load its rules/threshold view.
  async function afterSaved(confirmedDocuments: Doc[]) {
    const hhId = confirmedDocuments
      .map((d) => householdIdFromFileName(d.file_name))
      .find((id): id is string => id !== null)
    if (!hhId) {
      setError('Could not determine which household this application belongs to.')
      return
    }
    setError(null)
    setUnderstandLoading(true)
    try {
      const result = await fetchUnderstand(hhId)
      setHouseholdId(hhId)
      setEnrichedProfile(result)
      setView('understand')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setUnderstandLoading(false)
    }
  }

  const inFlow = view === 'upload' || view === 'review' || view === 'understand'
  const stepIndex = view === 'upload' ? 0 : view === 'review' ? 1 : 2

  return (
    <div className="page">
      <p className="gov-banner">
        An application-readiness tool. It organizes your documents; a housing officer decides eligibility.
      </p>

      <header className="masthead">
        <div className="masthead-inner">
          <span className="brand-mark">RealDoor</span>
          <span className="brand-sub">Affordable Housing Application Readiness</span>
        </div>
      </header>

      {inFlow && (
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
        {understandLoading && <p role="status" className="notice">Loading rules and thresholds…</p>}

        {ready && view === 'login' && (
          <LoginPage
            onLoggedIn={() => setView('account')}
            onStartNew={() => setView('upload')}
          />
        )}

        {ready && view === 'account' && account && (
          <AccountView account={account} onSignOut={signOut} />
        )}

        {ready && view === 'upload' && (
          <UploadForm
            documents={documents}
            busy={busy}
            onAddFiles={addFiles}
            onRemove={removeDoc}
            onContinue={() => setView('review')}
          />
        )}

        {ready && view === 'review' && (
          <ConfirmView
            documents={documents}
            onBack={() => setView('upload')}
            onSaved={afterSaved}
          />
        )}

        {ready && view === 'understand' && enrichedProfile && householdId && (
          <UnderstandView profile={enrichedProfile} householdId={householdId} />
        )}
      </main>
    </div>
  )
}
