import { type FormEvent, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'

import { Alert } from '../components/common'
import { useAuth } from '../lib/auth'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      const from = (location.state as { from?: string } | null)?.from
      navigate(from ?? '/')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page page--narrow">
      <h1>Entrar</h1>
      <p className="lead">Para moradores com conta, agentes de saúde e gestores.</p>
      <form onSubmit={submit} className="stack">
        <label className="field">
          <span>E-mail</span>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
        </label>
        <label className="field">
          <span>Senha</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error && <Alert>{error}</Alert>}
        <button type="submit" className="btn btn--primary btn--block" disabled={busy}>
          {busy ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
      <p className="hint">
        <Link to="/esqueci-senha">Esqueci minha senha</Link>
      </p>
      <p className="hint">
        Não tem conta? <Link to="/cadastro">Crie uma</Link>. Para registrar um foco, a conta é opcional.
      </p>
    </div>
  )
}
