'use strict';

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

// ── Batch creation (runs in background so popup can close safely) ──────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
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
