import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { Alert } from '../components/common'
import { TERMS_VERSION } from '../content/terms'
import { useAuth } from '../lib/auth'

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [accept, setAccept] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (password.length < 8) return setError('A senha precisa ter pelo menos 8 caracteres.')
    if (!accept) return setError('Para criar a conta, leia e aceite o termo de uso.')
    setBusy(true)
    setError(null)
    try {
      await register({ name, email, password, accept_terms: accept, terms_version: TERMS_VERSION })
      navigate('/')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page page--narrow">
      <h1>Criar conta</h1>
      <p className="lead">
        Pedimos só nome, e-mail e senha. Com a conta você acompanha seus registros e pode confirmar
        ocorrências de outros moradores.
      </p>
      <form onSubmit={submit} className="stack">
        <label className="field">
          <span>Nome</span>
          <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required minLength={2} />
        </label>
        <label className="field">
          <span>E-mail</span>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
        </label>
        <label className="field">
          <span>Senha (mínimo de 8 caracteres)</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
        </label>
        <label className="check">
          <input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} />
          <span>
            Li e aceito o{' '}
            <Link to="/termos" target="_blank">
              termo de uso e a política de privacidade
            </Link>
            .
          </span>
        </label>
        {error && <Alert>{error}</Alert>}
        <button type="submit" className="btn btn--primary btn--block" disabled={busy}>
          {busy ? 'Criando…' : 'Criar conta'}
        </button>
      </form>
    </div>
  )
}
