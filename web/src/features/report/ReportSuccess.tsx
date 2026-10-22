import { useState } from 'react'
import { Link } from 'react-router'

import { Alert } from '../../components/common'
import { buildTrackingPath } from '../../lib/labels'
import type { OccurrenceCreated } from '../../lib/types'
import { PreventionTips } from './PreventionTips'

export function ReportSuccess({
  created,
  loggedIn,
  typeName = '',
  tips = '',
}: {
  created: OccurrenceCreated
  loggedIn: boolean
  typeName?: string
  tips?: string
}) {
  const [copied, setCopied] = useState(false)
  const path = buildTrackingPath(created.protocol, created.tracking_token)
  const url = `${window.location.origin}${path}`
  const canShare = typeof navigator.share === 'function'

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="page page--narrow success">
      <p className="eyebrow">Registro enviado</p>
      <h1>Obrigado por avisar.</h1>
      <p className="lead">
        Encaminhamos ao setor <strong>{created.department}</strong>. A prefeitura recebe um aviso por e-mail.
      </p>

      <div className="protocol-card">
        <span>Protocolo</span>
        <strong className="mono">{created.protocol}</strong>
      </div>

      <Alert kind="info">
        <strong>Guarde o link de acompanhamento.</strong> Com ele você vê o andamento, as fotos e, quando o
        agente concluir, pode responder se o problema foi realmente resolvido.
        {!loggedIn && ' Sem conta, este link é a única forma de fazer isso.'}
      </Alert>

      <div className="link-box">
        <input readOnly value={url} aria-label="Link de acompanhamento" onFocus={(e) => e.target.select()} />
        <button type="button" className="btn btn--primary" onClick={copy}>
          {copied ? 'Copiado' : 'Copiar'}
        </button>
        {canShare && (
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => navigator.share({ title: `Sentinela Urbano ${created.protocol}`, url }).catch(() => {})}
          >
            Compartilhar
          </button>
        )}
      </div>

      <PreventionTips typeName={typeName} tips={tips} />

      <div className="actions">
        <Link to={path} className="btn btn--ghost">
          Ver acompanhamento
        </Link>
        <Link to="/" className="btn btn--ghost">
          Voltar ao mapa
        </Link>
      </div>
    </div>
  )
}
