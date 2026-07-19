import { useEffect, useState } from 'react'
import { getIdToken } from '../firebase'
import { listMyProfiles } from '../api'
import type { Account } from '../firebase'
import type { ProfileSummary } from '../api'

interface Props {
  account: Account
  onSignOut: () => void
}

export default function AccountView({ account, onSignOut }: Props) {
  const [profiles, setProfiles] = useState<ProfileSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    ;(async () => {
      try {
        const token = await getIdToken()
        if (!token) return
        const rows = await listMyProfiles(token)
        if (active) setProfiles(rows)
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => {
      active = false
    }
  }, [])

  return (
    <section className="account">
      <div className="account-head">
        <div>
          <h2>Your account</h2>
          <p className="lede">Signed in as {account.email}</p>
        </div>
        <button type="button" className="btn-secondary" onClick={onSignOut}>Sign out</button>
      </div>

      <h3 className="account-sub">Saved profiles</h3>
      {error && <p role="alert" className="notice notice-error">{error}</p>}

      {profiles === null && !error && <p className="status">Loading…</p>}

      {profiles !== null && profiles.length === 0 && (
        <p className="empty">No saved profiles yet.</p>
      )}

      {profiles !== null && profiles.length > 0 && (
        <ul className="file-list">
          {profiles.map((p) => (
            <li key={p.profile_id} className="file-item">
              <span className="file-name">{p.person_name ?? 'Household profile'}</span>
              <span className="file-type">{p.document_count} document{p.document_count === 1 ? '' : 's'}</span>
              <span className="muted">{new Date(p.created_at).toLocaleDateString()}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
