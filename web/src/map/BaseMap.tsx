import 'leaflet/dist/leaflet.css'

import L from 'leaflet'
import { type ReactNode, useEffect } from 'react'
import { MapContainer, TileLayer, useMap, ZoomControl } from 'react-leaflet'

import { MAP_CENTER, MAP_ZOOM, TILE_ATTRIBUTION, TILE_URL } from '../config'
import type { LatLng } from '../lib/geo'
import { useServiceArea } from '../lib/serviceArea'

interface Props {
  center?: LatLng
  zoom?: number
  className?: string
  children?: ReactNode
  scrollWheelZoom?: boolean
}

/**
 * Leaflet measures its container once. If the map is created while hidden or before the
 * flex layout settles (or the phone rotates), it keeps a 0×0 size: bounds collapse to a
 * point and nothing is drawn or fetched. Re-measure whenever the container resizes.
 */
function AutoResize() {
  const map = useMap()
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize({ pan: false }))
    observer.observe(map.getContainer())
    return () => observer.disconnect()
  }, [map])
  return null
}

/** Keeps the map on the served municipality (SERVICE_AREA_BBOX from the API). */
function ServiceAreaBounds() {
  const map = useMap()
  const area = useServiceArea()
  useEffect(() => {
    if (!area?.bbox) return
    const [minLon, minLat, maxLon, maxLat] = area.bbox
    const bounds = L.latLngBounds([minLat, minLon], [maxLat, maxLon])
    map.setMaxBounds(bounds.pad(0.1))
    map.options.maxBoundsViscosity = 0.8
    // Never zoom out past the point where the whole municipality fits.
    map.setMinZoom(Math.max(map.getBoundsZoom(bounds) - 1, 3))
  }, [area, map])
  return null
}

export function BaseMap({ center = MAP_CENTER, zoom = MAP_ZOOM, className, children, scrollWheelZoom = true }: Props) {
  return (
    <MapContainer center={center} zoom={zoom} className={className} scrollWheelZoom={scrollWheelZoom} zoomControl={false}>
      <AutoResize />
      <ServiceAreaBounds />
      {/* bottom-left stays clear of the filter panel, the attribution and the report button */}
      <ZoomControl position="bottomleft" />
      <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} maxZoom={19} />
      {children}
    </MapContainer>
  )
}
