import { adminPricingApi } from './api.js'
import { escapeHtml } from './icons.js'

const FIELDS = [
  {
    section: 'distance',
    key: 'shortTripMaxKm',
    label: 'Short-trip max (km)',
    hint: 'No distance surcharge below this distance.',
    step: '0.1',
  },
  {
    section: 'distance',
    key: 'midMaxKm',
    label: 'Mid-range max (km)',
    hint: 'Upper bound for the mid-range per-km rate.',
    step: '0.1',
  },
  {
    section: 'distance',
    key: 'midRateEurPerKm',
    label: 'Mid-range rate (€/km)',
    hint: 'Charged when distance is between short-trip max and mid-range max.',
    step: '0.01',
  },
  {
    section: 'distance',
    key: 'longRateEurPerKm',
    label: 'Long-range rate (€/km)',
    hint: 'Charged when distance is above mid-range max.',
    step: '0.01',
  },
  {
    section: 'seats',
    key: 'infantCarrierFare',
    label: 'Infant carrier (€)',
    hint: 'Flat fee per infant carrier.',
    step: '1',
  },
  {
    section: 'seats',
    key: 'childSeatFare',
    label: 'Child seat (€)',
    hint: 'Flat fee per child seat.',
    step: '1',
  },
  {
    section: 'seats',
    key: 'boosterFare',
    label: 'Booster (€)',
    hint: 'Flat fee per booster seat.',
    step: '1',
  },
]

const DEFAULT_TIERS = [
  { passengers: 1, luggage: 1, price: 52 },
  { passengers: 2, luggage: 2, price: 52 },
  { passengers: 3, luggage: 3, price: 57 },
  { passengers: 4, luggage: 4, price: 62 },
  { passengers: 5, luggage: 5, price: 72 },
  { passengers: 6, luggage: 6, price: 77 },
  { passengers: 7, luggage: 7, price: 84 },
  { passengers: 8, luggage: 8, price: 110 },
  { passengers: 8, luggage: 12, price: 127 },
  { passengers: 8, luggage: 16, price: 153 },
]

const MIN_TIERS = DEFAULT_TIERS.length

const DEFAULT_TIER_PRICE_BY_KEY = Object.fromEntries(
  DEFAULT_TIERS.map((t) => [`${t.passengers}:${t.luggage}`, t.price]),
)

function defaultTierMinPrice(passengers, luggage) {
  const key = `${passengers}:${luggage}`
  return Object.prototype.hasOwnProperty.call(DEFAULT_TIER_PRICE_BY_KEY, key)
    ? DEFAULT_TIER_PRICE_BY_KEY[key]
    : null
}

function emptyValues() {
  return {
    shortTripMaxKm: '',
    midMaxKm: '',
    midRateEurPerKm: '',
    longRateEurPerKm: '',
    infantCarrierFare: '',
    childSeatFare: '',
    boosterFare: '',
    passengerLuggageTiers: DEFAULT_TIERS.map((t) => ({ ...t })),
  }
}

function normalizeTiers(src) {
  if (!Array.isArray(src) || src.length === 0) {
    return DEFAULT_TIERS.map((t) => ({ ...t }))
  }
  return src.map((t) => ({
    passengers: t?.passengers ?? '',
    luggage: t?.luggage ?? '',
    price: t?.price ?? '',
  }))
}

function valuesFromApi(src) {
  return {
    shortTripMaxKm: src?.shortTripMaxKm ?? '',
    midMaxKm: src?.midMaxKm ?? '',
    midRateEurPerKm: src?.midRateEurPerKm ?? '',
    longRateEurPerKm: src?.longRateEurPerKm ?? '',
    infantCarrierFare: src?.infantCarrierFare ?? '',
    childSeatFare: src?.childSeatFare ?? '',
    boosterFare: src?.boosterFare ?? '',
    passengerLuggageTiers: normalizeTiers(src?.passengerLuggageTiers),
  }
}

function parseTiers(tiers) {
  if (!Array.isArray(tiers) || tiers.length < MIN_TIERS) {
    throw new Error(`At least ${MIN_TIERS} passenger/luggage tiers are required.`)
  }
  const parsed = tiers.map((tier, index) => {
    const passengers = Number(tier.passengers)
    const luggage = Number(tier.luggage)
    const price = Number(tier.price)
    if (![passengers, luggage, price].every(Number.isFinite)) {
      throw new Error(`Tier ${index + 1}: all fields must be valid numbers.`)
    }
    if (passengers < 1) {
      throw new Error(`Tier ${index + 1}: passengers must be at least 1.`)
    }
    if (luggage < 0 || price < 0) {
      throw new Error(`Tier ${index + 1}: luggage and price cannot be negative.`)
    }
    const rounded = {
      passengers: Math.round(passengers),
      luggage: Math.round(luggage),
      price: Math.round(price),
    }
    const floor = defaultTierMinPrice(rounded.passengers, rounded.luggage)
    if (floor != null && rounded.price < floor) {
      throw new Error(
        `Tier ${index + 1}: price for ${rounded.passengers} passengers / ${rounded.luggage} luggage cannot be below the default (€${floor}).`,
      )
    }
    return rounded
  })
  return parsed
}

function parsePayload(values) {
  const shortTripMaxKm = Number(values.shortTripMaxKm)
  const midMaxKm = Number(values.midMaxKm)
  const midRateEurPerKm = Number(values.midRateEurPerKm)
  const longRateEurPerKm = Number(values.longRateEurPerKm)
  const infantCarrierFare = Number(values.infantCarrierFare)
  const childSeatFare = Number(values.childSeatFare)
  const boosterFare = Number(values.boosterFare)
  const passengerLuggageTiers = parseTiers(values.passengerLuggageTiers)

  if (
    ![
      shortTripMaxKm,
      midMaxKm,
      midRateEurPerKm,
      longRateEurPerKm,
      infantCarrierFare,
      childSeatFare,
      boosterFare,
    ].every(Number.isFinite)
  ) {
    throw new Error('All fields must be valid numbers.')
  }
  if (shortTripMaxKm <= 0 || midMaxKm <= 0) {
    throw new Error('Distance thresholds must be greater than zero.')
  }
  if (midMaxKm <= shortTripMaxKm) {
    throw new Error('Mid-range max km must be greater than short-trip max km.')
  }
  if (
    midRateEurPerKm < 0 ||
    longRateEurPerKm < 0 ||
    infantCarrierFare < 0 ||
    childSeatFare < 0 ||
    boosterFare < 0
  ) {
    throw new Error('Rates and fees cannot be negative.')
  }

  return {
    shortTripMaxKm,
    midMaxKm,
    midRateEurPerKm,
    longRateEurPerKm,
    infantCarrierFare: Math.round(infantCarrierFare),
    childSeatFare: Math.round(childSeatFare),
    boosterFare: Math.round(boosterFare),
    passengerLuggageTiers,
  }
}

export function createPricesView(accessToken, container) {
  let values = emptyValues()
  let defaults = emptyValues()
  let loading = true
  let saving = false
  let message = null
  let destroyed = false

  function banner() {
    if (!message) return ''
    return `<div class="admin-form-banner admin-form-banner--${message.type}">${escapeHtml(message.text)}</div>`
  }

  function fieldHtml(field) {
    const def = defaults[field.key]
    const defLabel = def === '' || def == null ? '' : `Default: ${escapeHtml(String(def))}`
    return `
      <label class="admin-prices-field">
        <span class="admin-prices-field__label">${escapeHtml(field.label)}</span>
        <input
          class="admin-form-field"
          type="number"
          inputmode="decimal"
          step="${field.step}"
          min="0"
          data-field="${field.key}"
          value="${escapeHtml(String(values[field.key] ?? ''))}"
        />
        <span class="admin-prices-field__hint">${escapeHtml(field.hint)}${defLabel ? ` · ${defLabel}` : ''}</span>
      </label>`
  }

  function sectionHtml(id, title, subtitle) {
    const fields = FIELDS.filter((f) => f.section === id)
      .map(fieldHtml)
      .join('')
    return `
      <section class="admin-prices-section">
        <header class="admin-prices-section__head">
          <h2 class="admin-prices-section__title">${escapeHtml(title)}</h2>
          <p class="admin-prices-section__subtitle">${escapeHtml(subtitle)}</p>
        </header>
        <div class="admin-prices-section__grid">${fields}</div>
      </section>`
  }

  function tiersHtml() {
    const rows = (values.passengerLuggageTiers || [])
      .map((tier, index) => {
        const passengers = Number(tier.passengers)
        const luggage = Number(tier.luggage)
        const floor =
          Number.isFinite(passengers) && Number.isFinite(luggage)
            ? defaultTierMinPrice(Math.round(passengers), Math.round(luggage))
            : null
        const priceMinAttr = floor != null ? `min="${floor}"` : 'min="0"'
        const priceHint =
          floor != null ? ` · Min €${floor}` : ''
        return `
      <tr class="admin-prices-tiers__row" data-tier-index="${index}">
        <td>
          <input
            class="admin-form-field"
            type="number"
            inputmode="numeric"
            min="1"
            step="1"
            data-tier-field="passengers"
            data-tier-index="${index}"
            value="${escapeHtml(String(tier.passengers ?? ''))}"
            aria-label="Passengers for tier ${index + 1}"
          />
        </td>
        <td>
          <input
            class="admin-form-field"
            type="number"
            inputmode="numeric"
            min="0"
            step="1"
            data-tier-field="luggage"
            data-tier-index="${index}"
            value="${escapeHtml(String(tier.luggage ?? ''))}"
            aria-label="Luggage for tier ${index + 1}"
          />
        </td>
        <td>
          <input
            class="admin-form-field"
            type="number"
            inputmode="numeric"
            ${priceMinAttr}
            step="1"
            data-tier-field="price"
            data-tier-index="${index}"
            value="${escapeHtml(String(tier.price ?? ''))}"
            aria-label="Price for tier ${index + 1}"
            title="${floor != null ? `Default minimum €${floor}` : 'Price in euros'}"
          />
          ${priceHint ? `<span class="admin-prices-field__hint">${escapeHtml(priceHint.trim())}</span>` : ''}
        </td>
        <td class="admin-prices-tiers__actions">
          <button
            type="button"
            class="admin-prices-tier-remove"
            data-tier-remove="${index}"
            ${values.passengerLuggageTiers.length <= MIN_TIERS || saving ? 'disabled' : ''}
          >Remove</button>
        </td>
      </tr>`
      })
      .join('')

    return `
      <section class="admin-prices-section">
        <header class="admin-prices-section__head">
          <h2 class="admin-prices-section__title">Passenger / luggage base</h2>
          <p class="admin-prices-section__subtitle">
            Base fare tiers (minimum ${MIN_TIERS}). Price cannot go below the default for the same passengers/luggage pair.
          </p>
        </header>
        <div class="admin-prices-tiers-wrap">
          <table class="admin-prices-tiers">
            <thead>
              <tr>
                <th>Passengers</th>
                <th>Luggage</th>
                <th>Price (€)</th>
                <th></th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
          <button type="button" class="admin-prices-tier-add" id="prices-tier-add" ${saving ? 'disabled' : ''}>
            Add tier
          </button>
        </div>
      </section>`
  }

  function render() {
    if (destroyed) return
    container.innerHTML = `
      <div class="admin-form-shell">
        <header class="admin-form-shell__header">
          <h1 class="admin-form-shell__title">Prices</h1>
          <p class="admin-form-shell__subtitle">Passenger/luggage tiers, distance surcharge, and child seat fees used for booking quotes.</p>
        </header>
        <div class="admin-form-shell__body">
          ${banner()}
          ${
            loading
              ? `<div class="admin-prices-loading">Loading pricing settings…</div>`
              : `
          <form class="admin-form-card admin-prices-form" id="prices-form">
            ${tiersHtml()}
            ${sectionHtml('distance', 'Distance surcharge', 'Applied when trip distance meets or exceeds the short-trip threshold.')}
            ${sectionHtml('seats', 'Child seats', 'Flat add-on per infant carrier, child seat, or booster.')}
            <div class="admin-prices-actions">
              <button type="button" class="admin-prices-reset" id="prices-reset" ${saving ? 'disabled' : ''}>Reset to defaults</button>
              <button type="submit" class="admin-form-done" id="prices-save" ${saving ? 'disabled' : ''}>${saving ? 'Saving…' : 'Save'}</button>
            </div>
          </form>`
          }
        </div>
      </div>`

    if (loading) return

    container.querySelectorAll('[data-field]').forEach((input) => {
      input.addEventListener('input', () => {
        const key = input.dataset.field
        if (!key) return
        values = { ...values, [key]: input.value }
      })
    })

    container.querySelectorAll('[data-tier-field]').forEach((input) => {
      input.addEventListener('input', () => {
        const index = Number(input.dataset.tierIndex)
        const field = input.dataset.tierField
        if (!Number.isInteger(index) || !field) return
        const next = values.passengerLuggageTiers.map((tier, i) =>
          i === index ? { ...tier, [field]: input.value } : tier,
        )
        values = { ...values, passengerLuggageTiers: next }
      })
    })

    container.querySelectorAll('[data-tier-remove]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const index = Number(btn.dataset.tierRemove)
        if (!Number.isInteger(index) || values.passengerLuggageTiers.length <= MIN_TIERS) return
        values = {
          ...values,
          passengerLuggageTiers: values.passengerLuggageTiers.filter((_, i) => i !== index),
        }
        render()
      })
    })

    document.getElementById('prices-tier-add')?.addEventListener('click', () => {
      const last = values.passengerLuggageTiers[values.passengerLuggageTiers.length - 1]
      values = {
        ...values,
        passengerLuggageTiers: [
          ...values.passengerLuggageTiers,
          {
            passengers: last?.passengers ?? 1,
            luggage: last?.luggage ?? 0,
            price: last?.price ?? 0,
          },
        ],
      }
      render()
    })

    document.getElementById('prices-reset')?.addEventListener('click', () => {
      values = {
        ...defaults,
        passengerLuggageTiers: normalizeTiers(defaults.passengerLuggageTiers),
      }
      message = { type: 'success', text: 'Form reset to defaults. Click Save to apply.' }
      render()
    })

    document.getElementById('prices-form')?.addEventListener('submit', async (event) => {
      event.preventDefault()
      if (saving) return
      try {
        const payload = parsePayload(values)
        saving = true
        message = null
        render()
        const result = await adminPricingApi.update(accessToken, payload)
        values = valuesFromApi(result.values)
        defaults = valuesFromApi(result.defaults)
        message = { type: 'success', text: 'Pricing settings saved.' }
      } catch (err) {
        message = { type: 'error', text: err?.message || 'Could not save pricing settings.' }
      } finally {
        saving = false
        render()
      }
    })
  }

  async function load() {
    loading = true
    message = null
    render()
    try {
      const result = await adminPricingApi.get(accessToken)
      values = valuesFromApi(result.values)
      defaults = valuesFromApi(result.defaults)
    } catch (err) {
      message = { type: 'error', text: err?.message || 'Could not load pricing settings.' }
    } finally {
      loading = false
      render()
    }
  }

  load()

  return {
    destroy() {
      destroyed = true
      container.innerHTML = ''
    },
  }
}
