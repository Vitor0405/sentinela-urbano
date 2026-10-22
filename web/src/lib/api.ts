import { API_BASE } from '../config'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    /** Line-by-line problems, e.g. from a rejected CSV import. */
    readonly details: string[] = [],
  ) {
    super(message)
  }
}

let authToken: string | null = null

export function setAuthToken(token: string | null) {
  authToken = token
}

interface RequestOptions {
  method?: string
  json?: unknown
  form?: FormData
  headers?: Record<string, string>
  signal?: AbortSignal
}

/** Turns FastAPI error bodies (string or validation list) into one pt-BR sentence. */
export function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && 'message' in detail) return String(detail.message)
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { loc?: unknown[]; msg?: string }
    const field = first.loc?.[first.loc.length - 1]
    return field ? `Campo inválido (${String(field)}): ${first.msg ?? ''}`.trim() : (first.msg ?? 'Dados inválidos.')
  }
  if (status === 0) return 'Sem conexão com o servidor. Verifique sua internet.'
  if (status >= 500) return 'O servidor encontrou um erro. Tente novamente em instantes.'
  return 'Não foi possível concluir a solicitação.'
}

function buildHeaders(options: RequestOptions): Record<string, string> {
  const headers: Record<string, string> = { Accept: 'application/json', ...options.headers }
  if (options.json !== undefined) headers['Content-Type'] = 'application/json'
  if (authToken) headers.Authorization = `Bearer ${authToken}`
  return headers
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? (options.json !== undefined || options.form ? 'POST' : 'GET'),
      headers: buildHeaders(options),
      body: options.form ?? (options.json !== undefined ? JSON.stringify(options.json) : undefined),
      signal: options.signal,
    })
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err
    throw new ApiError(errorMessage(null, 0), 0)
  }
  const body = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) {
    const detail = (body as { detail?: { errors?: unknown } } | null)?.detail
    const details = Array.isArray(detail?.errors) ? detail.errors.map(String) : []
    throw new ApiError(errorMessage(body, response.status), response.status, details)
  }
  return body as T
}

/** Downloads a protected file (PDF, CSV) and hands it to the browser as a file to save. */
export async function downloadFile(
  path: string,
  filename: string,
  headers: Record<string, string> = {},
): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, { headers: buildHeaders({ headers }) })
  } catch {
    throw new ApiError(errorMessage(null, 0), 0)
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(errorMessage(body, response.status), response.status)
  }
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

/** Photos are never public: fetch with credentials and expose as an object URL. */
export async function fetchPhotoUrl(url: string, trackingToken?: string | null): Promise<string> {
  const headers = buildHeaders({ headers: trackingToken ? { 'X-Tracking-Token': trackingToken } : {} })
  const path = url.startsWith(API_BASE) ? url : url.replace(/^\/api/, API_BASE)
  const response = await fetch(path, { headers })
  if (!response.ok) throw new ApiError('Foto indisponível.', response.status)
  return URL.createObjectURL(await response.blob())
}
