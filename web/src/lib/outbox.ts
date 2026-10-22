/**
 * Offline reports (backlog story 11).
 *
 * A report that cannot be sent (no signal) is kept on the phone, photos included, in
 * IndexedDB, and sent automatically when the connection returns. Each report carries a
 * random `client_submission_id`, so re-sending after a lost response never duplicates it:
 * the API answers with the protocol already created.
 */
import { ApiError } from './api'
import type { OccurrenceCreated } from './types'

export type OutboxStatus = 'pendente' | 'enviado' | 'falhou'

export interface OutboxPhoto {
  blob: Blob
  name: string
}

export interface OutboxItem {
  id: string // client_submission_id
  observedAt: string // ISO, when the resident registered it on the phone
  typeId: number
  typeName: string
  /** "Outro risco" only. Optional: items saved before this field existed lack it. */
  customTypeLabel?: string
  latitude: number
  longitude: number
  description: string
  isAnonymous: boolean
  reporterName: string | null
  reporterContact: string | null
  photos: OutboxPhoto[]
  status: OutboxStatus
  attempts: number
  error?: string
  result?: { protocol: string; trackingToken: string; department: string }
  sentAt?: string
}

export interface OutboxStore {
  all(): Promise<OutboxItem[]>
  put(item: OutboxItem): Promise<void>
  remove(id: string): Promise<void>
}

/** UUID v4 from getRandomValues (randomUUID needs a secure context; LAN http has none). */
export function newSubmissionId(): string {
  const b = crypto.getRandomValues(new Uint8Array(16))
  b[6] = (b[6] & 0x0f) | 0x40
  b[8] = (b[8] & 0x3f) | 0x80
  const hex = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export function buildFormData(item: OutboxItem): FormData {
  const form = new FormData()
  form.set('type_id', String(item.typeId))
  form.set('latitude', item.latitude.toFixed(7))
  form.set('longitude', item.longitude.toFixed(7))
  form.set('description', item.description.trim())
  if (item.customTypeLabel) form.set('custom_type_label', item.customTypeLabel.trim())
  form.set('is_anonymous', String(item.isAnonymous))
  if (!item.isAnonymous && item.reporterName) form.set('reporter_name', item.reporterName.trim())
  if (!item.isAnonymous && item.reporterContact) form.set('reporter_contact', item.reporterContact.trim())
  form.set('client_submission_id', item.id)
  form.set('observed_at', item.observedAt)
  for (const photo of item.photos) form.append('photos', photo.blob, photo.name || 'foto.jpg')
  return form
}

/** Worth retrying later: no connection, timeout, rate limit or server trouble. */
export function isTransient(err: unknown): boolean {
  if (!(err instanceof ApiError)) return true
  return err.status === 0 || err.status === 408 || err.status === 429 || err.status >= 500
}

export type Sender = (form: FormData) => Promise<OccurrenceCreated>

export interface SyncResult {
  sent: number
  failed: number
  pending: number
}

/** Try every pending report once. Transient errors keep it pending; others mark it failed. */
export async function syncOutbox(store: OutboxStore, send: Sender, now: () => Date = () => new Date()): Promise<SyncResult> {
  const result: SyncResult = { sent: 0, failed: 0, pending: 0 }
  const items = (await store.all()).filter((i) => i.status === 'pendente')
  for (const item of items) {
    const attempt = { ...item, attempts: item.attempts + 1 }
    try {
      const created = await send(buildFormData(item))
      await store.put({
        ...attempt,
        status: 'enviado',
        error: undefined,
        photos: [], // free the phone's storage; the photos are on the server now
        sentAt: now().toISOString(),
        result: {
          protocol: created.protocol,
          trackingToken: created.tracking_token,
          department: created.department,
        },
      })
      result.sent++
    } catch (err) {
      if (isTransient(err)) {
        await store.put({ ...attempt, error: undefined })
        result.pending++
        // No connection: the next ones would fail the same way.
        if (err instanceof ApiError && err.status === 0) {
          result.pending += items.length - items.indexOf(item) - 1
          break
        }
      } else {
        await store.put({ ...attempt, status: 'falhou', error: (err as Error).message })
        result.failed++
      }
    }
  }
  return result
}

export class MemoryStore implements OutboxStore {
  private items = new Map<string, OutboxItem>()

  async all() {
    return [...this.items.values()].sort((a, b) => a.observedAt.localeCompare(b.observedAt))
  }

  async put(item: OutboxItem) {
    this.items.set(item.id, item)
  }

  async remove(id: string) {
    this.items.delete(id)
  }
}

const DB_NAME = 'sentinela'
const STORE = 'outbox'

function request<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export class IdbStore implements OutboxStore {
  private db: Promise<IDBDatabase> | null = null

  private open(): Promise<IDBDatabase> {
    this.db ??= new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1)
      req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'id' })
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
    return this.db
  }

  private async tx(mode: IDBTransactionMode) {
    return (await this.open()).transaction(STORE, mode).objectStore(STORE)
  }

  async all() {
    const items = (await request((await this.tx('readonly')).getAll())) as OutboxItem[]
    return items.sort((a, b) => a.observedAt.localeCompare(b.observedAt))
  }

  async put(item: OutboxItem) {
    await request((await this.tx('readwrite')).put(item))
  }

  async remove(id: string) {
    await request((await this.tx('readwrite')).delete(id))
  }
}
