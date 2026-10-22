export type UserRole = 'morador' | 'agente' | 'gestor'

export type OccurrenceStatus =
  | 'aberta'
  | 'em_atendimento'
  | 'resolvida_pelo_agente'
  | 'confirmada'
  | 'contestada'

export interface User {
  id: number
  name: string
  email: string
  role: UserRole
}

export interface OccurrenceType {
  id: number
  code: string
  name: string
  description: string
  department: string
  weight: string
  is_breeding_site: boolean
  prevention_tips: string
  /** The catch-all "Outro risco": the resident describes it in a few words. */
  is_other?: boolean
}

export interface MapItem {
  id: number | null
  protocol: string
  type_code: string
  type_name: string
  status: OccurrenceStatus
  latitude: number
  longitude: number
  location_is_exact: boolean
  created_at: string
  confirmations: number
  days_without_response?: number | null
  response_overdue?: boolean
}

export interface Photo {
  id: number
  kind: 'registro' | 'resolucao'
  width: number
  height: number
  url: string
}

export interface HistoryEntry {
  from_status: OccurrenceStatus | null
  to_status: OccurrenceStatus
  created_at: string
}

export interface OccurrenceCreated {
  id: number
  protocol: string
  status: OccurrenceStatus
  department: string
  tracking_token: string
  replayed?: boolean
}

export interface OccurrenceDetail {
  id: number
  protocol: string
  type: OccurrenceType
  status: OccurrenceStatus
  latitude: number
  longitude: number
  location_is_exact: boolean
  description: string
  /** Only for "Outro risco": what the resident said the risk is. */
  custom_type_label: string | null
  is_anonymous: boolean
  reporter: { name: string | null; contact: string | null } | null
  is_chronic: boolean
  notified_at: string | null
  first_response_at: string | null
  created_at: string
  updated_at: string
  photos: Photo[]
  history: HistoryEntry[]
  confirmations: number
  risk: Risk | null
}

export interface Tracking {
  protocol: string
  type_name: string
  department: string
  status: OccurrenceStatus
  created_at: string
  latitude: number
  longitude: number
  location_is_exact: boolean
  history: HistoryEntry[]
  is_owner: boolean
  can_answer: boolean
  confirmations: number
  deadline_days: number
  days_without_response: number | null
  response_overdue: boolean
  days_left: number | null
  responded_after_days: number | null
  can_request_ouvidoria: boolean
  description: string | null
  photos: Photo[]
}

export type LiraaClass = 'satisfatorio' | 'alerta' | 'risco'

export interface SectorCurrent {
  id: number
  code: string
  name: string
  population: number
  source: string
  active_count: number
  risk_sum: number
  risk_per_1000: number
  active_per_1000: number
}

export interface SectorComparison {
  id: number
  code: string
  name: string
  population: number
  survey_date: string | null
  iip: number | null
  ib: number | null
  liraa_class: LiraaClass | null
  occurrences: number | null
  community_index: number | null
  community_rank?: number
  liraa_rank?: number
}

export interface Feature<P> {
  type: 'Feature'
  geometry: GeoJSON.Geometry
  properties: P
}

export interface ComparisonResponse {
  type: 'FeatureCollection'
  features: Feature<SectorComparison>[]
  meta: {
    period: string | null
    periods: { period: string; survey_date: string; sectors: number }[]
    window_days: number
    paired_sectors: number
    spearman_rho: number | null
    interpretation: string
  }
}

export interface Summary {
  n: number
  mean_days: number | null
  median_days: number | null
}

export interface Indicators {
  period: { start: string; end: string }
  registered: number
  by_status: Partial<Record<OccurrenceStatus, number>>
  by_type: { code: string; name: string; count: number }[]
  time_to_first_response: Summary
  time_to_resolution: Summary
  no_response: { waiting: number; overdue: number; deadline_days: number }
  resolution: {
    closures: number
    confirmed: number
    contested: number
    confirmed_rate: number | null
    contested_rate: number | null
  }
  sectors: SectorCurrent[]
}

export type Recommendation = 'nova_visita' | 'notificar_proprietario'

export interface Risk {
  risk: number
  raw_risk: number
  capped: boolean
  type_weight: number
  days_open: number
  recurrence_count: number
  recurrence_factor: number
  proximity_factor: number
  nearest_sensitive: { name: string; kind: string; distance_m: number } | null
  confirmations: number
  recommendation: Recommendation
}

export interface QueueItem {
  id: number
  protocol: string
  type_code: string
  type_name: string
  department: string
  status: OccurrenceStatus
  latitude: number
  longitude: number
  created_at: string
  is_chronic: boolean
  risk: Risk
  distance_m: number | null
}

export interface ResolutionStats {
  closures: number
  confirmed: number
  contested: number
  awaiting: number
  confirmed_rate: number | null
  contested_rate: number | null
}

export interface RouteStop {
  position: number
  leg_m: number
  item: QueueItem
}

export interface RouteOut {
  start_latitude: number
  start_longitude: number
  stops: RouteStop[]
  total_m: number
  straight_line: boolean
}

export interface AreaAlert {
  id: number
  type_code: string
  type_name: string
  latitude: number
  longitude: number
  radius_m: number
  occurrence_count: number
  occurrence_ids: number[]
  window_start: string
  window_end: string
  created_at: string
}

export interface StaffMember {
  id: number
  name: string
  email: string
  role: UserRole
  is_active: boolean
  sector_ids: number[]
  type_ids: number[]
}

export interface SectorRef {
  id: number
  code: string
  name: string
  population: number
}

export interface TokenOut {
  access_token: string
  user: User
}

export interface Coefficient {
  key: string
  value: number
  description: string
  min: number
  max: number
  integer: boolean
}

export interface TypeSettings {
  id: number
  code: string
  name: string
  description: string
  weight: number
  department: string
  is_breeding_site: boolean
  is_other: boolean
  is_active: boolean
  notification_email: string | null
  prevention_tips: string
}

export interface SettingsView {
  coefficients: Coefficient[]
  types: TypeSettings[]
}

/** "Outro risco" descriptions grouped for the manager (candidates for a new type). */
export interface CustomLabel {
  label: string
  count: number
  active: number
  last_reported_at: string
  occurrence_ids: number[]
}

export interface TypeCreated {
  settings: SettingsView
  type_id: number
  reclassified: number
}
