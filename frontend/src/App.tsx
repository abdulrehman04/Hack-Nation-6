import { useState } from 'react'
import UploadForm from './components/UploadForm'
import ConfirmView from './components/ConfirmView'
import UnderstandView from './components/UnderstandView'
import { extractDocuments, fetchUnderstand } from './api'
import type { Doc, EnrichedProfile } from './types'

type Stage = 'upload' | 'review' | 'understand'

const STEPS = ['Upload documents', 'Review & confirm', 'Understand & confirm', 'Prepare packet']

// Documents are named hh-XXX_... in this challenge's synthetic dataset;
// the household_id is that prefix, uppercased.
function householdIdFromFileName(fileName: string): string | null {
  const match = fileName.match(/^(hh-\d+)/i)
  return match ? match[1].toUpperCase() : null
}

export default function App() {
  const [stage, setStage] = useState<Stage>('upload')
  const [documents, setDocuments] = useState<Doc[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [enrichedProfile, setEnrichedProfile] = useState<EnrichedProfile | null>(null)
  const [householdId, setHouseholdId] = useState<string | null>(null)
  const [understandLoading, setUnderstandLoading] = useState(false)
  const stepIndex = stage === 'upload' ? 0 : stage === 'review' ? 1 : 2

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

  async function onConfirmed(confirmedDocuments: Doc[]) {
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
      setStage('understand')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setUnderstandLoading(false)
    }
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
        {understandLoading && <p role="status" className="notice">Loading rules and thresholds…</p>}

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
          <ConfirmView documents={documents} onBack={() => setStage('upload')} onConfirmed={onConfirmed} />
        )}

        {stage === 'understand' && enrichedProfile && householdId && (
          <UnderstandView profile={enrichedProfile} householdId={householdId} />
        )}
      </main>
    </div>
  )
}
