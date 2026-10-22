import { type FormEvent, useEffect, useState } from 'react'
import { Link } from 'react-router'

import { Alert, Spinner } from '../components/common'
import { ManagementTabs } from '../components/ManagementTabs'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { describeAge, formatNumber } from '../lib/labels'
import type { CustomLabel, SettingsView, TypeCreated, TypeSettings } from '../lib/types'

const GROUPS: { title: string; keys: string[] }[] = [
  {
    title: 'Índice de risco',
    keys: [
      'min_days_open',
      'recurrence_increment',
      'recurrence_radius_m',
      'sensitive_proximity_factor',
      'sensitive_radius_m',
      'unconfirmed_risk_cap',
    ],
  },
  { title: 'Pontos crônicos e acúmulo', keys: ['chronic_radius_m', 'chronic_owner_notice_threshold', 'cluster_radius_m', 'cluster_min_count', 'cluster_window_days'] },
  { title: 'Prazos, mensagens, rota e LIRAa', keys: ['response_deadline_days', 'messaging_immediate_risk', 'route_max_stops', 'liraa_window_days'] },
]

function TypeRow({ t, onSaved }: { t: TypeSettings; onSaved: (v: SettingsView) => void }) {
  const [name, setName] = useState(t.name)
  const [description, setDescription] = useState(t.description)
  const [weight, setWeight] = useState(String(t.weight))
  const [department, setDepartment] = useState(t.department)
  const [email, setEmail] = useState(t.notification_email ?? '')
  const [tips, setTips] = useState(t.prevention_tips)
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)

  const save = async (isActive?: boolean) => {
    setMessage(null)
    try {
      const view = await api<SettingsView>(`/settings/types/${t.id}`, {
        method: 'PUT',
        json: {
          name,
          description,
          ...(isActive === undefined ? {} : { is_active: isActive }),
          weight: Number(weight.replace(',', '.')),
          department,
          notification_email: email.trim() || null,
          prevention_tips: tips,
        },
      })
      onSaved(view)
      setMessage({ kind: 'success', text: 'Salvo.' })
    } catch (err) {
      setMessage({ kind: 'error', text: (err as Error).message })
    }
  }

  return (
    <details className="type-settings">
      <summary>
        <strong>{t.name}</strong> <span className="tag">peso {formatNumber(t.weight)}</span>
        {!t.is_active && <span className="tag tag--warn">desativado</span>}
      </summary>
      <div className="field-row">
        <label className="field">
          <span>Nome</span>
          <input value={name} onChange={(e) => setName(e.target.value)} minLength={3} maxLength={80} />
        </label>
        <label className="field">
          <span>Descrição curta</span>
          <input value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} />
        </label>
      </div>
      <div className="field-row">
        <label className="field field--small">
          <span>Peso</span>
          <input inputMode="decimal" value={weight} onChange={(e) => setWeight(e.target.value)} />
        </label>
        <label className="field">
          <span>Setor de destino</span>
          <input value={department} onChange={(e) => setDepartment(e.target.value)} />
        </label>
        <label className="field">
          <span>E-mail próprio deste tipo (opcional)</span>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="usa o e-mail geral" />
        </label>
      </div>
      <label className="field">
        <span>Orientação de prevenção</span>
        <textarea rows={3} value={tips} maxLength={2000} onChange={(e) => setTips(e.target.value)} />
      </label>
      <div className="actions">
        <button type="button" className="btn btn--primary" onClick={() => save()}>
          Salvar {t.name.toLowerCase()}
        </button>
        {!t.is_other && (
          <button type="button" className="btn btn--ghost" onClick={() => save(!t.is_active)}>
            {t.is_active ? 'Desativar (sai do formulário)' : 'Reativar'}
          </button>
        )}
      </div>
      {message && <Alert kind={message.kind}>{message.text}</Alert>}
    </details>
  )
}

/** New official type, optionally absorbing the "Outro" reports that described it. */
function NewTypeForm({
  fromLabel,
  onCreated,
  onCancel,
}: {
  fromLabel: CustomLabel | null
  onCreated: (result: TypeCreated) => void
  onCancel: () => void
}) {
  const [name, setName] = useState(fromLabel?.label ?? '')
  const [description, setDescription] = useState('')
  const [weight, setWeight] = useState('2')
  const [department, setDepartment] = useState('Vigilância em Saúde – Controle de Endemias')
  const [breeding, setBreeding] = useState(false)
  const [tips, setTips] = useState('')
  const [moveReports, setMoveReports] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onCreated(
        await api<TypeCreated>('/settings/types', {
          json: {
            name,
            description,
            weight: Number(weight.replace(',', '.')),
            department,
            is_breeding_site: breeding,
            prevention_tips: tips,
            from_label: fromLabel && moveReports ? fromLabel.label : null,
          },
        }),
      )
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="new-type stack" onSubmit={submit}>
      <h3>{fromLabel ? `Novo tipo a partir de “${fromLabel.label}”` : 'Novo tipo de risco'}</h3>
      <div className="field-row">
        <label className="field">
          <span>Nome (aparece para os moradores)</span>
          <input value={name} onChange={(e) => setName(e.target.value)} minLength={3} maxLength={80} required />
        </label>
        <label className="field field--small">
          <span>Peso</span>
          <input inputMode="decimal" value={weight} onChange={(e) => setWeight(e.target.value)} required />
        </label>
      </div>
      <label className="field">
        <span>Descrição curta (ajuda o morador a escolher)</span>
        <input value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} />
      </label>
      <label className="field">
        <span>Setor de destino na prefeitura</span>
        <input value={department} onChange={(e) => setDepartment(e.target.value)} minLength={2} maxLength={120} required />
      </label>
      <label className="field">
        <span>Orientação de prevenção (opcional)</span>
        <textarea rows={2} value={tips} maxLength={2000} onChange={(e) => setTips(e.target.value)} />
      </label>
      <label className="check">
        <input type="checkbox" checked={breeding} onChange={(e) => setBreeding(e.target.checked)} />
        <span>É criadouro direto do mosquito (acumula água)</span>
      </label>
      {fromLabel && (
        <label className="check">
          <input type="checkbox" checked={moveReports} onChange={(e) => setMoveReports(e.target.checked)} />
          <span>
            Mover para o novo tipo os {fromLabel.count} registro(s) descritos assim (o risco passa a usar o novo peso)
          </span>
        </label>
      )}
      <p className="hint">
        Para comparação: água parada tem peso 5; lixo e vazamento, 3; terreno baldio e esgoto, 2; os demais, 1. "Outro
        risco" usa 2 até alguém classificar.
      </p>
      {error && <Alert>{error}</Alert>}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {busy ? 'Criando…' : 'Criar tipo'}
        </button>
        <button type="button" className="btn btn--ghost" onClick={onCancel}>
          Cancelar
        </button>
      </div>
    </form>
  )
}

/** What residents typed under "Outro risco", most frequent first. */
function CustomLabels({ onCreated }: { onCreated: (result: TypeCreated) => void }) {
  const [labels, setLabels] = useState<CustomLabel[] | null>(null)
  const [creating, setCreating] = useState<CustomLabel | 'blank' | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const reload = () =>
    api<CustomLabel[]>('/settings/custom-labels')
      .then(setLabels)
      .catch(() => setLabels([]))
  useEffect(() => {
    void reload()
  }, [])

  const created = (result: TypeCreated) => {
    const name = result.settings.types.find((t) => t.id === result.type_id)?.name ?? 'novo tipo'
    setMessage(
      `Tipo "${name}" criado. Ele já aparece no formulário de registro` +
        (result.reclassified ? ` e ${result.reclassified} registro(s) foram movidos para ele.` : '.'),
    )
    setCreating(null)
    onCreated(result)
    void reload()
  }

  return (
    <section className="card">
      <h2>Riscos descritos pelos moradores</h2>
      <p className="hint">
        Quando nenhum tipo serve, o morador escolhe "Outro risco" e descreve em poucas palavras. Descrições que se
        repetem são candidatas a um tipo oficial. Casos isolados, o agente reclassifica na própria ocorrência.
      </p>
      {message && <Alert kind="success">{message}</Alert>}
      {labels === null && <Spinner />}
      {labels?.length === 0 && <p>Nenhum registro em "Outro risco" aguardando classificação.</p>}
      {labels && labels.length > 0 && (
        <ul className="custom-labels">
          {labels.map((l) => (
            <li key={l.label}>
              <div>
                <strong>{l.label}</strong>
                <span className="hint">
                  {' '}
                  · {l.count} registro(s), {l.active} em aberto · último {describeAge(l.last_reported_at)} ·{' '}
                  {l.occurrence_ids.slice(0, 3).map((id, i) => (
                    <span key={id}>
                      {i > 0 && ', '}
                      <Link to={`/ocorrencias/${id}`}>ver</Link>
                    </span>
                  ))}
                </span>
              </div>
              <button type="button" className="btn btn--ghost btn--small" onClick={() => setCreating(l)}>
                Criar tipo
              </button>
            </li>
          ))}
        </ul>
      )}
      {creating ? (
        <NewTypeForm
          key={creating === 'blank' ? 'blank' : creating.label}
          fromLabel={creating === 'blank' ? null : creating}
          onCreated={created}
          onCancel={() => setCreating(null)}
        />
      ) : (
        <div className="actions">
          <button type="button" className="btn btn--ghost" onClick={() => setCreating('blank')}>
            + Novo tipo de risco
          </button>
        </div>
      )}
    </section>
  )
}

/** Manager calibrates the index during the pilot, without touching the database. */
export function SettingsPage() {
  const { user, ready } = useAuth()
  const isManager = user?.role === 'gestor'
  const [view, setView] = useState<SettingsView | null>(null)
  const [values, setValues] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const load = (v: SettingsView) => {
    setView(v)
    setValues(Object.fromEntries(v.coefficients.map((c) => [c.key, String(c.value).replace('.', ',')])))
  }

  useEffect(() => {
    if (ready && isManager) api<SettingsView>('/settings').then(load).catch((e: Error) => setMessage({ kind: 'error', text: e.message }))
  }, [ready, isManager])

  const changed = view?.coefficients.filter((c) => Number((values[c.key] ?? '').replace(',', '.')) !== c.value) ?? []

  const save = async () => {
    setBusy(true)
    setMessage(null)
    try {
      const payload = Object.fromEntries(changed.map((c) => [c.key, Number(values[c.key].replace(',', '.'))]))
      load(await api<SettingsView>('/settings/coefficients', { method: 'PUT', json: { values: payload } }))
      setMessage({ kind: 'success', text: `${changed.length} coeficiente(s) salvo(s). O índice já usa os novos valores.` })
    } catch (err) {
      setMessage({ kind: 'error', text: (err as Error).message })
    } finally {
      setBusy(false)
    }
  }

  if (ready && !isManager)
    return (
      <div className="page page--narrow">
        <Alert kind="info">
          As configurações são exclusivas do gestor. <Link to="/entrar">Entrar</Link>
        </Alert>
      </div>
    )

  const byKey = Object.fromEntries((view?.coefficients ?? []).map((c) => [c.key, c]))
  return (
    <div className="page page--narrow">
      <ManagementTabs />
      <h1>Configurações</h1>
      <p className="lead">
        Calibre o índice de risco com a vigilância durante o piloto. As mudanças valem na hora: o risco é recalculado a
        cada consulta.
      </p>
      {!view && !message && <Spinner />}

      {view &&
        GROUPS.map((g) => (
          <section className="card" key={g.title}>
            <h2>{g.title}</h2>
            <div className="coef-grid">
              {g.keys
                .filter((k) => byKey[k])
                .map((k) => {
                  const c = byKey[k]
                  return (
                    <label key={k} className="field coef">
                      <span>{c.description}</span>
                      <input
                        inputMode="decimal"
                        value={values[k] ?? ''}
                        onChange={(e) => setValues((cur) => ({ ...cur, [k]: e.target.value }))}
                        aria-describedby={`range-${k}`}
                      />
                      <small id={`range-${k}`}>
                        entre {formatNumber(c.min)} e {formatNumber(c.max)}
                        {c.integer ? ', inteiro' : ''}
                      </small>
                    </label>
                  )
                })}
            </div>
          </section>
        ))}

      {view && (
        <div className="sticky-save">
          {message && <Alert kind={message.kind}>{message.text}</Alert>}
          <button type="button" className="btn btn--primary" onClick={save} disabled={busy || changed.length === 0}>
            {busy ? 'Salvando…' : changed.length ? `Salvar ${changed.length} alteração(ões)` : 'Nenhuma alteração'}
          </button>
        </div>
      )}

      {view && (
        <section className="card">
          <h2>Tipos de risco</h2>
          <p className="hint">Peso no índice, setor da prefeitura que recebe e orientação de prevenção mostrada ao morador.</p>
          {view.types.map((t) => (
            <TypeRow key={t.id} t={t} onSaved={load} />
          ))}
        </section>
      )}

      {view && <CustomLabels onCreated={(result) => load(result.settings)} />}
    </div>
  )
}
