import { NavLink } from 'react-router'

/** Manager area: team and calibration live side by side. */
export function ManagementTabs() {
  return (
    <nav className="segmented management-tabs" aria-label="Gestão">
      <NavLink to="/equipe">Equipe</NavLink>
      <NavLink to="/configuracoes">Configurações</NavLink>
    </nav>
  )
}
