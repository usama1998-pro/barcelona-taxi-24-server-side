import { routingApi } from './api.js'
import { escapeHtml } from './icons.js'

const MAX_PASSENGERS = 8
const MAX_LUGGAGE = 16
const MAX_SEAT = 4
const PLACES_DEBOUNCE_MS = 300

function emptyState() {
  return {
    from: '',
    to: '',
    passengerCount: 1,
    luggageCount: 1,
    infantCarrierCount: 0,
    childSeatCount: 0,
    boosterCount: 0,
  }
}

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

function formatEur(value) {
  if (value == null || !Number.isFinite(Number(value))) return '—'
  return `€${Math.round(Number(value))}`
}

export function createCalculateView(_accessToken, container) {
  let state = emptyState()
  let calculating = false
  let message = null
  let quote = null
  let destroyed = false

  const places = {
    from: { timer: null, suggestions: [], loading: false, open: false, suppress: false },
    to: { timer: null, suggestions: [], loading: false, open: false, suppress: false },
  }

  function bannerHtml() {
    if (!message) return ''
    return `<div class="admin-form-banner admin-form-banner--${message.type}" id="calc-banner">${escapeHtml(message.text)}</div>`
  }

  function stepper(field, label, value, min, max) {
    return `
      <div class="admin-calc-stepper">
        <span class="admin-calc-stepper__label">${escapeHtml(label)}</span>
        <div class="admin-calc-stepper__controls">
          <button type="button" class="admin-calc-stepper__btn" data-step="${field}" data-delta="-1" ${value <= min || calculating ? 'disabled' : ''} aria-label="Decrease ${escapeHtml(label)}">−</button>
          <span class="admin-calc-stepper__value" data-step-value="${field}">${value}</span>
          <button type="button" class="admin-calc-stepper__btn" data-step="${field}" data-delta="1" ${value >= max || calculating ? 'disabled' : ''} aria-label="Increase ${escapeHtml(label)}">+</button>
        </div>
      </div>`
  }

  function suggestionsListHtml(side) {
    const meta = places[side]
    if (!meta.open || (!meta.loading && meta.suggestions.length === 0)) return ''
    const listItems =
      meta.loading && meta.suggestions.length === 0
        ? `<li class="admin-calc-places__status">Searching…</li>`
        : meta.suggestions
            .map(
              (s) => `
          <li>
            <button type="button" class="admin-calc-places__option" data-place-side="${side}">
              ${escapeHtml(s.description)}
            </button>
          </li>`,
            )
            .join('')
    return `<ul class="admin-calc-places__list" role="listbox" data-places-list="${side}">${listItems}</ul>`
  }

  function placeField(side, label, placeholder) {
    return `
      <label class="admin-prices-field admin-calc-place">
        <span class="admin-prices-field__label">${escapeHtml(label)}</span>
        <div class="admin-calc-places" data-place-wrap="${side}">
          <input
            class="admin-form-field"
            type="text"
            autocomplete="off"
            placeholder="${escapeHtml(placeholder)}"
            data-place-input="${side}"
            value="${escapeHtml(state[side])}"
            ${calculating ? 'disabled' : ''}
          />
          <div data-places-dropdown="${side}">${suggestionsListHtml(side)}</div>
        </div>
      </label>`
  }

  function resultsHtml() {
    if (!quote) return '<div id="calc-results"></div>'
    return `
      <section class="admin-calc-results" id="calc-results">
        <header class="admin-prices-section__head">
          <h2 class="admin-prices-section__title">Result</h2>
          <p class="admin-prices-section__subtitle">Same engine as customer booking quotes.</p>
        </header>
        <div class="admin-calc-results__grid">
          <div class="admin-calc-stat">
            <span class="admin-calc-stat__label">Distance</span>
            <span class="admin-calc-stat__value">${escapeHtml(String(quote.distanceKm))} km</span>
          </div>
          <div class="admin-calc-stat">
            <span class="admin-calc-stat__label">Duration</span>
            <span class="admin-calc-stat__value">${escapeHtml(String(quote.durationMinutes))} min</span>
          </div>
          <div class="admin-calc-stat">
            <span class="admin-calc-stat__label">Base (pax/luggage)</span>
            <span class="admin-calc-stat__value">${formatEur(quote.baseFareEur)}</span>
          </div>
          <div class="admin-calc-stat">
            <span class="admin-calc-stat__label">Distance surcharge</span>
            <span class="admin-calc-stat__value">${formatEur(quote.distanceSurchargeEur)}</span>
          </div>
          <div class="admin-calc-stat admin-calc-stat--emphasis">
            <span class="admin-calc-stat__label">One-way price</span>
            <span class="admin-calc-stat__value">${formatEur(quote.oneWayPriceEur ?? quote.estimatedPriceEur)}</span>
          </div>
          <div class="admin-calc-stat admin-calc-stat--emphasis">
            <span class="admin-calc-stat__label">Return price</span>
            <span class="admin-calc-stat__value">${formatEur(
              quote.returnPriceEur ??
                (quote.oneWayPriceEur != null ? Number(quote.oneWayPriceEur) * 2 : null),
            )}</span>
          </div>
        </div>
      </section>`
  }

  /** Update only the suggestions dropdown so address inputs keep focus. */
  function patchPlacesDropdown(side) {
    const slot = container.querySelector(`[data-places-dropdown="${side}"]`)
    if (!slot) return
    slot.innerHTML = suggestionsListHtml(side)
    slot.querySelectorAll('[data-place-side]').forEach((btn) => {
      btn.addEventListener('mousedown', (event) => event.preventDefault())
      btn.addEventListener('click', () => selectPlace(side, (btn.textContent || '').trim()))
    })
  }

  function patchBanner() {
    const body = container.querySelector('.admin-form-shell__body')
    if (!body) return
    const existing = document.getElementById('calc-banner')
    if (existing) existing.remove()
    if (!message) return
    body.insertAdjacentHTML('afterbegin', bannerHtml())
  }

  function patchResults() {
    const el = document.getElementById('calc-results')
    if (!el) return
    const wrap = document.createElement('div')
    wrap.innerHTML = resultsHtml()
    const next = wrap.firstElementChild
    if (next) el.replaceWith(next)
  }

  function patchSteppers() {
    ;['passengerCount', 'luggageCount', 'infantCarrierCount', 'childSeatCount', 'boosterCount'].forEach(
      (field) => {
        const valueEl = container.querySelector(`[data-step-value="${field}"]`)
        if (valueEl) valueEl.textContent = String(state[field])
      },
    )
    const limits = {
      passengerCount: [1, MAX_PASSENGERS],
      luggageCount: [0, MAX_LUGGAGE],
      infantCarrierCount: [0, MAX_SEAT],
      childSeatCount: [0, MAX_SEAT],
      boosterCount: [0, MAX_SEAT],
    }
    container.querySelectorAll('[data-step]').forEach((btn) => {
      const field = btn.dataset.step
      const delta = Number(btn.dataset.delta)
      const [min, max] = limits[field] || [0, 99]
      const value = Number(state[field]) || 0
      const next = value + delta
      btn.disabled = calculating || next < min || next > max
    })
  }

  function setAddressInputsDisabled(disabled) {
    container.querySelectorAll('[data-place-input]').forEach((input) => {
      input.disabled = disabled
    })
    const submit = document.getElementById('calc-submit')
    if (submit) {
      submit.disabled = disabled
      submit.textContent = disabled ? 'Calculating…' : 'Calculate'
    }
  }

  function selectPlace(side, description) {
    places[side].suppress = true
    places[side].open = false
    places[side].suggestions = []
    state = { ...state, [side]: description }
    quote = null
    const input = container.querySelector(`[data-place-input="${side}"]`)
    if (input) input.value = description
    patchPlacesDropdown(side)
    const results = document.getElementById('calc-results')
    if (results) results.innerHTML = ''
    quote = null
  }

  function schedulePlaces(side) {
    const meta = places[side]
    if (meta.timer) clearTimeout(meta.timer)
    const query = state[side].trim()
    if (meta.suppress || query.length < 1) {
      meta.suggestions = []
      meta.loading = false
      meta.open = false
      patchPlacesDropdown(side)
      return
    }
    meta.loading = true
    meta.open = true
    patchPlacesDropdown(side)
    meta.timer = setTimeout(async () => {
      try {
        const results = await routingApi.places(query)
        if (destroyed || state[side].trim() !== query) return
        meta.suggestions = results
        meta.loading = false
        meta.open = true
        patchPlacesDropdown(side)
      } catch {
        if (destroyed) return
        meta.suggestions = []
        meta.loading = false
        meta.open = false
        patchPlacesDropdown(side)
      }
    }, PLACES_DEBOUNCE_MS)
  }

  function bindShellEvents() {
    container.querySelectorAll('[data-place-input]').forEach((input) => {
      const side = input.dataset.placeInput
      input.addEventListener('input', () => {
        places[side].suppress = false
        state = { ...state, [side]: input.value }
        quote = null
        message = null
        const results = document.getElementById('calc-results')
        if (results) results.innerHTML = ''
        const banner = document.getElementById('calc-banner')
        if (banner) banner.remove()
        schedulePlaces(side)
      })
      input.addEventListener('focus', () => {
        if (!places[side].suppress && state[side].trim().length >= 1) {
          places[side].open = true
          patchPlacesDropdown(side)
        }
      })
      input.addEventListener('blur', () => {
        setTimeout(() => {
          if (destroyed) return
          places[side].open = false
          patchPlacesDropdown(side)
        }, 180)
      })
    })

    container.querySelectorAll('[data-step]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const field = btn.dataset.step
        const delta = Number(btn.dataset.delta)
        const limits = {
          passengerCount: [1, MAX_PASSENGERS],
          luggageCount: [0, MAX_LUGGAGE],
          infantCarrierCount: [0, MAX_SEAT],
          childSeatCount: [0, MAX_SEAT],
          boosterCount: [0, MAX_SEAT],
        }
        const [min, max] = limits[field] || [0, 99]
        state = {
          ...state,
          [field]: clamp((Number(state[field]) || 0) + delta, min, max),
        }
        quote = null
        const results = document.getElementById('calc-results')
        if (results) results.innerHTML = ''
        patchSteppers()
      })
    })

    document.getElementById('calc-form')?.addEventListener('submit', async (event) => {
      event.preventDefault()
      if (calculating) return

      const fromInput = container.querySelector('[data-place-input="from"]')
      const toInput = container.querySelector('[data-place-input="to"]')
      state = {
        ...state,
        from: fromInput?.value ?? state.from,
        to: toInput?.value ?? state.to,
      }

      const from = state.from.trim()
      const to = state.to.trim()
      if (!from || !to) {
        message = { type: 'error', text: 'Enter both pickup and drop-off addresses.' }
        patchBanner()
        return
      }

      calculating = true
      message = null
      quote = null
      patchBanner()
      const results = document.getElementById('calc-results')
      if (results) results.innerHTML = ''
      setAddressInputsDisabled(true)
      patchSteppers()

      try {
        const result = await routingApi.quote({
          from,
          to,
          passengerCount: state.passengerCount,
          luggageCount: state.luggageCount,
          infantCarrierCount: state.infantCarrierCount,
          childSeatCount: state.childSeatCount,
          boosterCount: state.boosterCount,
          isReturnTrip: false,
        })
        quote = result
        message = { type: 'success', text: 'Fare calculated.' }
      } catch (err) {
        message = { type: 'error', text: err?.message || 'Could not calculate fare.' }
      } finally {
        calculating = false
        setAddressInputsDisabled(false)
        patchSteppers()
        patchBanner()
        patchResults()
      }
    })
  }

  function render() {
    if (destroyed) return
    container.innerHTML = `
      <div class="admin-form-shell">
        <header class="admin-form-shell__header">
          <h1 class="admin-form-shell__title">Calculate</h1>
          <p class="admin-form-shell__subtitle">Enter pickup and drop-off to get distance and fare (one-way and return).</p>
        </header>
        <div class="admin-form-shell__body">
          ${bannerHtml()}
          <form class="admin-form-card admin-prices-form" id="calc-form">
            <section class="admin-prices-section">
              <header class="admin-prices-section__head">
                <h2 class="admin-prices-section__title">Route</h2>
                <p class="admin-prices-section__subtitle">Addresses use Google Places suggestions, same as booking.</p>
              </header>
              <div class="admin-calc-route">
                ${placeField('from', 'Pick up', 'Pickup address')}
                ${placeField('to', 'Drop off', 'Drop-off address')}
              </div>
            </section>

            <section class="admin-prices-section">
              <header class="admin-prices-section__head">
                <h2 class="admin-prices-section__title">Passengers & options</h2>
                <p class="admin-prices-section__subtitle">Affects base tier and seat add-ons.</p>
              </header>
              <div class="admin-calc-steppers">
                ${stepper('passengerCount', 'Passengers', state.passengerCount, 1, MAX_PASSENGERS)}
                ${stepper('luggageCount', 'Luggage', state.luggageCount, 0, MAX_LUGGAGE)}
                ${stepper('infantCarrierCount', 'Infant carrier', state.infantCarrierCount, 0, MAX_SEAT)}
                ${stepper('childSeatCount', 'Child seat', state.childSeatCount, 0, MAX_SEAT)}
                ${stepper('boosterCount', 'Booster', state.boosterCount, 0, MAX_SEAT)}
              </div>
            </section>

            <div class="admin-prices-actions">
              <button type="submit" class="admin-form-done" id="calc-submit" ${calculating ? 'disabled' : ''}>
                ${calculating ? 'Calculating…' : 'Calculate'}
              </button>
            </div>

            ${resultsHtml()}
          </form>
        </div>
      </div>`

    bindShellEvents()
    patchPlacesDropdown('from')
    patchPlacesDropdown('to')
  }

  render()

  return {
    destroy() {
      destroyed = true
      if (places.from.timer) clearTimeout(places.from.timer)
      if (places.to.timer) clearTimeout(places.to.timer)
      container.innerHTML = ''
    },
  }
}
