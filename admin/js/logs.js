import { logsApi } from './api.js'
import { escapeHtml, icon } from './icons.js'

export function createLogsView(accessToken, container) {
  let loading = false
  let error = null
  let lines = []
  let files = []
  let activeFile = ''
  let lineCount = 0
  let limit = 200
  let destroyed = false

  async function loadLogs() {
    if (destroyed) return
    loading = true
    error = null
    render()
    try {
      const res = await logsApi.list(accessToken, {
        limit,
        file: activeFile || undefined,
      })
      if (destroyed) return
      lines = res.lines || []
      lineCount = res.lineCount || lines.length
      files = res.files || []
      if (!activeFile && res.file?.name) activeFile = res.file.name
      error = null
    } catch (e) {
      if (destroyed) return
      error = e instanceof Error ? e.message : 'Could not load logs.'
      lines = []
    } finally {
      loading = false
      render()
    }
  }

  function render() {
    const fileOptions = files
      .map(
        (f) =>
          `<option value="${escapeHtml(f.name)}"${f.name === activeFile ? ' selected' : ''}>${escapeHtml(f.name)}${f.active ? ' (active)' : ''}</option>`,
      )
      .join('')

    const body = loading
      ? `<div class="admin-logs-shell__loading">${icon('loader')}</div>`
      : error
        ? `<p class="admin-logs-shell__error">${escapeHtml(error)}</p>`
        : `<p class="admin-logs-shell__meta">Showing last ${lineCount} line${lineCount === 1 ? '' : 's'}${activeFile ? ` from ${escapeHtml(activeFile)}` : ''}</p>
           <pre class="admin-logs-shell__pre">${lines.length ? escapeHtml(lines.join('\n')) : 'No log lines found.'}</pre>`

    container.innerHTML = `
      <div class="admin-logs-shell">
        <header class="admin-logs-shell__header">
          <h1 class="admin-logs-shell__title">Application Logs</h1>
          <div class="admin-logs-shell__tools">
            ${files.length ? `<select class="admin-logs-shell__select" data-input="file">${fileOptions}</select>` : ''}
            <button type="button" class="admin-bookings-btn admin-bookings-btn--primary" data-action="refresh" ${loading ? 'disabled' : ''}>Refresh</button>
          </div>
        </header>
        <div class="admin-logs-shell__body">${body}</div>
      </div>`

    const fileEl = container.querySelector('[data-input="file"]')
    if (fileEl) {
      fileEl.addEventListener('change', (e) => {
        activeFile = e.target.value
        void loadLogs()
      })
    }
  }

  container.addEventListener('click', (event) => {
    const target = event.target.closest('[data-action="refresh"]')
    if (target) void loadLogs()
  })

  void loadLogs()

  return {
    destroy() {
      destroyed = true
      container.innerHTML = ''
    },
  }
}
