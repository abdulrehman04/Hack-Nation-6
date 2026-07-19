import { useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import type { AuditEvent, Doc, Field } from '../types'
import { runSanityChecks } from '../sanity'
import { saveProfile } from '../api'
import AuthModal from './AuthModal'
import type { AuthedUser } from '../firebase'

const HOUSEHOLD_FIELDS = ['person_name', 'household_size', 'address']

const CONSENT_TEXT =
  'I consent to RealDoor reading these documents to prepare my application, '
  + 'and I understand it does not decide my eligibility.'

function householdIdFromFileName(fileName: string): string | null {
  const match = fileName.match(/^(hh-\d+)/i)
  return match ? match[1].toUpperCase() : null
}

const REVIEW_THRESHOLD = 0.6
const INJECTION_FIELD = 'untrusted_instruction_text'

const DOC_LABELS: Record<string, string> = {
  application_summary: 'Application Summary',
  pay_stub: 'Pay Stub',
  employment_letter: 'Employment Letter',
  benefit_letter: 'Benefit Letter',
  gig_statement: 'Gig Statement',
}

const FIELD_LABELS: Record<string, string> = {
  person_name: 'Name',
  household_size: 'Household size',
  address: 'Address',
  application_date: 'Application date',
  pay_date: 'Pay date',
  pay_period_start: 'Pay period start',
  pay_period_end: 'Pay period end',
  pay_frequency: 'Pay frequency',
  regular_hours: 'Regular hours',
  hourly_rate: 'Hourly rate',
  gross_pay: 'Gross pay',
  net_pay: 'Net pay',
  document_date: 'Document date',
  weekly_hours: 'Weekly hours',
  monthly_benefit: 'Monthly benefit',
  benefit_frequency: 'Benefit frequency',
  statement_month: 'Statement month',
  gross_receipts: 'Gross receipts',
  platform_fees: 'Platform fees',
}

function labelOf(map: Record<string, string>, key: string): string {
  return map[key] ?? key
}

function needsReview(field: Field): boolean {
  return field.status !== 'extracted' || field.confidence < REVIEW_THRESHOLD
}

function provenance(field: Field): string {
  if (field.source_method === 'ocr') {
    return `Scanned copy, ${Math.round(field.confidence * 100)}% match`
  }
  return 'From document text'
}

function boxStyle(bbox: number[], page: number[]): CSSProperties {
  const [x0, y0, x1, y1] = bbox
  const [w, h] = page
  return {
    left: `${(x0 / w) * 100}%`,
    top: `${((h - y1) / h) * 100}%`,
    width: `${((x1 - x0) / w) * 100}%`,
    height: `${((y1 - y0) / h) * 100}%`,
  }
}

function CheckIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m5 12 5 5 9-11" />
    </svg>
  )
}

interface Props {
  documents: Doc[]
  audit: AuditEvent[]
  onBack: () => void
  onSaved: (documents: Doc[]) => void
}

export default function ConfirmView({ documents, audit, onBack, onSaved }: Props) {
  const original = useMemo(() => {
    const o: Record<string, string> = {}
    documents.forEach((doc, di) => {
      doc.fields.forEach((f) => {
        if (f.name !== INJECTION_FIELD) o[`${di}:${f.name}`] = f.value == null ? '' : String(f.value)
      })
    })
    return o
  }, [documents])

  const reviewKeys = useMemo(() => {
    const keys: string[] = []
    documents.forEach((doc, di) => {
      doc.fields.forEach((f) => {
        if (f.name !== INJECTION_FIELD && needsReview(f)) keys.push(`${di}:${f.name}`)
      })
    })
    return keys
  }, [documents])

  const [values, setValues] = useState<Record<string, string>>(original)
  const [reviewed, setReviewed] = useState<Record<string, boolean>>({})
  const [checked, setChecked] = useState(false)
  const [issues, setIssues] = useState<string[]>([])
  const [confirmed, setConfirmed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeKey, setActiveKey] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [showAuth, setShowAuth] = useState(false)
  const [consented, setConsented] = useState(false)

  const edited = useMemo(
    () => Object.keys(original).some((k) => values[k] !== original[k]),
    [values, original],
  )
  const allReviewed = reviewKeys.every((k) => reviewed[k])
  const pendingReviews = reviewKeys.filter((k) => !reviewed[k]).length

  function resetGate() {
    setChecked(false)
    setConfirmed(false)
    setIssues([])
    setError(null)
  }

  function buildProfile() {
    const docs = documents.map((doc, di) => ({
      document_type: doc.document_type,
      file_name: doc.file_name,
      method: doc.method,
      fields: doc.fields
        .filter((f) => f.name !== INJECTION_FIELD)
        .map((f) => {
          const key = `${di}:${f.name}`
          return {
            name: f.name,
            value: values[key] ?? null,
            confidence: f.confidence,
            source_method: f.source_method,
            reviewed: needsReview(f) ? !!reviewed[key] : true,
          }
        }),
    }))
    const household: Record<string, string> = {}
    documents.forEach((doc, di) => {
      doc.fields.forEach((f) => {
        if (HOUSEHOLD_FIELDS.includes(f.name)) household[f.name] = values[`${di}:${f.name}`] ?? ''
      })
    })
    const householdId = documents
      .map((d) => householdIdFromFileName(d.file_name))
      .find((id): id is string => id !== null) ?? null

    const now = new Date().toISOString()
    const fieldLabel = (key: string) => labelOf(FIELD_LABELS, key.split(':')[1])
    const auditLog: AuditEvent[] = [
      ...audit,
      ...Object.keys(original)
        .filter((k) => values[k] !== original[k])
        .map((k) => ({ action: 'corrected', detail: fieldLabel(k), at: now })),
      ...reviewKeys
        .filter((k) => reviewed[k])
        .map((k) => ({ action: 'reviewed', detail: fieldLabel(k), at: now })),
      { action: 'confirmed', at: now },
    ]
    const consent = { consented: true, text: CONSENT_TEXT, at: now }

    return { household_id: householdId, household, documents: docs, sanity_issues: issues, consent, audit: auditLog }
  }

  async function saveForUser(user: AuthedUser) {
    setShowAuth(false)
    setSaving(true)
    try {
      await saveProfile(buildProfile(), user.idToken)
      setConfirmed(true)
      onSaved(documents)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  function setValue(key: string, value: string) {
    setValues((prev) => ({ ...prev, [key]: value }))
    setReviewed((prev) => (reviewKeys.includes(key) ? { ...prev, [key]: true } : prev))
    resetGate()
  }

  function toggleReviewed(key: string) {
    setReviewed((prev) => ({ ...prev, [key]: !prev[key] }))
    resetGate()
  }

  function handlePrimary() {
    if (!consented) {
      setError('Please agree to the consent statement below to continue.')
      return
    }
    if (!allReviewed) {
      setError(`Confirm the ${pendingReviews} highlighted field${pendingReviews === 1 ? '' : 's'} first (tap the check).`)
      return
    }
    setError(null)
    if (checked && issues.length > 0) {
      setShowAuth(true) // second click: proceed despite the flagged issues
      return
    }
    const found = runSanityChecks(documents, values)
    setIssues(found)
    setChecked(true)
    if (found.length === 0) setShowAuth(true)
  }

  const primaryLabel = saving
    ? 'Saving…'
    : confirmed
      ? 'Profile confirmed'
      : checked && issues.length > 0
        ? 'Confirm anyway'
        : edited
          ? 'Update value'
          : 'Confirm profile'

  return (
    <section className="review" aria-labelledby="review-heading">
      <h2 id="review-heading">Review what we read</h2>
      <p className="lede">
        Check each value against your document, using the highlights to see where it came from.
        Correct anything wrong, confirm the flagged fields, then confirm the profile. Nothing here
        decides your eligibility.
      </p>

      {documents.map((doc, di) => {
        const typeLabel = doc.document_type ? labelOf(DOC_LABELS, doc.document_type) : 'Unrecognized document'
        const injection = doc.fields.find((f) => f.name === INJECTION_FIELD)
        const fields = doc.fields.filter((f) => f.name !== INJECTION_FIELD)
        return (
          <article key={di} className="doc">
            <header className="doc-head">
              <div>
                <h3 className="doc-title">{typeLabel}</h3>
                <p className="doc-meta">
                  {doc.file_name} · {doc.method === 'ocr' ? 'read by OCR' : 'read from document text'}
                </p>
              </div>
              <span className={doc.document_type ? 'chip chip-ok' : 'chip chip-warn'}>
                {doc.document_type ? 'Identified' : 'Unrecognized'}
              </span>
            </header>

            {injection && (
              <p role="alert" className="notice notice-warn">
                <strong>Security note.</strong> An instruction hidden in this document was ignored and not acted on.
              </p>
            )}

            <div className="doc-body">
              <div className="doc-preview">
                <div className="preview-frame">
                  <img src={doc.page_image} alt={`Document: ${doc.file_name}`} />
                  {fields.map((f) => {
                    if (!f.source_bbox) return null
                    const key = `${di}:${f.name}`
                    const cls = ['box']
                    if (activeKey === key) cls.push('box-active')
                    if (needsReview(f) && !reviewed[key]) cls.push('box-review')
                    return (
                      <button
                        type="button"
                        key={f.name}
                        className={cls.join(' ')}
                        style={boxStyle(f.source_bbox, doc.page_size_points)}
                        onMouseEnter={() => setActiveKey(key)}
                        onMouseLeave={() => setActiveKey(null)}
                        onFocus={() => setActiveKey(key)}
                        onBlur={() => setActiveKey(null)}
                        onClick={() => document.getElementById(`field-${key}`)?.focus()}
                        aria-label={`Show ${labelOf(FIELD_LABELS, f.name)} on the document`}
                      />
                    )
                  })}
                  {injection?.source_bbox && (
                    <span
                      className="box box-danger"
                      style={boxStyle(injection.source_bbox, doc.page_size_points)}
                      aria-hidden="true"
                    />
                  )}
                </div>
              </div>

              <dl className="field-list">
                {fields.map((f) => {
                  const key = `${di}:${f.name}`
                  const review = needsReview(f)
                  const isReviewed = reviewed[key]
                  const inputId = `field-${key}`
                  return (
                    <div
                      key={f.name}
                      className={activeKey === key ? 'field field-active' : 'field'}
                      onMouseEnter={() => setActiveKey(key)}
                      onMouseLeave={() => setActiveKey(null)}
                    >
                      <dt><label htmlFor={inputId}>{labelOf(FIELD_LABELS, f.name)}</label></dt>
                      <dd>
                        <div className="input-row">
                          <input
                            id={inputId}
                            className={review && !isReviewed ? 'input-review' : undefined}
                            value={values[key] ?? ''}
                            onChange={(e) => setValue(key, e.target.value)}
                            onFocus={() => setActiveKey(key)}
                            aria-describedby={`${inputId}-meta`}
                          />
                          {review && (
                            <button
                              type="button"
                              className={isReviewed ? 'review-tick review-tick-on' : 'review-tick'}
                              onClick={() => toggleReviewed(key)}
                              aria-pressed={isReviewed}
                              aria-label={
                                isReviewed
                                  ? `${labelOf(FIELD_LABELS, f.name)} marked reviewed`
                                  : `Confirm you reviewed ${labelOf(FIELD_LABELS, f.name)}`
                              }
                            >
                              <CheckIcon />
                            </button>
                          )}
                        </div>
                        <span id={`${inputId}-meta`} className="field-meta">
                          <span className="prov">{provenance(f)}</span>
                          {review && !isReviewed && <span className="chip chip-warn">Needs review</span>}
                          {review && isReviewed && <span className="chip chip-ok">Reviewed</span>}
                        </span>
                      </dd>
                    </div>
                  )
                })}
              </dl>
            </div>
          </article>
        )
      })}

      {error && <p role="alert" className="notice notice-error">{error}</p>}

      {checked && issues.length > 0 && !confirmed && (
        <div role="alert" className="notice notice-warn">
          <strong>Please double-check these before continuing:</strong>
          <ul className="issues-list">
            {issues.map((issue, i) => <li key={i}>{issue}</li>)}
          </ul>
        </div>
      )}

      <article className="doc consent-block">
        <h3 className="doc-title">How your information is used</h3>
        <ul className="data-use-list">
          <li>Your documents are read to fill in this form. You confirm every value.</li>
          <li>Your income is compared to the program's published 60% AMI threshold.</li>
          <li>We keep the confirmed values, not the original documents, and never decide your eligibility.</li>
        </ul>
        <label className="consent-row">
          <input
            type="checkbox"
            checked={consented}
            onChange={(e) => { setConsented(e.target.checked); setError(null) }}
          />
          <span>{CONSENT_TEXT}</span>
        </label>
      </article>

      <div className="review-actions">
        <button type="button" className="btn-secondary" onClick={onBack} disabled={saving}>Back to upload</button>
        <button type="button" className="btn-primary" onClick={handlePrimary} disabled={confirmed || saving}>
          {primaryLabel}
        </button>
      </div>

      {confirmed && (
        <p role="status" className="notice notice-ok">
          <strong>Profile confirmed and saved.</strong>
        </p>
      )}

      {showAuth && (
        <AuthModal onClose={() => setShowAuth(false)} onAuthenticated={saveForUser} />
      )}
    </section>
  )
}
