import L from 'leaflet'
// Plugin attaches L.heatLayer to the global Leaflet object.
import 'leaflet.heat'
import { useEffect } from 'react'
import { useMap } from 'react-leaflet'

import { type HeatPoint, normalizeHeat } from './heat'

/** Risk-weighted heat (not count). Points are already snapped to the public grid. */
export function HeatLayer({ points }: { points: HeatPoint[] }) {
  const map = useMap()
  useEffect(() => {
    const layer = L.heatLayer(normalizeHeat(points), {
      radius: 34,
      blur: 26,
      maxZoom: 16,
      max: 1,
      minOpacity: 0.35,
      gradient: { 0.2: '#2f6db3', 0.45: '#c99a06', 0.7: '#d9622b', 1: '#b3261e' },
    })
    layer.addTo(map)
    return () => {
      layer.remove()
    }
  }, [map, points])
  return null
}
