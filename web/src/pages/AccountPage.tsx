import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { Alert } from '../components/common'
import { api, downloadFile } from '../lib/api'
import { useAuth } from '../lib/auth'
import { ROLE_LABEL } from '../lib/labels'
import type { TokenOut } from '../lib/types'

function ChangePassword() {
  const { acceptSession } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      const r = await api<TokenOut>('/auth/change-password', {
        json: { current_password: current, new_password: next },
      })
      acceptSession(r.access_token, r.user)
      setCurrent('')
      setNext('')
      setMessage({ kind: 'success', text: 'Senha alterada. As outras sessões foram encerradas.' })
    } catch (err) {
      setMessage({ kind: 'error', text: (err as Error).message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <h2>Trocar senha</h2>
      <form onSubmit={submit} className="stack">
        <label className="field">
          <span>Senha atual</span>
          <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" required />
        </label>
        <label className="field">
          <span>Nova senha (mínimo de 8 caracteres)</span>
          <input type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" minLength={8} required />
        </label>
        {message && <Alert kind={message.kind}>{message.text}</Alert>}
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {busy ? 'Salvando…' : 'Trocar senha'}
        </button>
      </form>
    </section>
  )
}

function DeleteAccount() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api('/me/delete', { json: { password } })
      logout()
      navigate('/', { replace: true })
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  return (
    <section className="card danger-zone">
      <h2>Excluir minha conta</h2>
      <p>
        Seus dados pessoais (nome, e-mail e senha) são apagados. As ocorrências que você registrou continuam no
        sistema, <strong>sem identificação</strong>, porque são informação de saúde pública. Não é possível desfazer.
      </p>
      {!open ? (
        <button type="button" className="btn btn--danger" onClick={() => setOpen(true)}>
          Quero excluir minha conta
        </button>
      ) : (
        <form onSubmit={submit} className="stack">
          <label className="field">
            <span>Confirme com a sua senha</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </label>
          {error && <Alert>{error}</Alert>}
          <div className="actions">
            <button type="submit" className="btn btn--danger" disabled={busy}>
              {busy ? 'Excluindo…' : 'Excluir definitivamente'}
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setOpen(false)}>
              Cancelar
            </button>
          </div>
        </form>
      )}
    </section>
  )
}

/** The person's own account: password, data export and deletion (LGPD, art. 18). */
export function AccountPage() {
  const { user, ready, logout } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  if (ready && !user)
    return (
      <div className="page page--narrow">
        <Alert kind="info">
          <Link to="/entrar">Entre</Link> para ver a sua conta.
        </Alert>
      </div>
    )
  if (!user) return null

  return (
    <div className="page page--narrow">
      <div className="page-head">
        <div>
          <h1>Minha conta</h1>
          <p className="lead">
            {user.name} · {user.email} · {ROLE_LABEL[user.role]}
          </p>
        </div>
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => {
            logout()
            navigate('/')
          }}
        >
          Sair
        </button>
      </div>

      <ChangePassword />

      <section className="card">
        <h2>Meus dados</h2>
        <p>
          Baixe tudo o que o Sentinela Urbano guarda sobre você: dados da conta, ocorrências registradas e
          confirmações, num arquivo JSON (direito de acesso, art. 18 da LGPD).
        </p>
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => downloadFile('/me/data', 'meus-dados-sentinela.json').catch((e: Error) => setError(e.message))}
        >
          Baixar meus dados
        </button>
        {error && <Alert>{error}</Alert>}
      </section>

      {user.role === 'morador' ? (
        <DeleteAccount />
      ) : (
        <p className="hint">Contas da equipe não são excluídas por aqui: o gestor desativa o acesso na tela Equipe.</p>
      )}
    </div>
  )
}
