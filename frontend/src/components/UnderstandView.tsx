import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import type { ChatMessage, EnrichedProfile } from '../types'
import { sendChat } from '../api'
import { getIdToken } from '../firebase'

const SUGGESTIONS = [
  'What is my annualized income?',
  'Am I approved?',
  'When do the MTSP limits take effect?',
  'Which property has a unit available?',
]

const REASON_LABELS: Record<string, string> = {
  PAY_STUB_TOTAL_CONFLICT: 'Conflicting pay stub totals',
  GIG_INCOME_UNCORROBORATED: 'Gig income requires corroboration',
  EMPLOYMENT_LETTER_EXPIRED: 'Employment letter is expired',
  MISSING_REQUIRED_EVIDENCE: 'Required document missing',
}

function labelForReason(code: string): string {
  return REASON_LABELS[code] ?? code
}

function money(value: number): string {
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// Defensive belt-and-suspenders: the prompt tells Gemini to skip markdown, but
// strip common markers anyway so a slip doesn't show literal asterisks/backticks.
function stripMarkdown(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
}

function WarningIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 9v4" />
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
      <path d="M12 17h.01" />
    </svg>
  )
}

interface Props {
  profile: EnrichedProfile
  householdId: string
  onContinue: () => void
  onDiscover: () => void
}

export default function UnderstandView({ profile, householdId, onContinue, onDiscover }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [chatError, setChatError] = useState<string | null>(null)
  const chatAreaRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = chatAreaRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, loading])

  async function send(question: string) {
    const text = question.trim()
    if (!text || loading) return
    const history = messages
    setChatError(null)
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setLoading(true)
    try {
      const token = await getIdToken()
      if (!token) throw new Error('Please sign in again to ask a question.')
      const res = await sendChat(householdId, text, history, token)
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: res.answer, rule_ids_cited: res.rule_ids_cited, abstained: res.abstained },
      ])
    } catch (e) {
      setChatError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    send(input)
  }

  const hasThreshold = profile.comparison !== 'no_frozen_threshold'
  const thresholdPct = Math.min(profile.threshold_pct_used, 100)
  const barClass = !hasThreshold
    ? 'threshold-bar-fill threshold-bar-fill-none'
    : profile.comparison === 'above'
      ? 'threshold-bar-fill threshold-bar-fill-above'
      : 'threshold-bar-fill threshold-bar-fill-below'

  const badgeClass = !hasThreshold
    ? 'readiness-badge no-threshold'
    : profile.readiness_status === 'READY_TO_REVIEW'
      ? 'readiness-badge ready'
      : 'readiness-badge review'
  const badgeLabel = !hasThreshold
    ? 'NO THRESHOLD'
    : profile.readiness_status === 'READY_TO_REVIEW'
      ? 'READY TO REVIEW'
      : 'NEEDS REVIEW'

  return (
    <section className="understand" aria-labelledby="understand-heading">
      <h2 id="understand-heading" className="visually-hidden">Review &amp; Confirm</h2>

      <div className="understand-layout">
        <div className="understand-col-left">
          <article className="understand-card">
            <div className="doc-head">
              <h3 className="doc-title">Threshold comparison</h3>
              <span className={badgeClass}>{badgeLabel}</span>
            </div>

            <p className="understand-label">Confirmed annualized income</p>
            <p className="understand-big-number">${money(profile.annualized_income)}</p>

            <div className="threshold-row">
              <div className="threshold-bar-container">
                <div className={barClass} style={{ width: `${thresholdPct}%` }} />
                <span className="threshold-marker" style={{ left: `${thresholdPct}%` }} aria-hidden="true" />
              </div>
              {hasThreshold && (
                <div className="threshold-side-label">
                  <p className="understand-label">60% AMI threshold</p>
                  <p className="threshold-value">
                    ${profile.frozen_60_percent_threshold.toLocaleString('en-US')}
                    {' '}(household {profile.household_size})
                  </p>
                  <p className="muted">{profile.threshold_pct_used}% of threshold</p>
                </div>
              )}
            </div>

            {hasThreshold && (
              <p className="understand-citation-line">
                HUD MTSP FY2026 · effective 2026-05-01 ·
                Boston-Cambridge-Quincy MA-NH HMFA · rule HUD-MTSP-002
              </p>
            )}
          </article>

          <article className="understand-card">
            <h3 className="doc-title">Review reasons</h3>
            {profile.review_reasons.length === 0 ? (
              <p className="muted"><em>No open review items.</em></p>
            ) : (
              <ul className="review-reason-list">
                {profile.review_reasons.map((reason) => (
                  <li key={reason} className="review-reason-row">
                    <span className="review-reason-icon"><WarningIcon /></span>
                    {labelForReason(reason)}
                  </li>
                ))}
              </ul>
            )}
            <p className="understand-disclosure muted">{profile.disclosure}</p>
          </article>
        </div>

        <div className="understand-col-right">
          <article className="understand-card">
            <h3 className="doc-title">Ask about this application</h3>

            <div className="suggestion-chips">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="suggestion-chip"
                  disabled={loading}
                  onClick={() => send(s)}
                >
                  {s}
                </button>
              ))}
            </div>

            <div className="chat-area" ref={chatAreaRef} role="log" aria-live="polite" aria-label="Conversation">
              {messages.length === 0 && (
                <p className="muted">Ask a question about {householdId}'s application.</p>
              )}
              {messages.map((m, i) => (
                <div key={i} className={`chat-message ${m.role}${m.abstained ? ' chat-message-abstained' : ''}`}>
                  <p>{m.role === 'assistant' ? stripMarkdown(m.content) : m.content}</p>
                  {m.role === 'assistant' && m.rule_ids_cited && m.rule_ids_cited.length > 0 && (
                    <div className="chat-citation-row">
                      {m.rule_ids_cited.map((id) => (
                        <span key={id} className="citation-chip chat-citation-chip">{id}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {loading && (
                <div className="chat-message assistant chat-typing" aria-hidden="true">
                  <p>...</p>
                </div>
              )}
            </div>

            {chatError && <p role="alert" className="notice notice-error">{chatError}</p>}

            <form className="chat-input-row" onSubmit={onSubmit}>
              <label htmlFor="chat-input" className="visually-hidden">Ask a question</label>
              <input
                id="chat-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question..."
                disabled={loading}
              />
              <button type="submit" className="btn-primary" disabled={loading || !input.trim()}>
                Ask
              </button>
            </form>
          </article>

          <article className="understand-card">
            <h3 className="doc-title">Citations</h3>
            <div className="citation-chip-list">
              {profile.citations.map((c, i) => (
                <span key={i} className="citation-chip">{c.file_name} · {c.rule_id}</span>
              ))}
            </div>
          </article>
        </div>
      </div>

      <div className="review-actions">
        <button type="button" className="btn-secondary" onClick={onDiscover}>
          Discover properties
        </button>
        <button type="button" className="btn-primary" onClick={onContinue}>
          Continue to prepare packet
        </button>
      </div>
    </section>
  )
}
