import { bookingsApi } from './api.js'
import { escapeHtml, icon } from './icons.js'

const FIXED_AIRPORT_LABEL = 'Barcelona-El Prat Airport'
const MAX_PASSENGERS = 20

function guestEmailFromPhone(phone) {
  const digits = String(phone || '').replace(/\D/g, '')
  const core = digits.length > 0 ? digits : 'unknown'
  return `guest.${core}@taxibarcelona24.guest`
}

function pad2(n) {
  return String(n).padStart(2, '0')
}

function todayYmd() {
  const d = new Date()
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

function nowHm() {
  const d = new Date()
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}

function combineToIso(dateYmd, timeHm) {
  const [y, mo, d] = String(dateYmd).split('-').map((n) => Number.parseInt(n, 10))
  const [h, mi] = String(timeHm).split(':').map((n) => Number.parseInt(n, 10))
  if (![y, mo, d, h, mi].every(Number.isFinite)) return null
  const dt = new Date(y, mo - 1, d, h, mi, 0, 0)
  return Number.isNaN(dt.getTime()) ? null : dt.toISOString()
}

function initialState() {
  return {
    fullName: '',
    phone: '',
    bookingRef: '',
    puTime: nowHm(),
    puDate: todayYmd(),
    passengerCount: 1,
    pickupKind: 'location',
    pickupDetail: '',
    pickupAirport: FIXED_AIRPORT_LABEL,
    pickupAirline: '',
    pickupFlight: '',
    dropoffKind: 'location',
    dropoffDetail: '',
    dropoffAirport: FIXED_AIRPORT_LABEL,
    dropoffAirline: '',
    dropoffFlight: '',
    dropoffTime: nowHm(),
    notes: '',
  }
}

export function createReservationView(accessToken, container) {
  let state = initialState()
  let submitting = false
  let message = null
  let destroyed = false

  function locationBar(side, kind) {
    const title = side === 'pickup' ? 'PICK UP' : 'DROP OFF'
    return `
      <div class="admin-form-locbar">
        <span class="admin-form-locbar__title">${title}</span>
        <div class="admin-seg-group">
          <button type="button" class="admin-seg${kind === 'location' ? ' admin-seg--active' : ''}" data-action="${side}-location">Location</button>
          <button type="button" class="admin-seg${kind === 'airport' ? ' admin-seg--active' : ''}" data-action="${side}-airport">Airport</button>
        </div>
      </div>`
  }

  function pickupBody() {
    if (state.pickupKind === 'location') {
      return `<input class="admin-form-field" type="text" placeholder="Street / area (optional)" data-field="pickupDetail" value="${escapeHtml(state.pickupDetail)}" />`
    }
    return `
      <div class="admin-form-airport">
        <input class="admin-form-airport__input" type="text" placeholder="Airline (optional)" data-field="pickupAirline" value="${escapeHtml(state.pickupAirline)}" />
        <span class="admin-form-airport__divider"></span>
        <input class="admin-form-airport__input" type="text" placeholder="Flight (optional)" data-field="pickupFlight" value="${escapeHtml(state.pickupFlight)}" />
      </div>
      <input class="admin-form-field admin-form-field--dark" type="text" placeholder="Airport name" data-field="pickupAirport" value="${escapeHtml(state.pickupAirport)}" />`
  }

  function dropoffBody() {
    if (state.dropoffKind === 'location') {
      return `<input class="admin-form-field" type="text" placeholder="Street / area (optional)" data-field="dropoffDetail" value="${escapeHtml(state.dropoffDetail)}" />`
    }
    const isCityToAirport = state.pickupKind === 'location' && state.dropoffKind === 'airport'
    return `
      <div class="admin-form-airport">
        <input class="admin-form-airport__input" type="text" placeholder="Airline (optional)" data-field="dropoffAirline" value="${escapeHtml(state.dropoffAirline)}" />
        <span class="admin-form-airport__divider"></span>
        <input class="admin-form-airport__input" type="text" placeholder="Flight (optional)" data-field="dropoffFlight" value="${escapeHtml(state.dropoffFlight)}" />
        ${
          isCityToAirport
            ? ''
            : `<span class="admin-form-airport__divider"></span>
               <label class="admin-form-airport__time">
                 <span>Time</span>
                 <input type="time" data-field="dropoffTime" value="${escapeHtml(state.dropoffTime)}" />
               </label>`
        }
      </div>
      <input class="admin-form-field admin-form-field--dark" type="text" placeholder="Airport name" data-field="dropoffAirport" value="${escapeHtml(state.dropoffAirport)}" />`
  }

  function banner() {
    if (!message) return ''
    return `<div class="admin-form-banner admin-form-banner--${message.type}">${escapeHtml(message.text)}</div>`
  }

  function render() {
    if (destroyed) return
    container.innerHTML = `
      <div class="admin-form-shell">
        <header class="admin-form-shell__header">
          <h1 class="admin-form-shell__title">New Reservation</h1>
          <p class="admin-form-shell__subtitle">Create a booking on behalf of a customer.</p>
        </header>
        <div class="admin-form-shell__body">
          <form class="admin-form-card" id="reservation-form" autocomplete="off">
            <input class="admin-form-field" type="text" placeholder="Full Name" data-field="fullName" value="${escapeHtml(state.fullName)}" />
            <input class="admin-form-field" type="tel" placeholder="Phone Number" data-field="phone" value="${escapeHtml(state.phone)}" />
            <input class="admin-form-field" type="text" placeholder="Booking Reference (optional)" data-field="bookingRef" value="${escapeHtml(state.bookingRef)}" />

            <div class="admin-form-bluebar">
              <label class="admin-form-bluebar__cell">
                <span class="admin-form-bluebar__label">PU TIME</span>
                <span class="admin-form-bluebar__underline"></span>
                <input class="admin-form-bluebar__control" type="time" data-field="puTime" value="${escapeHtml(state.puTime)}" />
              </label>
              <label class="admin-form-bluebar__cell">
                <span class="admin-form-bluebar__label">PU DATE</span>
                <span class="admin-form-bluebar__underline"></span>
                <input class="admin-form-bluebar__control" type="date" data-field="puDate" value="${escapeHtml(state.puDate)}" />
              </label>
              <div class="admin-form-bluebar__cell admin-form-bluebar__cell--divided">
                <span class="admin-form-bluebar__label">PASSENGER</span>
                <span class="admin-form-bluebar__underline"></span>
                <div class="admin-form-stepper">
                  <button type="button" class="admin-form-stepper__btn" data-action="pax-dec" aria-label="Decrease passengers">${icon('minus')}</button>
                  <span class="admin-form-stepper__count js-pax-count">${state.passengerCount}</span>
                  <button type="button" class="admin-form-stepper__btn" data-action="pax-inc" aria-label="Increase passengers">${icon('plus')}</button>
                </div>
              </div>
            </div>

            ${locationBar('pickup', state.pickupKind)}
            <div id="pickup-body">${pickupBody()}</div>

            ${locationBar('dropoff', state.dropoffKind)}
            <div id="dropoff-body">${dropoffBody()}</div>

            <textarea class="admin-form-field admin-form-field--notes" placeholder="Notes" rows="2" data-field="notes">${escapeHtml(state.notes)}</textarea>

            ${banner()}

            <button type="submit" class="admin-form-done" data-action="submit-reservation" ${submitting ? 'disabled' : ''}>
              ${submitting ? 'SAVING…' : 'DONE'}
            </button>
          </form>
        </div>
      </div>`
  }

  function refreshSection(id, html) {
    const el = container.querySelector(id)
    if (el) el.innerHTML = html
  }

  async function submit() {
    if (submitting) return
    message = null
    const name = state.fullName.trim()
    const phone = state.phone.trim()
    if (!name || !phone) {
      message = { type: 'error', text: 'Please enter full name and phone number.' }
      render()
      return
    }

    const pickupLocation =
      state.pickupKind === 'airport'
        ? {
            kind: 'airport',
            label: state.pickupAirport.trim() || FIXED_AIRPORT_LABEL,
            ...(state.pickupAirline.trim() ? { airline: state.pickupAirline.trim() } : {}),
            ...(state.pickupFlight.trim() ? { flight: state.pickupFlight.trim() } : {}),
          }
        : { kind: 'location', label: state.pickupDetail.trim() || 'Address TBC' }

    const isCityToAirport = state.pickupKind === 'location' && state.dropoffKind === 'airport'
    const dropoffLocation =
      state.dropoffKind === 'airport'
        ? {
            kind: 'airport',
            label: state.dropoffAirport.trim() || FIXED_AIRPORT_LABEL,
            ...(state.dropoffAirline.trim() ? { airline: state.dropoffAirline.trim() } : {}),
            ...(state.dropoffFlight.trim() ? { flight: state.dropoffFlight.trim() } : {}),
            ...(isCityToAirport ? {} : { departureTime: state.dropoffTime }),
          }
        : { kind: 'location', label: state.dropoffDetail.trim() || 'Address TBC' }

    const scheduledTime = combineToIso(state.puDate, state.puTime)
    if (!scheduledTime) {
      message = { type: 'error', text: 'Choose a valid pick-up date and time.' }
      render()
      return
    }

    const flightNumber =
      state.pickupKind === 'airport'
        ? [state.pickupAirline.trim(), state.pickupFlight.trim()].filter(Boolean).join(' ').trim() || undefined
        : undefined

    const body = {
      pickupLocation,
      dropoffLocation,
      scheduledTime,
      price: 0,
      status: 'PENDING',
      luggageCount: 0,
      passengerCount: state.passengerCount,
      customerName: name,
      customerPhone: phone,
      customerEmail: guestEmailFromPhone(phone),
    }
    if (flightNumber) body.flightNumber = flightNumber
    const note = state.notes.trim()
    if (note) body.note = note
    const ref = state.bookingRef.trim()
    if (ref) body.bookingReference = ref

    submitting = true
    render()
    try {
      const created = await bookingsApi.create(accessToken, body)
      if (destroyed) return
      state = initialState()
      submitting = false
      const createdRef = created?.bookingReference ? ` (Ref ${created.bookingReference})` : ''
      message = { type: 'success', text: `Reservation created successfully${createdRef}.` }
      render()
    } catch (e) {
      if (destroyed) return
      submitting = false
      message = { type: 'error', text: e instanceof Error ? e.message : 'Could not create reservation.' }
      render()
    }
  }

  container.addEventListener('input', (event) => {
    const field = event.target?.dataset?.field
    if (field && field in state) {
      state[field] = event.target.value
    }
  })

  container.addEventListener('click', (event) => {
    const btn = event.target.closest('[data-action]')
    if (!btn) return
    const action = btn.dataset.action
    if (action === 'submit-reservation') {
      event.preventDefault()
      void submit()
      return
    }
    if (action === 'pax-dec') {
      state.passengerCount = Math.max(1, state.passengerCount - 1)
      const el = container.querySelector('.js-pax-count')
      if (el) el.textContent = String(state.passengerCount)
      return
    }
    if (action === 'pax-inc') {
      state.passengerCount = Math.min(MAX_PASSENGERS, state.passengerCount + 1)
      const el = container.querySelector('.js-pax-count')
      if (el) el.textContent = String(state.passengerCount)
      return
    }
    if (action === 'pickup-location' || action === 'pickup-airport') {
      state.pickupKind = action === 'pickup-airport' ? 'airport' : 'location'
      btn.parentElement.querySelectorAll('.admin-seg').forEach((s) => s.classList.remove('admin-seg--active'))
      btn.classList.add('admin-seg--active')
      refreshSection('#pickup-body', pickupBody())
      refreshSection('#dropoff-body', dropoffBody())
      return
    }
    if (action === 'dropoff-location' || action === 'dropoff-airport') {
      state.dropoffKind = action === 'dropoff-airport' ? 'airport' : 'location'
      btn.parentElement.querySelectorAll('.admin-seg').forEach((s) => s.classList.remove('admin-seg--active'))
      btn.classList.add('admin-seg--active')
      refreshSection('#dropoff-body', dropoffBody())
    }
  })

  container.addEventListener('submit', (event) => {
    if (event.target?.id === 'reservation-form') {
      event.preventDefault()
      void submit()
    }
  })

  render()

  return {
    destroy() {
      destroyed = true
      container.innerHTML = ''
    },
  }
}
