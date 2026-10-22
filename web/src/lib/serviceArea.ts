import { useEffect, useState } from 'react'

import { cachedGet } from './offlineCache'

/** [min_lon, min_lat, max_lon, max_lat], same order as the API. */
export type BBox = [number, number, number, number]

export interface ServiceArea {
  name: string
  bbox: BBox | null
}

interface Meta {
  service_area: ServiceArea
}

// The API is the single source of truth for the served area (SERVICE_AREA_BBOX).
let cached: Promise<ServiceArea | null> | null = null

export function loadServiceArea(): Promise<ServiceArea | null> {
  cached ??= cachedGet<Meta>('/meta')
    .then((meta) => meta.service_area)
    .catch(() => {
      cached = null // retry on the next call
      return null
    })
  return cached
}

export function useServiceArea(): ServiceArea | null {
  const [area, setArea] = useState<ServiceArea | null>(null)
  useEffect(() => {
    let active = true
    loadServiceArea().then((value) => active && setArea(value))
    return () => {
      active = false
    }
  }, [])
  return area
}

export function isInsideArea(lat: number, lng: number, area: ServiceArea | null | undefined): boolean {
  if (!area?.bbox) return true
  const [minLon, minLat, maxLon, maxLat] = area.bbox
  return lng >= minLon && lng <= maxLon && lat >= minLat && lat <= maxLat
}
