// Cross-document consistency checks run before a profile is confirmed.
// These flag data-quality problems for the renter; they never decide eligibility.

import type { Doc } from './types'

const PAY_FLUCTUATION_LIMIT = 1.25 // 25% spread across pay stubs

function num(value: string | undefined): number {
  if (!value) return NaN
  const match = value.replace(/[, ]/g, '').match(/-?\d*\.?\d+/)
  return match ? parseFloat(match[0]) : NaN
}

function money(n: number): string {
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}

interface DocValues {
  type: string | null
  get: (field: string) => string
}

function collect(documents: Doc[], values: Record<string, string>): DocValues[] {
  return documents.map((doc, di) => ({
    type: doc.document_type,
    get: (field: string) => (values[`${di}:${field}`] ?? '').trim(),
  }))
}

export function runSanityChecks(documents: Doc[], values: Record<string, string>): string[] {
  const docs = collect(documents, values)
  const issues: string[] = []

  // Name should be the same person across every document.
  const names = [...new Set(docs.map((d) => d.get('person_name')).filter(Boolean))]
  if (names.length > 1) {
    issues.push(`The name differs across documents: ${names.join(', ')}.`)
  }

  // Hourly rate should match wherever it appears (pay stubs, employment letter).
  const rates = [...new Set(
    docs.map((d) => num(d.get('hourly_rate'))).filter((n) => !Number.isNaN(n)),
  )]
  if (rates.length > 1) {
    issues.push(`Hourly rate differs across documents: ${rates.map(money).join(', ')}.`)
  }

  // Gross pay should not swing wildly between pay stubs.
  const grosses = docs
    .filter((d) => d.type === 'pay_stub')
    .map((d) => num(d.get('gross_pay')))
    .filter((n) => !Number.isNaN(n) && n > 0)
  if (grosses.length > 1) {
    const lo = Math.min(...grosses)
    const hi = Math.max(...grosses)
    if (hi / lo > PAY_FLUCTUATION_LIMIT) {
      issues.push(`Gross pay swings more than 25% across pay stubs (${money(lo)} to ${money(hi)}).`)
    }
  }

  // A pay period must start before it ends.
  docs.forEach((d) => {
    if (d.type !== 'pay_stub') return
    const start = d.get('pay_period_start')
    const end = d.get('pay_period_end')
    if (start && end && start > end) {
      issues.push(`A pay period starts (${start}) after it ends (${end}).`)
    }
  })

  // Household size should be a positive whole number.
  docs.forEach((d) => {
    if (d.type !== 'application_summary') return
    const size = num(d.get('household_size'))
    if (Number.isNaN(size) || size < 1) {
      issues.push('Household size is missing or not a positive number.')
    }
  })

  return issues
}
