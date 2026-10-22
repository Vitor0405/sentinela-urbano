import { Link } from 'react-router'

import { Alert } from '../../components/common'
import type { OutboxItem } from '../../lib/outbox'
import { PreventionTips } from './PreventionTips'

/** No signal: the report stays on the phone and goes out when the connection returns. */
export function OfflineQueued({ item, tips }: { item: OutboxItem; tips: string }) {
  return (
    <div className="page page--narrow success">
      <p className="eyebrow">Sem conexão</p>
      <h1>Registro guardado no aparelho.</h1>
      <p className="lead">
        Assim que a internet voltar, o registro de <strong>{item.typeName}</strong> será enviado sozinho, com as
        fotos e o local marcados agora. Você não precisa fazer nada.
      </p>
      <Alert kind="info">
        O protocolo e o link de acompanhamento aparecem em <Link to="/envios">Envios deste aparelho</Link> depois
        do envio. Não apague os dados do navegador antes disso.
      </Alert>
      <PreventionTips typeName={item.typeName} tips={tips} />
      <div className="actions">
        <Link to="/envios" className="btn btn--primary">
          Ver envios deste aparelho
        </Link>
        <Link to="/registrar" className="btn btn--ghost" reloadDocument>
          Registrar outro foco
        </Link>
      </div>
    </div>
  )
}
