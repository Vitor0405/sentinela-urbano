import { describe, expect, it } from 'vitest'

import { type ReportDraft, validateReport } from './validation'

const valid: ReportDraft = {
  typeId: 1,
  photos: [{ size: 1_000_000, type: 'image/jpeg' }],
  location: { lat: -16.7207, lng: -43.866 }, // Montes Claros, Praça Doutor Chaves
  description: '',
  identification: 'anonymous',
  reporterName: '',
  reporterContact: '',
}

describe('validateReport', () => {
  it('accepts a minimal anonymous report', () => {
    expect(validateReport(valid)).toEqual({})
  })

  it('only allows sending with photo and coordinate (backlog story 2)', () => {
    const errors = validateReport({ ...valid, photos: [], location: null })
    expect(errors.photos).toBeDefined()
    expect(errors.location).toBeDefined()
  })

  it('limits photo count, size and type', () => {
    const photo = valid.photos[0]
    expect(validateReport({ ...valid, photos: [photo, photo, photo, photo] }).photos).toMatch(/no máximo 3/)
    expect(validateReport({ ...valid, photos: [{ size: 11 * 1024 * 1024, type: 'image/jpeg' }] }).photos).toMatch(
      /10 MB/,
    )
    expect(validateReport({ ...valid, photos: [{ size: 10, type: 'application/pdf' }] }).photos).toBeDefined()
  })

  it('requires a type and a sane description', () => {
    expect(validateReport({ ...valid, typeId: null }).type).toBeDefined()
    expect(validateReport({ ...valid, description: 'x'.repeat(501) }).description).toBeDefined()
  })

  it('asks what the risk is when the resident picks "Outro risco"', () => {
    const other = { ...valid, isOther: true }
    expect(validateReport({ ...other, customTypeLabel: '' }).type).toMatch(/poucas palavras/)
    expect(validateReport({ ...other, customTypeLabel: 'x'.repeat(61) }).type).toMatch(/60/)
    expect(validateReport({ ...other, customTypeLabel: 'liga 38 99999-1234' }).type).toMatch(/telefone/)
    expect(validateReport({ ...other, customTypeLabel: ' caixa  de isopor com água ' })).toEqual({})
    // Regular types ignore the field.
    expect(validateReport({ ...valid, customTypeLabel: '' })).toEqual({})
  })

  it('requires name and a valid contact only when the visitor chooses to identify', () => {
    const identified = { ...valid, identification: 'identified' as const }
    expect(validateReport(identified).reporter).toBeDefined()
    expect(validateReport({ ...identified, reporterName: 'Ana', reporterContact: 'nada' }).reporter).toBeDefined()
    expect(validateReport({ ...identified, reporterName: 'Ana', reporterContact: 'ana@x.test' })).toEqual({})
    expect(validateReport({ ...identified, reporterName: 'Ana', reporterContact: '(62) 99999-0000' })).toEqual({})
  })
})

describe('service area (Montes Claros)', () => {
  const area = {
    name: 'Montes Claros (MG)',
    bbox: [-44.2107, -17.1458, -43.6665, -16.0845] as [number, number, number, number],
  }

  it('accepts points inside the municipality', () => {
    expect(validateReport(valid, area)).toEqual({})
  })

  it('refuses points outside, naming the served area', () => {
    const goiania = { lat: -16.6799, lng: -49.255 }
    expect(validateReport({ ...valid, location: goiania }, area).location).toContain('Montes Claros (MG)')
  })

  it('does not restrict while the area is unknown or unbounded (the API still checks)', () => {
    const saoPaulo = { lat: -23.55, lng: -46.63 }
    expect(validateReport({ ...valid, location: saoPaulo }, null)).toEqual({})
    expect(validateReport({ ...valid, location: saoPaulo }, { name: 'x', bbox: null })).toEqual({})
  })
})
