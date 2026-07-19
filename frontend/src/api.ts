import type {
  ChatMessage,
  ChatResponse,
  DeleteSessionResponse,
  EnrichedProfile,
  ExtractResponse,
  PrepareData,
} from './types'

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

// Persist a renter-confirmed profile; returns the stored id.
export async function saveProfile(profile: unknown): Promise<{ profile_id: string }> {
  const res = await fetch(`${API_BASE}/profiles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  })
  if (!res.ok) {
    throw new Error(`Save failed (${res.status}): ${await res.text()}`)
  }
  return res.json()
}

// Phase 1: fetch the enriched, cited profile for one household.
export async function fetchUnderstand(householdId: string): Promise<EnrichedProfile> {
  const res = await fetch(`${API_BASE}/api/understand/${householdId}`)
  if (!res.ok) {
    throw new Error(`Understand failed (${res.status}): ${await res.text()}`)
  }
  return res.json()
}

// Phase 2: ask a grounded question about one household's profile.
export async function sendChat(
  householdId: string,
  question: string,
  conversationHistory: ChatMessage[],
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      household_id: householdId,
      question,
      conversation_history: conversationHistory,
    }),
  })
  if (!res.ok) {
    throw new Error(`Chat failed (${res.status}): ${await res.text()}`)
  }
  return res.json()
}

// Phase 3: checklist + packet data for the prepare/export/delete step.
export async function fetchPrepare(householdId: string): Promise<PrepareData> {
  const res = await fetch(`${API_BASE}/api/prepare/${householdId}`)
  if (!res.ok) {
    throw new Error(`Prepare failed (${res.status}): ${await res.text()}`)
  }
  return res.json()
}

// Assembles the final packet server-side and triggers a browser download of it.
export async function exportPacket(householdId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/export/${householdId}`, { method: 'POST' })
  if (!res.ok) {
    throw new Error(`Export failed (${res.status}): ${await res.text()}`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `realdoor_packet_${householdId}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// Renter-initiated deletion of all session data for this household.
export async function deleteSession(householdId: string): Promise<DeleteSessionResponse> {
  const res = await fetch(`${API_BASE}/api/session/${householdId}`, { method: 'DELETE' })
  if (!res.ok) {
    throw new Error(`Delete failed (${res.status}): ${await res.text()}`)
  }
  return res.json()
}
