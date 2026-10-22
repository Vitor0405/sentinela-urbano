import L from 'leaflet'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Marker, Polyline, useMap, useMapEvents } from 'react-leaflet'
import { Link } from 'react-router'

import { Alert, Spinner, StatusBadge } from '../components/common'
import { RiskScore } from '../components/RiskBreakdown'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { formatDistance } from '../lib/labels'
import type { RouteOut } from '../lib/types'
import { BaseMap } from '../map/BaseMap'

type Point = { lat: number; lon: number }

function numberIcon(n: number | 'start'): L.DivIcon {
  const label = n === 'start' ? 'Você' : String(n)
  return L.divIcon({
    className: '',
    html: `<span class="route-pin${n === 'start' ? ' route-pin--start' : ''}">${label}</span>`,
    iconSize: n === 'start' ? [44, 24] : [28, 28],
    iconAnchor: n === 'start' ? [22, 12] : [14, 14],
  })
}

function PickStart({ onPick }: { onPick: (p: Point) => void }) {
  useMapEvents({ click: (e) => onPick({ lat: e.latlng.lat, lon: e.latlng.lng }) })
  return null
}

function FitRoute({ points }: { points: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (points.length > 1) map.fitBounds(L.latLngBounds(points), { padding: [30, 30] })
  }, [map, points])
  return null
}

/** Suggested visit route for the agent (backlog story 13). */
export function RoutePage() {
  const { isStaff, ready } = useAuth()
  const [start, setStart] = useState<Point | null>(null)
  const [excluded, setExcluded] = useState<number[]>([])
  const [route, setRoute] = useState<RouteOut | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [locating, setLocating] = useState(false)
  const [loading, setLoading] = useState(false)

  const locate = () => {
    if (!('geolocation' in navigator)) return setError('Este aparelho não informa a localização. Toque no mapa.')
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setStart({ lat: pos.coords.latitude, lon: pos.coords.longitude })
        setLocating(false)
      },
      () => {
        setError('Não foi possível obter sua localização. Toque no mapa para marcar o ponto de partida.')
        setLocating(false)
      },
      { enableHighAccuracy: true, timeout: 20_000 },
    )
  }

  const load = useCallback(() => {
    if (!start) return
    const params = new URLSearchParams({ lat: String(start.lat), lon: String(start.lon) })
    excluded.forEach((id) => params.append('exclude', String(id)))
    setLoading(true)
    api<RouteOut>(`/route?${params}`)
      .then((r) => {
        setRoute(r)
        setError(null)
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [start, excluded])

  useEffect(() => {
    if (ready && isStaff) load()
  }, [ready, isStaff, load])

  const path = useMemo<[number, number][]>(
    () =>
      route
        ? [
            [route.start_latitude, route.start_longitude],
            ...route.stops.map((s) => [s.item.latitude, s.item.longitude] as [number, number]),
          ]
        : [],
    [route],
  )

  if (ready && !isStaff)
    return (
      <div className="page page--narrow">
        <Alert kind="info">
          A rota de visita é exclusiva para agentes de saúde e gestores. <Link to="/entrar">Entrar</Link>
        </Alert>
      </div>
    )

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Rota de visita</h1>
          <p className="lead">
            As ocorrências de <strong>maior risco</strong> da sua fila, na ordem que reduz o deslocamento a partir de
            onde você está.
          </p>
        </div>
        <button type="button" className="btn btn--primary" onClick={locate} disabled={locating}>
          {locating ? 'Localizando…' : start ? 'Atualizar minha posição' : 'Usar minha localização'}
        </button>
      </div>

      {error && <Alert>{error}</Alert>}
      {!start && <p className="hint">Use sua localização ou toque no mapa para marcar o ponto de partida.</p>}

      <div className="route-layout">
        <section className="card">
          <BaseMap className="route-map" scrollWheelZoom>
            <PickStart onPick={setStart} />
            {route && <FitRoute points={path} />}
            {start && <Marker position={[start.lat, start.lon]} icon={numberIcon('start')} />}
            {route && path.length > 1 && <Polyline positions={path} pathOptions={{ className: 'route-line' }} />}
            {route?.stops.map((s) => (
              <Marker key={s.item.id} position={[s.item.latitude, s.item.longitude]} icon={numberIcon(s.position)} />
            ))}
          </BaseMap>
          {route && (
            <p className="hint">
              {route.stops.length} parada(s) · {formatDistance(route.total_m)} em linha reta. O trajeto pelas ruas é um
              pouco maior.
            </p>
          )}
        </section>

        <section className="card">
          <div className="section-head">
            <h2>Paradas</h2>
            {excluded.length > 0 && (
              <button type="button" className="btn btn--ghost" onClick={() => setExcluded([])}>
                Restaurar {excluded.length} removida(s)
              </button>
            )}
          </div>
          <p className="hint">
            Toque em × para tirar uma parada; a próxima ocorrência de maior risco da fila entra no lugar.
          </p>
          {loading && <Spinner />}
          {route?.stops.length === 0 && <p className="hint">Nenhuma ocorrência aguardando atendimento.</p>}
          <ol className="route-list">
            {route?.stops.map((s) => (
              <li key={s.item.id}>
                <span className="route-pin">{s.position}</span>
                <RiskScore risk={s.item.risk} />
                <span className="route-list__body">
                  <Link to={`/ocorrencias/${s.item.id}`}>
                    <strong>{s.item.type_name}</strong>
                  </Link>
                  <StatusBadge status={s.item.status} />
                  <small>
                    <span className="mono">{s.item.protocol}</span> · {formatDistance(s.leg_m)} da parada anterior
                  </small>
                </span>
                <button
                  type="button"
                  className="icon-button"
                  aria-label={`Remover ${s.item.protocol} da rota`}
                  title="Remover da rota"
                  onClick={() => setExcluded((cur) => [...cur, s.item.id])}
                >
                  ×
                </button>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  )
}
