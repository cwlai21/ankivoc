'use strict';

// ── Server management via Native Messaging ──────────────────────────────────
const HOST_NAME = 'com.ankivoc.server';
const SERVER_URL = 'http://127.0.0.1:8000';
const HEARTBEAT_INTERVAL_MS = 2 * 60 * 1000; // 2 minutes

let _nativePort = null;
let _heartbeatTimer = null;

function getNativePort() {
  if (_nativePort) return _nativePort;
  try {
    _nativePort = chrome.runtime.connectNative(HOST_NAME);
    _nativePort.onDisconnect.addListener(() => {
      _nativePort = null;
      stopHeartbeat();
    });
  } catch (e) {
    console.error('[AnkiVoc] Native host connection failed:', e.message);
  }
  return _nativePort;
}

function sendToHost(msg) {
  return new Promise((resolve, reject) => {
    const port = getNativePort();
    if (!port) { reject(new Error('Native host unavailable')); return; }
    const onMsg = (resp) => { port.onMessage.removeListener(onMsg); resolve(resp); };
    const onDisc = () => { reject(new Error('Native host disconnected')); };
    port.onMessage.addListener(onMsg);
    port.onDisconnect.addListener(onDisc);
    port.postMessage(msg);
  });
}

async function pingServer() {
  try {
    const resp = await fetch(SERVER_URL + '/', {
      signal: AbortSignal.timeout(1500),
      redirect: 'manual',  // count redirect (302) as success too
    });
    return resp.status < 500;
  } catch {
    return false;
  }
}

async function ensureServerRunning() {
  // Already up?
  if (await pingServer()) return { ok: true, alreadyRunning: true };

  // Ask native host to start it
  try {
    await sendToHost({ action: 'start' });
  } catch (e) {
    return { ok: false, error: e.message };
  }

  // Poll up to 15 s for server to become ready
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 500));
    if (await pingServer()) return { ok: true, alreadyRunning: false };
  }
  return { ok: false, error: 'Server did not start within 15 seconds' };
}

function startHeartbeat() {
  stopHeartbeat();
  _heartbeatTimer = setInterval(() => {
    sendToHost({ action: 'heartbeat' }).catch(() => {});
  }, HEARTBEAT_INTERVAL_MS);
}

function stopHeartbeat() {
  if (_heartbeatTimer) { clearInterval(_heartbeatTimer); _heartbeatTimer = null; }
}

// ── Context menu ────────────────────────────────────────────────────────────
// Create context menu item: right-click selected text → "Add to Anki Vocab"
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'add-to-anki',
    title: 'Add to Anki Vocab',
    contexts: ['selection'],
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== 'add-to-anki') return;
  const text = info.selectionText?.trim();
  if (!text) return;

  // Store selected text and open popup
  chrome.storage.local.set({ selectedText: text }, () => {
    chrome.action.openPopup().catch(() => {
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon48.png',
        title: 'Anki Vocab Builder',
        message: `"${text.substring(0, 50)}" saved. Click the extension icon to add it.`,
      });
    });
  });
});

// ── Message handlers ───────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'ENSURE_SERVER') {
    ensureServerRunning().then(result => {
      if (result.ok) startHeartbeat();
      sendResponse(result);
    });
    return true;
  }

  if (msg.type === 'STOP_HEARTBEAT') {
    stopHeartbeat();
    sendResponse({ ok: true });
    return false;
  }

  if (msg.type !== 'CREATE_BATCH') return false;

  const { serverUrl, token, payload } = msg;

  fetch(serverUrl + '/api/v1/cards/batches/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Token ' + token,
    },
    body: JSON.stringify(payload),
  })
    .then(async resp => {
      let data;
      try { data = await resp.json(); } catch { data = {}; }

      if (resp.ok) {
        // Store result so popup can display it when reopened
        chrome.storage.local.set({ lastBatchResult: data });

        const summary = data.summary || {};
        const pushed  = summary.pushed ?? 0;
        const failed  = summary.failed ?? 0;
        const total   = summary.total  ?? (data.cards?.length ?? 0);
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icons/icon48.png',
          title: 'Anki Vocab Builder',
          message: `${pushed}/${total} cards pushed to Anki${failed ? ` · ${failed} failed` : ''}.`,
        });
        sendResponse({ ok: true, data });
      } else {
        const msg = data.detail || data.error || data.message
          || (typeof data === 'object' ? Object.values(data).flat().join(' ') : String(data))
          || `HTTP ${resp.status}`;
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icons/icon48.png',
          title: 'Anki Vocab Builder – Error',
          message: msg,
        });
        sendResponse({ ok: false, error: msg, status: resp.status });
      }
    })
    .catch(err => {
      const errMsg = `Cannot reach server at ${serverUrl}. Is Django running? (${err.message})`;
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon48.png',
        title: 'Anki Vocab Builder – Error',
        message: errMsg,
      });
      sendResponse({ ok: false, error: errMsg });
    });

  return true; // keep message channel open for async sendResponse
});
