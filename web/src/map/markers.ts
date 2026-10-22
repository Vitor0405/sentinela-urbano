import L from 'leaflet'

import type { OccurrenceStatus } from '../lib/types'

// Bundlers break Leaflet's default image icon, so every marker is a CSS divIcon.
export function statusIcon(status: OccurrenceStatus, approximate: boolean): L.DivIcon {
  return L.divIcon({
    className: '',
    html: `<span class="pin pin--${status}${approximate ? ' pin--approx' : ''}" aria-hidden="true"></span>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -12],
  })
}

export function pickerIcon(): L.DivIcon {
  return L.divIcon({
    className: '',
    html: '<span class="picker-pin" aria-hidden="true"></span>',
    iconSize: [34, 44],
    iconAnchor: [17, 42],
  })
}
