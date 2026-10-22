export type LatLng = [number, number]

export function isValidLatLng(lat: number, lng: number): boolean {
  return (
    Number.isFinite(lat) && Number.isFinite(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180
  )
}

/** Parses "lat,lng" (as used in VITE_MAP_CENTER). Falls back when missing or invalid. */
export function parseLatLng(raw: string | undefined, fallback: LatLng): LatLng {
  if (!raw) return fallback
  const parts = raw.split(',').map((p) => Number(p.trim()))
  if (parts.length !== 2) return fallback
  const [lat, lng] = parts
  return isValidLatLng(lat, lng) ? [lat, lng] : fallback
}

export function parseZoom(raw: string | undefined, fallback: number): number {
  const zoom = Number(raw)
  return Number.isInteger(zoom) && zoom >= 1 && zoom <= 19 ? zoom : fallback
}

const coordFormat = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 5,
  maximumFractionDigits: 5,
})

export function formatCoordinate(lat: number, lng: number): string {
  return `${coordFormat.format(lat)}; ${coordFormat.format(lng)}`
}

/** GPS readings worse than this suggest the resident should adjust the pin by hand. */
export const POOR_ACCURACY_METERS = 50

export function describeAccuracy(meters: number | null | undefined): string {
  if (meters == null || !Number.isFinite(meters)) return 'Ponto escolhido no mapa.'
  const rounded = Math.round(meters)
  if (meters <= POOR_ACCURACY_METERS) return `Localização obtida pelo GPS (precisão de ~${rounded} m).`
  return `Sinal impreciso (~${rounded} m). Arraste o marcador até o local exato.`
}

/** Leaflet bounds → "min_lon,min_lat,max_lon,max_lat" for the API. */
export function bboxParam(south: number, west: number, north: number, east: number): string {
  const clamp = (v: number, min: number, max: number) => Math.min(Math.max(v, min), max)
  return [clamp(west, -180, 180), clamp(south, -90, 90), clamp(east, -180, 180), clamp(north, -90, 90)]
    .map((v) => v.toFixed(6))
    .join(',')
}
