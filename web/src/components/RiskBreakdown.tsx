import { formatDistance, formatNumber, RECOMMENDATION_LABEL, sensitiveKindLabel } from '../lib/labels'
import type { Risk } from '../lib/types'

/** Compact score shown in the queue. */
export function RiskScore({ risk }: { risk: Risk }) {
  return (
    <span className={`risk-score${risk.capped ? ' risk-score--capped' : ''}`} title="Índice de risco">
      <strong>{formatNumber(risk.risk)}</strong>
      <small>risco</small>
    </span>
  )
}

export function RecommendationTag({ risk }: { risk: Risk }) {
  const owner = risk.recommendation === 'notificar_proprietario'
  return <span className={`tag${owner ? ' tag--warn' : ''}`}>{RECOMMENDATION_LABEL[risk.recommendation]}</span>
}

/** Every factor of risk = peso × dias × reincidência × proximidade, so the agent sees why. */
export function RiskBreakdown({ risk }: { risk: Risk }) {
  return (
    <div className="risk-breakdown">
      <div className="risk-breakdown__total">
        <RiskScore risk={risk} />
        <RecommendationTag risk={risk} />
      </div>
      <p className="risk-formula mono">
        {formatNumber(risk.type_weight)} × {risk.days_open} {risk.days_open === 1 ? 'dia' : 'dias'} ×{' '}
        {formatNumber(risk.recurrence_factor)} × {formatNumber(risk.proximity_factor)} ={' '}
        {formatNumber(risk.raw_risk)}
      </p>
      <dl className="facts">
        <dt>Peso do tipo</dt>
        <dd>{formatNumber(risk.type_weight)}</dd>
        <dt>Dias em aberto</dt>
        <dd>{risk.days_open}</dd>
        <dt>Reincidência</dt>
        <dd>
          {risk.recurrence_count === 0
            ? 'nenhuma resolução anterior no ponto'
            : `${risk.recurrence_count} ${risk.recurrence_count === 1 ? 'resolução anterior' : 'resoluções anteriores'} a até 30 m (×${formatNumber(risk.recurrence_factor)})`}
        </dd>
        <dt>Ponto sensível</dt>
        <dd>
          {risk.nearest_sensitive
            ? `${sensitiveKindLabel(risk.nearest_sensitive.kind)}: ${risk.nearest_sensitive.name}, a ${formatDistance(risk.nearest_sensitive.distance_m)} (×${formatNumber(risk.proximity_factor)})`
            : 'nenhum a até 200 m'}
        </dd>
        <dt>“Eu também vi”</dt>
        <dd>
          {risk.confirmations === 0 ? 'nenhuma confirmação' : `${risk.confirmations} morador(es)`}
        </dd>
      </dl>
      {risk.capped && (
        <p className="hint">
          Limitado ao teto até que outro morador confirme a ocorrência (proteção contra denúncia falsa).
          Sem o teto, o risco seria {formatNumber(risk.raw_risk)}.
        </p>
      )}
      {risk.recommendation === 'notificar_proprietario' && (
        <p className="hint">
          Ponto com {risk.recurrence_count} reincidências: em vez de nova visita, notifique o proprietário.
        </p>
      )}
    </div>
  )
}
