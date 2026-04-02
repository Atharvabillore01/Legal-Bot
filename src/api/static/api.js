// ── Shared API client ────────────────────────────────────────────────────────

const API = (() => {
  const BASE = '';  // same origin

  function getToken() { return localStorage.getItem('access_token'); }
  function getRefresh() { return localStorage.getItem('refresh_token'); }

  function setTokens(access, refresh) {
    localStorage.setItem('access_token', access);
    if (refresh) localStorage.setItem('refresh_token', refresh);
  }

  function clearTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }

  function requireAuth() {
    if (!getToken()) { window.location.href = '/app/index.html'; return false; }
    return true;
  }

  async function request(method, path, body, isForm) {
    const token = getToken();
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (!isForm) headers['Content-Type'] = 'application/json';

    const opts = { method, headers };
    if (body) opts.body = isForm ? body : JSON.stringify(body);

    let res = await fetch(BASE + path, opts);

    // Try refresh if 401
    if (res.status === 401 && getRefresh()) {
      try {
        const r = await fetch(BASE + '/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: getRefresh() }),
        });
        if (r.ok) {
          const data = await r.json();
          setTokens(data.access_token, null);
          headers['Authorization'] = `Bearer ${data.access_token}`;
          res = await fetch(BASE + path, { method, headers, body: opts.body });
        } else {
          clearTokens();
          window.location.href = '/app/index.html';
          return;
        }
      } catch (e) {
        clearTokens();
        window.location.href = '/app/index.html';
        return;
      }
    }

    if (res.status === 401) {
      clearTokens();
      window.location.href = '/app/index.html';
      return;
    }

    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw { status: res.status, detail: data.detail || 'Request failed' };
    return data;
  }

  return {
    getToken, setTokens, clearTokens, requireAuth,
    get: (p) => request('GET', p),
    post: (p, b) => request('POST', p, b),
    postForm: (p, fd) => request('POST', p, fd, true),
    del: (p) => request('DELETE', p),

    // Auth
    login: (email, password) => request('POST', '/auth/login', { email, password }),
    register: (email, password, fullName) => request('POST', '/auth/register', { email, password, full_name: fullName }),
    logout: () => request('POST', '/auth/logout', { refresh_token: getRefresh() }),
    me: () => request('GET', '/auth/me'),

    // Documents
    listDocuments: (page=1) => request('GET', `/documents?page=${page}&page_size=20`),
    deleteDocument: (id) => request('DELETE', `/documents/${id}`),
    resetStuck: () => request('POST', '/ingest/reset-stuck'),

    // Upload
    uploadDocument: (file, jurisdiction, authorityLevel='reference') => {
      const fd = new FormData();
      fd.append('file', file);
      if (jurisdiction) fd.append('jurisdiction', jurisdiction);
      fd.append('authority_level', authorityLevel);
      return request('POST', '/ingest', fd, true);
    },

    // Query
    query: (q, k=7, jurisdiction, docIds) => request('POST', '/query', {
      query: q, k,
      jurisdiction: jurisdiction || undefined,
      doc_ids: docIds && docIds.length ? docIds : undefined,
      detect_contradictions: true,
      rerank: true,
    }),
  };
})();

// ── Toast notifications ──────────────────────────────────────────────────────

function toast(msg, type = 'default', duration = 3500) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icons = { success: '✓', error: '✕', default: 'ℹ' };
  el.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateX(60px)'; el.style.transition = '0.3s'; setTimeout(() => el.remove(), 300); }, duration);
}

// ── Markdown → HTML (minimal) ────────────────────────────────────────────────

function renderMarkdown(text) {
  if (!text) return '';

  // Normalize inline markdown headings/bullets (LLM sometimes outputs them inline)
  text = text
    .replace(/(#{1,6})\s+/g, '\n\n$1 ')
    .replace(/\s+-\s+(?=[A-Z\w])/g, '\n- ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  // Process citation markers before markdown
  const citations = {};
  let citeIndex = 0;
  text = text.replace(/\[\[CITE:([^\]]+)\]\]/g, (_, rawId) => {
    const id = rawId.split(',')[0].trim();
    if (!citations[id]) citations[id] = ++citeIndex;
    return `[[__CITE__${citations[id]}__${id}__]]`;
  });

  // Escape HTML
  text = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

  // Headings
  text = text.replace(/^#{6}\s+(.+)$/gm, '<h6>$1</h6>');
  text = text.replace(/^#{5}\s+(.+)$/gm, '<h5>$1</h5>');
  text = text.replace(/^#{4}\s+(.+)$/gm, '<h4>$1</h4>');
  text = text.replace(/^#{3}\s+(.+)$/gm, '<h3>$1</h3>');
  text = text.replace(/^#{2}\s+(.+)$/gm, '<h2>$1</h2>');
  text = text.replace(/^#{1}\s+(.+)$/gm, '<h1>$1</h1>');

  // Bold & italic
  text = text.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Lists
  text = text.replace(/^[\-\*]\s+(.+)$/gm, '<li>$1</li>');
  text = text.replace(/^(\d+)\.\s+(.+)$/gm, '<li>$2</li>');
  text = text.replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`);

  // Paragraphs
  const lines = text.split(/\n\n+/);
  text = lines.map(block => {
    block = block.trim();
    if (!block) return '';
    if (/^<(h[1-6]|ul|ol|li|blockquote)/.test(block)) return block;
    return `<p>${block.replace(/\n/g, '<br>')}</p>`;
  }).join('\n');

  // Restore citations
  text = text.replace(/\[\[__CITE__(\d+)__([^\]]+)__\]\]/g, (_, num, id) => {
    return `<sup class="cite" data-chunk-id="${id}" title="Source chunk ${id}">[${num}]</sup>`;
  });

  return text;
}
