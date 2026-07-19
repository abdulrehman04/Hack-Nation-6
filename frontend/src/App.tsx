import { useState } from 'react'
import UploadForm from './components/UploadForm'
import ConfirmView from './components/ConfirmView'
import { extractDocuments } from './api'
import type { Doc } from './types'

type Stage = 'upload' | 'confirm'

export default function App() {
  const [stage, setStage] = useState<Stage>('upload')
  const [documents, setDocuments] = useState<Doc[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Files are read (and their type detected) as soon as they are added.
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
    <main className="app">
      <header className="app-header">
        <h1>RealDoor</h1>
        <p className="tagline">Application readiness. You confirm; a qualified person decides.</p>
      </header>

      {error && <p role="alert" className="banner banner-error">{error}</p>}

      {stage === 'upload' && (
        <UploadForm
          documents={documents}
          busy={busy}
          onAddFiles={addFiles}
          onRemove={remove}
          onContinue={() => setStage('confirm')}
        />
      )}

      {stage === 'confirm' && (
        <ConfirmView documents={documents} onBack={() => setStage('upload')} />
      )}
    </main>
  )
}
