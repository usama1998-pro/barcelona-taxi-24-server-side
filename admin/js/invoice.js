import { adminInvoicesApi } from './api.js'
import { escapeHtml } from './icons.js'

const TAX_RATE = 0.1
const MAX_PASSENGERS = 25

function formatMoney(amount) {
  return new Intl.NumberFormat('en-GB', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount)
}

function splitFlight(val) {
  const v = String(val).trim()
  const m = /^([A-Za-z]{2,3})[\s-]*(\d{1,4}[A-Za-z]?)$/.exec(v)
  if (m) return { airline: m[1].toUpperCase(), flightNo: m[2] }
  return { airline: '', flightNo: v }
}

function ymdValid(t) {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(t).trim())
}

function parsePastedBlock(raw) {
  const t = String(raw).trimEnd()
  if (!/\r?\n/.test(t)) return null
  const lower = t.toLowerCase()
  const looksLikeCopyAll =
    lower.includes('booking reference:') ||
    (lower.includes('name:') && (lower.includes('phone:') || lower.includes('trip date:'))) ||
    lower.includes('child seats:')
  if (!looksLikeCopyAll) return null
  const out = {}
  for (const line of t.split(/\r?\n/)) {
    const m = /^([^:]+):\s*(.*)$/.exec(line.trim())
    if (!m) continue
    const key = m[1].trim().toLowerCase()
    const val = m[2].trim()
    if (!val) continue
    if (key === 'name') out.fullName = val
    else if (key === 'phone') out.phoneNumber = val
    else if (key === 'flight') {
      const sp = splitFlight(val)
      out.pickupFlightNo = sp.flightNo
      out.pickupAirline = sp.airline
      out.useAirportPickup = true
    } else if (key === 'booking reference') out.bookingReference = val
    else if (key === 'trip date') {
      if (ymdValid(val)) out.pickupDateYmd = val
    } else if (key === 'child seats') out.childSeatsSummary = val
    else if (key === 'passengers' || key === 'passenger') {
      const n = Number.parseInt(val, 10)
      if (Number.isFinite(n)) out.passengerCount = Math.min(MAX_PASSENGERS, Math.max(1, n))
    }
  }
  return Object.keys(out).length ? out : null
}

function parsePickupDateIso(ymd) {
  if (!ymdValid(ymd)) return null
  const [y, mo, d] = ymd.split('-').map((n) => Number.parseInt(n, 10))
  const dt = new Date(y, mo - 1, d, 12, 0, 0, 0)
  return Number.isNaN(dt.getTime()) ? null : dt.toISOString()
}

function initialState() {
  return {
    fullName: '',
    phone: '',
    bookingRef: '',
    pickupDate: '',
    pickupKind: 'LOCATION',
    pickupAddress: '',
    pickupAirline: '',
    pickupFlight: '',
    dropoffKind: 'LOCATION',
    dropoffAddress: '',
    dropoffAirline: '',
    dropoffFlight: '',
    childSeatsSummary: '',
    passengerCount: 1,
    price: '',
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function createInvoiceView(accessToken, container) {
  let state = initialState()
  let submitting = false
  let loadingPrice = false
  let message = null
  let destroyed = false

  function locationBar(side, kind) {
    const title = side === 'pickup' ? 'PICK UP' : 'DROP OFF'
    return `
      <div class="admin-form-locbar">
        <span class="admin-form-locbar__title">${title}</span>
        <div class="admin-seg-group">
          <button type="button" class="admin-seg${kind === 'LOCATION' ? ' admin-seg--active' : ''}" data-action="${side}-LOCATION">Location</button>
          <button type="button" class="admin-seg${kind === 'AIRPORT' ? ' admin-seg--active' : ''}" data-action="${side}-AIRPORT">Airport</button>
        </div>
      </div>`
  }

  function endpointBody(side) {
    const kind = side === 'pickup' ? state.pickupKind : state.dropoffKind
    const addrField = side === 'pickup' ? 'pickupAddress' : 'dropoffAddress'
    const airlineField = side === 'pickup' ? 'pickupAirline' : 'dropoffAirline'
    const flightField = side === 'pickup' ? 'pickupFlight' : 'dropoffFlight'
    const addrPlaceholder = side === 'pickup' ? 'Pick-up address' : 'Drop-off address (optional)'
    if (kind === 'LOCATION') {
      return `<input class="admin-form-field" type="text" placeholder="${addrPlaceholder}" data-field="${addrField}" value="${escapeHtml(state[addrField])}" />`
    }
    const flightPlaceholder = side === 'pickup' ? 'Flight number' : 'Flight number (optional)'
    return `
      <input class="admin-form-field" type="text" placeholder="Airline (optional)" data-field="${airlineField}" value="${escapeHtml(state[airlineField])}" />
      <input class="admin-form-field" type="text" placeholder="${flightPlaceholder}" data-field="${flightField}" value="${escapeHtml(state[flightField])}" />`
  }

  function priceNum() {
    const n = Number.parseFloat(String(state.price).replace(/,/g, ''))
    return Number.isFinite(n) && n >= 0 ? n : 0
  }

  function banner() {
    if (!message) return ''
    return `<div class="admin-form-banner admin-form-banner--${message.type}">${escapeHtml(message.text)}</div>`
  }

  function render() {
    if (destroyed) return
    const subtotal = priceNum()
    const tax = subtotal * TAX_RATE
    const total = subtotal - tax
    container.innerHTML = `
      <div class="admin-form-shell">
        <header class="admin-form-shell__header">
          <h1 class="admin-form-shell__title">Generate Invoice</h1>
          <p class="admin-form-shell__subtitle">Create and download a PDF invoice.</p>
        </header>
        <div class="admin-form-shell__body">
          <form class="admin-form-card" id="invoice-form" autocomplete="off">
            <input class="admin-form-field" type="text" placeholder="Full Name" data-field="fullName" value="${escapeHtml(state.fullName)}" />
            <input class="admin-form-field" type="tel" placeholder="Phone Number" data-field="phone" value="${escapeHtml(state.phone)}" />
            <textarea class="admin-form-field admin-form-field--ref" placeholder="Booking Reference" rows="1" data-field="bookingRef">${escapeHtml(state.bookingRef)}</textarea>
            <div class="admin-form-pricehint${loadingPrice ? '' : ' admin-form-pricehint--hidden'}">Checking booking price…</div>

            <label class="admin-form-bluebar admin-form-bluebar--single">
              <span class="admin-form-bluebar__label">PU DATE</span>
              <span class="admin-form-bluebar__underline"></span>
              <input class="admin-form-bluebar__control" type="date" data-field="pickupDate" value="${escapeHtml(state.pickupDate)}" />
            </label>

            ${locationBar('pickup', state.pickupKind)}
            <div id="inv-pickup-body">${endpointBody('pickup')}</div>

            ${locationBar('dropoff', state.dropoffKind)}
            <div id="inv-dropoff-body">${endpointBody('dropoff')}</div>

            <input class="admin-form-field" type="text" inputmode="decimal" placeholder="Price" data-field="price" value="${escapeHtml(state.price)}" />
            <div class="admin-form-readonly js-tax">${subtotal > 0 ? formatMoney(tax) : '10% tax'}</div>
            <div class="admin-form-readonly js-total">${subtotal > 0 ? formatMoney(total) : 'Remaining'}</div>

            ${banner()}

            <button type="submit" class="admin-form-done" data-action="submit-invoice" ${submitting ? 'disabled' : ''}>
              ${submitting ? 'GENERATING…' : 'DONE'}
            </button>
          </form>
        </div>
      </div>`
  }

  function refreshSection(id, html) {
    const el = container.querySelector(id)
    if (el) el.innerHTML = html
  }

  function updateTotals() {
    const subtotal = priceNum()
    const tax = subtotal * TAX_RATE
    const total = subtotal - tax
    const taxEl = container.querySelector('.js-tax')
    const totalEl = container.querySelector('.js-total')
    if (taxEl) taxEl.textContent = subtotal > 0 ? formatMoney(tax) : '10% tax'
    if (totalEl) totalEl.textContent = subtotal > 0 ? formatMoney(total) : 'Remaining'
  }

  function applyPaste(parsed) {
    if (parsed.fullName) state.fullName = parsed.fullName
    if (parsed.phoneNumber) state.phone = parsed.phoneNumber
    if (parsed.pickupDateYmd) state.pickupDate = parsed.pickupDateYmd
    if (parsed.useAirportPickup && (parsed.pickupFlightNo || parsed.pickupAirline)) {
      state.pickupKind = 'AIRPORT'
      if (parsed.pickupAirline) state.pickupAirline = parsed.pickupAirline
      if (parsed.pickupFlightNo) state.pickupFlight = parsed.pickupFlightNo
    }
    if (parsed.childSeatsSummary) state.childSeatsSummary = parsed.childSeatsSummary
    if (parsed.passengerCount) state.passengerCount = parsed.passengerCount
    state.bookingRef = parsed.bookingReference ?? ''
    message = null
    render()
  }

  async function loadSuggestedPrice() {
    const ref = state.bookingRef.trim()
    if (!ref || loadingPrice) return
    loadingPrice = true
    const hint = container.querySelector('.admin-form-pricehint')
    if (hint) hint.classList.remove('admin-form-pricehint--hidden')
    try {
      const { price } = await adminInvoicesApi.suggestedPrice(accessToken, ref)
      if (destroyed) return
      state.price = String(price)
      const priceEl = container.querySelector('[data-field="price"]')
      if (priceEl) priceEl.value = state.price
      updateTotals()
    } catch {
      /* booking may not exist; leave price as-is */
    } finally {
      loadingPrice = false
      const hintEl = container.querySelector('.admin-form-pricehint')
      if (hintEl) hintEl.classList.add('admin-form-pricehint--hidden')
    }
  }

  async function submit() {
    if (submitting) return
    message = null
    const pickupIso = parsePickupDateIso(state.pickupDate)
    if (!pickupIso) {
      message = { type: 'error', text: 'Choose a pick-up date.' }
      render()
      return
    }
    if (!state.fullName.trim() || !state.phone.trim() || !state.bookingRef.trim()) {
      message = { type: 'error', text: 'Name, phone, and booking reference are required.' }
      render()
      return
    }
    const subtotal = priceNum()
    if (subtotal <= 0) {
      message = { type: 'error', text: 'Enter a valid price greater than zero.' }
      render()
      return
    }

    const body = {
      fullName: state.fullName.trim(),
      phoneNumber: state.phone.trim(),
      bookingReference: state.bookingRef.trim(),
      pickupDate: pickupIso,
      pickupKind: state.pickupKind,
      pickupAddress: state.pickupKind === 'LOCATION' ? state.pickupAddress.trim() : undefined,
      pickupAirline: state.pickupKind === 'AIRPORT' ? state.pickupAirline.trim() : undefined,
      pickupFlightNo: state.pickupKind === 'AIRPORT' ? state.pickupFlight.trim() : undefined,
      dropoffKind: state.dropoffKind,
      dropoffAddress: state.dropoffKind === 'LOCATION' ? state.dropoffAddress.trim() : undefined,
      dropoffAirline: state.dropoffKind === 'AIRPORT' ? state.dropoffAirline.trim() : undefined,
      dropoffFlightNo: state.dropoffKind === 'AIRPORT' ? state.dropoffFlight.trim() : undefined,
      passengerCount: Math.min(MAX_PASSENGERS, Math.max(1, state.passengerCount || 1)),
      priceAmount: subtotal,
    }
    const cs = state.childSeatsSummary.trim()
    if (cs) body.childSeatsSummary = cs

    submitting = true
    render()
    try {
      const { blob, filename } = await adminInvoicesApi.generatePdf(accessToken, body)
      if (destroyed) return
      downloadBlob(blob, filename)
      submitting = false
      message = { type: 'success', text: 'Invoice generated. Your PDF download should begin shortly.' }
      render()
    } catch (e) {
      if (destroyed) return
      submitting = false
      message = { type: 'error', text: e instanceof Error ? e.message : 'Could not generate invoice.' }
      render()
    }
  }

  container.addEventListener('input', (event) => {
    const field = event.target?.dataset?.field
    if (!field) return
    if (field === 'bookingRef') {
      const parsed = parsePastedBlock(event.target.value)
      if (parsed) {
        applyPaste(parsed)
        return
      }
    }
    if (field in state) state[field] = event.target.value
    if (field === 'price') updateTotals()
  })

  container.addEventListener('change', (event) => {
    if (event.target?.dataset?.field === 'bookingRef') void loadSuggestedPrice()
  })

  container.addEventListener('click', (event) => {
    const btn = event.target.closest('[data-action]')
    if (!btn) return
    const action = btn.dataset.action
    if (action === 'submit-invoice') {
      event.preventDefault()
      void submit()
      return
    }
    if (action === 'pickup-LOCATION' || action === 'pickup-AIRPORT') {
      state.pickupKind = action === 'pickup-AIRPORT' ? 'AIRPORT' : 'LOCATION'
      btn.parentElement.querySelectorAll('.admin-seg').forEach((s) => s.classList.remove('admin-seg--active'))
      btn.classList.add('admin-seg--active')
      refreshSection('#inv-pickup-body', endpointBody('pickup'))
      return
    }
    if (action === 'dropoff-LOCATION' || action === 'dropoff-AIRPORT') {
      state.dropoffKind = action === 'dropoff-AIRPORT' ? 'AIRPORT' : 'LOCATION'
      btn.parentElement.querySelectorAll('.admin-seg').forEach((s) => s.classList.remove('admin-seg--active'))
      btn.classList.add('admin-seg--active')
      refreshSection('#inv-dropoff-body', endpointBody('dropoff'))
    }
  })

  container.addEventListener('submit', (event) => {
    if (event.target?.id === 'invoice-form') {
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
