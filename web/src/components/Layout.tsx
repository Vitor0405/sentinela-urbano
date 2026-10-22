import { NavLink, Outlet, useLocation } from 'react-router'

import { useAuth } from '../lib/auth'
import { useOutbox } from '../lib/outboxContext'
import { ROLE_LABEL } from '../lib/labels'

export function Layout() {
  const { user } = useAuth()
  const { pendingCount } = useOutbox()
  const { pathname } = useLocation()
  const fullBleed = pathname === '/'

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
        <nav className="nav" aria-label="Principal">
          <NavLink to="/" end>
            Mapa
          </NavLink>
          <NavLink to="/registrar">Registrar</NavLink>
          <NavLink to="/acompanhar">Acompanhar</NavLink>
          <NavLink to="/prevencao">Prevenção</NavLink>
          {user ? (
            <>
              {user.role === 'morador' && <NavLink to="/minhas">Minhas</NavLink>}
              {user.role !== 'morador' && (
                <>
                  <NavLink to="/fila">Fila</NavLink>
                  <NavLink to="/rota">Rota</NavLink>
                  <NavLink to="/painel">Painel</NavLink>
                  <NavLink to="/liraa">LIRAa</NavLink>
                  {user.role === 'gestor' && <NavLink to="/equipe">Gestão</NavLink>}
                </>
              )}
              <NavLink to="/conta" title={`${user.name} (${ROLE_LABEL[user.role]})`}>
                Conta
              </NavLink>
            </>
          ) : (
            <NavLink to="/entrar">Entrar</NavLink>
          )}
        </nav>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
