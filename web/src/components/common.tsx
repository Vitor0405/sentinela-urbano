import { type ReactNode, useEffect, useState } from 'react'

import { fetchPhotoUrl } from '../lib/api'
import { formatDateTime, STATUS_LABEL } from '../lib/labels'
import type { HistoryEntry, OccurrenceStatus, Photo } from '../lib/types'

export function StatusBadge({ status }: { status: OccurrenceStatus }) {
  return <span className={`badge badge--${status}`}>{STATUS_LABEL[status]}</span>
}

export function Alert({ kind = 'error', children }: { kind?: 'error' | 'info' | 'success'; children: ReactNode }) {
  return (
    <div className={`alert alert--${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  )
}

export function Timeline({ history }: { history: HistoryEntry[] }) {
  return (
    <ol className="timeline">
      {history.map((entry, i) => (
        <li key={i}>
          <span className="timeline__dot" aria-hidden="true" />
          <strong>{STATUS_LABEL[entry.to_status]}</strong>
          <time dateTime={entry.created_at}>{formatDateTime(entry.created_at)}</time>
        </li>
      ))}
    </ol>
  )
}

/** Photos need credentials (login or tracking token), so they are fetched, not linked. */
export function ProtectedPhoto({ photo, trackingToken, alt }: { photo: Photo; trackingToken?: string | null; alt: string }) {
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false
    fetchPhotoUrl(photo.url, trackingToken)
      .then((url) => {
        objectUrl = url
        if (!cancelled) setSrc(url)
        else URL.revokeObjectURL(url)
      })
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [photo.url, trackingToken])

  if (failed) return <div className="photo photo--missing">Foto indisponível</div>
  return (
    <figure className="photo" style={{ aspectRatio: `${photo.width} / ${photo.height}` }}>
      {src ? <img src={src} alt={alt} /> : <span className="photo__loading">Carregando…</span>}
      <figcaption>{photo.kind === 'resolucao' ? 'Foto da resolução' : 'Foto do registro'}</figcaption>
    </figure>
  )
}

export function Spinner({ label = 'Carregando…' }: { label?: string }) {
  return (
    <p className="spinner" role="status">
      <span aria-hidden="true" />
      {label}
    </p>
  )
}
