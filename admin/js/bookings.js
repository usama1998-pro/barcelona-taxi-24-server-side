import { bookingsApi } from './api.js'
import {
  bookingDayKeyFromIso,
  bookingDetailAccentColor,
  bookingFromDisplay,
  bookingPassengerLabel,
  bookingToDisplay,
  formatFooterTimestamp,
  formatListTime24,
  formatPickupDateLocal,
  formatPickupTimeLocal24,
  bookingArrivalAirline,
  bookingArrivalFlight,
  publicBookingPageUrl,
  qrCodeImageUrl,
  reservationDisplayNumber,
  PUBLIC_SITE_DISPLAY,
} from './format.js'
import { bookingSourceIconHtml, escapeAttr, escapeHtml, icon, safeTelHref } from './icons.js'
import { DATE_FILTER_PAGE_SIZE, PAGE_SIZE } from './config.js'

const TABS = [
  { key: 'upcoming', label: 'Upcoming' },
  { key: 'current', label: 'Current' },
  { key: 'past', label: 'Past' },
]

function emptySection() {
  return {
    items: [],
    page: 0,
    totalPages: 0,
    total: 0,
    loading: false,
    loadingMore: false,
    error: null,
    loadMoreError: null,
  }
}

export function createBookingsView(accessToken, container) {
  let active = 'upcoming'
  let byScope = { past: emptySection(), current: emptySection(), upcoming: emptySection() }
  let refreshing = false
  let refInput = ''
  let appliedRefQuery = ''
  let dateDraft = ''
  let appliedScheduledOn = null
  let notesBooking = null
  let detailUuid = null
  let detailBooking = null
  let detailLoading = false
  let detailError = null
  let appendLock = false
  let destroyed = false

  function section() {
    return byScope[active]
  }

  function emptyCopy() {
    if (active === 'past') return 'No completed, cancelled, or overdue trips.'
    if (active === 'current') return "No open trips due today that haven't passed yet."
    return 'No upcoming open trips from tomorrow onward.'
  }

  function gridBookings() {
    const groups = new Map()
    for (const b of section().items) {
      const k = bookingDayKeyFromIso(b.scheduledTime)
      if (!groups.has(k)) groups.set(k, [])
      groups.get(k).push(b)
    }
    const keys = [...groups.keys()].sort((a, b) => {
      if (a === b) return 0
      return active === 'past' ? (a < b ? 1 : -1) : a < b ? -1 : 1
    })
    const out = []
    for (const k of keys) {
      const chunk = groups.get(k)
      chunk.sort((a, b) =>
        active === 'past'
          ? new Date(b.scheduledTime).getTime() - new Date(a.scheduledTime).getTime()
          : new Date(a.scheduledTime).getTime() - new Date(b.scheduledTime).getTime(),
      )
      out.push(...chunk)
    }
    return out
  }

  async function refreshScope(scope) {
    if (destroyed) return
    if (!accessToken) {
      byScope = { ...byScope, [scope]: { ...emptySection(), error: 'Not signed in.', loading: false } }
      render()
      return
    }
    byScope = {
      ...byScope,
      [scope]: { ...byScope[scope], error: null, loadMoreError: null, loading: true, loadingMore: false },
    }
    render()
    try {
      const scheduledOn = scope !== 'current' ? appliedScheduledOn || undefined : undefined
      const bookingReference = appliedRefQuery.trim() || undefined
      const useLargePage = Boolean(scheduledOn || bookingReference)
      const res = await bookingsApi.list(accessToken, {
        page: 1,
        pageSize: useLargePage ? DATE_FILTER_PAGE_SIZE : PAGE_SIZE,
        timeScope: scope,
        scheduledOn,
        bookingReference,
      })
      if (destroyed) return
      byScope = {
        ...byScope,
        [scope]: {
          ...byScope[scope],
          items: res.data,
          page: res.page,
          totalPages: res.totalPages,
          total: res.total,
          loading: false,
          loadingMore: false,
          error: null,
          loadMoreError: null,
        },
      }
    } catch (e) {
      if (destroyed) return
      byScope = {
        ...byScope,
        [scope]: {
          ...byScope[scope],
          loading: false,
          loadingMore: false,
          error: e instanceof Error ? e.message : 'Could not load bookings.',
          items: [],
          page: 0,
          total: 0,
          totalPages: 0,
          loadMoreError: null,
        },
      }
    }
    render()
  }

  async function loadNextPage(scope) {
    if (!accessToken || appendLock || destroyed) return
    const st = byScope[scope]
    if (st.loading || st.loadingMore || st.items.length === 0) return
    const hasMore = st.totalPages > 0 ? st.page < st.totalPages : st.total > st.items.length
    if (!hasMore) return

    appendLock = true
    byScope = { ...byScope, [scope]: { ...st, loadingMore: true, loadMoreError: null } }
    render()
    try {
      const nextPage = st.page + 1
      const scheduledOn = scope !== 'current' ? appliedScheduledOn || undefined : undefined
      const bookingReference = appliedRefQuery.trim() || undefined
      const useLargePage = Boolean(scheduledOn || bookingReference)
      const res = await bookingsApi.list(accessToken, {
        page: nextPage,
        pageSize: useLargePage ? DATE_FILTER_PAGE_SIZE : PAGE_SIZE,
        timeScope: scope,
        scheduledOn,
        bookingReference,
      })
      if (destroyed) return
      const seen = new Set(st.items.map((b) => b.uuid))
      const merged = [...st.items]
      for (const b of res.data) {
        if (!seen.has(b.uuid)) {
          seen.add(b.uuid)
          merged.push(b)
        }
      }
      byScope = {
        ...byScope,
        [scope]: {
          ...st,
          items: merged,
          page: res.page,
          totalPages: res.totalPages,
          total: res.total,
          loadingMore: false,
          loadMoreError: null,
        },
      }
    } catch (e) {
      if (destroyed) return
      byScope = {
        ...byScope,
        [scope]: {
          ...st,
          loadingMore: false,
          loadMoreError: e instanceof Error ? e.message : 'Could not load more bookings.',
        },
      }
    } finally {
      appendLock = false
      render()
    }
  }

  async function openDetail(uuid) {
    detailUuid = uuid
    detailBooking = null
    detailError = null
    detailLoading = true
    render()
    try {
      const b = await bookingsApi.getByUuid(accessToken, uuid)
      if (destroyed) return
      detailBooking = b
      detailError = null
    } catch (e) {
      if (destroyed) return
      detailBooking = null
      detailError = e instanceof Error ? e.message : 'Could not load booking.'
    } finally {
      detailLoading = false
      render()
    }
  }

  function renderBookingCard(b) {
    const passenger = escapeHtml(bookingPassengerLabel(b))
    const dateKey = bookingDayKeyFromIso(b.scheduledTime)
    return `
      <article class="admin-booking-card" data-uuid="${escapeHtml(b.uuid)}">
        <div class="admin-booking-card__date-strip">${escapeHtml(dateKey)}</div>
        <div class="admin-booking-card__main">
          <div class="admin-booking-card__body-row">
            <div class="admin-booking-card__time-col">
              <span class="admin-booking-card__time24">${escapeHtml(formatListTime24(b.scheduledTime))}</span>
            </div>
            <div class="admin-booking-card__detail-col">
              <div class="admin-booking-card__name-row">
                <div class="admin-booking-card__name">${passenger}</div>
                ${bookingSourceIconHtml(b)}
              </div>
              <p class="admin-booking-card__route"><span class="admin-booking-card__route-prefix">From : </span>${escapeHtml(bookingFromDisplay(b))}</p>
              <p class="admin-booking-card__route"><span class="admin-booking-card__route-prefix">To : </span>${escapeHtml(bookingToDisplay(b))}</p>
              <div class="admin-booking-card__actions">
                <span class="admin-booking-card__pax" aria-label="${b.passengerCount} passengers">
                  <span class="admin-booking-card__pax-icon">${icon('users')}</span>
                  <span class="admin-booking-card__pax-num">${b.passengerCount}</span>
                </span>
                <button type="button" class="admin-booking-card__btn-notes" data-action="notes" data-uuid="${escapeHtml(b.uuid)}">Notes</button>
                <button type="button" class="admin-booking-card__btn-view" data-action="view" data-uuid="${escapeHtml(b.uuid)}" aria-label="View booking">${icon('eye')}</button>
                <button type="button" class="admin-booking-card__btn-delete" data-action="delete" data-uuid="${escapeHtml(b.uuid)}" aria-label="Delete booking">${icon('trash')}</button>
              </div>
            </div>
          </div>
        </div>
      </article>`
  }

  function renderDetailModal() {
    if (!detailUuid) return ''
    const booking = detailBooking
    const accent = booking ? bookingDetailAccentColor(booking) : '#29b6f6'
    const accentClass = booking && !detailLoading && !detailError ? ' admin-res-detail__header--accent' : ''
    const closeAccent = booking && !detailLoading && !detailError ? ' admin-res-detail__close-x--on-accent' : ''
    const headerStyle = booking && !detailLoading && !detailError ? ` style="background-color:${accent}"` : ''

    let body = ''
    if (detailLoading) {
      body = `<div class="admin-res-detail__loading">${icon('loader')}</div>`
    } else if (detailError) {
      body = `<p class="admin-res-detail__error">${escapeHtml(detailError)}</p>`
    } else if (booking) {
      const phone = booking.customerPhone?.trim() || booking.user?.phone?.trim()
      const telHref = safeTelHref(phone)
      const phoneHtml = telHref
        ? `<a class="admin-res-detail__tel" href="${escapeAttr(telHref)}">${escapeHtml(phone)}</a>`
        : phone
          ? escapeHtml(phone)
          : '—'
      const pageUrl = publicBookingPageUrl(booking.uuid)
      body = `
        <section class="admin-res-detail__section">
          <div class="admin-res-detail__section-head" style="background-color:${accent}">Pickup Information</div>
          <div class="admin-res-detail__section-body">
            <div class="admin-res-detail__row"><span class="admin-res-detail__label">Pickup Address:</span><span class="admin-res-detail__value">${escapeHtml(bookingFromDisplay(booking))}</span></div>
            <div class="admin-res-detail__row"><span class="admin-res-detail__label">Passengers:</span><span class="admin-res-detail__value">${booking.passengerCount}</span></div>
            <div class="admin-res-detail__row"><span class="admin-res-detail__label">Pickup Date:</span><span class="admin-res-detail__value">${escapeHtml(formatPickupDateLocal(booking.scheduledTime))}</span></div>
            <div class="admin-res-detail__row"><span class="admin-res-detail__label">Pickup Time:</span><span class="admin-res-detail__value">${escapeHtml(formatPickupTimeLocal24(booking.scheduledTime))}</span></div>
            <div class="admin-res-detail__row"><span class="admin-res-detail__label">Arrival Airline:</span><span class="admin-res-detail__value">${escapeHtml(bookingArrivalAirline(booking) ?? '—')}</span></div>
            <div class="admin-res-detail__row"><span class="admin-res-detail__label">Arrival Flight:</span><span class="admin-res-detail__value">${escapeHtml(bookingArrivalFlight(booking) ?? '—')}</span></div>
          </div>
        </section>
        <section class="admin-res-detail__section">
          <div class="admin-res-detail__section-head" style="background-color:${accent}">Dropoff Information</div>
          <div class="admin-res-detail__section-body">
            <div class="admin-res-detail__row"><span class="admin-res-detail__label">Dropoff Address:</span><span class="admin-res-detail__value">${escapeHtml(bookingToDisplay(booking))}</span></div>
          </div>
        </section>
        <section class="admin-res-detail__section">
          <div class="admin-res-detail__section-head" style="background-color:${accent}">Customer Information</div>
          <div class="admin-res-detail__section-body">
            <div class="admin-res-detail__row"><span class="admin-res-detail__label">Customer Name:</span><span class="admin-res-detail__value">${escapeHtml(bookingPassengerLabel(booking))}</span></div>
            <div class="admin-res-detail__row"><span class="admin-res-detail__label">Phone number:</span><span class="admin-res-detail__value">${phoneHtml}</span></div>
            <div class="admin-res-detail__row"><span class="admin-res-detail__label">Booking Ref:</span><span class="admin-res-detail__value">${escapeHtml(booking.bookingReference)}</span></div>
          </div>
        </section>
        <div class="admin-res-detail__footer-meta">
          <img class="admin-res-detail__qr" src="${qrCodeImageUrl(pageUrl)}" alt="" width="90" height="90" loading="lazy" />
          <span class="admin-res-detail__site">${PUBLIC_SITE_DISPLAY}</span>
          <span class="admin-res-detail__stamp">${escapeHtml(formatFooterTimestamp(booking.createdAt))}</span>
        </div>`
    }

    const title =
      booking && !detailLoading && !detailError
        ? `<span class="admin-res-detail__title-row"><span>RES # ${escapeHtml(reservationDisplayNumber(booking))}</span>${bookingSourceIconHtml(booking, '#fff')}</span>`
        : 'Reservation'

    return `
      <div class="admin-res-detail-overlay" data-action="close-detail" role="presentation">
        <div class="admin-res-detail" role="dialog" aria-modal="true" aria-labelledby="admin-res-detail-title">
          <header class="admin-res-detail__header${accentClass}"${headerStyle}>
            <h2 id="admin-res-detail-title" class="admin-res-detail__title">${title}</h2>
            <button type="button" class="admin-res-detail__close-x${closeAccent}" data-action="close-detail" aria-label="Close">${icon('x')}</button>
          </header>
          <div class="admin-res-detail__body">${body}</div>
          <footer class="admin-res-detail__footer">
            <button type="button" class="admin-res-detail__btn-close" data-action="close-detail">Close</button>
          </footer>
        </div>
      </div>`
  }

  function render() {
    const st = section()
    const items = gridBookings()
    const canLoadMore =
      st.items.length > 0 &&
      !st.loading &&
      !st.loadingMore &&
      (st.totalPages > 0 ? st.page < st.totalPages : st.total > st.items.length)

    const tabsHtml = TABS.map(
      (tab) =>
        `<button type="button" class="admin-bookings-shell__tab${active === tab.key ? ' admin-bookings-shell__tab--active' : ''}" data-action="tab" data-tab="${tab.key}">${tab.label}</button>`,
    ).join('')

    const dateFilter =
      active !== 'current'
        ? `
      <section class="admin-bookings-filter-card">
        <div class="admin-bookings-filter-card__title">Search by Date</div>
        <div class="admin-bookings-filter-card__body">
          <label class="admin-bookings-filter-card__label" for="admin-date-input">Select Date</label>
          <div class="admin-bookings-filter-card__row">
            <div class="admin-bookings-filter-card__date-wrap">
              <span class="admin-bookings-filter-card__cal-icon">${icon('calendar')}</span>
              <input id="admin-date-input" type="date" class="admin-bookings-filter-card__input admin-bookings-filter-card__input--date" value="${escapeHtml(dateDraft)}" data-input="date" />
            </div>
            <button type="button" class="admin-bookings-btn admin-bookings-btn--primary" data-action="date-search">Search</button>
            <button type="button" class="admin-bookings-btn admin-bookings-btn--danger" data-action="date-clear">Clear</button>
          </div>
        </div>
      </section>`
        : ''

    let listHtml = ''
    if (st.error && st.items.length === 0 && !st.loading) {
      listHtml = `<p class="admin-bookings-shell__error-text">${escapeHtml(st.error)}</p>`
    } else if (st.loading && st.items.length === 0) {
      listHtml = `<div class="admin-bookings-shell__empty-loading admin-bookings-shell__spinner">${icon('loader')}</div>`
    } else if (items.length === 0) {
      const emptyIcon = active === 'past' ? icon('archive') : icon('calendar')
      listHtml = `<div class="admin-bookings-shell__empty">${emptyIcon}<p class="admin-bookings-shell__empty-msg">${emptyCopy()}</p></div>`
    } else {
      listHtml = `<div class="admin-bookings-shell__grid">${items.map(renderBookingCard).join('')}</div>`
    }

    const footer =
      st.items.length > 0 && !st.loading
        ? `<div class="admin-bookings-shell__load-more-wrap">
            ${st.total > 0 ? `<p class="admin-bookings-shell__load-more-meta">Showing ${st.items.length} of ${st.total} booking${st.total === 1 ? '' : 's'}</p>` : ''}
            ${canLoadMore ? `<button type="button" class="admin-bookings-btn admin-bookings-btn--primary admin-bookings-shell__load-more-btn" data-action="load-more"${st.loadingMore ? ' disabled' : ''}>${st.loadingMore ? 'Loading…' : 'Load more'}</button>` : ''}
            ${st.loadMoreError ? `<p class="admin-bookings-shell__footer-error">${escapeHtml(st.loadMoreError)}</p>` : ''}
          </div>`
        : st.loadMoreError
          ? `<p class="admin-bookings-shell__footer-error">${escapeHtml(st.loadMoreError)}</p>`
          : ''

    const notesModal = notesBooking
      ? `
      <div class="admin-bookings-modal-overlay" data-action="close-notes" role="presentation">
        <div class="admin-bookings-modal-sheet" role="dialog" aria-labelledby="admin-notes-title">
          <h2 id="admin-notes-title" class="admin-bookings-modal-title">Notes</h2>
          <p class="admin-bookings-notes-body">${escapeHtml(notesBooking.note?.trim() ? notesBooking.note.trim() : 'No notes for this booking.')}</p>
          <div class="admin-bookings-modal-actions">
            <button type="button" class="admin-bookings-modal-btn-primary" data-action="close-notes">Close</button>
          </div>
        </div>
      </div>`
      : ''

    container.innerHTML = `
      <div class="admin-bookings-shell">
        <header class="admin-bookings-shell__navbar">
          <nav class="admin-bookings-shell__tabs" aria-label="Booking period">${tabsHtml}</nav>
          <div class="admin-bookings-shell__tools">
            <button type="button" class="admin-bookings-shell__icon-btn" data-action="refresh" ${refreshing || st.loading ? 'disabled' : ''} aria-label="Refresh list">
              <span class="${refreshing ? 'admin-bookings-shell__spin' : ''}">${icon('refresh')}</span>
            </button>
          </div>
        </header>
        <div class="admin-bookings-shell__filters">
          <section class="admin-bookings-filter-card">
            <div class="admin-bookings-filter-card__title">Search by booking ref</div>
            <div class="admin-bookings-filter-card__body">
              <label class="admin-bookings-filter-card__label" for="admin-ref-input">Enter Booking Ref</label>
              <div class="admin-bookings-filter-card__row">
                <input id="admin-ref-input" class="admin-bookings-filter-card__input" value="${escapeHtml(refInput)}" data-input="ref" />
                <button type="button" class="admin-bookings-btn admin-bookings-btn--primary" data-action="ref-search">Search</button>
                <button type="button" class="admin-bookings-btn admin-bookings-btn--danger" data-action="ref-clear">Clear</button>
              </div>
            </div>
          </section>
          ${dateFilter}
        </div>
        <div class="admin-bookings-shell__scroll">${listHtml}${footer}</div>
        ${notesModal}
        ${renderDetailModal()}
      </div>`

    const refEl = container.querySelector('[data-input="ref"]')
    if (refEl) refEl.addEventListener('input', (e) => { refInput = e.target.value })
    const dateEl = container.querySelector('[data-input="date"]')
    if (dateEl) dateEl.addEventListener('input', (e) => { dateDraft = e.target.value })
  }

  function bindEvents() {
    container.addEventListener('click', (event) => {
      const target = event.target.closest('[data-action]')
      if (!target) return
      const action = target.dataset.action
      const uuid = target.dataset.uuid

      if (action === 'tab') {
        active = target.dataset.tab
        if (active === 'current') {
          dateDraft = ''
          appliedScheduledOn = null
        }
        void refreshScope(active).then(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
        return
      }
      if (action === 'refresh') {
        refreshing = true
        render()
        void refreshScope(active).then(() => {
          refreshing = false
          window.scrollTo({ top: 0, behavior: 'smooth' })
          render()
        })
        return
      }
      if (action === 'ref-search') {
        appliedRefQuery = refInput.trim()
        void refreshScope(active)
        return
      }
      if (action === 'ref-clear') {
        refInput = ''
        appliedRefQuery = ''
        void refreshScope(active)
        return
      }
      if (action === 'date-search') {
        const v = dateDraft.trim()
        if (!v) {
          appliedScheduledOn = null
        } else {
          appliedScheduledOn = v
        }
        void refreshScope(active)
        return
      }
      if (action === 'date-clear') {
        dateDraft = ''
        appliedScheduledOn = null
        void refreshScope(active)
        return
      }
      if (action === 'load-more') {
        void loadNextPage(active)
        return
      }
      if (action === 'notes' && uuid) {
        notesBooking = section().items.find((b) => b.uuid === uuid) || null
        render()
        return
      }
      if (action === 'close-notes') {
        if (event.target.dataset.action === 'close-notes' || event.target.closest('[data-action="close-notes"]') === target) {
          notesBooking = null
          render()
        }
        return
      }
      if (action === 'view' && uuid) {
        void openDetail(uuid)
        return
      }
      if (action === 'close-detail') {
        detailUuid = null
        detailBooking = null
        detailError = null
        detailLoading = false
        render()
        return
      }
      if (action === 'delete' && uuid) {
        const b = section().items.find((item) => item.uuid === uuid)
        if (!b || !window.confirm(`Remove booking ${b.bookingReference}?`)) return
        void (async () => {
          try {
            await bookingsApi.removeReservation(accessToken, uuid)
            await refreshScope(active)
          } catch (e) {
            window.alert(e instanceof Error ? e.message : 'This booking could not be removed.')
          }
        })()
      }
    })

    container.addEventListener('click', (event) => {
      if (event.target.classList.contains('admin-bookings-modal-overlay')) {
        notesBooking = null
        render()
      }
      if (event.target.classList.contains('admin-res-detail-overlay')) {
        detailUuid = null
        detailBooking = null
        detailError = null
        detailLoading = false
        render()
      }
    })
  }

  bindEvents()
  void refreshScope(active)

  return {
    destroy() {
      destroyed = true
      container.innerHTML = ''
    },
  }
}
