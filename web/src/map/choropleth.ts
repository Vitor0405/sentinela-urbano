import type { LiraaClass } from '../lib/types'

export const NO_DATA_COLOR = '#d9d6cc'

// Sequential, light → dark: more risk per inhabitant, darker.
export const SEQUENTIAL = ['#fdf1e4', '#f9d2a8', '#f0a35e', '#d9622b', '#8a3410']

export const LIRAA_COLORS: Record<LiraaClass, string> = {
  satisfatorio: '#2e7d32',
  alerta: '#c99a06',
  risco: '#b3261e',
}

export const LIRAA_LABEL: Record<LiraaClass, string> = {
  satisfatorio: 'Satisfatório (< 1%)',
  alerta: 'Alerta (1 a 3,9%)',
  risco: 'Risco (≥ 4%)',
}

/**
 * Quantile breaks for up to `classes` classes (upper bounds, ascending).
 * Equal values collapse, so a flat distribution never shows fake contrast.
 */
export function quantileBreaks(values: number[], classes = SEQUENTIAL.length): number[] {
  const sorted = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b)
  if (sorted.length === 0) return []
  const breaks: number[] = []
  for (let i = 1; i <= classes; i++) {
    const index = Math.min(sorted.length - 1, Math.ceil((i / classes) * sorted.length) - 1)
    const value = sorted[index]
    if (breaks[breaks.length - 1] !== value) breaks.push(value)
  }
  return breaks
}

/** Color for `value` given ascending upper-bound `breaks`. */
export function classColor(value: number | null | undefined, breaks: number[]): string {
  if (value == null || breaks.length === 0) return NO_DATA_COLOR
  const index = breaks.findIndex((b) => value <= b)
  const position = index === -1 ? breaks.length - 1 : index
  // Spread the used classes over the whole palette (darkest = highest).
  const paletteIndex =
    breaks.length === 1 ? SEQUENTIAL.length - 1 : Math.round((position / (breaks.length - 1)) * (SEQUENTIAL.length - 1))
  return value === 0 ? SEQUENTIAL[0] : SEQUENTIAL[paletteIndex]
}
