let port = null;
let nextId = 1;

function ensurePort() {
  if (port && port.name === 'com.serp.companion') return port;
  port = chrome.runtime.connectNative('com.serp.companion');
  port.onDisconnect.addListener(() => {
    port = null;
  });
  port.onMessage.addListener((msg) => {
    // Fan-out events/responses to any listeners (popup)
    chrome.runtime.sendMessage(msg).catch(() => {});
  });
  return port;
}

chrome.runtime.onMessage.addListener((req, _sender, sendResponse) => {
  try {
    const p = ensurePort();
    const id = String(nextId++);
    const msg = { id, type: req.type, payload: req.payload || {} };
    p.postMessage(msg);
    sendResponse({ ok: true, id });
  } catch (e) {
    sendResponse({ ok: false, error: String(e) });
  }
  // Keep channel open only for immediate response
  return false;
});

