import { describe, expect, it } from 'vitest'

import { ensureOsmAttribution, OSM_ATTRIBUTION } from '../config'
import { bboxParam, describeAccuracy, isValidLatLng, parseLatLng, parseZoom } from './geo'
import { buildTrackingPath, daysSince, describeAge, readTrackingToken } from './labels'

describe('map configuration from env', () => {
  it('parses VITE_MAP_CENTER and falls back on bad values', () => {
    expect(parseLatLng('-16.68, -49.25', [0, 0])).toEqual([-16.68, -49.25])
    expect(parseLatLng(undefined, [1, 2])).toEqual([1, 2])
    expect(parseLatLng('abc', [1, 2])).toEqual([1, 2])
    expect(parseLatLng('-95,10', [1, 2])).toEqual([1, 2])
    expect(parseLatLng('1,2,3', [1, 2])).toEqual([1, 2])
  })

  it('parses VITE_MAP_ZOOM within Leaflet limits', () => {
    expect(parseZoom('15', 14)).toBe(15)
    expect(parseZoom('0', 14)).toBe(14)
    expect(parseZoom('25', 14)).toBe(14)
    expect(parseZoom('12.5', 14)).toBe(14)
  })

  it('always keeps the OpenStreetMap attribution', () => {
    expect(ensureOsmAttribution(undefined)).toBe(OSM_ATTRIBUTION)
    expect(ensureOsmAttribution('  ')).toBe(OSM_ATTRIBUTION)
    expect(ensureOsmAttribution('Tiles © Provedor X')).toContain('OpenStreetMap')
    expect(ensureOsmAttribution('Tiles © X | © OpenStreetMap contributors')).toBe(
      'Tiles © X | © OpenStreetMap contributors',
    )
  })
})

describe('geo helpers', () => {
  it('validates coordinates', () => {
    expect(isValidLatLng(-16.6, -49.2)).toBe(true)
    expect(isValidLatLng(91, 0)).toBe(false)
    expect(isValidLatLng(0, -181)).toBe(false)
    expect(isValidLatLng(Number.NaN, 0)).toBe(false)
  })

  it('builds the API bbox in lon/lat order', () => {
    expect(bboxParam(-16.7, -49.3, -16.6, -49.2)).toBe('-49.300000,-16.700000,-49.200000,-16.600000')
    expect(bboxParam(-95, -200, 95, 200)).toBe('-180.000000,-90.000000,180.000000,90.000000')
  })

  it('asks for a manual adjustment when GPS is imprecise', () => {
    expect(describeAccuracy(12)).toContain('~12 m')
    expect(describeAccuracy(180)).toContain('Arraste')
    expect(describeAccuracy(null)).toContain('mapa')
  })
})

describe('tracking link', () => {
  it('puts the token in the URL fragment, never in the query string', () => {
    const path = buildTrackingPath('SU-2026-000123', 'abc_DEF-123')
    expect(path).toBe('/acompanhar/SU-2026-000123#t=abc_DEF-123')
    expect(path).not.toContain('?')
    expect(readTrackingToken('#t=abc_DEF-123')).toBe('abc_DEF-123')
    expect(readTrackingToken('')).toBeNull()
    expect(buildTrackingPath('SU-2026-000123')).toBe('/acompanhar/SU-2026-000123')
  })
})

describe('dates', () => {
  const now = new Date('2026-10-07T12:00:00Z')
  it('counts whole days', () => {
    expect(daysSince('2026-10-07T08:00:00Z', now)).toBe(0)
    expect(daysSince('2026-10-05T11:00:00Z', now)).toBe(2)
    expect(daysSince('2026-10-08T00:00:00Z', now)).toBe(0)
    expect(describeAge('2026-10-06T11:00:00Z', now)).toBe('registrada há 1 dia')
  })
})
