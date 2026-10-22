import { describe, expect, it } from 'vitest'

import { ApiError } from './api'
import { buildFormData, isTransient, MemoryStore, newSubmissionId, type OutboxItem, syncOutbox } from './outbox'
import type { OccurrenceCreated } from './types'

function item(id: string, overrides: Partial<OutboxItem> = {}): OutboxItem {
  return {
    id,
    observedAt: `2026-10-21T10:00:0${id.length % 10}.000Z`,
    typeId: 1,
    typeName: 'Água parada',
    latitude: -16.7207,
    longitude: -43.866,
    description: '',
    isAnonymous: true,
    reporterName: null,
    reporterContact: null,
    photos: [{ blob: new Blob(['x'], { type: 'image/jpeg' }), name: 'f.jpg' }],
    status: 'pendente',
    attempts: 0,
    ...overrides,
  }
}

const created = (protocol: string): OccurrenceCreated => ({
  id: 1,
  protocol,
  status: 'aberta',
  department: 'Endemias',
  tracking_token: `token-${protocol}`,
})

describe('submission id', () => {
  it('is a v4 UUID and unique', () => {
    const ids = new Set(Array.from({ length: 200 }, newSubmissionId))
    expect(ids.size).toBe(200)
    for (const id of ids) expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
  })
})

describe('buildFormData', () => {
  it('sends the idempotency id, the observation time and the photos', () => {
    const form = buildFormData(item('abc', { observedAt: '2026-10-21T09:30:00.000Z' }))
    expect(form.get('client_submission_id')).toBe('abc')
    expect(form.get('observed_at')).toBe('2026-10-21T09:30:00.000Z')
    expect(form.getAll('photos')).toHaveLength(1)
    expect(form.get('latitude')).toBe('-16.7207000')
  })

  it('sends the description of an "Outro risco" only when there is one', () => {
    expect(buildFormData(item('a', { customTypeLabel: ' Caixa de isopor ' })).get('custom_type_label')).toBe('Caixa de isopor')
    expect(buildFormData(item('b')).has('custom_type_label')).toBe(false)
  })

  it('never sends name or contact on anonymous reports', () => {
    const form = buildFormData(item('a', { isAnonymous: true, reporterName: 'Ana', reporterContact: 'ana@x.test' }))
    expect(form.get('is_anonymous')).toBe('true')
    expect(form.has('reporter_name')).toBe(false)
    expect(form.has('reporter_contact')).toBe(false)
  })

  it('sends trimmed identification when the visitor identifies', () => {
    const form = buildFormData(item('a', { isAnonymous: false, reporterName: ' Ana ', reporterContact: 'ana@x.test' }))
    expect(form.get('is_anonymous')).toBe('false')
    expect(form.get('reporter_name')).toBe('Ana')
  })
})

describe('isTransient', () => {
  it('retries connection, timeout, rate limit and server errors only', () => {
    expect(isTransient(new ApiError('sem rede', 0))).toBe(true)
    expect(isTransient(new ApiError('x', 503))).toBe(true)
    expect(isTransient(new ApiError('x', 429))).toBe(true)
    expect(isTransient(new ApiError('fora da área', 422))).toBe(false)
    expect(isTransient(new ApiError('x', 401))).toBe(false)
    expect(isTransient(new TypeError('fetch failed'))).toBe(true)
  })
})

describe('syncOutbox', () => {
  it('sends pending reports, keeps the protocol and frees the photos', async () => {
    const store = new MemoryStore()
    await store.put(item('a'))
    await store.put(item('b', { status: 'enviado' }))
    const sent: FormData[] = []
    const result = await syncOutbox(store, async (form) => {
      sent.push(form)
      return created('SU-2026-000123')
    })
    expect(result).toEqual({ sent: 1, failed: 0, pending: 0 })
    expect(sent).toHaveLength(1) // the already-sent one is left alone
    const [a] = (await store.all()).filter((i) => i.id === 'a')
    expect(a.status).toBe('enviado')
    expect(a.result).toEqual({ protocol: 'SU-2026-000123', trackingToken: 'token-SU-2026-000123', department: 'Endemias' })
    expect(a.photos).toEqual([])
    expect(a.attempts).toBe(1)
  })

  it('keeps everything pending and stops early when there is no connection', async () => {
    const store = new MemoryStore()
    await store.put(item('a'))
    await store.put(item('bb'))
    let calls = 0
    const result = await syncOutbox(store, async () => {
      calls++
      throw new ApiError('Sem conexão', 0)
    })
    expect(calls).toBe(1)
    expect(result).toEqual({ sent: 0, failed: 0, pending: 2 })
    expect((await store.all()).every((i) => i.status === 'pendente')).toBe(true)
  })

  it('marks reports the server refuses as failed, with the reason', async () => {
    const store = new MemoryStore()
    await store.put(item('a'))
    const result = await syncOutbox(store, async () => {
      throw new ApiError('O ponto informado está fora de Montes Claros (MG)', 422)
    })
    expect(result.failed).toBe(1)
    const [a] = await store.all()
    expect(a.status).toBe('falhou')
    expect(a.error).toContain('fora de Montes Claros')
    expect(a.photos).toHaveLength(1) // kept, so the resident can decide what to do
  })

  it('retries server errors on the next sync', async () => {
    const store = new MemoryStore()
    await store.put(item('a'))
    await syncOutbox(store, async () => {
      throw new ApiError('erro', 502)
    })
    expect((await store.all())[0]).toMatchObject({ status: 'pendente', attempts: 1 })
    await syncOutbox(store, async () => created('SU-2026-000200'))
    expect((await store.all())[0]).toMatchObject({ status: 'enviado', attempts: 2 })
  })
})
