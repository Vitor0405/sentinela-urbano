export type HeatPoint = [number, number, number]

/**
 * Scales summed risk per cell to leaflet.heat intensities in [0, 1].
 *
 * Uses the 95th percentile as the top of the scale so a single extreme cell does not wash
 * every other cell out; a floor keeps small but real risk visible.
 */
export function normalizeHeat(points: HeatPoint[], floor = 0.3): HeatPoint[] {
  const weights = points.map((p) => p[2]).filter((w) => w > 0)
  if (weights.length === 0) return []
  const sorted = [...weights].sort((a, b) => a - b)
  const top = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))] || 1
  return points
    .filter((p) => p[2] > 0)
    .map(([lat, lng, w]) => [lat, lng, Math.min(1, Math.max(floor, w / top))])
}
