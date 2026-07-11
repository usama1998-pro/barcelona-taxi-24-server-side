import {
  ADMIN_ACCESS_TOKEN_KEY,
  ADMIN_AUTH_KEY,
} from './config.js'
import {
  apiUrl,
  decodeJwtPayload,
  isSuperAdminStaffPayload,
  parseJsonErrorBody,
} from './api.js'
import { BRAND_NAME } from './config.js'
import { createBookingsView } from './bookings.js'
import { createLogsView } from './logs.js'
import { createReservationView } from './reservation.js'
import { createInvoiceView } from './invoice.js'
import { escapeHtml, icon } from './icons.js'

const DOCS_URL = '/internal/api-docs'

const NAV_ITEMS = [
  { view: 'bookings', label: 'Bookings', icon: 'bookings' },
  { view: 'reservation', label: 'New Reservation', icon: 'reservation' },
  { view: 'invoice', label: 'Generate Invoice', icon: 'invoice' },
  { view: 'logs', label: 'Logs', icon: 'logs' },
  { view: 'docs', label: 'API Docs', icon: 'docs', external: DOCS_URL },
]

const SIDEBAR_COLLAPSED_KEY = 'taxi_admin_sidebar_collapsed'

let activeView = 'bookings'
let activePanel = null
let showPassword = false
let navOpen = false
let loginLockTimer = null
let loginLockedUntil = 0
let loginEmailDraft = ''

function clearLoginLockTimer() {
  if (loginLockTimer) {
    clearTimeout(loginLockTimer)
    loginLockTimer = null
  }
}

function isLoginLocked() {
  return loginLockedUntil > Date.now()
}

function lockLoginFor(seconds, email = '') {
  const secs = Math.max(1, Number(seconds) || 0)
  loginLockedUntil = Date.now() + secs * 1000
  if (email) loginEmailDraft = email
  clearLoginLockTimer()
  loginLockTimer = setTimeout(() => {
    loginLockedUntil = 0
    loginLockTimer = null
    renderLogin('Lockout ended. You can try signing in again.')
  }, secs * 1000)
}

function clearAdminSession() {
  localStorage.removeItem(ADMIN_AUTH_KEY)
  localStorage.removeItem(ADMIN_ACCESS_TOKEN_KEY)
  document.cookie = `${ADMIN_ACCESS_TOKEN_KEY}=; Path=/; Max-Age=0; SameSite=Lax`
}

function persistAdminSession(accessToken) {
  localStorage.setItem(ADMIN_AUTH_KEY, 'true')
  localStorage.setItem(ADMIN_ACCESS_TOKEN_KEY, accessToken)
  // Cookie lets /internal/api-docs return real 404 when missing (server cannot read localStorage).
  document.cookie = `${ADMIN_ACCESS_TOKEN_KEY}=${encodeURIComponent(accessToken)}; Path=/; SameSite=Lax`
}

function readStoredSession() {
  const ok = localStorage.getItem(ADMIN_AUTH_KEY) === 'true'
  const token = localStorage.getItem(ADMIN_ACCESS_TOKEN_KEY)
  if (!ok || !token) return { isAuthenticated: false, accessToken: null }
  const payload = decodeJwtPayload(token)
  if (!payload?.exp || payload.exp * 1000 < Date.now()) {
    clearAdminSession()
    return { isAuthenticated: false, accessToken: null }
  }
  if (isSuperAdminStaffPayload(payload)) {
    persistAdminSession(token)
    return { isAuthenticated: true, accessToken: token }
  }
  clearAdminSession()
  return { isAuthenticated: false, accessToken: null }
}

function isSidebarCollapsed() {
  return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true'
}

function setSidebarCollapsed(value) {
  localStorage.setItem(SIDEBAR_COLLAPSED_KEY, value ? 'true' : 'false')
}

function destroyActivePanel() {
  if (activePanel) {
    activePanel.destroy()
    activePanel = null
  }
}

function mountView(accessToken) {
  const main = document.getElementById('admin-main-content')
  if (!main) return
  destroyActivePanel()
  if (activeView === 'logs') {
    activePanel = createLogsView(accessToken, main)
  } else if (activeView === 'reservation') {
    activePanel = createReservationView(accessToken, main)
  } else if (activeView === 'invoice') {
    activePanel = createInvoiceView(accessToken, main)
  } else {
    activePanel = createBookingsView(accessToken, main)
  }
}

function renderDashboard(accessToken) {
  const root = document.getElementById('app')
  const collapsed = isSidebarCollapsed()
  root.innerHTML = `
    <div class="admin-layout${collapsed ? ' admin-layout--collapsed' : ''}${navOpen ? ' admin-layout--nav-open' : ''}" id="admin-layout">
      <header class="admin-topbar">
        <span class="admin-topbar__brand">
          <span class="admin-topbar__brand-plane" aria-hidden="true">${icon('plane')}</span>
          <span class="admin-topbar__brand-name">${escapeHtml(BRAND_NAME)}</span>
        </span>
        <button type="button" class="admin-topbar__toggle" id="nav-open" aria-label="Open menu">${icon('menu')}</button>
      </header>
      <aside class="admin-sidebar${collapsed ? ' admin-sidebar--collapsed' : ''}" id="admin-sidebar">
        <div class="admin-sidebar__head">
          <span class="admin-sidebar__brand">
            <span class="admin-sidebar__brand-plane" aria-hidden="true">${icon('plane')}</span>
            <span class="admin-sidebar__brand-name">${escapeHtml(BRAND_NAME)}</span>
          </span>
          <button type="button" class="admin-sidebar__toggle" id="sidebar-toggle" aria-label="${collapsed ? 'Expand sidebar' : 'Collapse sidebar'}">${icon('menu')}</button>
          <button type="button" class="admin-sidebar__close" id="nav-close" aria-label="Close menu">${icon('x')}</button>
        </div>
        <nav class="admin-sidebar__nav" aria-label="Admin sections">
          ${NAV_ITEMS.map((item) => {
            const isActive = !item.external && activeView === item.view
            return `
          <button type="button" class="admin-sidebar__item${isActive ? ' admin-sidebar__item--active' : ''}" data-view="${item.view}" title="${escapeHtml(item.label)}" aria-current="${isActive ? 'page' : 'false'}">
            <span class="admin-sidebar__item-icon">${icon(item.icon)}</span>
            <span class="admin-sidebar__item-label">${escapeHtml(item.label)}</span>
            ${item.external ? `<span class="admin-sidebar__item-external">${icon('external')}</span>` : ''}
          </button>`
          }).join('')}
        </nav>
        <div class="admin-sidebar__foot">
          <button type="button" class="admin-sidebar__logout" id="admin-logout">
            ${icon('logout')}
            <span class="admin-sidebar__logout-label">Log out</span>
          </button>
        </div>
      </aside>
      <div class="admin-main" id="admin-main-content"></div>
    </div>`

  const layout = document.getElementById('admin-layout')

  const openNav = () => {
    navOpen = true
    layout?.classList.add('admin-layout--nav-open')
  }
  const closeNav = () => {
    navOpen = false
    layout?.classList.remove('admin-layout--nav-open')
  }

  document.getElementById('nav-open')?.addEventListener('click', openNav)
  document.getElementById('nav-close')?.addEventListener('click', closeNav)

  document.getElementById('sidebar-toggle')?.addEventListener('click', () => {
    const next = !isSidebarCollapsed()
    setSidebarCollapsed(next)
    document.getElementById('admin-sidebar')?.classList.toggle('admin-sidebar--collapsed', next)
    layout?.classList.toggle('admin-layout--collapsed', next)
    document.getElementById('sidebar-toggle')?.setAttribute('aria-label', next ? 'Expand sidebar' : 'Collapse sidebar')
  })

  root.querySelectorAll('[data-view]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.view
      if (!view) return
      const item = NAV_ITEMS.find((entry) => entry.view === view)
      if (item?.external) {
        const token = localStorage.getItem(ADMIN_ACCESS_TOKEN_KEY)
        if (!token) {
          clearAdminSession()
          renderLogin('Sign in again to open API docs.')
          return
        }
        persistAdminSession(token)
        window.open(item.external, '_blank', 'noopener,noreferrer')
        closeNav()
        return
      }
      if (view === activeView) {
        closeNav()
        return
      }
      activeView = view
      navOpen = false
      renderDashboard(accessToken)
    })
  })

  document.getElementById('admin-logout')?.addEventListener('click', () => {
    navOpen = false
    clearAdminSession()
    destroyActivePanel()
    renderLogin()
  })

  mountView(accessToken)
}

function renderLogin(errorMessage = '') {
  destroyActivePanel()
  const root = document.getElementById('app')
  const locked = isLoginLocked()
  const disabledAttr = locked ? ' disabled' : ''
  root.innerHTML = `
    <main class="admin-portal-page">
      <div class="admin-portal-inner">
        <section class="admin-card admin-card--login">
          <div class="admin-login-brand">
            <img
              class="admin-login-brand__logo"
              src="assets/logo.png"
              alt=""
              width="72"
              height="72"
              decoding="async"
            />
            <p class="admin-brand-title">${escapeHtml(BRAND_NAME)}</p>
          </div>
          <h1 class="admin-title admin-title--login">Admin Login</h1>
          <p class="admin-subtitle admin-subtitle--login">Sign in as super admin to continue.</p>
          <form id="admin-login-form" class="admin-form admin-form--login${locked ? ' admin-form--locked' : ''}" autocomplete="off">
            <label class="admin-field-label" for="admin-email">Email</label>
            <input id="admin-email" name="admin-email-no-autofill" type="email" placeholder="Enter admin email" required class="admin-input" autocomplete="off" value="${escapeHtml(loginEmailDraft)}"${disabledAttr} />
            <label class="admin-field-label" for="admin-password">Password</label>
            <div class="admin-password-wrap">
              <input id="admin-password" name="admin-password-no-autofill" type="${showPassword ? 'text' : 'password'}" placeholder="Enter password" required class="admin-input admin-input--password" autocomplete="off"${disabledAttr} />
              <button type="button" class="admin-password-toggle" id="password-toggle" aria-label="${showPassword ? 'Hide password' : 'Show password'}"${disabledAttr}>${showPassword ? icon('eyeOff') : icon('eyeOn')}</button>
            </div>
            ${errorMessage ? `<p class="admin-error">${escapeHtml(errorMessage)}</p>` : ''}
            <button type="submit" class="admin-button" id="login-submit"${disabledAttr}>${locked ? 'Account Locked' : 'Sign In to Admin'}</button>
          </form>
        </section>
      </div>
    </main>`

  document.getElementById('password-toggle')?.addEventListener('click', () => {
    if (isLoginLocked()) return
    showPassword = !showPassword
    loginEmailDraft = document.getElementById('admin-email')?.value || loginEmailDraft
    renderLogin(errorMessage)
    document.getElementById('admin-email')?.focus()
  })

  document.getElementById('admin-email')?.addEventListener('input', (event) => {
    loginEmailDraft = event.target.value
  })

  document.getElementById('admin-login-form')?.addEventListener('submit', async (event) => {
    event.preventDefault()
    if (isLoginLocked()) return
    const email = document.getElementById('admin-email')?.value?.trim().toLowerCase() || ''
    const password = document.getElementById('admin-password')?.value || ''
    loginEmailDraft = email
    const submitBtn = document.getElementById('login-submit')
    if (submitBtn) {
      submitBtn.disabled = true
      submitBtn.textContent = 'Signing in…'
    }
    try {
      const res = await fetch(apiUrl('/auth/signin'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!res.ok) {
        const text = await res.text()
        let message = text.trim() || `Sign in failed (${res.status})`
        try {
          const parsed = parseJsonErrorBody(JSON.parse(text))
          if (parsed) message = parsed
        } catch {
          /* ignore */
        }
        const isLockout =
          res.status === 429 ||
          /locked|too many failed/i.test(message)
        if (isLockout) {
          const retryAfter = Number.parseInt(res.headers.get('Retry-After') || '', 10)
          lockLoginFor(Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : 15 * 60, email)
        }
        renderLogin(message)
        return
      }
      clearLoginLockTimer()
      loginLockedUntil = 0
      loginEmailDraft = ''
      const data = await res.json()
      const accessToken = data.access_token
      if (!accessToken) {
        renderLogin('Server did not return an access token.')
        return
      }
      const payload = decodeJwtPayload(accessToken)
      if (!isSuperAdminStaffPayload(payload)) {
        renderLogin(
          'This account is not a super admin. Use python -m scripts.create_admin (answer y to super admin) or python -m scripts.promote_super_admin.',
        )
        return
      }
      persistAdminSession(accessToken)
      renderDashboard(accessToken)
    } catch {
      renderLogin(`Could not reach the API at ${apiUrl('/auth/signin')}. Check that the server is running.`)
    }
  })
}

function boot() {
  const session = readStoredSession()
  if (session.isAuthenticated && session.accessToken) {
    renderDashboard(session.accessToken)
  } else {
    renderLogin()
  }
}

boot()
