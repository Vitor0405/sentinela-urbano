import { api } from './api'

const PREFIX = 'sentinela.cache.'

/**
 * GET that remembers its last answer in localStorage and falls back to it when offline,
 * so the report form (types, served area) still works without signal.
 */
export async function cachedGet<T>(path: string): Promise<T> {
  try {
    const data = await api<T>(path)
    try {
      localStorage.setItem(PREFIX + path, JSON.stringify(data))
    } catch {
      // storage full or blocked: the live answer is still fine
    }
    return data
  } catch (err) {
    try {
      const raw = localStorage.getItem(PREFIX + path)
      if (raw) return JSON.parse(raw) as T
    } catch {
      // fall through to the original error
    }
    throw err
  }
}
