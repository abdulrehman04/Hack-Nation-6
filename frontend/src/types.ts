// Shapes returned by the FastAPI /extract endpoint.

export interface Field {
  name: string
  value: string | number | null
  confidence: number
  source_method: string | null
  source_bbox: number[] | null
  status: string
  reason: string | null
}

export interface Doc {
  file_name: string
  document_type: string | null
  detected: boolean
  method: string
  injected_instruction: string | null
  page_image: string
  page_size_points: number[]
  fields: Field[]
}

export interface ExtractResponse {
  documents: Doc[]
}

// Shapes returned by the Stage 02 endpoints: /api/understand and /api/chat.

export interface Citation {
  document_id: string
  file_name: string
  page: number
  bbox: [number, number, number, number]
  rule_id: string
}

export interface IncomeSource {
  document_id: string
  file_name: string
  document_type: string
  gross_amount: number
  frequency: string
  multiplier: number
  annualized: number
  is_current: boolean
  citation: Citation
}

export interface EnrichedProfile {
  household_id: string
  household_size: number
  person_name: string
  address: string
  application_date: string
  annualized_income: number
  frozen_60_percent_threshold: number
  comparison: 'below_or_equal' | 'above' | 'no_frozen_threshold'
  threshold_pct_used: number
  readiness_status: 'READY_TO_REVIEW' | 'NEEDS_REVIEW'
  review_reasons: string[]
  income_sources: IncomeSource[]
  citations: Citation[]
  calculation_steps: string[]
  rule_versions_used: string[]
  disclosure: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  rule_ids_cited?: string[]
  abstained?: boolean
}

export interface ChatResponse {
  answer: string
  rule_ids_cited: string[]
  citations?: Citation[]
  abstained: boolean
}

// Shapes returned by the Stage 03 endpoints: /api/prepare, /api/export, /api/session.

export interface ChecklistRow {
  document_type: string
  label: string
  optional: boolean
  status: 'PRESENT_AND_CURRENT' | 'PRESENT_BUT_EXPIRED' | 'MISSING_REQUIRED' | 'NOT_PROVIDED_OPTIONAL'
  count: number
  message: string
}

export interface PrepareDocumentField {
  field: string
  value: string | number | null
  page: number
  bbox: [number, number, number, number] | null
  bbox_units: string
  confidence: number
  status: string
}

export interface PrepareDocument {
  document_id: string
  document_type: string
  file_name: string
  fields: PrepareDocumentField[]
}

export interface PrepareData {
  household_id: string
  person_name: string
  household_size: number
  address: string
  application_date: string
  annualized_income: number
  frozen_60_percent_threshold: number
  comparison: 'below_or_equal' | 'above' | 'no_frozen_threshold'
  readiness_status: 'READY_TO_REVIEW' | 'NEEDS_REVIEW'
  review_reasons: string[]
  checklist: ChecklistRow[]
  documents: PrepareDocument[]
  citations: Citation[]
  disclosure: string
}

export interface DeleteSessionResponse {
  deleted: boolean
  household_id: string
  deleted_at: string
  items_deleted: string[]
}
