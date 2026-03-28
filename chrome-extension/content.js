'use strict';

// Listen for messages from background to capture selected text
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'GET_SELECTION') {
    sendResponse({ text: window.getSelection().toString().trim() });
  }
});
