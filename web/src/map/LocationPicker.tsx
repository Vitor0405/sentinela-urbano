import type { LeafletEventHandlerFnMap, Marker as LeafletMarker } from 'leaflet'
import { useEffect, useMemo, useRef } from 'react'
import { Marker, useMap, useMapEvents } from 'react-leaflet'

import { pickerIcon } from './markers'

type Point = { lat: number; lng: number }

interface Props {
  value: Point | null
  onChange: (point: Point) => void
  /** When this changes (e.g. a GPS reading), the map flies there. Taps and drags don't. */
  focus?: Point | null
}

/** Tap the map or drag the pin to set the point. */
export function LocationPicker({ value, onChange, focus }: Props) {
  const map = useMap()
  const markerRef = useRef<LeafletMarker | null>(null)
  const icon = useMemo(() => pickerIcon(), [])

  useMapEvents({
    click(event) {
      onChange({ lat: event.latlng.lat, lng: event.latlng.lng })
    },
  })

  useEffect(() => {
    if (focus) map.flyTo([focus.lat, focus.lng], Math.max(map.getZoom(), 17), { duration: 0.6 })
  }, [focus, map])

  const handlers = useMemo<LeafletEventHandlerFnMap>(
    () => ({
      dragend() {
        const point = markerRef.current?.getLatLng()
        if (point) onChange({ lat: point.lat, lng: point.lng })
      },
    }),
    [onChange],
  )

  if (!value) return null
  return (
    <Marker
      position={[value.lat, value.lng]}
      draggable
      icon={icon}
      eventHandlers={handlers}
      ref={markerRef}
      title="Local da ocorrência (arraste para ajustar)"
    />
  )
}
