import type { ExtractResponse, UploadItem } from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000'

// Send each file with its document type and get back assembled fields.
export async function extractDocuments(items: UploadItem[]): Promise<ExtractResponse> {
  const form = new FormData()
  for (const { file, type } of items) {
    form.append('files', file)
    form.append('document_types', type)
  }
  const res = await fetch(`${API_BASE}/extract`, { method: 'POST', body: form })
  if (!res.ok) {
    throw new Error(`Extraction failed (${res.status}): ${await res.text()}`)
  }
  return res.json()
}
