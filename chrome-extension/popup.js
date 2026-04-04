'use strict';

const DEFAULT_SERVER = 'http://localhost:8000';

// ── State ──────────────────────────────────────────────────────────────────
let state = {
  token: null,
  serverUrl: DEFAULT_SERVER,
  languages: [],
  selectedText: '',
  pendingVerificationToken: null, // token held during email verification
};

// ── Storage helpers ────────────────────────────────────────────────────────
function load(keys) {
  return new Promise(resolve => chrome.storage.local.get(keys, resolve));
}
function save(data) {
  return new Promise(resolve => chrome.storage.local.set(data, resolve));
}

// ── API helpers ────────────────────────────────────────────────────────────
async function api(path, options = {}) {
  const url = state.serverUrl + path;
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (state.token) headers['Authorization'] = 'Token ' + state.token;

  let resp;
  try {
    resp = await fetch(url, { ...options, headers });
  } catch (e) {
    throw new Error(`Cannot reach server at ${state.serverUrl}. Is Django running? (${e.message})`);
  }

  let data;
  try { data = await resp.json(); } catch { data = {}; }

  if (!resp.ok) {
    // Stale/invalid token — clear it and go back to login
    if (resp.status === 401) {
      state.token = null;
      await save({ token: null });
      showScreen('screen-login');
    }
    const msg = data.detail || data.error || data.message
      || (typeof data === 'object' ? Object.values(data).flat().join(' ') : String(data))
      || `HTTP ${resp.status}`;
    throw new Error(msg);
  }
  return data;
}

// ── Screen helpers ─────────────────────────────────────────────────────────
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.add('hidden'));
  document.getElementById(id).classList.remove('hidden');
}

function showError(elId, msg) {
  const el = document.getElementById(elId);
  el.textContent = msg;
  el.classList.remove('hidden');
}
function hideAlert(elId) {
  document.getElementById(elId).classList.add('hidden');
}

function setLoading(btn, loading) {
  const text = btn.querySelector('.btn-text');
  const spinner = btn.querySelector('.btn-spinner');
  btn.disabled = loading;
  if (text) text.classList.toggle('hidden', loading);
  if (spinner) spinner.classList.toggle('hidden', !loading);
}

// ── Init ───────────────────────────────────────────────────────────────────
async function init() {
  // Show "starting" screen while we ensure the server is up
  showScreen('screen-starting');

  const result = await chrome.runtime.sendMessage({ type: 'ENSURE_SERVER' });
  if (!result?.ok) {
    document.getElementById('starting-status').textContent =
      '❌ Could not start server: ' + (result?.error || 'unknown error');
    return;
  }

  const stored = await load(['token', 'serverUrl', 'selectedText', 'lastBatchResult']);
  state.token = stored.token || null;
  state.serverUrl = (stored.serverUrl || DEFAULT_SERVER).replace(/\/$/, '');
  state.selectedText = stored.selectedText || '';
  await save({ selectedText: '' });

  if (state.token) {
    showScreen('screen-main');
    await loadLanguagesAndProfile();
    prefillSelectedText();

    // If the background worker finished a batch while the popup was closed, show it
    if (stored.lastBatchResult) {
      await save({ lastBatchResult: null });
      showResultScreen(stored.lastBatchResult);
    }
  } else {
    showScreen('screen-login');
  }
}

// ── Login ──────────────────────────────────────────────────────────────────
document.getElementById('login-form').addEventListener('submit', async e => {
  e.preventDefault();
  hideAlert('login-error');
  const btn = document.getElementById('login-btn');
  setLoading(btn, true);

  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;

  try {
    const data = await api('/api/v1/auth/login/', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    state.token = data.token;
    await save({ token: state.token });
    showScreen('screen-main');
    await loadLanguagesAndProfile();
    prefillSelectedText();
  } catch (err) {
    showError('login-error', err.message);
  } finally {
    setLoading(btn, false);
  }
});

// ── Logout ─────────────────────────────────────────────────────────────────
document.getElementById('logout-btn').addEventListener('click', async e => {
  e.preventDefault();
  try { await api('/api/v1/auth/logout/', { method: 'POST' }); } catch {}
  state.token = null;
  await save({ token: null });
  showScreen('screen-login');
});

// ── Register ───────────────────────────────────────────────────────────────
document.getElementById('go-to-register').addEventListener('click', e => {
  e.preventDefault();
  hideAlert('register-error');
  showScreen('screen-register');
});

document.getElementById('back-from-register').addEventListener('click', () => {
  showScreen('screen-login');
});

document.getElementById('register-form').addEventListener('submit', async e => {
  e.preventDefault();
  hideAlert('register-error');
  const btn = document.getElementById('register-btn');
  setLoading(btn, true);

  const username = document.getElementById('reg-username').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;
  const password_confirm = document.getElementById('reg-password-confirm').value;

  if (password !== password_confirm) {
    showError('register-error', 'Passwords do not match.');
    setLoading(btn, false);
    return;
  }

  try {
    const data = await api('/api/v1/auth/register/', {
      method: 'POST',
      body: JSON.stringify({ username, email, password, password_confirm }),
    });

    // Hold token for verification step (not yet authenticated)
    state.pendingVerificationToken = data.token;

    // Show verify screen
    document.getElementById('verify-email-hint').textContent =
      `We sent a 6-digit code to ${email}. Enter it below.`;
    hideAlert('verify-error');
    hideAlert('verify-success');
    document.getElementById('verify-code').value = '';
    showScreen('screen-verify');

  } catch (err) {
    showError('register-error', err.message);
  } finally {
    setLoading(btn, false);
  }
});

// ── Email verification ─────────────────────────────────────────────────────
document.getElementById('back-from-verify').addEventListener('click', () => {
  showScreen('screen-register');
});

document.getElementById('verify-form').addEventListener('submit', async e => {
  e.preventDefault();
  hideAlert('verify-error');
  const btn = document.getElementById('verify-btn');
  setLoading(btn, true);

  const code = document.getElementById('verify-code').value.trim();

  // Temporarily use the pending token for this request
  const savedToken = state.token;
  state.token = state.pendingVerificationToken;

  try {
    await api('/api/v1/auth/verify-email/', {
      method: 'POST',
      body: JSON.stringify({ code }),
    });

    // Verification succeeded — log in for real
    state.token = state.pendingVerificationToken;
    state.pendingVerificationToken = null;
    await save({ token: state.token });

    showScreen('screen-main');
    await loadLanguagesAndProfile();
  } catch (err) {
    state.token = savedToken; // restore
    showError('verify-error', err.message);
  } finally {
    setLoading(btn, false);
  }
});

document.getElementById('resend-code-btn').addEventListener('click', async e => {
  e.preventDefault();
  hideAlert('verify-error');
  const savedToken = state.token;
  state.token = state.pendingVerificationToken;
  try {
    await api('/api/v1/auth/resend-verification/', { method: 'POST' });
    document.getElementById('verify-success').textContent = 'Code resent! Check your email.';
    document.getElementById('verify-success').classList.remove('hidden');
    setTimeout(() => hideAlert('verify-success'), 4000);
  } catch (err) {
    showError('verify-error', err.message);
  } finally {
    state.token = savedToken;
  }
});

// ── Languages + Profile ────────────────────────────────────────────────────
async function loadLanguagesAndProfile() {
  // Load languages first (public endpoint — no auth needed)
  try {
    state.languages = await api('/api/v1/languages/');
    populateLanguageSelects();
  } catch (err) {
    showError('main-error', 'Could not load languages: ' + err.message);
    return;
  }

  // Load profile for default language prefs (requires auth)
  if (state.token) {
    try {
      const profile = await api('/api/v1/auth/profile/');
      applyLanguageDefaults(profile);
    } catch {
      // Profile fetch failed (e.g. stale token) — fall back to local prefs
      const stored = await load(['targetLang', 'explLang']);
      if (stored.targetLang) document.getElementById('target-language').value = stored.targetLang;
      if (stored.explLang) document.getElementById('explanation-language').value = stored.explLang;
    }
  }
}

function populateLanguageSelects() {
  const target = document.getElementById('target-language');
  const expl = document.getElementById('explanation-language');

  target.innerHTML = '';
  expl.innerHTML = '<option value="">Auto</option>';

  state.languages.forEach(lang => {
    target.add(new Option(lang.name, lang.code));
    expl.add(new Option(lang.name, lang.code));
  });
}

async function applyLanguageDefaults(profile) {
  // Use profile defaults first; fall back to locally saved prefs
  const stored = await load(['targetLang', 'explLang']);

  const targetCode = profile.default_target_language_code || stored.targetLang || '';
  const explCode = profile.default_explanation_language_code || stored.explLang || '';

  if (targetCode) document.getElementById('target-language').value = targetCode;
  if (explCode) document.getElementById('explanation-language').value = explCode;
}

// ── Selected text from page ────────────────────────────────────────────────
function prefillSelectedText() {
  if (!state.selectedText) return;
  const preview = document.getElementById('selected-text-preview');
  preview.textContent = '📋 ' + state.selectedText.substring(0, 60) + (state.selectedText.length > 60 ? '…' : '');
  document.getElementById('selected-text-badge').classList.remove('hidden');
}

document.getElementById('add-selected-btn').addEventListener('click', async () => {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => window.getSelection().toString().trim(),
    });
    const text = results[0]?.result || '';
    if (!text) {
      showError('main-error', 'No text selected on the page.');
      setTimeout(() => hideAlert('main-error'), 3000);
      return;
    }
    appendToVocab(text);
  } catch (err) {
    showError('main-error', 'Cannot read selection: ' + err.message);
    setTimeout(() => hideAlert('main-error'), 3000);
  }
});

document.getElementById('clear-selected').addEventListener('click', () => {
  state.selectedText = '';
  document.getElementById('selected-text-badge').classList.add('hidden');
});

function appendToVocab(text) {
  const ta = document.getElementById('vocabulary-input');
  const lines = text.split(/[\n,;]+/).map(l => l.trim()).filter(Boolean);
  const existing = ta.value.trim();
  ta.value = existing ? existing + '\n' + lines.join('\n') : lines.join('\n');
}

// ── Batch form submit ──────────────────────────────────────────────────────
document.getElementById('batch-form').addEventListener('submit', async e => {
  e.preventDefault();
  hideAlert('main-error');
  hideAlert('main-success');

  const btn = document.getElementById('submit-btn');
  const targetLang = document.getElementById('target-language').value;
  const explLang = document.getElementById('explanation-language').value;
  const rawText = document.getElementById('vocabulary-input').value.trim();

  if (!rawText) {
    showError('main-error', 'Please enter at least one vocabulary word.');
    return;
  }

  const vocabulary = rawText.split('\n').map(l => l.trim()).filter(Boolean);
  if (vocabulary.length > 50) {
    showError('main-error', 'Maximum 50 words per batch.');
    return;
  }

  await save({ targetLang, explLang });

  // Persist language choice to user profile as defaults
  try {
    const langPayload = { default_target_language: null, default_explanation_language: null };
    const targetLangObj = state.languages.find(l => l.code === targetLang);
    const explLangObj = state.languages.find(l => l.code === explLang);
    if (targetLangObj) langPayload.default_target_language = targetLangObj.id;
    if (explLangObj) langPayload.default_explanation_language = explLangObj.id;
    await api('/api/v1/auth/profile/', { method: 'PATCH', body: JSON.stringify(langPayload) });
  } catch {} // Non-critical — ignore failures

  document.getElementById('vocabulary-input').value = '';
  state.selectedText = '';
  document.getElementById('selected-text-badge').classList.add('hidden');

  const payload = { target_language: targetLang, vocabulary };
  if (explLang) payload.explanation_language = explLang;

  setLoading(btn, true);

  // Delegate to background service worker so the fetch survives popup close
  chrome.runtime.sendMessage(
    { type: 'CREATE_BATCH', serverUrl: state.serverUrl, token: state.token, payload },
    resp => {
      setLoading(btn, false);
      if (!resp) {
        showError('main-error', 'No response from background worker.');
        return;
      }
      if (resp.ok) {
        showResultScreen(resp.data);
      } else {
        if (resp.status === 401) {
          state.token = null;
          save({ token: null });
          showScreen('screen-login');
        }
        showError('main-error', resp.error);
      }
    }
  );
});

// ── Result screen ──────────────────────────────────────────────────────────
function statusEmoji(s) {
  const map = { completed: '✅', failed: '❌', pending: '⏳', translated: '🔤', tts_done: '🔊', pushed: '✅', partial_failure: '⚠️' };
  return map[s] || '❓';
}

function showResultScreen(batch) {
  showScreen('screen-result');
  const summary = batch.summary || {};
  document.getElementById('result-summary').innerHTML = `
    <div class="stat-row">
      <div class="stat stat-total"><div class="stat-num">${summary.total ?? batch.cards?.length ?? 0}</div><div class="stat-label">Total</div></div>
      <div class="stat stat-success"><div class="stat-num">${summary.pushed ?? 0}</div><div class="stat-label">Pushed to Anki</div></div>
      <div class="stat stat-fail"><div class="stat-num">${summary.failed ?? 0}</div><div class="stat-label">Failed</div></div>
    </div>
    <div style="text-align:center;margin-top:8px;font-size:0.8rem;color:#888;">
      ${batch.target_language_name || ''} → ${batch.explanation_language_name || ''}
      &nbsp;·&nbsp; ${statusEmoji(batch.status)} ${batch.status}
    </div>`;

  document.getElementById('result-cards').innerHTML = (batch.cards || []).map(card => {
    const icon = card.status === 'pushed' ? '✅' : (card.status === 'failed' ? '❌' : '⏳');
    return `<div class="card-item">
      <div class="card-status">${icon}</div>
      <div class="card-info">
        <div class="card-word">${escHtml(card.target_word || card.input_text)}</div>
        ${card.explanation_word ? `<div class="card-translation">${escHtml(card.explanation_word)}</div>` : ''}
        ${card.error_message ? `<div class="card-err">${escHtml(card.error_message)}</div>` : ''}
      </div>
    </div>`;
  }).join('');
}

document.getElementById('back-to-main').addEventListener('click', () => showScreen('screen-main'));

// ── History screen ─────────────────────────────────────────────────────────
document.getElementById('go-history').addEventListener('click', async e => {
  e.preventDefault();
  showScreen('screen-history');
  document.getElementById('history-list').innerHTML = '<div class="loading">Loading…</div>';
  try {
    const batches = await api('/api/v1/cards/batches/list/');
    renderHistory(batches);
  } catch (err) {
    document.getElementById('history-list').innerHTML = `<div class="loading" style="color:#f87171">${escHtml(err.message)}</div>`;
  }
});

function renderHistory(batches) {
  if (!batches.length) {
    document.getElementById('history-list').innerHTML = '<div class="loading">No batches yet.</div>';
    return;
  }
  document.getElementById('history-list').innerHTML = batches.map(b => {
    const badgeClass = { completed: 'badge-completed', failed: 'badge-failed', partial_failure: 'badge-partial', pending: 'badge-pending' }[b.status] || 'badge-pending';
    const date = new Date(b.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    return `<div class="history-item" data-id="${b.id}">
      <div class="hi-top"><span class="hi-lang">${escHtml(b.target_language_name || '?')}</span><span class="hi-badge ${badgeClass}">${b.status}</span></div>
      <div class="hi-meta">${date} · ${b.total_cards} cards · ${b.pushed_cards} pushed</div>
    </div>`;
  }).join('');
}

document.getElementById('back-from-history').addEventListener('click', () => showScreen('screen-main'));

// ── Settings screen ────────────────────────────────────────────────────────
async function openSettings() {
  document.getElementById('server-url').value = state.serverUrl;
  document.getElementById('settings-saved').classList.add('hidden');
  document.getElementById('settings-error').classList.add('hidden');
  const ankiGroup = document.getElementById('anki-url-group');
  if (state.token) {
    ankiGroup.classList.remove('hidden');
    try {
      const profile = await api('/api/v1/auth/profile/');
      document.getElementById('anki-connect-url').value = profile.anki_connect_url || 'http://localhost:8765';
    } catch {}
  } else {
    ankiGroup.classList.add('hidden');
  }
  showScreen('screen-settings');
}

document.getElementById('go-settings').addEventListener('click', e => { e.preventDefault(); openSettings(); });
document.getElementById('go-to-settings-from-login').addEventListener('click', e => { e.preventDefault(); openSettings(); });

document.getElementById('save-settings-btn').addEventListener('click', async () => {
  const url = document.getElementById('server-url').value.trim().replace(/\/$/, '');
  if (!url) return;
  state.serverUrl = url;
  await save({ serverUrl: url });

  const ankiUrl = document.getElementById('anki-connect-url').value.trim().replace(/\/$/, '');
  if (state.token && ankiUrl) {
    try {
      await api('/api/v1/auth/profile/', { method: 'PATCH', body: JSON.stringify({ anki_connect_url: ankiUrl }) });
    } catch (err) {
      document.getElementById('settings-error').textContent = 'Saved server URL, but failed to update AnkiConnect URL: ' + err.message;
      document.getElementById('settings-error').classList.remove('hidden');
      return;
    }
  }

  document.getElementById('settings-saved').classList.remove('hidden');
  setTimeout(() => document.getElementById('settings-saved').classList.add('hidden'), 2000);
});

document.getElementById('back-from-settings').addEventListener('click', () => {
  if (state.token) showScreen('screen-main');
  else showScreen('screen-login');
});

// ── Util ───────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Start ──────────────────────────────────────────────────────────────────
init();
