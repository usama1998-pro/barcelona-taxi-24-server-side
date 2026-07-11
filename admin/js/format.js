import { BOOKING_TIME_ZONE, PUBLIC_SITE_DISPLAY, PUBLIC_SITE_URL } from './config.js'

function pad2(n) {
  return String(n).padStart(2, '0')
}

function formatLocationJson(value) {
  if (value == null) return '—'
  if (typeof value === 'string') return value || '—'
  if (typeof value === 'object' && !Array.isArray(value)) {
    const o = value
    const label =
      (typeof o.label === 'string' && o.label) ||
      (typeof o.address === 'string' && o.address) ||
      (typeof o.formattedAddress === 'string' && o.formattedAddress) ||
      (typeof o.name === 'string' && o.name)
    if (label) return label
  }
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function pickupLocationNameOnly(value) {
  if (value == null) return '—'
  if (typeof value === 'string') {
    const s = value.trim()
    return s || '—'
  }
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    const name =
      (typeof value.label === 'string' && value.label.trim()) ||
      (typeof value.name === 'string' && value.name.trim())
    if (name) return name
  }
  return '—'
}

export function bookingFromDisplay(b) {
  return pickupLocationNameOnly(b.pickupLocation)
}

export function bookingToDisplay(b) {
  return formatLocationJson(b.dropoffLocation)
}

function guestAppEmail(email) {
  return email.startsWith('guest.') && email.endsWith('@taxibarcelona24.guest')
}

export function isAppBooking(b) {
  const email = (b.customerEmail || b.user?.email || '').toLowerCase()
  return guestAppEmail(email)
}

export function isViatorEmailBooking(b) {
  const email = (b.customerEmail || b.user?.email || '').toLowerCase()
  if (guestAppEmail(email)) return false
  if (email.startsWith('viator.')) return true
  const note = (b.note ?? '').trim()
  if (note.startsWith('[Viator')) return true
  const ref = (b.bookingReference ?? '').trim().toUpperCase()
  return ref.startsWith('BR-')
}

export function isWebsiteBooking(b) {
  return !isViatorEmailBooking(b) && !isAppBooking(b)
}

export function bookingSourceIcon(b) {
  if (isViatorEmailBooking(b)) return 'mail'
  if (isAppBooking(b)) return 'smartphone'
  return 'globe'
}

export function bookingSourceAccessibilityLabel(b) {
  if (isViatorEmailBooking(b)) return 'Viator email booking'
  if (isAppBooking(b)) return 'App booking'
  return 'Website booking'
}

export function bookingSourceIconColor(b) {
  if (isViatorEmailBooking(b)) return '#1E88E5'
  if (isAppBooking(b)) return '#43A047'
  return '#F57C00'
}

export function bookingDetailAccentColor(b) {
  if (isAppBooking(b)) return '#43A047'
  if (isViatorEmailBooking(b)) return '#1E88E5'
  if (isWebsiteBooking(b)) return '#F57C00'
  return '#2196F3'
}

export function bookingPassengerLabel(b) {
  return (
    b.customerName?.trim() ||
    b.user?.fullName?.trim() ||
    b.customerEmail ||
    b.user?.email ||
    'Passenger'
  )
}

function bookingFlightLine(b) {
  const loc = b.pickupLocation
  if (typeof loc === 'object' && loc !== null && !Array.isArray(loc)) {
    const airline = typeof loc.airline === 'string' ? loc.airline.trim() : ''
    const flight = typeof loc.flight === 'string' ? loc.flight.trim() : ''
    if (airline || flight) return { flight: flight || '—', airline: airline || undefined }
  }
  const fn = b.flightNumber?.trim()
  if (fn) return { flight: fn }
  return null
}

export function bookingDayKeyFromIso(iso) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: BOOKING_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(iso))
}

export function formatListTime24(iso) {
  try {
    return new Intl.DateTimeFormat('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(new Date(iso))
  } catch {
    return ''
  }
}

export function reservationDisplayNumber(b) {
  const digits = b.bookingReference.replace(/\D/g, '')
  if (digits.length >= 4) return digits.length <= 6 ? digits : digits.slice(-6)
  const hex = b.uuid.replace(/-/g, '').slice(0, 10)
  const n = Number.parseInt(hex, 16)
  if (Number.isFinite(n)) return String(n % 1_000_000)
  return b.uuid.slice(0, 8).toUpperCase()
}

export function formatPickupDateLocal(iso) {
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

export function formatPickupTimeLocal24(iso) {
  const d = new Date(iso)
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}

export function formatFooterTimestamp(iso) {
  const d = new Date(iso)
  return `${pad2(d.getDate())}-${pad2(d.getMonth() + 1)}-${d.getFullYear()} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}

export function bookingArrivalAirline(b) {
  const line = bookingFlightLine(b)
  return line?.airline?.trim() ? line.airline : null
}

export function bookingArrivalFlight(b) {
  const line = bookingFlightLine(b)
  if (!line) return null
  const f = line.flight.trim()
  if (!f || f === '—') return null
  return f
}

export function publicBookingPageUrl(uuid) {
  return `${PUBLIC_SITE_URL.replace(/\/$/, '')}/booking/${uuid}`
}

export function qrCodeImageUrl(data) {
  return `https://api.qrserver.com/v1/create-qr-code/?size=90x90&data=${encodeURIComponent(data)}`
}

export { PUBLIC_SITE_DISPLAY }
