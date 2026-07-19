import { useState } from 'react'
import UploadForm from './components/UploadForm'
import ConfirmView from './components/ConfirmView'
import { extractDocuments } from './api'
import type { Doc } from './types'

type Stage = 'upload' | 'review'

const STEPS = ['Upload documents', 'Review & confirm', 'Prepare packet']

export default function App() {
  const [stage, setStage] = useState<Stage>('upload')
  const [documents, setDocuments] = useState<Doc[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const stepIndex = stage === 'upload' ? 0 : 1

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

  function remove(index: number) {
    setDocuments((prev) => prev.filter((_, i) => i !== index))
  }

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

      <main className="content">
        {error && <p role="alert" className="notice notice-error">{error}</p>}

        {stage === 'upload' && (
          <UploadForm
            documents={documents}
            busy={busy}
            onAddFiles={addFiles}
            onRemove={remove}
            onContinue={() => setStage('review')}
          />
        )}

        {stage === 'review' && (
          <ConfirmView documents={documents} onBack={() => setStage('upload')} />
        )}
      </main>
    </div>
  )
}
