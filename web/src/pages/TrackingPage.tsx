import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { Circle, Marker } from 'react-leaflet'
import { useLocation, useNavigate, useParams } from 'react-router'

import { Alert, ProtectedPhoto, Spinner, StatusBadge, Timeline } from '../components/common'
import { PRIVACY_GRID_METERS } from '../config'
import { api, downloadFile } from '../lib/api'
import { formatCoordinate } from '../lib/geo'
import { describeAge, formatDateTime, readTrackingToken } from '../lib/labels'
import type { Tracking } from '../lib/types'
import { BaseMap } from '../map/BaseMap'
import { statusIcon } from '../map/markers'

export function TrackingLookupPage() {
  const navigate = useNavigate()
  const [protocol, setProtocol] = useState('')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const value = protocol.trim().toUpperCase()
    if (value) navigate(`/acompanhar/${encodeURIComponent(value)}`)
  }

  return (
    <div className="page page--narrow">
      <h1>Acompanhar ocorrência</h1>
      <p className="lead">Digite o número de protocolo recebido no registro. Não é preciso entrar.</p>
      <form onSubmit={submit} className="inline-form">
        <label className="field">
          <span>Protocolo</span>
          <input
            value={protocol}
            onChange={(e) => setProtocol(e.target.value)}
            placeholder="SU-2026-000123"
            autoCapitalize="characters"
            className="mono"
          />
        </label>
        <button type="submit" className="btn btn--primary">
          Consultar
        </button>
      </form>
      <p className="hint">
        Se você guardou o link de acompanhamento, abra-o diretamente: ele também mostra as fotos e a
        localização exata.
      </p>
    </div>
  )
}

/** "X dias sem resposta": the prefecture's silence made visible, and the way out of it. */
function PrefectureResponse({ data, token }: { data: Tracking; token: string | null }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (data.days_without_response == null) {
    return data.responded_after_days != null ? (
      <section className="card response response--ok">
        <h2>Resposta da prefeitura</h2>
        <p>
          A equipe de saúde atuou{' '}
          {data.responded_after_days === 0 ? 'no mesmo dia' : `em ${data.responded_after_days} dia(s)`} após o aviso.
        </p>
      </section>
    ) : null
  }

  const days = data.days_without_response
  const progress = Math.min(100, (days / data.deadline_days) * 100)

  const download = async () => {
    setBusy(true)
    setError(null)
    try {
      await downloadFile(
        `/tracking/${encodeURIComponent(data.protocol)}/ouvidoria.pdf`,
        `ouvidoria-${data.protocol}.pdf`,
        token ? { 'X-Tracking-Token': token } : {},
      )
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className={`card response${data.response_overdue ? ' response--overdue' : ''}`}>
      <h2>Resposta da prefeitura</h2>
      <p className="response__count">
        <strong>{days}</strong> {days === 1 ? 'dia' : 'dias'} sem resposta
      </p>
      <div className="deadline" aria-hidden="true">
        <span style={{ width: `${progress}%` }} />
      </div>
      <p className="hint">
        {data.response_overdue
          ? `O prazo de ${data.deadline_days} dias venceu.`
          : `Prazo de ${data.deadline_days} dias: faltam ${data.days_left} dia(s).`}
      </p>
      {data.can_request_ouvidoria && (
        <>
          <p>
            Você pode gerar um documento com protocolo, fotos, coordenada, datas e histórico para encaminhar à
            Ouvidoria Municipal.
          </p>
          <button type="button" className="btn btn--primary" onClick={download} disabled={busy}>
            {busy ? 'Gerando…' : 'Gerar documento para a ouvidoria (PDF)'}
          </button>
        </>
      )}
      {data.is_owner && !data.response_overdue && (
        <p className="hint">
          Se a prefeitura não responder até o fim do prazo, você poderá gerar aqui um documento para a ouvidoria.
        </p>
      )}
      {error && <Alert>{error}</Alert>}
    </section>
  )
}

/** The single question after the agent closes the occurrence (improvement 3). */
function FeedbackQuestion({
  protocol,
  token,
  onAnswered,
}: {
  protocol: string
  token: string | null
  onAnswered: (data: Tracking) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const answer = async (resolved: boolean) => {
    setBusy(true)
    setError(null)
    try {
      onAnswered(
        await api<Tracking>(`/tracking/${encodeURIComponent(protocol)}/feedback`, {
          json: { resolved },
          headers: token ? { 'X-Tracking-Token': token } : {},
        }),
      )
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card question" aria-labelledby="question-title">
      <h2 id="question-title">O problema foi realmente resolvido?</h2>
      <p className="hint">
        O agente informou que resolveu. Confira o local (de preferência pela via pública) e responda. Se não foi
        resolvido, a ocorrência volta para a fila de atendimento. Você só pode responder uma vez.
      </p>
      <div className="actions">
        <button type="button" className="btn btn--primary" disabled={busy} onClick={() => answer(true)}>
          Sim, foi resolvido
        </button>
        <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => answer(false)}>
          Não, continua o problema
        </button>
      </div>
      {error && <Alert>{error}</Alert>}
    </section>
  )
}

export function TrackingPage() {
  const { protocol = '' } = useParams()
  const { hash } = useLocation()
  const token = useMemo(() => readTrackingToken(hash), [hash])
  const [data, setData] = useState<Tracking | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setData(null)
    setError(null)
    api<Tracking>(`/tracking/${encodeURIComponent(protocol)}`, {
      headers: token ? { 'X-Tracking-Token': token } : {},
    })
      .then(setData)
      .catch((err: Error) => setError(err.message))
  }, [protocol, token])

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
  return (
    <div className="page page--narrow">
      <p className="eyebrow mono">{data.protocol}</p>
      <h1>{data.type_name}</h1>
      <div className="meta-row">
        <StatusBadge status={data.status} />
        <span>{describeAge(data.created_at)}</span>
        <span>Setor: {data.department}</span>
      </div>

      {token && !data.is_owner && (
        <Alert>Este link de acompanhamento não é válido para o protocolo. Mostrando só os dados públicos.</Alert>
      )}

      {data.can_answer && <FeedbackQuestion protocol={data.protocol} token={token} onAnswered={setData} />}

      <PrefectureResponse data={data} token={token} />

      <section className="card">
        <h2>Andamento</h2>
        <Timeline history={data.history} />
      </section>

      <section className="card">
        <h2>Local</h2>
        <BaseMap center={center} zoom={17} className="small-map" scrollWheelZoom={false}>
          {data.location_is_exact ? (
            <Marker position={center} icon={statusIcon(data.status, false)} />
          ) : (
            <Circle center={center} radius={PRIVACY_GRID_METERS * 0.71} pathOptions={{ className: 'approx-area' }} />
          )}
        </BaseMap>
        <p className="hint">
          {data.location_is_exact
            ? `Localização exata: ${formatCoordinate(data.latitude, data.longitude)}`
            : `Área aproximada (~${PRIVACY_GRID_METERS} m). A localização exata só aparece para quem registrou e para a equipe de saúde.`}
        </p>
      </section>

      {data.is_owner && (
        <section className="card">
          <h2>Seu registro</h2>
          {data.description && <p>{data.description}</p>}
          <div className="photo-list">
            {data.photos.map((p) => (
              <ProtectedPhoto key={p.id} photo={p} trackingToken={token} alt={`Foto do protocolo ${data.protocol}`} />
            ))}
          </div>
          <p className="hint">Registrada em {formatDateTime(data.created_at)}.</p>
        </section>
      )}
    </div>
  )
}
