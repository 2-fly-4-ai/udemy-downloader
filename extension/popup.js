const $ = (id) => document.getElementById(id);
const logEl = $('log');
const infoEl = $('infoPanel');
let currentJobId = null;

function log(line) {
  logEl.textContent += line + "\n";
  logEl.scrollTop = logEl.scrollHeight;
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.kind === 'event' && msg.type === 'host.ready') {
    log(`[host] ready: ${msg.root}`);
  } else if (msg.kind === 'event' && msg.type === 'job.log') {
    log(msg.line);
  } else if (msg.kind === 'event' && msg.type === 'job.started') {
    log(`[job ${msg.jobId}] started`);
    // If host provided args, show them and extract output directory
    if (Array.isArray(msg.args)) {
      try {
        const argsStr = msg.args.join(' ');
        log(`[job ${msg.jobId}] args: ${argsStr}`);
        const idx = msg.args.indexOf('-o');
        if (idx >= 0 && msg.args[idx + 1]) {
          log(`[job ${msg.jobId}] output: ${msg.args[idx + 1]}`);
        }
      } catch (_) {}
    }
    currentJobId = msg.jobId;
  } else if (msg.kind === 'event' && msg.type === 'job.completed') {
    log(`[job ${msg.jobId}] completed (${msg.code})`);
    if (currentJobId === msg.jobId) currentJobId = null;
  } else if (msg.kind === 'event' && msg.type === 'job.failed') {
    log(`[job ${msg.jobId}] failed (${msg.code})`);
    if (currentJobId === msg.jobId) currentJobId = null;
  } else if (msg.kind === 'response') {
    if (msg.ok) {
      if (msg.result && msg.result.jobId) {
        currentJobId = msg.result.jobId;
      }
      log(`[ok] ${JSON.stringify(msg.result)}`);
      // Populate info panel if this is companion.info
      if (msg.result && (msg.result.python || msg.result.ffmpeg || msg.result.aria2c)) {
        infoEl.textContent = JSON.stringify(msg.result, null, 2);
      }
    } else {
      log(`[err] ${msg.error}`);
    }
  }
});

$('ping').addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'companion.ping' }, (resp) => {
    if (!resp || !resp.ok) log(`[err] ping: ${resp && resp.error}`);
  });
});

$('info').addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'companion.info' }, (resp) => {
    if (!resp || !resp.ok) log(`[err] info: ${resp && resp.error}`);
  });
});

$('start').addEventListener('click', () => {
  const url = $('url').value.trim();
  if (!url) { log('Enter a course URL'); return; }
  const payload = {
    courseUrl: url,
    browser: 'chrome',
    downloadAssets: $('assets').checked,
    downloadCaptions: $('captions').checked,
    captionLang: 'en',
  };
  const q = $('quality').value.trim();
  if (q) payload.quality = parseInt(q, 10);
  const out = $('outDir') ? $('outDir').value.trim() : '';
  if (out) payload.outDir = out;
  // Persist last used output directory
  try {
    chrome.storage?.local?.set({ outDir: out }).catch?.(() => {});
  } catch (_) {}
  chrome.runtime.sendMessage({ type: 'udemy.start', payload }, (resp) => {
    if (!resp || !resp.ok) log(`[err] start: ${resp && resp.error}`);
  });
});

$('cancel').addEventListener('click', () => {
  if (!currentJobId) { log('No active job to cancel.'); return; }
  chrome.runtime.sendMessage({ type: 'udemy.cancel', payload: { jobId: currentJobId } }, (resp) => {
    if (!resp || !resp.ok) log(`[err] cancel: ${resp && resp.error}`);
  });
});

$('clear').addEventListener('click', () => { logEl.textContent = ''; });

// Pairing: automatically register this extension ID in the native host
$('pair').addEventListener('click', async () => {
  try {
    const id = chrome.runtime.id;
    const url = `http://127.0.0.1:60123/pair?extId=${id}`;
    const res = await fetch(url);
    const json = await res.json();
    if (json.ok) {
      log(`[pair] ok: manifest=${json.manifest}`);
    } else {
      log(`[pair] err: ${json.error}`);
    }
  } catch (e) {
    log(`[pair] failed: ${e}`);
  }
});

// Attempt auto-pair on popup open (no-op if server not running)
document.addEventListener('DOMContentLoaded', async () => {
  try {
    // Load last used output directory
    try {
      const saved = await chrome.storage?.local?.get?.('outDir');
      if (saved && saved.outDir && $('outDir')) $('outDir').value = saved.outDir;
    } catch (_) {}

    const id = chrome.runtime.id;
    const url = `http://127.0.0.1:60123/pair?extId=${id}`;
    const res = await fetch(url);
    if (res.ok) {
      const json = await res.json();
      if (json && json.ok) log(`[pair] ok: manifest=${json.manifest}`);
    }
  } catch (_) {
    // ignore; server may not be running yet
  }
});
