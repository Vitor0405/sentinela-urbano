import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

import { api } from './api'
import { cachedGet } from './offlineCache'
import { loadServiceArea } from './serviceArea'
import { IdbStore, MemoryStore, type OutboxItem, type OutboxStore, syncOutbox } from './outbox'
import type { OccurrenceCreated } from './types'

interface OutboxContextValue {
  items: OutboxItem[]
  pendingCount: number
  syncing: boolean
  enqueue: (item: OutboxItem) => Promise<void>
  retry: (id: string) => Promise<void>
  remove: (id: string) => Promise<void>
  syncNow: () => Promise<void>
}

const OutboxContext = createContext<OutboxContextValue | null>(null)

const RETRY_EVERY_MS = 60_000

function createStore(): OutboxStore {
  // Private windows or blocked storage: keep working for this session at least.
  return typeof indexedDB === 'undefined' ? new MemoryStore() : new IdbStore()
}

const send = (form: FormData) => api<OccurrenceCreated>('/occurrences', { form })

export function OutboxProvider({ children }: { children: ReactNode }) {
  const store = useMemo(createStore, [])
  const [items, setItems] = useState<OutboxItem[]>([])
  const [syncing, setSyncing] = useState(false)
  const running = useRef(false)

  const refresh = useCallback(async () => {
    try {
      setItems(await store.all())
    } catch {
      setItems([])
    }
  }, [store])

  const syncNow = useCallback(async () => {
    if (running.current || !navigator.onLine) return
    running.current = true
    setSyncing(true)
    try {
      await syncOutbox(store, send)
    } finally {
      running.current = false
      setSyncing(false)
      await refresh()
    }
  }, [store, refresh])

  const pendingCount = items.filter((i) => i.status === 'pendente').length

  useEffect(() => {
    // Warm the offline cache on every start, so the report form works later without signal
    // even if the resident never opened it while online.
    void cachedGet('/occurrence-types').catch(() => {})
    void loadServiceArea()
    void refresh().then(syncNow)
    const onOnline = () => void syncNow()
    window.addEventListener('online', onOnline)
    return () => window.removeEventListener('online', onOnline)
  }, [refresh, syncNow])

  // Some phones report "online" while the network is unusable: retry periodically too.
  useEffect(() => {
    if (pendingCount === 0) return
    const timer = window.setInterval(() => void syncNow(), RETRY_EVERY_MS)
    return () => window.clearInterval(timer)
  }, [pendingCount, syncNow])

  const value = useMemo<OutboxContextValue>(
    () => ({
      items,
      pendingCount,
      syncing,
      async enqueue(item) {
        await store.put(item)
        await refresh()
      },
      async retry(id) {
        const item = items.find((i) => i.id === id)
        if (!item) return
        await store.put({ ...item, status: 'pendente', error: undefined })
        await refresh()
        await syncNow()
      },
      async remove(id) {
        await store.remove(id)
        await refresh()
      },
      syncNow,
    }),
    [items, pendingCount, syncing, store, refresh, syncNow],
  )

  return <OutboxContext.Provider value={value}>{children}</OutboxContext.Provider>
}

export function useOutbox(): OutboxContextValue {
  const ctx = useContext(OutboxContext)
  if (!ctx) throw new Error('useOutbox must be used inside <OutboxProvider>')
  return ctx
}
