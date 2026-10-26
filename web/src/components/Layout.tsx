import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'

import { useAuth } from '../lib/auth'
import { useOutbox } from '../lib/outboxContext'
import { ROLE_LABEL } from '../lib/labels'

type IconName =
  | 'map'
  | 'plus'
  | 'search'
  | 'shield'
  | 'list'
  | 'queue'
  | 'route'
  | 'chart'
  | 'grid'
  | 'team'
  | 'user'
  | 'login'
  | 'more'

interface NavItem {
  to: string
  label: string
  icon: IconName
  end?: boolean
  title?: string
  /** Other paths that belong to this item (marks "Mais" as active on the phone bar). */
  also?: string[]
}

// Stroke icons (24x24) for the phone bar and the "Mais" sheet.
const ICON_PATHS: Record<IconName, string> = {
  map: 'M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14',
  plus: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 8v8M8 12h8',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4',
  shield: 'M12 3 5 6v5c0 4.5 3 8.3 7 10 4-1.7 7-5.5 7-10V6l-7-3zM9 12l2 2 4-4',
  list: 'M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01',
  queue: 'M4 6h16M4 12h12M4 18h8',
  route: 'M6 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM18 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM6 15V9a3 3 0 0 1 3-3h6M18 9v6a3 3 0 0 1-3 3H8',
  chart: 'M4 20h16M7 16v-5M12 16V6M17 16v-8',
  grid: 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z',
  team: 'M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3 20a6 6 0 0 1 12 0M16 5a3 3 0 0 1 0 6M18 20a6 6 0 0 0-3-5.2',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0',
  login: 'M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4M10 16l4-4-4-4M14 12H4',
  more:
    'M6 10.6a1.4 1.4 0 1 0 0 2.8 1.4 1.4 0 0 0 0-2.8zM12 10.6a1.4 1.4 0 1 0 0 2.8 1.4 1.4 0 0 0 0-2.8zM18 10.6a1.4 1.4 0 1 0 0 2.8 1.4 1.4 0 0 0 0-2.8z',
}

function NavIcon({ name }: { name: IconName }) {
  return (
    <svg className="nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={ICON_PATHS[name]} />
    </svg>
  )
}

// Always on the phone bar; everything else goes under "Mais".
const PRIMARY_PATHS = ['/', '/registrar', '/acompanhar']

function matches(item: NavItem, pathname: string): boolean {
  return [item.to, ...(item.also ?? [])].some(
    (path) => pathname === path || pathname.startsWith(`${path}/`),
  )
}

export function Layout() {
  const { user } = useAuth()
  const { pendingCount } = useOutbox()
  const { pathname } = useLocation()
  const fullBleed = pathname === '/'
  const [moreOpen, setMoreOpen] = useState(false)
  const sheetRef = useRef<HTMLDialogElement>(null)

  const items: NavItem[] = [
    { to: '/', label: 'Mapa', icon: 'map', end: true },
    { to: '/registrar', label: 'Registrar', icon: 'plus' },
    { to: '/acompanhar', label: 'Acompanhar', icon: 'search' },
    { to: '/prevencao', label: 'Prevenção', icon: 'shield' },
  ]
  if (user) {
    if (user.role === 'morador') {
      items.push({ to: '/minhas', label: 'Minhas', icon: 'list' })
    } else {
      items.push(
        { to: '/fila', label: 'Fila', icon: 'queue' },
        { to: '/rota', label: 'Rota', icon: 'route' },
        { to: '/painel', label: 'Painel', icon: 'chart' },
        { to: '/liraa', label: 'LIRAa', icon: 'grid' },
      )
      if (user.role === 'gestor') {
        items.push({ to: '/equipe', label: 'Gestão', icon: 'team', also: ['/configuracoes'] })
      }
    }
    items.push({
      to: '/conta',
      label: 'Conta',
      icon: 'user',
      title: `${user.name} (${ROLE_LABEL[user.role]})`,
    })
  } else {
    items.push({ to: '/entrar', label: 'Entrar', icon: 'login', also: ['/cadastro', '/esqueci-senha'] })
  }

  const primary = items.filter((item) => PRIMARY_PATHS.includes(item.to))
  const more = items.filter((item) => !PRIMARY_PATHS.includes(item.to))
  const moreActive = more.some((item) => matches(item, pathname))

  // Open/close the native dialog: it brings focus trap, Esc and the top layer for free.
  useEffect(() => {
    const sheet = sheetRef.current
    if (!sheet) return
    if (moreOpen && !sheet.open) sheet.showModal()
    if (!moreOpen && sheet.open) sheet.close()
  }, [moreOpen])

  // Navigating anywhere closes the sheet.
  useEffect(() => {
    setMoreOpen(false)
  }, [pathname])

  // Leaving the app (home screen, another app, the camera) closes the sheet, so it is never
  // left open as a modal on return.
  useEffect(() => {
    const onHide = () => {
      if (document.visibilityState === 'hidden') {
        sheetRef.current?.close()
        setMoreOpen(false)
      }
    }
    document.addEventListener('visibilitychange', onHide)
    return () => document.removeEventListener('visibilitychange', onHide)
  }, [])

  // The sheet only exists on phones: growing past the breakpoint closes it.
  useEffect(() => {
    const desktop = window.matchMedia('(min-width: 768px)')
    const onChange = () => {
      if (desktop.matches) setMoreOpen(false)
    }
    desktop.addEventListener('change', onChange)
    return () => desktop.removeEventListener('change', onChange)
  }, [])

  return (
    <div className={`shell${fullBleed ? ' shell--map' : ''}`}>
      <header className="topbar">
        <NavLink to="/" className="brand" aria-label="Sentinela Urbano, página inicial">
          <svg className="brand__mark" viewBox="0 0 32 32" aria-hidden="true">
            <path d="M16 2C9.4 2 4 7.2 4 13.7 4 22.5 16 30 16 30s12-7.5 12-16.3C28 7.2 22.6 2 16 2z" />
            <circle cx="16" cy="13.5" r="4.5" />
          </svg>
          <span className="brand__name">Sentinela Urbano</span>
        </NavLink>
        {pendingCount > 0 && (
          <NavLink to="/envios" className="pending-chip" title="Registros guardados aguardando conexão">
            {pendingCount} pendente{pendingCount > 1 ? 's' : ''}
          </NavLink>
        )}
        {/* Desktop and tablet: every option in the top bar. */}
        <nav className="nav" aria-label="Principal">
          {items.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} title={item.title}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="content">
        <Outlet />
      </main>

      {/* Phones: three fixed options plus "Mais". */}
      <nav className="bottomnav" aria-label="Principal">
        {primary.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end} className="bottomnav__item">
            <NavIcon name={item.icon} />
            <span>{item.label}</span>
          </NavLink>
        ))}
        <button
          type="button"
          className={`bottomnav__item${moreActive || moreOpen ? ' active' : ''}`}
          aria-haspopup="dialog"
          aria-expanded={moreOpen}
          onClick={() => setMoreOpen((open) => !open)}
        >
          <NavIcon name="more" />
          <span>Mais</span>
        </button>
      </nav>

      <dialog
        ref={sheetRef}
        className="more-sheet"
        aria-label="Mais opções"
        onClose={() => setMoreOpen(false)}
        onClick={(event) => {
          // A click on the backdrop lands on the dialog itself.
          if (event.target === event.currentTarget) setMoreOpen(false)
        }}
      >
        <div className="more-sheet__head">
          <strong>Mais opções</strong>
          {user && (
            <small>
              {user.name} · {ROLE_LABEL[user.role]}
            </small>
          )}
        </div>
        <ul className="more-sheet__list">
          {more.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                className={() => `more-sheet__link${matches(item, pathname) ? ' active' : ''}`}
                onClick={() => setMoreOpen(false)}
              >
                <NavIcon name={item.icon} />
                <span>{item.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </dialog>
    </div>
  )
}
