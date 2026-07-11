import { API_V1_PREFIX } from './config.js'

export function apiUrl(path) {
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${API_V1_PREFIX}${normalized}`
}

export function parseJsonErrorBody(body) {
  if (!body || typeof body !== 'object') return null
  if (typeof body.detail === 'string' && body.detail.trim()) return body.detail
  if (Array.isArray(body.detail)) {
    const lines = body.detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object' && 'msg' in item) return String(item.msg)
        return String(item)
      })
      .filter(Boolean)
    if (lines.length) return lines.join('\n')
  }
  if (Array.isArray(body.message)) return body.message.map(String).join('\n')
  if (typeof body.message === 'string' && body.message.trim()) return body.message
  return null
}

export async function readApiErrorMessage(res) {
  const text = await res.text()
  try {
    const parsed = parseJsonErrorBody(JSON.parse(text))
    if (parsed) return parsed
  } catch {
    /* ignore */
  }
  return text.trim() || `Request failed (${res.status})`
}

export async function authorizedJson(path, token) {
  const res = await fetch(apiUrl(path), {
    headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(await readApiErrorMessage(res))
  return res.json()
}

export async function authorizedJsonDelete(path, token) {
  const res = await fetch(apiUrl(path), {
    method: 'DELETE',
    headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(await readApiErrorMessage(res))
}

export function decodeJwtPayload(accessToken) {
  const parts = accessToken.split('.')
  if (parts.length < 2 || !parts[1]) return null
  try {
    const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const pad = b64.length % 4 === 0 ? '' : '='.repeat(4 - (b64.length % 4))
    return JSON.parse(atob(b64 + pad))
  } catch {
    return null
  }
}

export function isSuperAdminStaffPayload(p) {
  return Boolean(p && p.typ === 'user' && p.is_admin === true && p.is_super_admin === true)
}

export async function authorizedPostJson(path, body, token) {
  const res = await fetch(apiUrl(path), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await readApiErrorMessage(res))
  return res.json()
}

export const bookingsApi = {
  list(token, params = {}) {
    const page = params.page ?? 1
    const pageSize = params.pageSize ?? 20
    const q = new URLSearchParams({ page: String(page), pageSize: String(pageSize) })
    if (params.timeScope) q.set('timeScope', params.timeScope)
    if (params.scheduledOn) q.set('scheduledOn', params.scheduledOn)
    if (params.bookingReference?.trim()) q.set('bookingReference', params.bookingReference.trim())
    return authorizedJson(`/bookings?${q}`, token)
  },
  getByUuid(token, uuid) {
    return authorizedJson(`/bookings/${uuid}`, token)
  },
  create(token, body) {
    return authorizedPostJson('/bookings', body, token)
  },
  removeReservation(token, uuid) {
    return authorizedJsonDelete(`/bookings/${uuid}/remove`, token)
  },
}

export const adminInvoicesApi = {
  suggestedPrice(token, bookingReference) {
    const q = new URLSearchParams({ bookingReference })
    return authorizedJson(`/admin/invoices/suggested-price?${q}`, token)
  },
  async generatePdf(token, body) {
    const res = await fetch(apiUrl('/admin/invoices/pdf'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/pdf',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error(await readApiErrorMessage(res))
    const disposition = res.headers.get('Content-Disposition') || ''
    const match = /filename="?([^"]+)"?/.exec(disposition)
    const filename = match?.[1] || 'invoice.pdf'
    const blob = await res.blob()
    return { blob, filename }
  },
}

export const logsApi = {
  list(token, params = {}) {
    const q = new URLSearchParams()
    if (params.limit) q.set('limit', String(params.limit))
    if (params.file) q.set('file', params.file)
    const suffix = q.toString() ? `?${q}` : ''
    return authorizedJson(`/logs${suffix}`, token)
  },
  listFiles(token) {
    return authorizedJson('/logs/files', token)
  },
}
