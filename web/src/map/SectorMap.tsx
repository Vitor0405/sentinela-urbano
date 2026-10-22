import L from 'leaflet'
import { useEffect } from 'react'
import { GeoJSON, useMap } from 'react-leaflet'

import type { Feature } from '../lib/types'
import { BaseMap } from './BaseMap'

interface Props<P> {
  features: Feature<P>[]
  color: (properties: P) => string
  tooltip: (properties: P) => string
  /** Changes whenever the data changes: react-leaflet's GeoJSON does not update in place. */
  dataKey: string
  className?: string
}

function FitToFeatures({ features }: { features: Feature<unknown>[] }) {
  const map = useMap()
  useEffect(() => {
    if (features.length === 0) return
    const bounds = L.geoJSON({ type: 'FeatureCollection', features } as GeoJSON.FeatureCollection).getBounds()
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [12, 12] })
  }, [features, map])
  return null
}

/** Sector polygons coloured by a value (choropleth), with a tooltip per sector. */
export function SectorMap<P>({ features, color, tooltip, dataKey, className = 'sector-map' }: Props<P>) {
  return (
    <BaseMap className={className} scrollWheelZoom={false}>
      <FitToFeatures features={features as Feature<unknown>[]} />
      <GeoJSON
        key={dataKey}
        data={{ type: 'FeatureCollection', features } as GeoJSON.FeatureCollection}
        style={(feature) => ({
          color: '#1b2622',
          weight: 1,
          fillOpacity: 0.72,
          fillColor: color(feature?.properties as P),
        })}
        onEachFeature={(feature, layer) => {
          // textContent-safe: tooltip strings are built from our own numbers and names.
          const el = document.createElement('div')
          el.textContent = tooltip(feature.properties as P)
          el.style.whiteSpace = 'pre-line'
          layer.bindTooltip(el, { sticky: true })
        }}
      />
    </BaseMap>
  )
}
