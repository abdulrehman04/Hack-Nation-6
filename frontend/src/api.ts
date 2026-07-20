import type {
  ChatMessage,
  ChatResponse,
  DeleteSessionResponse,
  DiscoverData,
  EnrichedProfile,
  ExtractResponse,
  PrepareData,
} from './types'

// Production build talks to the same origin (FastAPI serves this bundle); dev hits local uvicorn.
const API_BASE = import.meta.env.VITE_API_BASE ?? (import.meta.env.PROD ? '' : 'http://127.0.0.1:8000')

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

// Persist a renter-confirmed profile against the signed-in user.
export async function saveProfile(profile: unknown, idToken: string): Promise<{ profile_id: string }> {
  const res = await fetch(`${API_BASE}/profiles`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify(profile),
  })
  if (!res.ok) {
    throw new Error(`Save failed (${res.status}): ${await res.text()}`)
  }
  return res.json()
}

export interface ProfileSummary {
  profile_id: string
  created_at: string
  household_id: string | null
  person_name: string | null
  document_count: number
}

// List the signed-in user's saved profiles.
export async function listMyProfiles(idToken: string): Promise<ProfileSummary[]> {
  const res = await fetch(`${API_BASE}/profiles`, {
    headers: { Authorization: `Bearer ${idToken}` },
  })
  if (!res.ok) {
    throw new Error(`Could not load profiles (${res.status})`)
  }
  const data = await res.json()
  return data.profiles
}

// Permanently delete all of the signed-in user's saved data.
export async function deleteMyData(idToken: string): Promise<{ deleted: number }> {
  const res = await fetch(`${API_BASE}/profiles`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${idToken}` },
  })
  if (!res.ok) {
    throw new Error(`Delete failed (${res.status}): ${await res.text()}`)
  }
  return res.json()
}

// Phase 1: fetch the enriched, cited profile computed from the signed-in user's saved data.
export async function fetchUnderstand(householdId: string, idToken: string): Promise<EnrichedProfile> {
  const res = await fetch(`${API_BASE}/api/understand/${householdId}`, {
    headers: { Authorization: `Bearer ${idToken}` },
  })
  if (!res.ok) {
    throw new Error(`Understand failed (${res.status}): ${await res.text()}`)
  }
  return res.json()
}

// Phase 2: ask a grounded question about the signed-in user's saved profile.
export async function sendChat(
  householdId: string,
  question: string,
  conversationHistory: ChatMessage[],
  idToken: string,
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${idToken}` },
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

// Phase 3: checklist + packet data computed from the signed-in user's saved data.
export async function fetchPrepare(householdId: string, idToken: string): Promise<PrepareData> {
  const res = await fetch(`${API_BASE}/api/prepare/${householdId}`, {
    headers: { Authorization: `Bearer ${idToken}` },
  })
  if (!res.ok) {
    throw new Error(`Prepare failed (${res.status}): ${await res.text()}`)
  }
  return res.json()
}

// Assembles the final packet server-side and triggers a browser download of it.
export async function exportPacket(householdId: string, idToken: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/export/${householdId}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${idToken}` },
  })
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

// Stretch: fetch the full, unfiltered public LIHTC property set (public data, no auth).
export async function fetchDiscover(): Promise<DiscoverData> {
  const res = await fetch(`${API_BASE}/api/discover`)
  if (!res.ok) {
    throw new Error(`Discover failed (${res.status}): ${await res.text()}`)
  }
  return res.json()
}

// Renter-initiated deletion of all session data for this household.
export async function deleteSession(householdId: string): Promise<DeleteSessionResponse> {
  const res = await fetch(`${API_BASE}/api/session/${householdId}`, { method: 'DELETE' })
  if (!res.ok) {
    throw new Error(`Delete failed (${res.status}): ${await res.text()}`)
  }
  return res.json()
}
