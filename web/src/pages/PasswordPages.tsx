import { type FormEvent, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'

import { Alert } from '../components/common'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { TokenOut } from '../lib/types'

/** "Esqueci minha senha": always the same answer, so accounts cannot be discovered. */
export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const r = await api<{ message: string }>('/auth/forgot', { json: { email } })
      setMessage(r.message)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page page--narrow">
      <h1>Esqueci minha senha</h1>
      <p className="lead">Informe o e-mail da sua conta. Enviaremos um link para criar uma nova senha.</p>
      {message ? (
        <Alert kind="success">
          {message} O link vale por 1 hora. Confira também a caixa de spam.
        </Alert>
      ) : (
        <form onSubmit={submit} className="stack">
          <label className="field">
            <span>E-mail</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
          </label>
          {error && <Alert>{error}</Alert>}
          <button type="submit" className="btn btn--primary btn--block" disabled={busy}>
            {busy ? 'Enviando…' : 'Enviar link'}
          </button>
        </form>
      )}
      <p className="hint">
        <Link to="/entrar">Voltar para entrar</Link>
      </p>
    </div>
  )
}

/** Link from the e-mail (#t=…&tipo=redefinir|convite): sets the password and logs in. */
export function NewPasswordPage() {
  const { hash } = useLocation()
  const navigate = useNavigate()
  const { acceptSession } = useAuth()
  const params = useMemo(() => new URLSearchParams(hash.replace(/^#/, '')), [hash])
  const token = params.get('t') ?? ''
  const invite = params.get('tipo') === 'convite'
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (password.length < 8) return setError('A senha precisa ter pelo menos 8 caracteres.')
    if (password !== confirm) return setError('As duas senhas não são iguais.')
    setBusy(true)
    setError(null)
    try {
      const r = await api<TokenOut>('/auth/reset', { json: { token, password } })
      acceptSession(r.access_token, r.user)
      navigate(r.user.role === 'morador' ? '/' : '/fila')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!token)
    return (
      <div className="page page--narrow">
        <Alert>Link incompleto. Abra o link exatamente como chegou no e-mail.</Alert>
      </div>
    )

  return (
    <div className="page page--narrow">
      <h1>{invite ? 'Bem-vindo(a) à equipe' : 'Criar nova senha'}</h1>
      <p className="lead">
        {invite
          ? 'Crie a senha que você vai usar para entrar no Sentinela Urbano.'
          : 'Escolha uma nova senha. Ao salvar, as outras sessões abertas com a senha antiga são encerradas.'}
      </p>
      <form onSubmit={submit} className="stack">
        <label className="field">
          <span>Nova senha (mínimo de 8 caracteres)</span>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" required minLength={8} />
        </label>
        <label className="field">
          <span>Repita a senha</span>
          <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" required />
        </label>
        {error && <Alert>{error}</Alert>}
        <button type="submit" className="btn btn--primary btn--block" disabled={busy}>
          {busy ? 'Salvando…' : 'Salvar senha e entrar'}
        </button>
      </form>
    </div>
  )
}
