import { useState } from 'react'
import type { Doc, Field } from '../types'

const REVIEW_THRESHOLD = 0.6
const INJECTION_FIELD = 'untrusted_instruction_text'

const DOC_LABELS: Record<string, string> = {
  application_summary: 'Application summary',
  pay_stub: 'Pay stub',
  employment_letter: 'Employment letter',
  benefit_letter: 'Benefit letter',
  gig_statement: 'Gig statement',
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

function label(map: Record<string, string>, key: string): string {
  return map[key] ?? key
}

function needsReview(field: Field): boolean {
  return field.status !== 'extracted' || field.confidence < REVIEW_THRESHOLD
}

interface Props {
  documents: Doc[]
  onBack: () => void
}

export default function ConfirmView({ documents, onBack }: Props) {
  // Editable values, keyed "docIndex:fieldName". The renter can correct any value.
  const [values, setValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {}
    documents.forEach((doc, di) => {
      doc.fields.forEach((f) => {
        if (f.name !== INJECTION_FIELD) {
          initial[`${di}:${f.name}`] = f.value == null ? '' : String(f.value)
        }
      })
    })
    return initial
  })
  const [confirmed, setConfirmed] = useState(false)

  function setValue(key: string, value: string) {
    setValues((prev) => ({ ...prev, [key]: value }))
    setConfirmed(false)
  }

  return (
    <section aria-labelledby="confirm-heading" className="confirm">
      <h2 id="confirm-heading">Check what we read</h2>
      <p className="hint">
        Correct anything that looks wrong, then confirm. Nothing is decided here.
      </p>

      {documents.map((doc, di) => {
        const injection = doc.fields.find((f) => f.name === INJECTION_FIELD)
        return (
          <article key={di} className="doc-card">
            <h3>
              {label(DOC_LABELS, doc.document_type)}{' '}
              <span className="method">read by {doc.method === 'ocr' ? 'OCR' : 'text layer'}</span>
            </h3>

            {injection && (
              <p role="alert" className="banner banner-warn">
                An instruction hidden in this document was ignored and not acted on.
              </p>
            )}

            <dl className="fields">
              {doc.fields
                .filter((f) => f.name !== INJECTION_FIELD)
                .map((f) => {
                  const key = `${di}:${f.name}`
                  const review = needsReview(f)
                  const inputId = `field-${key}`
                  return (
                    <div className="field-row" key={f.name}>
                      <dt>
                        <label htmlFor={inputId}>{label(FIELD_LABELS, f.name)}</label>
                      </dt>
                      <dd>
                        <input
                          id={inputId}
                          className={review ? 'input-review' : undefined}
                          value={values[key] ?? ''}
                          onChange={(e) => setValue(key, e.target.value)}
                          aria-describedby={`${inputId}-meta`}
                        />
                        <span id={`${inputId}-meta`} className="meta">
                          <span className="conf">{Math.round(f.confidence * 100)}% confident</span>
                          {review && <span className="badge badge-review">Needs review</span>}
                        </span>
                      </dd>
                    </div>
                  )
                })}
            </dl>
          </article>
        )
      })}

      <div className="actions">
        <button type="button" className="secondary" onClick={onBack}>
          Back to upload
        </button>
        <button type="button" onClick={() => setConfirmed(true)}>
          Confirm profile
        </button>
      </div>

      {confirmed && (
        <p role="status" aria-live="polite" className="banner banner-ok">
          Profile confirmed. Ready for the rules check.
        </p>
      )}
    </section>
  )
}
