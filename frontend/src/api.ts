import type { ExtractResponse } from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000'

// Send PDFs; the backend detects each document's type and returns its fields.
export async function extractDocuments(files: File[]): Promise<ExtractResponse> {
  const form = new FormData()
  for (const file of files) form.append('files', file)
  const res = await fetch(`${API_BASE}/extract`, { method: 'POST', body: form })
  if (!res.ok) {
    throw new Error(`Extraction failed (${res.status}): ${await res.text()}`)
  }
  return res.json()
}
