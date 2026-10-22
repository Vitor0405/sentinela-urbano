import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'

import { Alert, Spinner } from '../components/common'
import { ApiError, api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { formatDateTime, formatNumber } from '../lib/labels'
import type { ComparisonResponse, LiraaClass } from '../lib/types'
import { classColor, LIRAA_COLORS, LIRAA_LABEL, NO_DATA_COLOR, quantileBreaks, SEQUENTIAL } from '../map/choropleth'
import { SectorMap } from '../map/SectorMap'

function formatDate(iso: string | null): string {
  return iso ? formatDateTime(`${iso}T12:00:00`).split(' ')[0].replace(',', '') : '—'
}

/** Gestor uploads a LIRAa CSV; the whole file is rejected if any line is wrong. */
function LiraaUpload({ onImported }: { onImported: () => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [errors, setErrors] = useState<string[]>([])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const file = input.current?.files?.[0]
    if (!file) return setErrors(['Escolha o arquivo CSV do LIRAa.'])
    setBusy(true)
    setErrors([])
    setResult(null)
    const form = new FormData()
    form.set('file', file)
    try {
      const r = await api<{ inserted: number; updated: number; lines: number }>('/liraa/import', { form })
      setResult(`${r.lines} linha(s) importada(s): ${r.inserted} nova(s), ${r.updated} atualizada(s).`)
      if (input.current) input.current.value = ''
      onImported()
    } catch (err) {
      // 422 carries the validator's line-by-line errors.
      const details = err instanceof ApiError ? err.details : []
      setErrors([(err as Error).message, ...details])
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="stack upload">
      <strong>Importar resultado do LIRAa (CSV)</strong>
      <p className="hint">
        Colunas: <span className="mono">setor;periodo;data;iip;ib</span> (ib opcional). Se alguma linha tiver erro,
        nada é gravado.
      </p>
      <div className="inline-form">
        <input ref={input} type="file" accept=".csv,text/csv" aria-label="Arquivo CSV do LIRAa" />
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {busy ? 'Importando…' : 'Importar'}
        </button>
      </div>
      {result && <Alert kind="success">{result}</Alert>}
      {errors.length > 0 && (
        <Alert>
          {errors.map((e) => (
            <div key={e}>{e}</div>
          ))}
        </Alert>
      )}
    </form>
  )
}

export function LiraaPage() {
  const { user, isStaff, ready } = useAuth()
  const [period, setPeriod] = useState<string | null>(null)
  const [data, setData] = useState<ComparisonResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    const params = period ? `?${new URLSearchParams({ period })}` : ''
    api<ComparisonResponse>(`/liraa/comparison${params}`)
      .then((d) => {
        setData(d)
        setError(null)
      })
      .catch((err: Error) => setError(err.message))
  }, [period])

  useEffect(() => {
    if (ready && isStaff) load()
  }, [ready, isStaff, load])

  const features = data?.features ?? []
  const paired = features.filter((f) => f.properties.iip != null)
  const breaks = quantileBreaks(paired.map((f) => f.properties.community_index ?? 0))
  const rho = data?.meta.spearman_rho ?? null
  const fictitious = (data?.meta.period ?? '').includes('fictício')

  if (ready && !isStaff)
    return (
      <div className="page page--narrow">
        <Alert kind="info">
          A comparação com o LIRAa é exclusiva para a equipe de saúde. <Link to="/entrar">Entrar</Link>
        </Alert>
      </div>
    )

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Sentinela × LIRAa</h1>
          <p className="lead">
            O índice gerado pelos moradores, por setor e por 1.000 habitantes, confrontado com o Levantamento Rápido
            de Índices para <i>Aedes aegypti</i> do mesmo setor.
          </p>
        </div>
        {data && data.meta.periods.length > 0 && (
          <label className="field filters">
            <span>Levantamento</span>
            <select value={data.meta.period ?? ''} onChange={(e) => setPeriod(e.target.value)}>
              {data.meta.periods.map((p) => (
                <option key={p.period} value={p.period}>
                  {p.period} ({formatDate(p.survey_date)}, {p.sectors} setores)
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {error && <Alert>{error}</Alert>}
      {!data && !error && <Spinner />}
      {fictitious && (
        <Alert kind="info">
          <strong>Dados de demonstração:</strong> setores, populações e resultados do LIRAa deste levantamento são
          fictícios e aleatórios. A concordância abaixo não tem valor epidemiológico; importe o LIRAa real da
          vigilância para a validação.
        </Alert>
      )}

      {data && data.meta.periods.length === 0 && (
        <Alert kind="info">Nenhum resultado do LIRAa importado ainda.</Alert>
      )}

      {data && paired.length > 0 && (
        <>
          <section className={`card agreement${rho != null && rho >= 0.4 ? ' agreement--good' : ''}`}>
            <div>
              <span className="agreement__label">Concordância (Spearman)</span>
              <strong className="agreement__value">{rho == null ? '—' : formatNumber(rho)}</strong>
            </div>
            <p>
              {data.meta.interpretation} Índice comunitário: soma dos pesos das ocorrências registradas nos{' '}
              {data.meta.window_days} dias antes do levantamento, por 1.000 habitantes. {data.meta.paired_sectors}{' '}
              setores com os dois índices.
            </p>
          </section>

          <div className="side-by-side">
            <section className="card">
              <h2>Índice comunitário (Sentinela)</h2>
              <SectorMap
                features={features}
                dataKey={`community-${data.meta.period}-${breaks.join(',')}`}
                color={(p) => (p.iip == null ? NO_DATA_COLOR : classColor(p.community_index, breaks))}
                tooltip={(p) =>
                  `${p.name}\n${p.community_index == null ? 'sem LIRAa no período' : `${formatNumber(p.community_index)} por 1.000 hab. (${p.occurrences} ocorrência(s))`}`
                }
              />
              <div className="legend">
                <span>menor</span>
                {SEQUENTIAL.map((c) => (
                  <i key={c} style={{ background: c }} />
                ))}
                <span>maior índice por habitante</span>
              </div>
            </section>
            <section className="card">
              <h2>LIRAa (IIP)</h2>
              <SectorMap
                features={features}
                dataKey={`liraa-${data.meta.period}`}
                color={(p) => (p.liraa_class ? LIRAA_COLORS[p.liraa_class] : NO_DATA_COLOR)}
                tooltip={(p) => `${p.name}\nIIP ${p.iip == null ? '—' : `${formatNumber(p.iip)}%`}`}
              />
              <div className="legend">
                {(Object.keys(LIRAA_COLORS) as LiraaClass[]).map((k) => (
                  <span key={k} className="legend__item">
                    <i style={{ background: LIRAA_COLORS[k] }} /> {LIRAA_LABEL[k]}
                  </span>
                ))}
              </div>
            </section>
          </div>

          <section className="card">
            <h2>Setor a setor</h2>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Setor</th>
                    <th className="num">População</th>
                    <th className="num">Índice comunitário</th>
                    <th className="num">Posição</th>
                    <th className="num">IIP (%)</th>
                    <th className="num">Posição</th>
                    <th>Classificação LIRAa</th>
                  </tr>
                </thead>
                <tbody>
                  {[...paired]
                    .sort((a, b) => (a.properties.liraa_rank ?? 0) - (b.properties.liraa_rank ?? 0))
                    .map(({ properties: p }) => {
                      const gap = Math.abs((p.community_rank ?? 0) - (p.liraa_rank ?? 0))
                      return (
                        <tr key={p.code} className={gap >= paired.length / 2 ? 'row--diverge' : ''}>
                          <td>
                            <span className="mono">{p.code}</span> {p.name}
                          </td>
                          <td className="num">{formatNumber(p.population)}</td>
                          <td className="num">{formatNumber(p.community_index ?? 0)}</td>
                          <td className="num">{p.community_rank}º</td>
                          <td className="num">{formatNumber(p.iip ?? 0)}</td>
                          <td className="num">{p.liraa_rank}º</td>
                          <td>
                            {p.liraa_class && (
                              <span className="badge" style={{ background: LIRAA_COLORS[p.liraa_class] }}>
                                {LIRAA_LABEL[p.liraa_class]}
                              </span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                </tbody>
              </table>
            </div>
            <p className="hint">
              Linhas destacadas: setores em que as duas posições divergem muito. Vale investigar se há sub-registro
              (poucos moradores usando o app) ou focos que o LIRAa não amostrou.
            </p>
          </section>
        </>
      )}

      {user?.role === 'gestor' && (
        <section className="card">
          <LiraaUpload onImported={load} />
        </section>
      )}
    </div>
  )
}
