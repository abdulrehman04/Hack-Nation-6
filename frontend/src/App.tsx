import { useEffect, useRef, useState } from 'react'
import LoginPage from './components/LoginPage'
import AccountView from './components/AccountView'
import UploadForm from './components/UploadForm'
import ConfirmView from './components/ConfirmView'
import { extractDocuments } from './api'
import { logOut, onAuth } from './firebase'
import type { Account } from './firebase'
import type { Doc } from './types'

type View = 'login' | 'upload' | 'review' | 'account'

const STEPS = ['Upload documents', 'Review & confirm', 'Prepare packet']

export default function App() {
  const [account, setAccount] = useState<Account | null>(null)
  const [ready, setReady] = useState(false)
  const [view, setView] = useState<View>('login')
  const [documents, setDocuments] = useState<Doc[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
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
    setView('login')
  }

  const inFlow = view === 'upload' || view === 'review'

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
            {STEPS.map((label, i) => {
              const stepIndex = view === 'upload' ? 0 : 1
              return (
                <li
                  key={label}
                  className={`step${i === stepIndex ? ' step-current' : ''}${i < stepIndex ? ' step-done' : ''}`}
                  aria-current={i === stepIndex ? 'step' : undefined}
                >
                  <span className="step-num">{i + 1}</span>
                  <span className="step-label">{label}</span>
                </li>
              )
            })}
          </ol>
        </nav>
      )}

      <main className="content">
        {!ready && <p className="status">Loading…</p>}

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
          <>
            {error && <p role="alert" className="notice notice-error">{error}</p>}
            <UploadForm
              documents={documents}
              busy={busy}
              onAddFiles={addFiles}
              onRemove={removeDoc}
              onContinue={() => setView('review')}
            />
          </>
        )}

        {ready && view === 'review' && (
          <ConfirmView
            documents={documents}
            onBack={() => setView('upload')}
            onSaved={() => setView('account')}
          />
        )}
      </main>
    </div>
  )
}
