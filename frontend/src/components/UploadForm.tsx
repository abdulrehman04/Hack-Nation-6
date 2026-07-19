import { useState } from 'react'
import type { FormEvent } from 'react'
import type { UploadItem } from '../types'

interface Props {
  onSubmit: (items: UploadItem[]) => void
}

// Three upload slots that map straight to document types.
export default function UploadForm({ onSubmit }: Props) {
  const [appSummary, setAppSummary] = useState<File | null>(null)
  const [payStubs, setPayStubs] = useState<File[]>([])
  const [employment, setEmployment] = useState<File | null>(null)

  const items: UploadItem[] = [
    ...(appSummary ? [{ file: appSummary, type: 'application_summary' }] : []),
    ...payStubs.map((file) => ({ file, type: 'pay_stub' })),
    ...(employment ? [{ file: employment, type: 'employment_letter' }] : []),
  ]

  function submit(e: FormEvent) {
    e.preventDefault()
    if (items.length) onSubmit(items)
  }

  return (
    <form onSubmit={submit} className="card">
      <fieldset>
        <legend>Upload your documents</legend>

        <div className="field">
          <label htmlFor="app-summary">Application summary (PDF)</label>
          <input
            id="app-summary"
            type="file"
            accept="application/pdf"
            onChange={(e) => setAppSummary(e.target.files?.[0] ?? null)}
          />
        </div>

        <div className="field">
          <label htmlFor="pay-stubs">Pay stubs (one or more PDFs)</label>
          <input
            id="pay-stubs"
            type="file"
            accept="application/pdf"
            multiple
            onChange={(e) => setPayStubs(Array.from(e.target.files ?? []))}
          />
        </div>

        <div className="field">
          <label htmlFor="employment">Employment letter (PDF)</label>
          <input
            id="employment"
            type="file"
            accept="application/pdf"
            onChange={(e) => setEmployment(e.target.files?.[0] ?? null)}
          />
        </div>
      </fieldset>

      <p className="hint" aria-live="polite">
        {items.length} file{items.length === 1 ? '' : 's'} selected
      </p>

      <button type="submit" disabled={items.length === 0}>
        Read documents
      </button>
    </form>
  )
}
