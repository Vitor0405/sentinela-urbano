import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'

import { Alert, Spinner, StatusBadge } from '../components/common'
import { RecommendationTag, RiskScore } from '../components/RiskBreakdown'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { describeAge, formatDistance, formatPercent, sensitiveKindLabel } from '../lib/labels'
import type { QueueItem, ResolutionStats } from '../lib/types'

type Order = 'risk' | 'distance'
type Position = { lat: number; lon: number }

export function QueuePage() {
  const { isStaff, ready } = useAuth()
  const [order, setOrder] = useState<Order>('risk')
  const [position, setPosition] = useState<Position | null>(null)
  const [items, setItems] = useState<QueueItem[] | null>(null)
  const [stats, setStats] = useState<ResolutionStats | null>(null)
  const [scope, setScope] = useState<{ sector_ids: number[]; type_ids: number[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [locating, setLocating] = useState(false)

  const load = useCallback(() => {
    const params = new URLSearchParams({ order })
    if (position) {
      params.set('lat', String(position.lat))
      params.set('lon', String(position.lon))
    }
    api<{ items: QueueItem[] }>(`/queue?${params}`)
      .then((d) => {
        setItems(d.items)
        setError(null)
      })
      .catch((err: Error) => setError(err.message))
  }, [order, position])

  useEffect(() => {
    if (ready && isStaff) load()
  }, [ready, isStaff, load])

  useEffect(() => {
    if (ready && isStaff) api<ResolutionStats>('/stats/resolution').then(setStats).catch(() => {})
  }, [ready, isStaff])

  useEffect(() => {
    if (ready && isStaff) api<{ sector_ids: number[]; type_ids: number[] }>('/me/scope').then(setScope).catch(() => {})
  }, [ready, isStaff])

  const orderByDistance = () => {
    if (position) return setOrder('distance')
    if (!('geolocation' in navigator)) return setError('Este aparelho não informa a localização.')
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setPosition({ lat: pos.coords.latitude, lon: pos.coords.longitude })
        setOrder('distance')
        setLocating(false)
      },
      () => {
        setError('Não foi possível obter sua localização para ordenar por proximidade.')
        setLocating(false)
      },
      { enableHighAccuracy: true, timeout: 20_000 },
    )
  }

  if (ready && !isStaff)
    return (
      <div className="page page--narrow">
        <Alert kind="info">
          A fila de atendimento é exclusiva para agentes de saúde e gestores. <Link to="/entrar">Entrar</Link>
        </Alert>
      </div>
    )

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Fila de atendimento</h1>
          <p className="lead">
            Ordenada pelo <strong>risco real</strong>: peso do tipo × dias em aberto × reincidência × proximidade
            de escolas e unidades de saúde.
          </p>
        </div>
        {stats && (
          <dl className="kpis">
            <div>
              <dt>Resolução confirmada</dt>
              <dd>{formatPercent(stats.confirmed_rate)}</dd>
            </div>
            <div>
              <dt>Fechamento contestado</dt>
              <dd>{formatPercent(stats.contested_rate)}</dd>
            </div>
            <div>
              <dt>Aguardando morador</dt>
              <dd>{stats.awaiting}</dd>
            </div>
          </dl>
        )}
      </div>

      {scope && (scope.sector_ids.length > 0 || scope.type_ids.length > 0) && (
        <Alert kind="info">
          Sua fila está limitada pelo gestor a{' '}
          {scope.sector_ids.length > 0 ? `${scope.sector_ids.length} setor(es)` : 'todos os setores'} e{' '}
          {scope.type_ids.length > 0 ? `${scope.type_ids.length} tipo(s) de risco` : 'todos os tipos'}.
        </Alert>
      )}

      <div className="queue-actions">
      <div className="segmented" role="group" aria-label="Ordenar fila">
        <button type="button" aria-pressed={order === 'risk'} onClick={() => setOrder('risk')}>
          Por risco
        </button>
        <button type="button" aria-pressed={order === 'distance'} onClick={orderByDistance} disabled={locating}>
          {locating ? 'Localizando…' : 'Por proximidade'}
        </button>
      </div>
        <Link to="/rota" className="btn btn--primary">
          Montar rota de visita
        </Link>
      </div>

      {error && <Alert>{error}</Alert>}
      {!items && !error && <Spinner />}
      {items?.length === 0 && <p className="lead">Nenhuma ocorrência aguardando atendimento.</p>}

      <ol className="queue">
        {items?.map((item, index) => (
          <li key={item.id}>
            <Link to={`/ocorrencias/${item.id}`} className="queue-item">
              <span className="queue-item__rank">{index + 1}</span>
              <RiskScore risk={item.risk} />
              <span className="queue-item__body">
                <span className="queue-item__title">
                  <strong>{item.type_name}</strong>
                  <StatusBadge status={item.status} />
                  {item.is_chronic && <span className="tag tag--warn">ponto crônico</span>}
                  <RecommendationTag risk={item.risk} />
                </span>
                <small className="queue-item__meta">
                  <span className="mono">{item.protocol}</span> · {describeAge(item.created_at)}
                  {item.distance_m != null && <> · a {formatDistance(item.distance_m)} de você</>}
                </small>
                <small className="queue-item__why">
                  {item.risk.nearest_sensitive &&
                    `${sensitiveKindLabel(item.risk.nearest_sensitive.kind)} a ${formatDistance(item.risk.nearest_sensitive.distance_m)} · `}
                  {item.risk.recurrence_count > 0 && `${item.risk.recurrence_count} reincidência(s) · `}
                  {item.risk.confirmations > 0
                    ? `${item.risk.confirmations} confirmação(ões) de moradores`
                    : 'sem confirmação de outro morador'}
                </small>
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </div>
  )
}
