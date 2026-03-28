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
    // Open the extension popup by creating an action click simulation
    // (Chrome MV3: we can't programmatically open popup, so we open a small window)
    chrome.action.openPopup().catch(() => {
      // openPopup not always available; fallback: store text, user clicks icon
      chrome.notifications?.create({
        type: 'basic',
        iconUrl: 'icons/icon48.png',
        title: 'Anki Vocab Builder',
        message: `"${text.substring(0, 50)}" saved. Click the extension icon to add it.`,
      });
    });
  });
});
