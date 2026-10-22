import { parseLatLng, parseZoom } from './lib/geo'

const env = import.meta.env

export const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

/**
 * The OSM attribution is mandatory whatever tile provider is configured, so it is appended
 * when a custom attribution leaves it out.
 */
export function ensureOsmAttribution(custom: string | undefined): string {
  const value = custom?.trim()
  if (!value) return OSM_ATTRIBUTION
  return /openstreetmap/i.test(value) ? value : `${value} | ${OSM_ATTRIBUTION}`
}

// tile.openstreetmap.org is fine for development only; production must point
// VITE_TILE_URL at a paid provider or a self-hosted tile server (OSM tile usage policy).
export const TILE_URL: string = env.VITE_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
export const TILE_ATTRIBUTION = ensureOsmAttribution(env.VITE_TILE_ATTRIBUTION)
// Default: Montes Claros (MG), Praça Doutor Chaves.
export const MAP_CENTER = parseLatLng(env.VITE_MAP_CENTER, [-16.7207, -43.866])
export const MAP_ZOOM = parseZoom(env.VITE_MAP_ZOOM, 14)
export const API_BASE: string = env.VITE_API_URL || '/api'
/** Radius of the public map grid, only used in explanatory text. */
export const PRIVACY_GRID_METERS = 100
