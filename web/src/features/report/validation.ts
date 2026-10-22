import { isValidLatLng } from '../../lib/geo'
import { isInsideArea, type ServiceArea } from '../../lib/serviceArea'

export const MAX_PHOTOS = 3
export const MAX_PHOTO_BYTES = 10 * 1024 * 1024
export const MAX_DESCRIPTION = 500
export const CUSTOM_LABEL_MIN = 3
export const CUSTOM_LABEL_MAX = 60

export type Identification = 'anonymous' | 'identified' | 'account'

export interface ReportDraft {
  typeId: number | null
  /** The chosen type is "Outro risco": the resident must say what it is. */
  isOther?: boolean
  customTypeLabel?: string
  photos: { size: number; type: string }[]
  location: { lat: number; lng: number } | null
  description: string
  identification: Identification
  reporterName: string
  reporterContact: string
}

export type ReportErrors = Partial<Record<'type' | 'photos' | 'location' | 'description' | 'reporter', string>>

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PHONE_RE = /^[\d\s()+-]{10,20}$/
// Same rule as the API: no phone, e-mail or link inside the risk description.
const CONTACT_RE = /(https?:|www\.|@|\d[\d .-]{6,}\d)/i

export function validateReport(draft: ReportDraft, area?: ServiceArea | null): ReportErrors {
  const errors: ReportErrors = {}

  if (draft.photos.length === 0) errors.photos = 'Adicione pelo menos uma foto do local.'
  else if (draft.photos.length > MAX_PHOTOS) errors.photos = `Envie no máximo ${MAX_PHOTOS} fotos.`
  else if (draft.photos.some((p) => p.size > MAX_PHOTO_BYTES))
    errors.photos = 'Cada foto pode ter no máximo 10 MB.'
  else if (draft.photos.some((p) => p.type && !p.type.startsWith('image/')))
    errors.photos = 'Envie apenas arquivos de imagem.'

  if (draft.typeId == null) errors.type = 'Escolha o tipo de risco.'
  else if (draft.isOther) {
    const label = (draft.customTypeLabel ?? '').trim().replace(/\s+/g, ' ')
    if (label.length < CUSTOM_LABEL_MIN) errors.type = 'Descreva o risco em poucas palavras (por exemplo, "caixa de isopor com água").'
    else if (label.length > CUSTOM_LABEL_MAX) errors.type = `Use no máximo ${CUSTOM_LABEL_MAX} caracteres para descrever o risco.`
    else if (CONTACT_RE.test(label)) errors.type = 'A descrição do risco não pode ter telefone, e-mail ou link.'
  }

  if (!draft.location) errors.location = 'Marque o local: use o GPS ou toque no mapa.'
  else if (!isValidLatLng(draft.location.lat, draft.location.lng)) errors.location = 'Localização inválida.'
  else if (area && !isInsideArea(draft.location.lat, draft.location.lng, area))
    errors.location = `O ponto está fora de ${area.name}, a área atendida pelo Sentinela Urbano.`

  if (draft.description.length > MAX_DESCRIPTION)
    errors.description = `A descrição pode ter no máximo ${MAX_DESCRIPTION} caracteres.`

  if (draft.identification === 'identified') {
    const name = draft.reporterName.trim()
    const contact = draft.reporterContact.trim()
    if (name.length < 2) errors.reporter = 'Informe seu nome ou escolha enviar anonimamente.'
    else if (!EMAIL_RE.test(contact) && !PHONE_RE.test(contact))
      errors.reporter = 'Informe um e-mail ou telefone válido para contato.'
  }

  return errors
}
