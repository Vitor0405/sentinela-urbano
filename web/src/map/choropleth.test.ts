import { describe, expect, it } from 'vitest'

import { classColor, NO_DATA_COLOR, quantileBreaks, SEQUENTIAL } from './choropleth'

describe('choropleth classes (per-capita index)', () => {
  it('builds ascending quantile breaks', () => {
    expect(quantileBreaks([5, 1, 4, 2, 3])).toEqual([1, 2, 3, 4, 5])
    expect(quantileBreaks([])).toEqual([])
  })

  it('collapses equal values so a flat map shows no fake contrast', () => {
    expect(quantileBreaks([2, 2, 2, 2])).toEqual([2])
  })

  it('colours highest values darkest and missing data grey', () => {
    const breaks = quantileBreaks([1, 2, 3, 4, 5])
    expect(classColor(5, breaks)).toBe(SEQUENTIAL[SEQUENTIAL.length - 1])
    expect(classColor(1, breaks)).toBe(SEQUENTIAL[0])
    expect(classColor(0, breaks)).toBe(SEQUENTIAL[0])
    expect(classColor(null, breaks)).toBe(NO_DATA_COLOR)
  })
})
