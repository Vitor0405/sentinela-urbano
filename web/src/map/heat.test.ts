import { describe, expect, it } from 'vitest'

import { normalizeHeat } from './heat'

describe('normalizeHeat (risk-weighted heat)', () => {
  it('scales by the 95th percentile and caps at 1', () => {
    const cells = Array.from({ length: 20 }, (_, i) => [0, i, i + 1] as [number, number, number])
    cells.push([0, 99, 1000]) // one extreme cell must not wash out the rest
    const out = normalizeHeat(cells)
    const byLng = new Map(out.map(([, lng, w]) => [lng, w]))
    expect(byLng.get(99)).toBe(1)
    expect(byLng.get(19)).toBe(1) // 20 is the 95th percentile
    expect(byLng.get(9)).toBeCloseTo(0.5)
  })

  it('keeps small but real risk visible and drops empty cells', () => {
    const out = normalizeHeat([
      [0, 0, 100],
      [0, 1, 1],
      [0, 2, 0],
    ])
    expect(out).toHaveLength(2)
    expect(out[1][2]).toBe(0.3)
  })

  it('handles no data', () => {
    expect(normalizeHeat([])).toEqual([])
  })
})
