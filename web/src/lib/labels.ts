import type { OccurrenceStatus, Recommendation, UserRole } from './types'

export const STATUS_LABEL: Record<OccurrenceStatus, string> = {
  aberta: 'Aberta',
  em_atendimento: 'Em atendimento',
  resolvida_pelo_agente: 'Resolvida pelo agente',
  confirmada: 'Resolução confirmada',
  contestada: 'Resolução contestada',
}

/** Statuses that still need action; the map shows these by default. */
export const ACTIVE_STATUSES: OccurrenceStatus[] = ['aberta', 'em_atendimento', 'contestada']
export const ALL_STATUSES = Object.keys(STATUS_LABEL) as OccurrenceStatus[]

export const ROLE_LABEL: Record<UserRole, string> = {
  morador: 'Morador',
  agente: 'Agente de saúde',
  gestor: 'Gestor',
}

const dateFormat = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

export function formatDateTime(iso: string): string {
  return dateFormat.format(new Date(iso))
}

/** Whole days since `iso` (0 on the same day). */
export function daysSince(iso: string, now: Date = new Date()): number {
  const ms = now.getTime() - new Date(iso).getTime()
  return Math.max(0, Math.floor(ms / 86_400_000))
}

export function describeAge(iso: string, now: Date = new Date()): string {
  const days = daysSince(iso, now)
  if (days === 0) return 'registrada hoje'
  if (days === 1) return 'registrada há 1 dia'
  return `registrada há ${days} dias`
}

export const RECOMMENDATION_LABEL: Record<Recommendation, string> = {
  nova_visita: 'Nova visita',
  notificar_proprietario: 'Notificar proprietário',
}

const SENSITIVE_KIND: Record<string, string> = {
  school: 'Escola',
  kindergarten: 'Creche',
  hospital: 'Hospital',
  clinic: 'Clínica / posto de saúde',
  doctors: 'Consultório',
}

export function sensitiveKindLabel(kind: string): string {
  return SENSITIVE_KIND[kind] ?? (kind.startsWith('healthcare:') ? 'Unidade de saúde' : kind)
}

const numberFormat = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 })

export function formatNumber(value: number): string {
  return numberFormat.format(value)
}

export function formatPercent(value: number | null): string {
  return value == null ? '—' : `${Math.round(value * 100)}%`
}

export function formatDistance(meters: number | null | undefined): string {
  if (meters == null) return ''
  return meters < 1000 ? `${Math.round(meters)} m` : `${formatNumber(meters / 1000)} km`
}

/** The tracking token goes in the URL fragment, which browsers never send to servers. */
export function buildTrackingPath(protocol: string, token?: string): string {
  const base = `/acompanhar/${encodeURIComponent(protocol)}`
  return token ? `${base}#t=${encodeURIComponent(token)}` : base
}

export function readTrackingToken(hash: string): string | null {
  const params = new URLSearchParams(hash.replace(/^#/, ''))
  return params.get('t')
}
