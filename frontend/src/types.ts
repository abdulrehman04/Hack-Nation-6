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
  fields: Field[]
}

export interface ExtractResponse {
  documents: Doc[]
}
