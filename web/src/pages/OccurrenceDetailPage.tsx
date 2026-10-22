import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Marker } from 'react-leaflet'
import { Link, useParams } from 'react-router'

import { Alert, ProtectedPhoto, Spinner, StatusBadge, Timeline } from '../components/common'
import { RiskBreakdown } from '../components/RiskBreakdown'
import { MAX_PHOTOS } from '../features/report/validation'
import { api } from '../lib/api'
import { cachedGet } from '../lib/offlineCache'
import { useAuth } from '../lib/auth'
import { formatCoordinate } from '../lib/geo'
import { describeAge, formatDateTime } from '../lib/labels'
import type { OccurrenceDetail, OccurrenceStatus, OccurrenceType } from '../lib/types'
import { BaseMap } from '../map/BaseMap'
import { statusIcon } from '../map/markers'

const CAN_START: OccurrenceStatus[] = ['aberta', 'contestada']
const CAN_CLOSE: OccurrenceStatus[] = ['aberta', 'em_atendimento', 'contestada']

/** Agent or manager moves the report to the right type; "Outro" ones need it most. */
function Reclassify({ data, onChange }: { data: OccurrenceDetail; onChange: (d: OccurrenceDetail) => void }) {
  const [types, setTypes] = useState<OccurrenceType[]>([])
  const [typeId, setTypeId] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    cachedGet<OccurrenceType[]>('/occurrence-types')
      .then((all) => setTypes(all.filter((t) => !t.is_other && t.id !== data.type.id)))
      .catch(() => setTypes([]))
  }, [data.type.id])

  const save = async (event: FormEvent) => {
    event.preventDefault()
    if (!typeId) return
    setBusy(true)
    setMessage(null)
    try {
      const next = await api<OccurrenceDetail>(`/occurrences/${data.id}/type`, {
        method: 'PUT',
        json: { type_id: Number(typeId) },
      })
      onChange(next)
      setTypeId('')
      setMessage({ kind: 'success', text: `Reclassificada como "${next.type.name}". O risco já usa o novo peso.` })
    } catch (err) {
      setMessage({ kind: 'error', text: (err as Error).message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={save} className="stack">
      {data.type.is_other && (
        <p>
          O morador não achou o risco na lista e descreveu assim:{' '}
          <strong>“{data.custom_type_label ?? 'sem descrição'}”</strong>. Escolha o tipo que corresponde. Se nenhum
          servir e o caso se repetir, o gestor pode criar um tipo novo em <Link to="/configuracoes">Configurações</Link>.
        </p>
      )}
      <label className="field">
        <span>{data.type.is_other ? 'Tipo correto' : 'Mudar o tipo'}</span>
        <select value={typeId} onChange={(e) => setTypeId(e.target.value)}>
          <option value="">Escolha…</option>
          {types.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} (peso {t.weight.replace('.00', '')})
            </option>
          ))}
        </select>
      </label>
      <button type="submit" className="btn btn--ghost" disabled={busy || !typeId}>
        {busy ? 'Salvando…' : 'Reclassificar'}
      </button>
      {message && <Alert kind={message.kind}>{message.text}</Alert>}
    </form>
  )
}

/** Agent actions: take the occurrence and close it with a mandatory photo. */
function StaffActions({ data, onChange }: { data: OccurrenceDetail; onChange: (d: OccurrenceDetail) => void }) {
  const [files, setFiles] = useState<File[]>([])
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)

  const start = async () => {
    setBusy(true)
    setError(null)
    try {
      onChange(await api<OccurrenceDetail>(`/occurrences/${data.id}/start`, { json: {} }))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const close = async (event: FormEvent) => {
    event.preventDefault()
    if (files.length === 0) return setError('A foto do local após a ação é obrigatória para encerrar.')
    setBusy(true)
    setError(null)
    const form = new FormData()
    form.set('note', note.trim())
    files.forEach((f) => form.append('photos', f, f.name || 'resolucao.jpg'))
    try {
      onChange(await api<OccurrenceDetail>(`/occurrences/${data.id}/resolve`, { form }))
      setFiles([])
      setNote('')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!CAN_CLOSE.includes(data.status)) {
    return (
      <p className="hint">
        {data.status === 'resolvida_pelo_agente'
          ? 'Encerrada. Aguardando o morador confirmar se o problema foi realmente resolvido.'
          : 'Resolução confirmada pelo morador. Nenhuma ação pendente.'}
      </p>
    )
  }

  return (
    <div className="stack">
      {CAN_START.includes(data.status) && (
        <button type="button" className="btn btn--ghost" onClick={start} disabled={busy}>
          {data.status === 'contestada' ? 'Retomar atendimento' : 'Iniciar atendimento'}
        </button>
      )}
      <form onSubmit={close} className="stack">
        <strong>Encerrar ocorrência</strong>
        <div className="photo-actions">
          <button type="button" className="btn btn--ghost" onClick={() => input.current?.click()}>
            {files.length ? `${files.length} foto(s) selecionada(s)` : 'Foto do local após a ação'}
          </button>
        </div>
        <input
          ref={input}
          type="file"
          accept="image/*"
          capture="environment"
          multiple
          hidden
          onChange={(e) => {
            setFiles(Array.from(e.target.files ?? []).slice(0, MAX_PHOTOS))
            e.target.value = ''
          }}
        />
        <textarea
          rows={2}
          maxLength={500}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="O que foi feito? (opcional)"
        />
        {error && <Alert>{error}</Alert>}
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {busy ? 'Enviando…' : 'Encerrar com foto'}
        </button>
        <p className="hint">Quem registrou receberá a pergunta: “o problema foi realmente resolvido?”.</p>
      </form>
    </div>
  )
}

/** Private view for agents, managers and the author. */
export function OccurrenceDetailPage() {
  const { id = '' } = useParams()
  const { user, ready, isStaff } = useAuth()
  const [data, setData] = useState<OccurrenceDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!ready || !user) return
    api<OccurrenceDetail>(`/occurrences/${encodeURIComponent(id)}`)
      .then(setData)
      .catch((err: Error) => setError(err.message))
  }, [id, user, ready])

  const onChange = useCallback((next: OccurrenceDetail) => setData(next), [])

  if (ready && !user)
    return (
      <div className="page page--narrow">
        <Alert kind="info">
          Esta página é restrita. <Link to="/entrar" state={{ from: `/ocorrencias/${id}` }}>Entre</Link> com seu
          perfil de agente ou gestor.
        </Alert>
      </div>
    )
  if (error)
    return (
      <div className="page page--narrow">
        <Alert>{error}</Alert>
      </div>
    )
  if (!data)
    return (
      <div className="page page--narrow">
        <Spinner />
      </div>
    )

  const center: [number, number] = [data.latitude, data.longitude]
  const osm = `https://www.openstreetmap.org/?mlat=${data.latitude}&mlon=${data.longitude}#map=19/${data.latitude}/${data.longitude}`
  return (
    <div className="page">
      {isStaff && (
        <p className="back-link">
          <Link to="/fila">← Voltar para a fila</Link>
        </p>
      )}
      <p className="eyebrow mono">{data.protocol}</p>
      <h1>
        {data.type.name}
        {data.custom_type_label && <span className="h1-sub">: {data.custom_type_label}</span>}
      </h1>
      <div className="meta-row">
        <StatusBadge status={data.status} />
        <span>{describeAge(data.created_at)}</span>
        <span>Setor: {data.type.department}</span>
        {data.is_chronic && <span className="tag tag--warn">ponto crônico</span>}
      </div>

      <div className="detail-grid">
        {isStaff && data.risk && (
          <section className="card">
            <h2>Risco</h2>
            <RiskBreakdown risk={data.risk} />
          </section>
        )}

        {isStaff && (
          <section className="card">
            <h2>Atendimento</h2>
            <StaffActions data={data} onChange={onChange} />
          </section>
        )}

        {isStaff && (
          <section className={`card${data.type.is_other ? ' card--attention' : ''}`}>
            <h2>Classificação</h2>
            <Reclassify data={data} onChange={onChange} />
          </section>
        )}

        <section className="card">
          <h2>Local exato</h2>
          <BaseMap center={center} zoom={18} className="small-map" scrollWheelZoom={false}>
            <Marker position={center} icon={statusIcon(data.status, false)} />
          </BaseMap>
          <p className="hint">
            <span className="mono">{formatCoordinate(data.latitude, data.longitude)}</span> ·{' '}
            <a href={osm} target="_blank" rel="noreferrer">
              Abrir no OpenStreetMap
            </a>
          </p>
        </section>

        <section className="card">
          <h2>Registro</h2>
          <p>{data.description || <em>Sem descrição.</em>}</p>
          <dl className="facts">
            <dt>Registrada em</dt>
            <dd>{formatDateTime(data.created_at)}</dd>
            <dt>Prefeitura avisada</dt>
            <dd>{data.notified_at ? formatDateTime(data.notified_at) : 'aguardando envio'}</dd>
            <dt>Primeira resposta</dt>
            <dd>{data.first_response_at ? formatDateTime(data.first_response_at) : 'nenhuma ainda'}</dd>
            <dt>“Eu também vi”</dt>
            <dd>{data.confirmations}</dd>
            <dt>Quem registrou</dt>
            <dd>
              {data.is_anonymous
                ? 'Anônimo'
                : data.reporter
                  ? [data.reporter.name, data.reporter.contact].filter(Boolean).join(' · ')
                  : 'Não identificado'}
            </dd>
          </dl>
        </section>

        <section className="card detail-grid__wide">
          <h2>Fotos</h2>
          <div className="photo-list">
            {data.photos.map((p) => (
              <ProtectedPhoto key={p.id} photo={p} alt={`Foto da ocorrência ${data.protocol}`} />
            ))}
          </div>
        </section>

        <section className="card">
          <h2>Histórico</h2>
          <Timeline history={data.history} />
        </section>
      </div>
    </div>
  )
}
