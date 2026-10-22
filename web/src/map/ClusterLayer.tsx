import 'leaflet.markercluster/dist/MarkerCluster.css'

import L from 'leaflet'
// The plugin attaches itself to the global `L` that Leaflet 1.x always sets.
import 'leaflet.markercluster'
import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'

import { PRIVACY_GRID_METERS } from '../config'
import { describeAge, STATUS_LABEL } from '../lib/labels'
import type { MapItem } from '../lib/types'
import { statusIcon } from './markers'

interface Props {
  items: MapItem[]
  onOpenDetail?: (item: MapItem) => void
  /** "Eu também vi"; omitted for staff, who do not vouch for reports. */
  onConfirm?: (item: MapItem) => void
}

const CONFIRMABLE = new Set(['aberta', 'em_atendimento', 'contestada'])

function clusterIcon(cluster: L.MarkerCluster): L.DivIcon {
  const count = cluster.getChildCount()
  const size = count < 10 ? 'sm' : count < 50 ? 'md' : 'lg'
  return L.divIcon({
    className: '',
    html: `<span class="cluster cluster--${size}"><span>${count}</span></span>`,
    iconSize: size === 'sm' ? [36, 36] : size === 'md' ? [44, 44] : [54, 54],
  })
}

// Popups are built with DOM nodes (textContent), never HTML strings, so data from the
// API cannot inject markup.
function popupContent(
  item: MapItem,
  onOpenDetail?: (item: MapItem) => void,
  onConfirm?: (item: MapItem) => void,
): HTMLElement {
  const root = document.createElement('div')
  root.className = 'popup'
  const add = (tag: string, className: string, text: string) => {
    const el = document.createElement(tag)
    el.className = className
    el.textContent = text
    root.appendChild(el)
    return el
  }
  add('strong', 'popup__title', item.type_name)
  add('span', `badge badge--${item.status}`, STATUS_LABEL[item.status])
  add('span', 'popup__meta', `${item.protocol} · ${describeAge(item.created_at)}`)
  add(
    'span',
    'popup__note',
    item.location_is_exact ? 'Localização exata.' : `Localização aproximada (~${PRIVACY_GRID_METERS} m).`,
  )
  if (item.days_without_response != null) {
    const days = item.days_without_response
    add(
      'span',
      `popup__silence${item.response_overdue ? ' popup__silence--overdue' : ''}`,
      `${days} ${days === 1 ? 'dia' : 'dias'} sem resposta da prefeitura`,
    )
  }
  if (item.confirmations > 0) {
    add(
      'span',
      'popup__note',
      item.confirmations === 1
        ? '1 morador também viu'
        : `${item.confirmations} moradores também viram`,
    )
  }
  if (onConfirm && CONFIRMABLE.has(item.status)) {
    const button = add('button', 'popup__confirm', 'Eu também vi')
    button.setAttribute('type', 'button')
    button.addEventListener('click', () => onConfirm(item))
  }
  if (onOpenDetail && item.id != null) {
    const button = add('button', 'popup__link', 'Ver detalhes')
    button.setAttribute('type', 'button')
    button.addEventListener('click', () => onOpenDetail(item))
  }
  return root
}

export function ClusterLayer({ items, onOpenDetail, onConfirm }: Props) {
  const map = useMap()
  const groupRef = useRef<L.MarkerClusterGroup | null>(null)
  const markersRef = useRef(new Map<string, { marker: L.Marker; signature: string }>())
  // Callbacks are read at click time, so changing them never forces markers to be rebuilt.
  const handlersRef = useRef({ onOpenDetail, onConfirm })
  handlersRef.current = { onOpenDetail, onConfirm }

  useEffect(() => {
    const group = L.markerClusterGroup({
      showCoverageOnHover: false,
      maxClusterRadius: 50,
      spiderfyOnMaxZoom: true,
      iconCreateFunction: clusterIcon,
    })
    groupRef.current = group
    markersRef.current.clear()
    map.addLayer(group)
    return () => {
      map.removeLayer(group)
      groupRef.current = null
      markersRef.current.clear()
    }
  }, [map])

  // Incremental update: opening a popup pans the map, which refetches the items. Rebuilding
  // every marker would close the popup the person just opened, so only changed points are
  // replaced and unchanged markers (and their open popups) stay put.
  useEffect(() => {
    const group = groupRef.current
    if (!group) return
    const markers = markersRef.current
    const next = new Map(items.map((item) => [item.protocol, item]))

    const stale: L.Marker[] = []
    for (const [key, entry] of markers) {
      const item = next.get(key)
      if (!item || signature(item) !== entry.signature) {
        stale.push(entry.marker)
        markers.delete(key)
      }
    }
    group.removeLayers(stale)

    const fresh: L.Marker[] = []
    for (const item of items) {
      if (markers.has(item.protocol)) continue
      const marker = L.marker([item.latitude, item.longitude], {
        icon: statusIcon(item.status, !item.location_is_exact),
        title: `${item.type_name}: ${STATUS_LABEL[item.status]}`,
        keyboard: true,
      }).bindPopup(
        () => popupContent(item, handlersRef.current.onOpenDetail, handlersRef.current.onConfirm),
        // keep the popup clear of the filter panel (left on desktop, top on phones)
        { autoPanPaddingTopLeft: window.innerWidth >= 900 ? [400, 16] : [16, 90] },
      )
      markers.set(item.protocol, { marker, signature: signature(item) })
      fresh.push(marker)
    }
    group.addLayers(fresh)
  }, [items])

  return null
}

function signature(item: MapItem): string {
  return [
    item.status,
    item.confirmations,
    item.latitude,
    item.longitude,
    item.location_is_exact,
    item.days_without_response,
  ].join('|')
}
