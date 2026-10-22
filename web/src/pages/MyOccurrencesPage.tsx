import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { Alert, Spinner, StatusBadge } from '../components/common'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { buildTrackingPath, describeAge } from '../lib/labels'
import type { MapItem } from '../lib/types'

export function MyOccurrencesPage() {
  const { user, ready } = useAuth()
  const [items, setItems] = useState<MapItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!ready || !user) return
    api<{ items: MapItem[] }>('/occurrences/mine')
      .then((d) => setItems(d.items))
      .catch((err: Error) => setError(err.message))
  }, [user, ready])

  if (ready && !user)
    return (
      <div className="page page--narrow">
        <Alert kind="info">
          <Link to="/entrar">Entre</Link> para ver as ocorrências registradas com a sua conta.
        </Alert>
      </div>
    )

  return (
    <div className="page page--narrow">
      <h1>Minhas ocorrências</h1>
      {error && <Alert>{error}</Alert>}
      {!items && !error && <Spinner />}
      {items?.length === 0 && (
        <p className="lead">
          Você ainda não registrou nenhuma ocorrência. <Link to="/registrar">Registrar agora</Link>.
        </p>
      )}
      <ul className="list">
        {items?.map((item) => (
          <li key={item.protocol}>
            <Link to={buildTrackingPath(item.protocol)} className="list-item">
              <span>
                <strong>{item.type_name}</strong>
                <small className="mono">
                  {item.protocol} · {describeAge(item.created_at)}
                </small>
                {item.status === 'resolvida_pelo_agente' && (
                  <small className="answer-needed">Responda: o problema foi realmente resolvido?</small>
                )}
              </span>
              <StatusBadge status={item.status} />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
