import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'

import { Alert, Spinner } from '../components/common'
import { api, downloadFile } from '../lib/api'
import { useAuth } from '../lib/auth'
import { formatNumber, formatPercent, STATUS_LABEL } from '../lib/labels'
import type { AreaAlert, Feature, Indicators, OccurrenceStatus, SectorCurrent } from '../lib/types'
import { formatDateTime } from '../lib/labels'
import { classColor, quantileBreaks, SEQUENTIAL } from '../map/choropleth'
import { SectorMap } from '../map/SectorMap'

function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

function days(value: number | null): string {
  return value == null ? '—' : `${formatNumber(value)} ${value === 1 ? 'dia' : 'dias'}`
}

export function PanelPage() {
  const { isStaff, ready } = useAuth()
  const [from, setFrom] = useState(isoDaysAgo(90))
  const [to, setTo] = useState(isoDaysAgo(0))
  const [data, setData] = useState<Indicators | null>(null)
  const [sectors, setSectors] = useState<Feature<SectorCurrent>[]>([])
  const [error, setError] = useState<string | null>(null)
  const [alerts, setAlerts] = useState<AreaAlert[]>([])

  const load = useCallback(() => {
    const params = new URLSearchParams({ date_from: from, date_to: to })
    api<Indicators>(`/indicators?${params}`)
      .then((d) => {
        setData(d)
        setError(null)
      })
      .catch((err: Error) => setError(err.message))
  }, [from, to])

  useEffect(() => {
    if (ready && isStaff) load()
  }, [ready, isStaff, load])

  useEffect(() => {
    if (ready && isStaff)
      api<{ features: Feature<SectorCurrent>[] }>('/sectors/current')
        .then((d) => setSectors(d.features))
        .catch(() => setSectors([]))
  }, [ready, isStaff])

  useEffect(() => {
    if (ready && isStaff) api<AreaAlert[]>('/alerts?days=30').then(setAlerts).catch(() => setAlerts([]))
  }, [ready, isStaff])

  const breaks = useMemo(() => quantileBreaks(sectors.map((f) => f.properties.risk_per_1000)), [sectors])
  const fictitious = sectors.some((f) => f.properties.source.includes('ficticio'))
  const maxType = Math.max(1, ...(data?.by_type.map((t) => t.count) ?? [1]))

  if (ready && !isStaff)
    return (
      <div className="page page--narrow">
        <Alert kind="info">
          O painel é exclusivo para agentes de saúde e gestores. <Link to="/entrar">Entrar</Link>
        </Alert>
      </div>
    )

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Painel de indicadores</h1>
          <p className="lead">Índices por setor sempre por 1.000 habitantes, nunca em números absolutos.</p>
        </div>
        <div className="filters">
          <label className="field">
            <span>De</span>
            <input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label className="field">
            <span>Até</span>
            <input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} />
          </label>
        </div>
      </div>

      {error && <Alert>{error}</Alert>}
      {!data && !error && <Spinner />}

      {data && (
        <>
          <dl className="kpi-grid">
            <div>
              <dt>Registradas no período</dt>
              <dd>{data.registered}</dd>
            </div>
            <div className={data.no_response.overdue ? 'kpi--alert' : ''}>
              <dt>Sem resposta além do prazo ({data.no_response.deadline_days} dias)</dt>
              <dd>{data.no_response.overdue}</dd>
              <small>{data.no_response.waiting} aguardando a primeira resposta</small>
            </div>
            <div>
              <dt>Tempo até a primeira resposta</dt>
              <dd>{days(data.time_to_first_response.median_days)}</dd>
              <small>mediana · média {days(data.time_to_first_response.mean_days)}</small>
            </div>
            <div>
              <dt>Tempo até a resolução</dt>
              <dd>{days(data.time_to_resolution.median_days)}</dd>
              <small>mediana · média {days(data.time_to_resolution.mean_days)}</small>
            </div>
            <div>
              <dt>Resolução confirmada</dt>
              <dd>{formatPercent(data.resolution.confirmed_rate)}</dd>
              <small>{data.resolution.closures} encerramentos no período</small>
            </div>
            <div>
              <dt>Fechamento contestado</dt>
              <dd>{formatPercent(data.resolution.contested_rate)}</dd>
              <small>{data.resolution.contested} contestações</small>
            </div>
          </dl>

          <section className={`card alerts${alerts.length ? ' alerts--active' : ''}`}>
            <h2>Alertas de acúmulo (últimos 30 dias)</h2>
            {alerts.length === 0 ? (
              <p className="hint">Nenhum acúmulo de registros do mesmo tipo numa mesma área.</p>
            ) : (
              <ul className="list">
                {alerts.map((a) => (
                  <li key={a.id} className="alert-row">
                    <span>
                      <strong>
                        {a.occurrence_count} registros de {a.type_name}
                      </strong>
                      <small>
                        num raio de {a.radius_m} m · {formatDateTime(a.window_start)} a {formatDateTime(a.window_end)}
                      </small>
                    </span>
                    <Link className="btn btn--ghost" to={`/?lat=${a.latitude}&lon=${a.longitude}&z=17`}>
                      Ver no mapa
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <div className="detail-grid">
            <section className="card">
              <h2>Por tipo de risco</h2>
              <ul className="bars">
                {data.by_type.map((t) => (
                  <li key={t.code}>
                    <span>{t.name}</span>
                    <span className="bars__track">
                      <span className="bars__fill" style={{ width: `${(t.count / maxType) * 100}%` }} />
                    </span>
                    <strong>{t.count}</strong>
                  </li>
                ))}
              </ul>
              <h2 className="spaced">Por situação</h2>
              <ul className="bars">
                {(Object.entries(data.by_status) as [OccurrenceStatus, number][]).map(([s, n]) => (
                  <li key={s}>
                    <span>{STATUS_LABEL[s]}</span>
                    <span className="bars__track">
                      <span
                        className={`bars__fill bars__fill--${s}`}
                        style={{ width: `${(n / Math.max(1, data.registered)) * 100}%` }}
                      />
                    </span>
                    <strong>{n}</strong>
                  </li>
                ))}
              </ul>
            </section>

            <section className="card">
              <h2>Risco atual por 1.000 habitantes</h2>
              {fictitious && (
                <p className="hint warn-note">Setores e populações fictícios (demonstração).</p>
              )}
              {sectors.length > 0 ? (
                <>
                  <SectorMap
                    features={sectors}
                    dataKey={`current-${sectors.length}-${breaks.join(',')}`}
                    color={(p) => classColor(p.risk_per_1000, breaks)}
                    tooltip={(p) =>
                      `${p.name}\n${formatNumber(p.risk_per_1000)} de risco por 1.000 hab.\n${p.active_count} ocorrência(s) ativa(s) · ${formatNumber(p.population)} hab.`
                    }
                  />
                  <div className="legend" aria-label="Legenda">
                    <span>menos</span>
                    {SEQUENTIAL.map((c) => (
                      <i key={c} style={{ background: c }} />
                    ))}
                    <span>mais risco por habitante</span>
                  </div>
                </>
              ) : (
                <p className="hint">Nenhum setor cadastrado. Importe com `import-sectors`.</p>
              )}
            </section>

            <section className="card detail-grid__wide">
              <div className="section-head">
                <h2>Setores</h2>
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() =>
                    downloadFile('/indicators/sectors.csv', 'indicadores-setores.csv').catch((e: Error) =>
                      setError(e.message),
                    )
                  }
                >
                  Exportar CSV
                </button>
              </div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Setor</th>
                      <th className="num">População</th>
                      <th className="num">Ativas</th>
                      <th className="num">Ativas / 1.000 hab.</th>
                      <th className="num">Risco / 1.000 hab.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.sectors.map((s) => (
                      <tr key={s.code}>
                        <td>
                          <span className="mono">{s.code}</span> {s.name}
                        </td>
                        <td className="num">{formatNumber(s.population)}</td>
                        <td className="num">{s.active_count}</td>
                        <td className="num">{formatNumber(s.active_per_1000)}</td>
                        <td className="num">
                          <strong>{formatNumber(s.risk_per_1000)}</strong>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  )
}
