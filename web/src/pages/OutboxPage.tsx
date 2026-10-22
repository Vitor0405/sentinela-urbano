import { Link } from 'react-router'

import { Alert } from '../components/common'
import { buildTrackingPath, formatDateTime } from '../lib/labels'
import { useOutbox } from '../lib/outboxContext'

/** Reports kept on this phone: waiting for signal, sent (with protocol) or refused. */
export function OutboxPage() {
  const { items, pendingCount, syncing, retry, remove, syncNow } = useOutbox()
  const online = typeof navigator === 'undefined' || navigator.onLine

  return (
    <div className="page page--narrow">
      <h1>Envios deste aparelho</h1>
      <p className="lead">
        Registros feitos sem internet ficam guardados aqui e são enviados sozinhos quando a conexão volta.
      </p>

      {pendingCount > 0 && (
        <Alert kind="info">
          {pendingCount === 1 ? '1 registro aguardando' : `${pendingCount} registros aguardando`} envio.{' '}
          {online ? (
            <button type="button" className="link-button" onClick={() => void syncNow()} disabled={syncing}>
              {syncing ? 'Enviando…' : 'Tentar agora'}
            </button>
          ) : (
            'Sem conexão no momento.'
          )}
        </Alert>
      )}

      {items.length === 0 && (
        <p className="hint">
          Nenhum registro guardado neste aparelho. <Link to="/registrar">Registrar um foco</Link>.
        </p>
      )}

      <ul className="list">
        {[...items].reverse().map((item) => (
          <li key={item.id} className={`outbox-item outbox-item--${item.status}`}>
            <div>
              <strong>{item.typeName}</strong>
              <small>Registrado em {formatDateTime(item.observedAt)}</small>
              {item.status === 'pendente' && (
                <small className="outbox-item__status">
                  Aguardando conexão{item.attempts > 0 ? ` · ${item.attempts} tentativa(s)` : ''}
                </small>
              )}
              {item.status === 'enviado' && item.result && (
                <small className="outbox-item__status">
                  Enviado · protocolo <span className="mono">{item.result.protocol}</span>
                </small>
              )}
              {item.status === 'falhou' && <small className="outbox-item__error">Não aceito: {item.error}</small>}
            </div>
            <div className="outbox-item__actions">
              {item.status === 'enviado' && item.result && (
                <Link className="btn btn--ghost" to={buildTrackingPath(item.result.protocol, item.result.trackingToken)}>
                  Acompanhar
                </Link>
              )}
              {item.status === 'falhou' && (
                <button type="button" className="btn btn--ghost" onClick={() => void retry(item.id)}>
                  Tentar de novo
                </button>
              )}
              {item.status !== 'pendente' && (
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => void remove(item.id)}
                  title={
                    item.status === 'enviado'
                      ? 'Remove só deste aparelho. Guarde o link de acompanhamento antes.'
                      : 'Descartar este registro'
                  }
                >
                  Remover
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
