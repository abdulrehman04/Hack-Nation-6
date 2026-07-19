import { useState } from 'react'
import UploadForm from './components/UploadForm'
import ConfirmView from './components/ConfirmView'
import { extractDocuments } from './api'
import type { Doc, UploadItem } from './types'

type Stage = 'upload' | 'loading' | 'confirm'

export default function App() {
  const [stage, setStage] = useState<Stage>('upload')
  const [documents, setDocuments] = useState<Doc[]>([])
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(items: UploadItem[]) {
    setError(null)
    setStage('loading')
    try {
      const res = await extractDocuments(items)
      setDocuments(res.documents)
      setStage('confirm')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setStage('upload')
    }
  }

  return (
    <main className="app">
      <header className="app-header">
        <h1>RealDoor</h1>
        <p className="tagline">Application readiness. You confirm; a qualified person decides.</p>
      </header>

      {error && (
        <p role="alert" className="banner banner-error">{error}</p>
      )}

      {stage === 'upload' && <UploadForm onSubmit={handleSubmit} />}

      {stage === 'loading' && (
        <p role="status" aria-live="polite" className="status">Reading your documents…</p>
      )}

      {stage === 'confirm' && (
        <ConfirmView documents={documents} onBack={() => setStage('upload')} />
      )}
    </main>
  )
}
