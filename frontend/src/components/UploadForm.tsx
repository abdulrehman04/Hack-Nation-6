import { useState } from 'react'
import type { DragEvent } from 'react'
import type { Doc } from '../types'

const LABELS: Record<string, string> = {
  application_summary: 'Application Summary',
  pay_stub: 'Pay Stub',
  employment_letter: 'Employment Letter',
  benefit_letter: 'Benefit Letter',
  gig_statement: 'Gig Statement',
}

interface Props {
  documents: Doc[]
  busy: boolean
  onAddFiles: (files: File[]) => void
  onRemove: (index: number) => void
  onContinue: () => void
}

function UploadIcon() {
  return (
    <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 16V4" />
      <path d="m7 9 5-5 5 5" />
      <path d="M5 20h14" />
    </svg>
  )
}

function DocIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
    </svg>
  )
}

function XIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  )
}

export default function UploadForm({ documents, busy, onAddFiles, onRemove, onContinue }: Props) {
  const [drag, setDrag] = useState(false)

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDrag(false)
    onAddFiles(Array.from(e.dataTransfer.files))
  }

  return (
    <div className="upload">
      <label
        htmlFor="upload-input"
        className={`dropzone ${drag ? 'dropzone-drag' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
      >
        <span className="slot-icon"><UploadIcon /></span>
        <span className="slot-title">Upload your documents</span>
        <span className="slot-hint">Drop PDFs here, or click to choose. We identify each one for you.</span>
        <span className="slot-action">Application summary, pay stubs, employment letter, and more</span>
        <input
          id="upload-input"
          type="file"
          accept="application/pdf"
          multiple
          className="visually-hidden"
          onChange={(e) => { onAddFiles(Array.from(e.target.files ?? [])); e.target.value = '' }}
        />
      </label>

      <section className="uploaded" aria-label="Uploaded documents">
        <h2 className="uploaded-title">
          Documents <span className="muted">({documents.length})</span>
          {busy && <span className="muted"> · reading…</span>}
        </h2>

        {documents.length === 0 && !busy ? (
          <p className="empty">Nothing yet. Upload one or more PDFs above.</p>
        ) : (
          <ul className="file-list">
            {documents.map((d, i) => {
              const known = d.document_type ? LABELS[d.document_type] : undefined
              return (
                <li key={`${d.file_name}-${i}`} className="file-item">
                  <span className="file-icon"><DocIcon /></span>
                  <span className="file-name">{d.file_name}</span>
                  <span className={known ? 'file-type' : 'file-type file-type-unknown'}>
                    {known ?? 'Unrecognized'}
                  </span>
                  <button
                    type="button"
                    className="file-remove"
                    onClick={() => onRemove(i)}
                    aria-label={`Remove ${d.file_name}`}
                  >
                    <XIcon />
                  </button>
                </li>
              )
            })}
            {busy && (
              <li className="file-item file-item-busy" aria-live="polite">
                <span className="muted">Reading and identifying…</span>
              </li>
            )}
          </ul>
        )}
      </section>

      <button
        type="button"
        className="read-btn"
        disabled={documents.length === 0 || busy}
        onClick={onContinue}
      >
        Continue to confirm
      </button>
    </div>
  )
}
