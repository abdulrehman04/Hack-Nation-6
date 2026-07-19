import { useState } from 'react'
import type { FormEvent } from 'react'
import { authErrorMessage, logIn } from '../firebase'

interface Props {
  onLoggedIn: () => void
  onStartNew: () => void
}

export default function LoginPage({ onLoggedIn, onStartNew }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await logIn(email.trim(), password)
      onLoggedIn()
    } catch (err) {
      setError(authErrorMessage(err))
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="card auth-card">
        <h2>Log in</h2>
        <p className="lede">Access the application readiness you saved earlier.</p>

        <form onSubmit={submit}>
          <div className="modal-field">
            <label htmlFor="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="modal-field">
            <label htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {error && <p role="alert" className="notice notice-error">{error}</p>}

          <button type="submit" className="btn-primary btn-block" disabled={busy}>
            {busy ? 'Logging in…' : 'Log in'}
          </button>
        </form>

        <p className="auth-alt">
          New here?{' '}
          <button type="button" className="linklike" onClick={onStartNew}>
            Start a new application
          </button>
        </p>
      </div>
    </div>
  )
}
