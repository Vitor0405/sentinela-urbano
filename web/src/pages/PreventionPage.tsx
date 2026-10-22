import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { Alert, Spinner } from '../components/common'
import { cachedGet } from '../lib/offlineCache'
import type { OccurrenceType } from '../lib/types'

/** Fixed prevention section, in plain language (backlog story 14). Works offline. */
export function PreventionPage() {
  const [types, setTypes] = useState<OccurrenceType[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    cachedGet<OccurrenceType[]>('/occurrence-types')
      .then(setTypes)
      .catch((err: Error) => setError(err.message))
  }, [])

  return (
    <div className="page page--narrow prose">
      <p className="eyebrow">Prevenção</p>
      <h1>Como evitar os riscos no seu bairro</h1>
      <section className="card tips">
        <h2>10 minutos por semana contra a dengue</h2>
        <p>
          A maior parte dos criadouros do <i>Aedes aegypti</i> fica dentro das casas e quintais. Uma vez por semana,
          procure e elimine água parada: vasos, pneus, garrafas, calhas, caixas d'água e qualquer recipiente que
          acumule chuva. O ciclo do ovo ao mosquito adulto leva cerca de uma semana.
        </p>
      </section>
      {error && <Alert>{error}</Alert>}
      {!types && !error && <Spinner />}
      {types?.map((t) => (
        <section key={t.id}>
          <h2>{t.name}</h2>
          <p>{t.prevention_tips}</p>
        </section>
      ))}
      <p className="hint">
        Viu um foco que não consegue resolver sozinho? <Link to="/registrar">Registre aqui</Link>.
      </p>
    </div>
  )
}
