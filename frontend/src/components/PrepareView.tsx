import { useState } from 'react'
import type { ChecklistRow, PrepareDocument, PrepareData } from '../types'
import { deleteSession, exportPacket } from '../api'
import { getIdToken } from '../firebase'

const DOC_LABELS: Record<string, string> = {
  application_summary: 'Application summary',
  pay_stub: 'Pay stub',
  employment_letter: 'Employment verification letter',
  benefit_letter: 'Benefit award letter',
  gig_statement: 'Gig / self-employment statement',
}

function docLabel(documentType: string): string {
  return DOC_LABELS[documentType] ?? documentType.replace(/_/g, ' ')
}

const STATUS_CLASS: Record<ChecklistRow['status'], string> = {
  PRESENT_AND_CURRENT: 'checklist-ok',
  PRESENT_BUT_EXPIRED: 'checklist-warn',
  MISSING_REQUIRED: 'checklist-danger',
  NOT_PROVIDED_OPTIONAL: 'checklist-muted',
}

const STATUS_ICON: Record<ChecklistRow['status'], string> = {
  PRESENT_AND_CURRENT: '✓',
  PRESENT_BUT_EXPIRED: '⚠',
  MISSING_REQUIRED: '✗',
  NOT_PROVIDED_OPTIONAL: '—',
}

const REASON_LABELS: Record<string, string> = {
  PAY_STUB_TOTAL_CONFLICT: 'Conflicting pay stub totals',
  GIG_INCOME_UNCORROBORATED: 'Gig income requires corroboration',
  EMPLOYMENT_LETTER_EXPIRED: 'Employment letter is expired',
  MISSING_REQUIRED_EVIDENCE: 'Required document missing',
}

function formatReason(code: string): string {
  return REASON_LABELS[code] ?? code
}

interface DocumentRowProps {
  doc: PrepareDocument
  personName: string
  onDelete: (documentId: string) => void
}

function DocumentRow({ doc, personName, onDelete }: DocumentRowProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="document-row">
      <div className="document-row-head">
        <div>
          <span className="document-row-title">{docLabel(doc.document_type)} — {personName}</span>
          <p className="document-row-file muted">{doc.file_name}</p>
        </div>
        <div className="document-row-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
          >
            {expanded ? 'Hide fields' : 'Preview fields'}
          </button>
          <button type="button" className="btn-danger" onClick={() => onDelete(doc.document_id)}>
            Delete
          </button>
        </div>
      </div>
      {expanded && (
        <dl className="document-row-fields">
          {doc.fields.map((f) => (
            <div key={f.field} className="document-row-field">
              <dt>{f.field.replace(/_/g, ' ')}</dt>
              <dd>{f.value ?? '—'}</dd>
            </div>
          ))}
        </dl>
      )}
      {expanded && (
        <p className="muted document-row-hint">
          These are read-only — they were confirmed in the Review &amp; confirm step. Go back there to
          correct a value.
        </p>
      )}
    </div>
  )
}

interface Props {
  data: PrepareData
  householdId: string
  onBack: () => void
  onEdit: () => void
  onStartOver: () => void
}

export default function PrepareView({ data, householdId, onBack, onEdit, onStartOver }: Props) {
  const [visibleDocuments, setVisibleDocuments] = useState(data.documents)
  const [exporting, setExporting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  function handleDeleteDoc(documentId: string) {
    setVisibleDocuments((prev) => prev.filter((d) => d.document_id !== documentId))
  }

  async function handleExport() {
    setActionError(null)
    setExporting(true)
    try {
      const token = await getIdToken()
      if (!token) throw new Error('Please sign in again to export your packet.')
      await exportPacket(householdId, token)
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    } finally {
      setExporting(false)
    }
  }

  async function handleDelete() {
    const confirmed = window.confirm(
      'This will permanently delete all session data.\nThis cannot be undone.'
    )
    if (!confirmed) return
    setActionError(null)
    try {
      await deleteSession(householdId)
      onStartOver()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    }
  }

  const badgeClass = data.readiness_status === 'READY_TO_REVIEW' ? 'ready' : 'review'

  return (
    <section className="prepare" aria-labelledby="prepare-heading">
      <h2 id="prepare-heading">Prepare your packet</h2>
      <p className="lede">
        Check what's on file below, export a copy for your records, or delete everything from this
        session. Nothing here is ever sent anywhere automatically.
      </p>

      {/* SECTION A — Document checklist */}
      <div className="understand-card">
        <h2>Document checklist</h2>
        <p className="card-subtitle">
          Flags missing or expired items against the standard checklist for this program.
        </p>
        <ul className="checklist-list">
          {data.checklist.map((item) => (
            <li key={item.document_type} className={`checklist-row ${STATUS_CLASS[item.status]}`}>
              <span className="checklist-icon" aria-hidden="true">{STATUS_ICON[item.status]}</span>
              <span className="checklist-label">
                {item.label}
                {item.optional && <span className="optional-badge">optional</span>}
              </span>
              <span className="checklist-message">{item.message}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* SECTION B — Your documents */}
      <div className="understand-card">
        <div className="section-head">
          <h2>Your documents ({visibleDocuments.length})</h2>
          <button type="button" className="btn-secondary btn-sm" onClick={onEdit}>Edit details</button>
        </div>
        <p className="card-subtitle">
          Preview, edit, or remove any document before exporting. Nothing here is sent anywhere
          automatically.
        </p>
        {visibleDocuments.map((doc) => (
          <DocumentRow key={doc.document_id} doc={doc} personName={data.person_name} onDelete={handleDeleteDoc} />
        ))}
      </div>

      {/* SECTION C — Readiness summary */}
      <div className="understand-card">
        <h2>Readiness summary</h2>

        <div className="readiness-summary-grid">
          <div>
            <div className="summary-label">HOUSEHOLD</div>
            <div className="summary-value">{data.household_id}</div>
          </div>
          <div>
            <div className="summary-label">STATUS</div>
            <span className={`readiness-badge ${badgeClass}`}>{data.readiness_status}</span>
          </div>
          <div>
            <div className="summary-label">ANNUALIZED INCOME</div>
            <div className="summary-value income">
              ${data.annualized_income.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </div>
          </div>
          <div>
            <div className="summary-label">REVIEW ITEMS</div>
            <div className="summary-value">
              {data.review_reasons.length === 0
                ? 'None'
                : data.review_reasons.map((r) => (
                  <div key={r} className="review-reason-tag">{formatReason(r)}</div>
                ))}
            </div>
          </div>
        </div>

        {actionError && <p role="alert" className="notice notice-error">{actionError}</p>}

        <div className="confirm-row">
          <button type="button" className="btn-primary" onClick={handleExport} disabled={exporting}>
            {exporting ? 'Exporting...' : 'Export packet (JSON)'}
          </button>
          <button type="button" className="btn-danger" onClick={handleDelete}>
            Delete all session data
          </button>
        </div>
      </div>

      {/* SECTION D — Disclaimer */}
      <p className="packet-disclaimer">
        RealDoor never approves, denies, scores, ranks, or determines eligibility. It compares a
        confirmed, cited figure against a frozen published threshold. Final determinations remain
        human and program-specific (rule CH-DECISION-001). Document contents are treated as
        untrusted data; embedded instructions are ignored.
      </p>

      <div className="review-actions">
        <button type="button" className="btn-secondary" onClick={onBack}>Back to understand</button>
      </div>
    </section>
  )
}
