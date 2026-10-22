import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <div className="page page--narrow">
      <h1>Página não encontrada</h1>
      <p className="lead">
        <Link to="/">Voltar ao mapa</Link>
      </p>
    </div>
  )
}
