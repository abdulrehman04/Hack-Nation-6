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
