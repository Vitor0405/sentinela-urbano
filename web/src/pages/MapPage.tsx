import type { LatLngBounds } from 'leaflet'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useMapEvents } from 'react-leaflet'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { PRIVACY_GRID_METERS } from '../config'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { bboxParam, isValidLatLng, parseZoom } from '../lib/geo'
import { useServiceArea } from '../lib/serviceArea'
import { ACTIVE_STATUSES, ALL_STATUSES, STATUS_LABEL } from '../lib/labels'
import type { MapItem, OccurrenceStatus, OccurrenceType } from '../lib/types'
import { BaseMap } from '../map/BaseMap'
import { ClusterLayer } from '../map/ClusterLayer'
import type { HeatPoint } from '../map/heat'
import { HeatLayer } from '../map/HeatLayer'

function BoundsWatcher({ onChange }: { onChange: (bounds: LatLngBounds) => void }) {
  const map = useMapEvents({
    moveend: () => onChange(map.getBounds()),
  })
  useEffect(() => onChange(map.getBounds()), [map, onChange])
  return null
}

export function MapPage() {
  const { user, isStaff, ready } = useAuth()
  const serviceArea = useServiceArea()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const focus = useMemo(() => {
    const lat = Number(params.get('lat'))
    const lon = Number(params.get('lon'))
    if (!params.get('lat') || !isValidLatLng(lat, lon)) return null
    return { center: [lat, lon] as [number, number], zoom: parseZoom(params.get('z') ?? undefined, 16) }
  }, [params])
  const [layer, setLayer] = useState<'pontos' | 'calor'>('pontos')
  const [heat, setHeat] = useState<HeatPoint[]>([])
  const [notice, setNotice] = useState<string | null>(null)
  const [types, setTypes] = useState<OccurrenceType[]>([])
  const [selectedTypes, setSelectedTypes] = useState<string[]>([])
  const [statuses, setStatuses] = useState<OccurrenceStatus[]>(ACTIVE_STATUSES)
  const [bounds, setBounds] = useState<LatLngBounds | null>(null)
  const [items, setItems] = useState<MapItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [filtersOpen, setFiltersOpen] = useState(false)

  useEffect(() => {
    api<OccurrenceType[]>('/occurrence-types').then(setTypes).catch(() => setTypes([]))
  }, [])

  useEffect(() => {
    if (!bounds || !ready) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams()
      params.set('bbox', bboxParam(bounds.getSouth(), bounds.getWest(), bounds.getNorth(), bounds.getEast()))
      selectedTypes.forEach((t) => params.append('type', t))
      statuses.forEach((s) => params.append('status', s))
      // Staff get exact points; everyone else gets the grid-snapped public layer.
      const path = isStaff ? '/occurrences' : '/occurrences/public'
      setLoading(true)
      api<{ items: MapItem[] }>(`${path}?${params}`, { signal: controller.signal })
        .then((data) => {
          setItems(data.items)
          setError(null)
        })
        .catch((err: Error) => {
          if (err.name !== 'AbortError') setError(err.message)
        })
        .finally(() => setLoading(false))
    }, 250)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [bounds, selectedTypes, statuses, isStaff, ready])

  // Heat layer: risk-weighted (not count), from public grid cells, active occurrences only.
  useEffect(() => {
    if (layer !== 'calor' || !bounds) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams()
      params.set('bbox', bboxParam(bounds.getSouth(), bounds.getWest(), bounds.getNorth(), bounds.getEast()))
      selectedTypes.forEach((t) => params.append('type', t))
      api<{ points: HeatPoint[] }>(`/heatmap/public?${params}`, { signal: controller.signal })
        .then((data) => setHeat(data.points))
        .catch((err: Error) => {
          if (err.name !== 'AbortError') setError(err.message)
        })
    }, 250)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [layer, bounds, selectedTypes])

  const onBounds = useCallback((b: LatLngBounds) => setBounds(b), [])
  const openDetail = useCallback((item: MapItem) => navigate(`/ocorrencias/${item.id}`), [navigate])

  const confirmSighting = useCallback(
    async (item: MapItem) => {
      if (!user) {
        navigate('/entrar', { state: { from: '/' } })
        return
      }
      try {
        const result = await api<{ confirmations: number }>(
          `/tracking/${encodeURIComponent(item.protocol)}/confirmations`,
          { method: 'POST' },
        )
        setItems((cur) =>
          cur.map((i) => (i.protocol === item.protocol ? { ...i, confirmations: result.confirmations } : i)),
        )
        setNotice('Obrigado! Sua confirmação ajuda a priorizar o atendimento.')
      } catch (err) {
        setNotice((err as Error).message)
      }
    },
    [user, navigate],
  )

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(null), 4000)
    return () => window.clearTimeout(timer)
  }, [notice])

  const toggle = <T,>(list: T[], value: T) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value])

  return (
    <div className="map-page">
      <h1 className="sr-only">Mapa de focos de risco</h1>
      <BaseMap className="map-page__map" center={focus?.center} zoom={focus?.zoom}>
        <BoundsWatcher onChange={onBounds} />
        {layer === 'pontos' ? (
          <ClusterLayer
            items={items}
            onOpenDetail={isStaff ? openDetail : undefined}
            onConfirm={isStaff ? undefined : confirmSighting}
          />
        ) : (
          <HeatLayer points={heat} />
        )}
      </BaseMap>

      <div className="layer-switch segmented" role="group" aria-label="Camada do mapa">
        <button type="button" aria-pressed={layer === 'pontos'} onClick={() => setLayer('pontos')}>
          Pontos
        </button>
        <button type="button" aria-pressed={layer === 'calor'} onClick={() => setLayer('calor')}>
          Calor por risco
        </button>
      </div>

      {notice && (
        <p className="toast" role="status">
          {notice}
        </p>
      )}

      <section className={`map-panel${filtersOpen ? ' map-panel--open' : ''}`} aria-label="Filtros do mapa">
        <button
          type="button"
          className="map-panel__toggle"
          aria-expanded={filtersOpen}
          onClick={() => setFiltersOpen((v) => !v)}
        >
          {error ? (
            <span className="map-panel__error">{error}</span>
          ) : (
            <span>
              <strong>{items.length}</strong> {items.length === 1 ? 'ocorrência' : 'ocorrências'} nesta área
              {loading && <span className="map-panel__loading"> · atualizando…</span>}
            </span>
          )}
          <span className="map-panel__chevron" aria-hidden="true">
            {filtersOpen ? '▾' : '▴'}
          </span>
        </button>

        <div className="map-panel__body">
          <fieldset>
            <legend>Situação</legend>
            <div className="chips">
              {ALL_STATUSES.map((s) => (
                <label key={s} className={`chip chip--${s}`}>
                  <input
                    type="checkbox"
                    checked={statuses.includes(s)}
                    onChange={() => setStatuses((cur) => toggle(cur, s))}
                  />
                  {STATUS_LABEL[s]}
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend>Tipo de risco {selectedTypes.length === 0 && <small>(todos)</small>}</legend>
            <div className="chips">
              {types.map((t) => (
                <label key={t.code} className="chip">
                  <input
                    type="checkbox"
                    checked={selectedTypes.includes(t.code)}
                    onChange={() => setSelectedTypes((cur) => toggle(cur, t.code))}
                  />
                  {t.name}
                </label>
              ))}
            </div>
          </fieldset>
          {serviceArea && <p className="map-panel__area">Área atendida: {serviceArea.name}</p>}
          {layer === 'calor' && (
            <p className="map-panel__privacy">
              O calor soma o <strong>risco</strong> (não a quantidade) das ocorrências ativas em cada célula de ~
              {PRIVACY_GRID_METERS} m.
            </p>
          )}
          <p className="map-panel__privacy">
            {isStaff
              ? 'Você está vendo a localização exata (perfil de agente ou gestor).'
              : `Para proteger moradores, cada ponto aparece no centro de uma grade de ~${PRIVACY_GRID_METERS} m, nunca no endereço exato.`}
          </p>
        </div>
      </section>

      <Link to="/registrar" className="fab">
        <span aria-hidden="true">＋</span> Registrar foco
      </Link>
    </div>
  )
}
