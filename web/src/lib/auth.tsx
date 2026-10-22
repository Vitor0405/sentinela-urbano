import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, ApiError, setAuthToken } from './api'
import type { User } from './types'

const STORAGE_KEY = 'sentinela.session'

interface Session {
  token: string
  user: User
}

interface AuthContextValue {
  user: User | null
  ready: boolean
  isStaff: boolean
  login: (email: string, password: string) => Promise<User>
  register: (data: RegisterData) => Promise<User>
  /** Start a session from a token the API returned (password reset, password change). */
  acceptSession: (token: string, user: User) => void
  logout: () => void
}

export interface RegisterData {
  name: string
  email: string
  password: string
  accept_terms: boolean
  terms_version: string
}

const AuthContext = createContext<AuthContextValue | null>(null)

function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as Session) : null
  } catch {
    return null
  }
}

function saveSession(session: Session | null) {
  try {
    if (session) localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Private mode or blocked storage: the session simply lasts until the tab closes.
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => {
    const stored = loadSession()
    setAuthToken(stored?.token ?? null)
    return stored
  })
  const [ready, setReady] = useState(session === null)

  const apply = useCallback((next: Session | null) => {
    setAuthToken(next?.token ?? null)
    saveSession(next)
    setSession(next)
  }, [])

  // Revalidate a stored session once (expired token, deactivated user, changed role).
  // Only a 401 ends the session: being offline or a server hiccup must not log people out.
  useEffect(() => {
    if (!session || ready) return
    api<User>('/auth/me')
      .then((user) => apply({ token: session.token, user }))
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) apply(null)
      })
      .finally(() => setReady(true))
  }, [session, ready, apply])

  const value = useMemo<AuthContextValue>(() => {
    const user = session?.user ?? null
    return {
      user,
      ready,
      isStaff: user?.role === 'agente' || user?.role === 'gestor',
      async login(email, password) {
        const result = await api<{ access_token: string; user: User }>('/auth/login', {
          json: { email, password },
        })
        apply({ token: result.access_token, user: result.user })
        return result.user
      },
      async register(data) {
        const result = await api<{ access_token: string; user: User }>('/auth/register', { json: data })
        apply({ token: result.access_token, user: result.user })
        return result.user
      },
      acceptSession(token, user) {
        apply({ token, user })
      },
      logout() {
        apply(null)
      },
    }
  }, [session, ready, apply])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
