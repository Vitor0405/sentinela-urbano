import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'

import { Alert } from '../components/common'
import {
  CUSTOM_LABEL_MAX,
  MAX_DESCRIPTION,
  MAX_PHOTOS,
  validateReport,
  type Identification,
  type ReportErrors,
} from '../features/report/validation'
import { OfflineQueued } from '../features/report/OfflineQueued'
import { ReportSuccess } from '../features/report/ReportSuccess'
import { api } from '../lib/api'
import { cachedGet } from '../lib/offlineCache'
import { buildFormData, isTransient, newSubmissionId, type OutboxItem } from '../lib/outbox'
import { useOutbox } from '../lib/outboxContext'
import { useAuth } from '../lib/auth'
import { isInsideArea, useServiceArea } from '../lib/serviceArea'
import { describeAccuracy, formatCoordinate } from '../lib/geo'
import type { OccurrenceCreated, OccurrenceType } from '../lib/types'
import { BaseMap } from '../map/BaseMap'
import { LocationPicker } from '../map/LocationPicker'

type Point = { lat: number; lng: number }
type GpsState = { kind: 'idle' } | { kind: 'locating' } | { kind: 'error'; message: string }

interface PhotoItem {
  file: File
  preview: string
}

function geolocationError(err: GeolocationPositionError): string {
  if (err.code === err.PERMISSION_DENIED)
    return 'Permissão de localização negada. Toque no mapa para marcar o local.'
  if (err.code === err.TIMEOUT) return 'O GPS demorou para responder. Tente de novo ou toque no mapa.'
  return 'Não foi possível obter a localização. Toque no mapa para marcar o local.'
}

export function ReportPage() {
  const { user } = useAuth()
  const serviceArea = useServiceArea()
  const [types, setTypes] = useState<OccurrenceType[]>([])
  const [typeId, setTypeId] = useState<number | null>(null)
  const [customLabel, setCustomLabel] = useState('')
  const [photos, setPhotos] = useState<PhotoItem[]>([])
  const [location, setLocation] = useState<Point | null>(null)
  const [focus, setFocus] = useState<Point | null>(null)
  const [accuracy, setAccuracy] = useState<number | null>(null)
  const [gps, setGps] = useState<GpsState>({ kind: 'idle' })
  const [description, setDescription] = useState('')
  const [identification, setIdentification] = useState<Identification>(user ? 'account' : 'anonymous')
  const [reporterName, setReporterName] = useState('')
  const [reporterContact, setReporterContact] = useState('')
  const [errors, setErrors] = useState<ReportErrors>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [created, setCreated] = useState<OccurrenceCreated | null>(null)
  const [queued, setQueued] = useState<OutboxItem | null>(null)
  const { enqueue } = useOutbox()
  const cameraInput = useRef<HTMLInputElement>(null)
  const galleryInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    // Cached, so the form keeps working without signal.
    cachedGet<OccurrenceType[]>('/occurrence-types')
      .then(setTypes)
      .catch((err: Error) => setSubmitError(err.message))
  }, [])

  useEffect(() => {
    setIdentification((cur) => (user ? (cur === 'anonymous' ? cur : 'account') : cur === 'account' ? 'anonymous' : cur))
  }, [user])

  // Release preview object URLs when photos are removed or the page unmounts.
  const photosRef = useRef(photos)
  photosRef.current = photos
  useEffect(() => () => photosRef.current.forEach((p) => URL.revokeObjectURL(p.preview)), [])

  const selectedType = useMemo(() => types.find((t) => t.id === typeId) ?? null, [types, typeId])
  const geolocationAvailable = typeof navigator !== 'undefined' && 'geolocation' in navigator
  const secureContext = typeof window !== 'undefined' && window.isSecureContext

  const addFiles = (list: FileList | null) => {
    if (!list) return
    const incoming = Array.from(list).slice(0, MAX_PHOTOS - photos.length)
    setPhotos((cur) => [...cur, ...incoming.map((file) => ({ file, preview: URL.createObjectURL(file) }))])
    setErrors((e) => ({ ...e, photos: undefined }))
  }

  const removePhoto = (index: number) => {
    setPhotos((cur) => {
      URL.revokeObjectURL(cur[index].preview)
      return cur.filter((_, i) => i !== index)
    })
  }

  const locate = () => {
    if (!geolocationAvailable) return
    setGps({ kind: 'locating' })
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const point = { lat: pos.coords.latitude, lng: pos.coords.longitude }
        if (serviceArea && !isInsideArea(point.lat, point.lng, serviceArea)) {
          setGps({
            kind: 'error',
            message: `Sua localização atual está fora de ${serviceArea.name}. Toque no mapa para marcar o local do foco.`,
          })
          return
        }
        setLocation(point)
        setFocus(point)
        setAccuracy(pos.coords.accuracy)
        setGps({ kind: 'idle' })
        setErrors((e) => ({ ...e, location: undefined }))
      },
      (err) => setGps({ kind: 'error', message: geolocationError(err) }),
      { enableHighAccuracy: true, timeout: 20_000, maximumAge: 30_000 },
    )
  }

  const pickOnMap = useCallback((point: Point) => {
    setLocation(point)
    setAccuracy(null)
    setErrors((e) => ({ ...e, location: undefined }))
  }, [])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitError(null)
    const isOther = !!selectedType?.is_other
    const draft = {
      typeId,
      isOther,
      customTypeLabel: customLabel,
      photos: photos.map((p) => ({ size: p.file.size, type: p.file.type })),
      location,
      description,
      identification,
      reporterName,
      reporterContact,
    }
    const found = validateReport(draft, serviceArea)
    setErrors(found)
    if (Object.keys(found).length > 0) {
      document.querySelector('[data-error="true"]')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
    setSubmitting(true)
    const item: OutboxItem = {
      id: newSubmissionId(),
      observedAt: new Date().toISOString(),
      typeId: typeId!,
      typeName: isOther ? `${selectedType?.name}: ${customLabel.trim()}` : (selectedType?.name ?? ''),
      customTypeLabel: isOther ? customLabel.trim().replace(/\s+/g, ' ') : undefined,
      latitude: location!.lat,
      longitude: location!.lng,
      description,
      isAnonymous: identification === 'anonymous',
      reporterName: identification === 'identified' ? reporterName : null,
      reporterContact: identification === 'identified' ? reporterContact : null,
      photos: photos.map((p) => ({ blob: p.file, name: p.file.name || 'foto.jpg' })),
      status: 'pendente',
      attempts: 0,
    }
    const keepOnPhone = async () => {
      await enqueue(item)
      setQueued(item)
      window.scrollTo({ top: 0 })
    }
    try {
      if (!navigator.onLine) {
        await keepOnPhone()
        return
      }
      const result = await api<OccurrenceCreated>('/occurrences', { form: buildFormData(item) })
      setCreated(result)
      window.scrollTo({ top: 0 })
    } catch (err) {
      // Lost connection mid-way: same id, so a later re-send cannot duplicate it.
      if (isTransient(err)) await keepOnPhone().catch(() => setSubmitError((err as Error).message))
      else setSubmitError((err as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const tips = selectedType?.prevention_tips ?? ''
  if (created)
    return (
      <ReportSuccess
        created={created}
        loggedIn={!!user}
        typeName={selectedType?.is_other ? `${selectedType.name}: ${customLabel.trim()}` : selectedType?.name}
        tips={tips}
      />
    )
  if (queued) return <OfflineQueued item={queued} tips={tips} />

  return (
    <div className="page page--narrow">
      <h1>Registrar foco de risco</h1>
      <p className="lead">
        Leva menos de um minuto. A prefeitura é avisada automaticamente.
        {serviceArea && <> Por enquanto, atendemos apenas {serviceArea.name}.</>}
      </p>

      <Alert kind="info">
        <strong>Fotografe a partir da via pública.</strong> Não entre em imóveis, não fotografe o interior
        de casas ou quintais e evite que pessoas apareçam na foto.
      </Alert>

      <form onSubmit={submit} noValidate className="report-form">
        <section className="step" data-error={!!errors.photos}>
          <h2>
            <span className="step__n">1</span> Foto do local
          </h2>
          <div className="photo-grid">
            {photos.map((p, i) => (
              <div key={p.preview} className="photo-thumb">
                <img src={p.preview} alt={`Foto ${i + 1} selecionada`} />
                <button type="button" onClick={() => removePhoto(i)} aria-label={`Remover foto ${i + 1}`}>
                  ×
                </button>
              </div>
            ))}
            {photos.length < MAX_PHOTOS && (
              <div className="photo-actions">
                <button type="button" className="btn btn--primary" onClick={() => cameraInput.current?.click()}>
                  Tirar foto
                </button>
                <button type="button" className="btn btn--ghost" onClick={() => galleryInput.current?.click()}>
                  Escolher da galeria
                </button>
              </div>
            )}
          </div>
          <input
            ref={cameraInput}
            type="file"
            accept="image/*"
            capture="environment"
            hidden
            aria-label="Tirar foto"
            onChange={(e) => {
              addFiles(e.target.files)
              e.target.value = ''
            }}
          />
          <input
            ref={galleryInput}
            type="file"
            accept="image/*"
            multiple
            hidden
            aria-label="Escolher fotos da galeria"
            onChange={(e) => {
              addFiles(e.target.files)
              e.target.value = ''
            }}
          />
          <p className="hint">Até {MAX_PHOTOS} fotos. A localização gravada na foto é removida no envio.</p>
          {errors.photos && <p className="field-error">{errors.photos}</p>}
        </section>

        <section className="step" data-error={!!errors.type}>
          <h2>
            <span className="step__n">2</span> Tipo de risco
          </h2>
          <div className="type-grid" role="radiogroup" aria-label="Tipo de risco">
            {types.map((t) => (
              <label key={t.id} className={`type-card${typeId === t.id ? ' type-card--on' : ''}`}>
                <input
                  type="radio"
                  name="type"
                  value={t.id}
                  checked={typeId === t.id}
                  onChange={() => {
                    setTypeId(t.id)
                    setErrors((e) => ({ ...e, type: undefined }))
                  }}
                />
                <span className="type-card__name">
                  {t.name}
                  {t.is_breeding_site && <span className="tag">criadouro</span>}
                </span>
                <span className="type-card__desc">{t.description}</span>
              </label>
            ))}
          </div>
          {selectedType?.is_other && (
            <label className="field other-type">
              <span>Qual é o risco?</span>
              <input
                value={customLabel}
                maxLength={CUSTOM_LABEL_MAX}
                onChange={(e) => {
                  setCustomLabel(e.target.value)
                  setErrors((er) => ({ ...er, type: undefined }))
                }}
                placeholder="Ex.: caixa de isopor com água"
                aria-describedby="other-type-hint"
                autoComplete="off"
                autoFocus
              />
              <small id="other-type-hint" className="hint">
                Em poucas palavras, sem nomes, telefones ou endereços. A equipe de saúde avalia e classifica. No mapa
                público aparece só "Outro risco". {customLabel.length}/{CUSTOM_LABEL_MAX}
              </small>
            </label>
          )}
          {selectedType && (
            <p className="destination">
              Será encaminhado a: <strong>{selectedType.department}</strong>
            </p>
          )}
          {errors.type && <p className="field-error">{errors.type}</p>}
        </section>

        <section className="step" data-error={!!errors.location}>
          <h2>
            <span className="step__n">3</span> Local
          </h2>
          <div className="location-actions">
            <button
              type="button"
              className="btn btn--primary"
              onClick={locate}
              disabled={!geolocationAvailable || !secureContext || gps.kind === 'locating'}
            >
              {gps.kind === 'locating' ? 'Localizando…' : 'Usar minha localização'}
            </button>
            <span className="hint">ou toque no mapa para marcar o ponto</span>
          </div>
          {!secureContext && (
            <p className="hint">A localização automática exige conexão segura (HTTPS). Marque o ponto no mapa.</p>
          )}
          {gps.kind === 'error' && <p className="field-error">{gps.message}</p>}
          <BaseMap className="picker-map">
            <LocationPicker value={location} onChange={pickOnMap} focus={focus} />
          </BaseMap>
          {location && (
            <p className="hint">
              {describeAccuracy(accuracy)} <span className="mono">{formatCoordinate(location.lat, location.lng)}</span>
            </p>
          )}
          {errors.location && <p className="field-error">{errors.location}</p>}
        </section>

        <section className="step" data-error={!!errors.description}>
          <h2>
            <span className="step__n">4</span> Descrição <small>(opcional)</small>
          </h2>
          <textarea
            value={description}
            maxLength={MAX_DESCRIPTION}
            rows={3}
            aria-label="Descrição"
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Ex.: vários pneus acumulando água na calçada, perto do ponto de ônibus."
            aria-describedby="description-hint"
          />
          <p className="hint" id="description-hint">
            Descreva o que vê. Não escreva nomes de pessoas. {description.length}/{MAX_DESCRIPTION}
          </p>
          {errors.description && <p className="field-error">{errors.description}</p>}
        </section>

        <section className="step" data-error={!!errors.reporter}>
          <h2>
            <span className="step__n">5</span> Identificação
          </h2>
          {user ? (
            <label className="check">
              <input
                type="checkbox"
                checked={identification === 'anonymous'}
                onChange={(e) => setIdentification(e.target.checked ? 'anonymous' : 'account')}
              />
              <span>
                Enviar anonimamente. A prefeitura não verá seu nome, mas você acompanha pela sua conta
                ({user.name}).
              </span>
            </label>
          ) : (
            <>
              <div className="radio-row" role="radiogroup" aria-label="Identificação">
                <label className="check">
                  <input
                    type="radio"
                    name="identification"
                    checked={identification === 'anonymous'}
                    onChange={() => setIdentification('anonymous')}
                  />
                  <span>Enviar anonimamente</span>
                </label>
                <label className="check">
                  <input
                    type="radio"
                    name="identification"
                    checked={identification === 'identified'}
                    onChange={() => setIdentification('identified')}
                  />
                  <span>Informar nome e contato</span>
                </label>
              </div>
              {identification === 'identified' && (
                <div className="field-row">
                  <label className="field">
                    <span>Nome</span>
                    <input value={reporterName} maxLength={120} onChange={(e) => setReporterName(e.target.value)} autoComplete="name" />
                  </label>
                  <label className="field">
                    <span>E-mail ou telefone</span>
                    <input
                      value={reporterContact}
                      maxLength={254}
                      onChange={(e) => setReporterContact(e.target.value)}
                      autoComplete="email"
                    />
                  </label>
                </div>
              )}
              <p className="hint">
                Você não precisa de conta: vai receber um protocolo e um link de acompanhamento.{' '}
                <Link to="/entrar">Entrar</Link> permite confirmar ocorrências de outros moradores.
              </p>
            </>
          )}
          {errors.reporter && <p className="field-error">{errors.reporter}</p>}
        </section>

        {submitError && <Alert>{submitError}</Alert>}

        <button type="submit" className="btn btn--primary btn--block btn--lg" disabled={submitting}>
          {submitting ? 'Enviando…' : 'Enviar registro'}
        </button>
      </form>
    </div>
  )
}
