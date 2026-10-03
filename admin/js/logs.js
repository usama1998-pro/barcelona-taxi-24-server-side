import { logsApi } from './api.js'
import { escapeHtml, icon } from './icons.js'

const LEVELS = ['ERROR', 'WARNING', 'INFO', 'DEBUG']

const LEVEL_ALIASES = {
  ERR: 'ERROR',
  ERROR: 'ERROR',
  CRITICAL: 'ERROR',
  FATAL: 'ERROR',
  WARN: 'WARNING',
  WARNING: 'WARNING',
  INFO: 'INFO',
  DEBUG: 'DEBUG',
}

// Prefer longer level names first so WARN does not steal WARNING.
const LINE_RE =
  /^(\S+)\s+(CRITICAL|WARNING|ERROR|DEBUG|INFO|FATAL|WARN|ERR)\s+\[([^\]]+)\]\s*(.*)$/i

const STACK_RE =
  /^\s*(Traceback \(most recent call last\):|File ".*", line \d+|^\s+\^+\s*$|[A-Za-z_][\w.]*(Error|Exception|Exit):)/

const HTTP_STATUS_RE = /"\s*[A-Z]+ [^"]*"\s+(\d{3})\b/

function normalizeLevel(raw) {
  const key = String(raw || '')
    .trim()
    .toUpperCase()
  return LEVEL_ALIASES[key] || 'INFO'
}

function looksLikeStack(line) {
  const text = String(line || '')
  if (/^\s*Traceback \(most recent call last\):/.test(text)) return true
  if (/^\s*File ".+", line \d+/.test(text)) return true
  if (/^\s{2,}\S/.test(text) && /(?:Error|Exception|raise |await |return |File )/.test(text)) {
    return true
  }
  if (/^[A-Za-z_][\w.]*(?:Error|Exception)\b/.test(text.trim())) return true
  return false
}

function inferLevel({ level, logger, message, extras }) {
  let next = normalizeLevel(level)
  const blob = [message, ...(extras || [])].join('\n')
  const statusMatch = blob.match(HTTP_STATUS_RE)
  if (statusMatch) {
    const code = Number(statusMatch[1])
    if (code >= 500) next = 'ERROR'
    else if (code >= 400 && next === 'INFO') next = 'WARNING'
  }
  if (
    /exception in asgi application/i.test(blob) ||
    /traceback \(most recent call last\)/i.test(blob) ||
    /\b(RuntimeError|ValueError|TypeError|HTTPException|Error)\b/.test(blob)
  ) {
    next = 'ERROR'
  }
  if (String(logger || '').toLowerCase().endsWith('.error') && /exception|traceback|error/i.test(blob)) {
    next = 'ERROR'
  }
  return next
}

function parseLogLines(lines) {
  const entries = []
  for (const line of lines) {
    const text = String(line)
    const match = text.match(LINE_RE)
    if (match) {
      entries.push({
        time: match[1],
        level: normalizeLevel(match[2]),
        logger: match[3],
        message: match[4] || '',
        extras: [],
      })
      continue
    }
    if (entries.length) {
      entries[entries.length - 1].extras.push(text)
      continue
    }
    // Orphan stack / continuation at the start of the buffer.
    entries.push({
      time: '',
      level: looksLikeStack(text) || STACK_RE.test(text) ? 'ERROR' : 'INFO',
      logger: '',
      message: text,
      extras: [],
    })
  }

  for (const entry of entries) {
    entry.level = inferLevel(entry)
  }
  return entries
}

function levelClass(level) {
  return `admin-logs-row--${String(level || 'INFO').toLowerCase()}`
}

export function createLogsView(accessToken, container) {
  let loading = false
  let error = null
  let lines = []
  let entries = []
  let files = []
  let activeFile = ''
  let lineCount = 0
  let limit = 200
  let levelFilter = 'ALL'
  let searchQuery = ''
  let destroyed = false

  function filteredEntries() {
    const q = searchQuery.trim().toLowerCase()
    return entries.filter((entry) => {
      if (levelFilter !== 'ALL' && entry.level !== levelFilter) return false
      if (!q) return true
      const hay = [
        entry.time,
        entry.level,
        entry.logger,
        entry.message,
        ...(entry.extras || []),
      ]
        .join('\n')
        .toLowerCase()
      return hay.includes(q)
    })
  }

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
      // Newest entries first (API returns chronological tail).
      entries = parseLogLines(lines).reverse()
      lineCount = res.lineCount || lines.length
      files = res.files || []
      if (!activeFile && res.file?.name) activeFile = res.file.name
      error = null
    } catch (e) {
      if (destroyed) return
      error = e instanceof Error ? e.message : 'Could not load logs.'
      lines = []
      entries = []
    } finally {
      loading = false
      render()
      const list = container.querySelector('[data-logs-list]')
      if (list) list.scrollTop = 0
    }
  }

  function renderLevelFilters() {
    const counts = { ALL: entries.length, ERROR: 0, WARNING: 0, INFO: 0, DEBUG: 0 }
    for (const entry of entries) {
      if (counts[entry.level] != null) counts[entry.level] += 1
    }
    const chips = ['ALL', ...LEVELS]
      .map((level) => {
        const active = levelFilter === level ? ' is-active' : ''
        const label = level === 'ALL' ? 'All' : level
        return `<button type="button" class="admin-logs-filter${active} admin-logs-filter--${level.toLowerCase()}" data-action="level" data-level="${level}">${label}<span class="admin-logs-filter__count">${counts[level] || 0}</span></button>`
      })
      .join('')
    return `<div class="admin-logs-filters" role="group" aria-label="Filter by level">${chips}</div>`
  }

  function renderEntry(entry) {
    const extras = (entry.extras || [])
      .map((line) => `<div class="admin-logs-row__extra">${escapeHtml(line)}</div>`)
      .join('')
    return `
      <article class="admin-logs-row ${levelClass(entry.level)}">
        <div class="admin-logs-row__rail" aria-hidden="true"></div>
        <div class="admin-logs-row__content">
          <div class="admin-logs-row__meta">
            <span class="admin-logs-row__level">${escapeHtml(entry.level)}</span>
            ${entry.time ? `<time class="admin-logs-row__time">${escapeHtml(entry.time)}</time>` : ''}
            ${entry.logger ? `<span class="admin-logs-row__logger">${escapeHtml(entry.logger)}</span>` : ''}
          </div>
          <pre class="admin-logs-row__message">${escapeHtml(entry.message || '')}</pre>
          ${extras ? `<div class="admin-logs-row__extras">${extras}</div>` : ''}
        </div>
      </article>`
  }

  function renderList() {
    const visible = filteredEntries()
    if (!entries.length) {
      return `<p class="admin-logs-shell__empty">No log lines found.</p>`
    }
    if (!visible.length) {
      return `<p class="admin-logs-shell__empty">No log entries match the current filters.</p>`
    }
    return `
      <div class="admin-logs-list" data-logs-list>
        ${visible.map((entry) => renderEntry(entry)).join('<hr class="admin-logs-divider" />')}
      </div>`
  }

  function render() {
    const fileOptions = files
      .map(
        (f) =>
          `<option value="${escapeHtml(f.name)}"${f.name === activeFile ? ' selected' : ''}>${escapeHtml(f.name)}${f.active ? ' (active)' : ''}</option>`,
      )
      .join('')

    const visibleCount = loading || error ? 0 : filteredEntries().length

    const body = loading
      ? `<div class="admin-logs-shell__loading">${icon('loader')}</div>`
      : error
        ? `<p class="admin-logs-shell__error">${escapeHtml(error)}</p>`
        : `
          <div class="admin-logs-toolbar">
            ${renderLevelFilters()}
            <label class="admin-logs-search">
              <span class="admin-logs-search__label">Search</span>
              <input
                type="search"
                class="admin-logs-search__input"
                data-input="search"
                placeholder="Filter by text, logger, message…"
                value="${escapeHtml(searchQuery)}"
              />
            </label>
          </div>
          <p class="admin-logs-shell__meta">
            Showing ${visibleCount} of ${entries.length} entr${entries.length === 1 ? 'y' : 'ies'}
            (last ${lineCount} raw line${lineCount === 1 ? '' : 's'}${activeFile ? ` from ${escapeHtml(activeFile)}` : ''})
          </p>
          ${renderList()}
        `

    container.innerHTML = `
      <div class="admin-logs-shell">
        <header class="admin-logs-shell__header">
          <h1 class="admin-logs-shell__title">Application Logs</h1>
          <div class="admin-logs-shell__tools">
            ${files.length ? `<select class="admin-logs-shell__select" data-input="file" aria-label="Log file">${fileOptions}</select>` : ''}
            <select class="admin-logs-shell__select" data-input="limit" aria-label="Line limit">
              ${[100, 200, 500, 1000]
                .map(
                  (n) =>
                    `<option value="${n}"${n === limit ? ' selected' : ''}>Last ${n}</option>`,
                )
                .join('')}
            </select>
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

    const limitEl = container.querySelector('[data-input="limit"]')
    if (limitEl) {
      limitEl.addEventListener('change', (e) => {
        limit = Number(e.target.value) || 200
        void loadLogs()
      })
    }

    const searchEl = container.querySelector('[data-input="search"]')
    if (searchEl) {
      searchEl.addEventListener('input', (e) => {
        searchQuery = e.target.value
        const meta = container.querySelector('.admin-logs-shell__meta')
        const listHost = container.querySelector('.admin-logs-shell__body')
        if (!listHost) return
        const toolbar = listHost.querySelector('.admin-logs-toolbar')
        const nextList = renderList()
        const oldList = listHost.querySelector('[data-logs-list], .admin-logs-shell__empty')
        if (oldList) {
          oldList.outerHTML = nextList
        } else if (toolbar) {
          toolbar.insertAdjacentHTML('afterend', nextList)
        }
        if (meta) {
          const visibleCount = filteredEntries().length
          meta.textContent = `Showing ${visibleCount} of ${entries.length} entr${entries.length === 1 ? 'y' : 'ies'} (last ${lineCount} raw line${lineCount === 1 ? '' : 's'}${activeFile ? ` from ${activeFile}` : ''})`
        }
      })
    }
  }

  container.addEventListener('click', (event) => {
    const refreshBtn = event.target.closest('[data-action="refresh"]')
    if (refreshBtn) {
      void loadLogs()
      return
    }
    const levelBtn = event.target.closest('[data-action="level"]')
    if (levelBtn) {
      levelFilter = levelBtn.getAttribute('data-level') || 'ALL'
      render()
    }
  })

  void loadLogs()

  return {
    destroy() {
      destroyed = true
      container.innerHTML = ''
    },
  }
}
