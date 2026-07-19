import { useEffect, useRef, useState } from 'react'
import LoginPage from './components/LoginPage'
import AccountView from './components/AccountView'
import UploadForm from './components/UploadForm'
import ConfirmView from './components/ConfirmView'
import UnderstandView from './components/UnderstandView'
import { extractDocuments, fetchUnderstand, listMyProfiles } from './api'
import { getIdToken, logOut, onAuth } from './firebase'
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
      const result = await fetchUnderstand(hhId)
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

  // After a new user saves and creates an account, open their dashboard.
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
          {account && (
            <div className="masthead-account">
              <span className="muted">{account.email}</span>
              <button type="button" className="btn-secondary btn-sm" onClick={signOut}>Sign out</button>
            </div>
          )}
        </div>
      </header>

      {inFlow && !understandLoading && (
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

        {ready && !understandLoading && (
          <>
            {view === 'login' && (
              <LoginPage onLoggedIn={enterDashboard} onStartNew={() => setView('upload')} />
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
                onBack={() => setView('upload')}
                onSaved={afterSaved}
              />
            )}

            {view === 'understand' && enrichedProfile && householdId && (
              <UnderstandView profile={enrichedProfile} householdId={householdId} />
            )}
          </>
        )}
      </main>
    </div>
  )
}
