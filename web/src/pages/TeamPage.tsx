import { type FormEvent, useEffect, useState } from 'react'
import { Link } from 'react-router'

import { Alert, Spinner } from '../components/common'
import { ManagementTabs } from '../components/ManagementTabs'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { OccurrenceType, SectorRef, StaffMember } from '../lib/types'

function toggle(list: number[], id: number): number[] {
  return list.includes(id) ? list.filter((x) => x !== id) : [...list, id]
}

function AgentScope({
  member,
  sectors,
  types,
  onSaved,
  onDeactivate,
}: {
  member: StaffMember
  sectors: SectorRef[]
  types: OccurrenceType[]
  onSaved: (m: StaffMember) => void
  onDeactivate: () => void
}) {
  const [sectorIds, setSectorIds] = useState(member.sector_ids)
  const [typeIds, setTypeIds] = useState(member.type_ids)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const dirty =
    [...sectorIds].sort().join() !== [...member.sector_ids].sort().join() ||
    [...typeIds].sort().join() !== [...member.type_ids].sort().join()

  const save = async () => {
    setBusy(true)
    setMessage(null)
    try {
      const saved = await api<StaffMember>(`/staff/${member.id}/scope`, {
        method: 'PUT',
        json: { sector_ids: sectorIds, type_ids: typeIds },
      })
      onSaved(saved)
      setMessage({ kind: 'success', text: 'Área de atuação salva.' })
    } catch (err) {
      setMessage({ kind: 'error', text: (err as Error).message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <div className="section-head">
        <div>
          <h2>{member.name}</h2>
          <small className="hint">{member.email}</small>
        </div>
        <div className="actions actions--tight">
          <button type="button" className="btn btn--ghost" onClick={onDeactivate} title="Encerra o acesso na hora">
            Desativar
          </button>
          <button type="button" className="btn btn--primary" onClick={save} disabled={busy || !dirty}>
            {busy ? 'Salvando…' : 'Salvar'}
          </button>
        </div>
      </div>
      <fieldset className="scope-group">
        <legend>
          Setores {sectorIds.length === 0 && <small>(todos)</small>}
        </legend>
        <div className="chips">
          {sectors.map((s) => (
            <label key={s.id} className="chip">
              <input type="checkbox" checked={sectorIds.includes(s.id)} onChange={() => setSectorIds(toggle(sectorIds, s.id))} />
              <span className="mono">{s.code}</span> {s.name}
            </label>
          ))}
          {sectors.length === 0 && <span className="hint">Nenhum setor cadastrado.</span>}
        </div>
      </fieldset>
      <fieldset className="scope-group">
        <legend>
          Tipos de risco {typeIds.length === 0 && <small>(todos)</small>}
        </legend>
        <div className="chips">
          {types.map((t) => (
            <label key={t.id} className="chip">
              <input type="checkbox" checked={typeIds.includes(t.id)} onChange={() => setTypeIds(toggle(typeIds, t.id))} />
              {t.name}
            </label>
          ))}
        </div>
      </fieldset>
      {message && <Alert kind={message.kind}>{message.text}</Alert>}
    </section>
  )
}

function InviteForm({ onInvited }: { onInvited: (m: StaffMember) => void }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<'agente' | 'gestor'>('agente')
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      const member = await api<StaffMember>('/staff', { json: { name, email, role } })
      onInvited(member)
      setMessage({ kind: 'success', text: `Convite enviado para ${member.email}. O link para criar a senha vale por 3 dias.` })
      setName('')
      setEmail('')
    } catch (err) {
      setMessage({ kind: 'error', text: (err as Error).message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <h2>Convidar para a equipe</h2>
      <form onSubmit={submit} className="stack">
        <div className="field-row">
          <label className="field">
            <span>Nome</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
          </label>
          <label className="field">
            <span>E-mail</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="field field--small">
            <span>Perfil</span>
            <select value={role} onChange={(e) => setRole(e.target.value as 'agente' | 'gestor')}>
              <option value="agente">Agente</option>
              <option value="gestor">Gestor</option>
            </select>
          </label>
        </div>
        {message && <Alert kind={message.kind}>{message.text}</Alert>}
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {busy ? 'Enviando…' : 'Enviar convite por e-mail'}
        </button>
      </form>
    </section>
  )
}

/** Manager defines which sectors and risk types each agent handles (backlog story 6). */
export function TeamPage() {
  const { user, ready } = useAuth()
  const [staff, setStaff] = useState<StaffMember[] | null>(null)
  const [sectors, setSectors] = useState<SectorRef[]>([])
  const [types, setTypes] = useState<OccurrenceType[]>([])
  const [error, setError] = useState<string | null>(null)
  const isManager = user?.role === 'gestor'

  useEffect(() => {
    if (!ready || !isManager) return
    Promise.all([
      api<StaffMember[]>('/staff'),
      api<SectorRef[]>('/sectors'),
      api<OccurrenceType[]>('/occurrence-types'),
    ])
      .then(([s, sec, t]) => {
        setStaff(s)
        setSectors(sec)
        setTypes(t)
      })
      .catch((err: Error) => setError(err.message))
  }, [ready, isManager])

  if (ready && !isManager)
    return (
      <div className="page page--narrow">
        <Alert kind="info">
          A gestão da equipe é exclusiva do gestor. <Link to="/entrar">Entrar</Link>
        </Alert>
      </div>
    )

  const agents = staff?.filter((m) => m.role === 'agente' && m.is_active) ?? []
  const others = staff?.filter((m) => m.role === 'gestor' || !m.is_active) ?? []
  const replace = (saved: StaffMember) =>
    setStaff((cur) => (cur?.some((x) => x.id === saved.id) ? cur.map((x) => (x.id === saved.id ? saved : x)) : [...(cur ?? []), saved]))
  const setActive = async (member: StaffMember, active: boolean) => {
    try {
      replace(await api<StaffMember>(`/staff/${member.id}`, { method: 'PATCH', json: { is_active: active } }))
    } catch (err) {
      setError((err as Error).message)
    }
  }
  return (
    <div className="page page--narrow">
      <ManagementTabs />
      <h1>Equipe</h1>
      <p className="lead">
        Convide agentes por e-mail e defina os setores e os tipos de risco de cada um. A fila, a rota e o mapa do agente passam a mostrar só o que é
        da competência dele. Sem nada marcado, o agente vê o município inteiro.
      </p>
      {error && <Alert>{error}</Alert>}
      {!staff && !error && <Spinner />}
      {staff && <InviteForm onInvited={replace} />}
      {staff && agents.length === 0 && <p className="hint">Nenhum agente ativo. Convide um acima.</p>}
      {agents.map((m) => (
        <AgentScope
          key={m.id}
          member={m}
          sectors={sectors}
          types={types}
          onSaved={replace}
          onDeactivate={() => setActive(m, false)}
        />
      ))}
      {others.length > 0 && (
        <section className="card">
          <h2>Gestores e contas desativadas</h2>
          <ul className="list">
            {others.map((m) => (
              <li key={m.id} className="staff-row">
                <span>
                  <strong>{m.name}</strong>
                  <small>
                    {m.email} · {m.role === 'gestor' ? 'Gestor' : 'Agente'}
                    {!m.is_active && ' · desativado'}
                  </small>
                </span>
                {!m.is_active && (
                  <button type="button" className="btn btn--ghost" onClick={() => setActive(m, true)}>
                    Reativar
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
