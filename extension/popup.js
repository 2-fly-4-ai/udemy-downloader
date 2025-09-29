const $ = (id) => document.getElementById(id);
const logEl = $('log');
const infoEl = $('infoPanel');
let currentJobId = null;
let lastLogFile = null;

const DEFAULTS = {
  url: '',
  assets: false,
  captions: false,
  captionLang: 'en',
  quality: '', // empty means best available (no --quality)
  useCookies: true,
  bearer: '',
  outDir: ''
};

function getStateFromUI() {
  return {
    url: $('url')?.value?.trim() || '',
    assets: $('assets')?.checked || false,
    captions: $('captions')?.checked || false,
    captionLang: $('langSelect')?.value || 'en',
    quality: $('qualitySelect')?.value || '',
    useCookies: $('useCookies')?.checked || false,
    bearer: $('bearer')?.value?.trim() || '',
    outDir: $('outDir')?.value?.trim() || ''
  };
}

function applyStateToUI(s) {
  $('url').value = s.url || '';
  $('assets').checked = !!s.assets;
  $('captions').checked = !!s.captions;
  $('langSelect').value = s.captionLang || 'en';
  $('langSelect').disabled = !$('captions').checked;
  $('qualitySelect').value = s.quality || '';
  $('useCookies').checked = s.useCookies !== false; // default true
  $('bearer').value = s.bearer || '';
  $('outDir').value = s.outDir || '';
}

async function saveState(s) {
  try {
    const ui = { ...DEFAULTS, ...(s || getStateFromUI()) };
    await chrome.storage?.local?.set?.({ ui });
    // Keep outDir compatibility key as well
    await chrome.storage?.local?.set?.({ outDir: ui.outDir });
  } catch (_) { /* ignore */ }
}

const ALLOWED_QUALITIES = new Set(['', '1080', '720', '480', '360', '240']);

async function loadState() {
  try {
    const saved = await chrome.storage?.local?.get?.('ui');
    const merged = { ...DEFAULTS, ...(saved?.ui || {}) };
    // Sanitize any previously saved higher-than-1080 values
    if (!ALLOWED_QUALITIES.has(String(merged.quality || ''))) {
      merged.quality = '';
    }
    return merged;
  } catch (_) {
    return { ...DEFAULTS };
  }
}

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
    if (msg.logFile) {
      lastLogFile = msg.logFile;
      log(`[job ${msg.jobId}] logfile: ${msg.logFile}`);
      try { $('openLog').disabled = false; } catch (_) {}
    }
    currentJobId = msg.jobId;
  } else if (msg.kind === 'event' && msg.type === 'job.completed') {
    log(`[job ${msg.jobId}] completed (${msg.code})`);
    if (currentJobId === msg.jobId) currentJobId = null;
  } else if (msg.kind === 'event' && msg.type === 'job.failed') {
    log(`[job ${msg.jobId}] failed (${msg.code})`);
    if (currentJobId === msg.jobId) currentJobId = null;
  } else if (msg.kind === 'event' && msg.type === 'job.active') {
    log(`[job] another download is already running (jobId=${msg.jobId}). Cancel it or wait to start a new one.`);
  } else if (msg.kind === 'event' && msg.type === 'host.cookies_saved') {
    log(`[host] cookies.txt saved: ${msg.path} (${msg.bytes} bytes)`);
  } else if (msg.kind === 'event' && msg.type === 'host.cookies_save_failed') {
    log(`[host] cookies.txt save failed: ${msg.error}`);
  } else if (msg.kind === 'event' && msg.type === 'job.retry_bearer') {
    log(`[job ${msg.jobId}] retrying with bearer: ${msg.args?.join(' ')}`);
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
  (async () => {
    const state = getStateFromUI();
    const url = state.url;
    if (!url) { log('Enter a course URL'); return; }
    const useCookies = state.useCookies;
    const bearer = state.bearer;

    const payload = {
      courseUrl: url,
      downloadAssets: state.assets,
      downloadCaptions: state.captions,
      captionLang: state.captionLang,
      preferCookies: true,
    };
    const q = state.quality.trim();
    if (ALLOWED_QUALITIES.has(q) && /^\d+$/.test(q)) {
      payload.quality = parseInt(q, 10); // only set when user selected explicit quality
    }
    const out = state.outDir;
    if (out) payload.outDir = out;
    // Persist full UI state
    await saveState(state);

    if (useCookies) {
      const cookies = await getUdemyCookies();
      log(`[cookies] extracted ${cookies.length} cookies for udemy.com`);
      if (cookies.length > 0) {
        payload.cookiesTxt = netscapeFromCookies(cookies);
        payload.browser = 'file';
      } else {
        log('[cookies] none found; will fall back to browser=chrome');
        payload.browser = 'chrome';
      }
    } else {
      payload.browser = 'chrome';
    }

    if (bearer) {
      payload.bearer = bearer;
      log('[auth] bearer provided; will retry with bearer if cookies fail');
    }

    chrome.runtime.sendMessage({ type: 'udemy.start', payload }, (resp) => {
      if (!resp || !resp.ok) log(`[err] start: ${resp && resp.error}`);
    });
  })();
});

$('cancel').addEventListener('click', () => {
  if (!currentJobId) { log('No active job to cancel.'); return; }
  chrome.runtime.sendMessage({ type: 'udemy.cancel', payload: { jobId: currentJobId } }, (resp) => {
    if (!resp || !resp.ok) log(`[err] cancel: ${resp && resp.error}`);
  });
});

$('clear').addEventListener('click', () => { logEl.textContent = ''; });

$('openLog').addEventListener('click', () => {
  if (!lastLogFile) { log('[log] No logfile path available yet. Start a job first.'); return; }
  chrome.runtime.sendMessage({ type: 'companion.openLog', payload: { path: lastLogFile } }, (resp) => {
    if (!resp || !resp.ok) log(`[err] openLog: ${resp && resp.error}`);
    else log('[log] opened in default editor');
  });
});

// Pairing: automatically register this extension ID in the native host
const PAIR_PORTS = [60123, 53123, 54123, 55123, 56123, 47123, 42123, 23123];

async function tryPair(extId) {
  for (const p of PAIR_PORTS) {
    try {
      const res = await fetch(`http://127.0.0.1:${p}/pair?extId=${extId}`);
      if (res.ok) {
        const json = await res.json();
        if (json && json.ok) {
          log(`[pair] ok on :${p} manifest=${json.manifest}`);
          return true;
        }
      }
    } catch (_) { /* try next */ }
  }
  return false;
}

$('pair').addEventListener('click', async () => {
  const id = chrome.runtime.id;
  const ok = await tryPair(id);
  if (!ok) log('[pair] no pair server found on candidate ports');
});

// Attempt auto-pair on popup open (no-op if server not running)
document.addEventListener('DOMContentLoaded', async () => {
  try { $('openLog').disabled = true; } catch (_) {}
  // Restore UI
  const s = await loadState();
  applyStateToUI(s);
  // Enable/disable language selection with captions toggle
  $('captions').addEventListener('change', async () => {
    $('langSelect').disabled = !$('captions').checked;
    await saveState();
  });
  // Persist on changes
  ['url','assets','useCookies','bearer','outDir'].forEach(id => {
    $(id)?.addEventListener('input', () => saveState());
    $(id)?.addEventListener('change', () => saveState());
  });
  $('langSelect')?.addEventListener('change', () => saveState());
  $('qualitySelect')?.addEventListener('change', () => saveState());

  // Attempt auto-pair across candidate ports (no-op if server not running)
  try { const id = chrome.runtime.id; await tryPair(id); } catch (_) {}
});

$('reset').addEventListener('click', async () => {
  applyStateToUI(DEFAULTS);
  await saveState(DEFAULTS);
  log('[ui] reset to defaults');
});
async function getUdemyCookies() {
  try {
    const list = await chrome.cookies.getAll({ url: 'https://www.udemy.com/' });
    return list || [];
  } catch (e) {
    log(`[cookies] getAll failed: ${e}`);
    return [];
  }
}

function toNetscapeCookieLine(c) {
  const includeSub = c.hostOnly ? 'FALSE' : 'TRUE';
  let domain = c.domain || '';
  if (includeSub === 'TRUE' && !domain.startsWith('.')) domain = '.' + domain;
  const path = c.path || '/';
  const secure = c.secure ? 'TRUE' : 'FALSE';
  const expiry = c.expirationDate ? Math.floor(c.expirationDate) : 0;
  return [domain, includeSub, path, secure, String(expiry), c.name, c.value].join('\t');
}

function netscapeFromCookies(cookies) {
  const header = [
    '# Netscape HTTP Cookie File',
    '# This file was generated by SERP Companion',
    '# https://curl.se/docs/http-cookies.html',
    ''
  ].join('\n');
  const lines = cookies.map(toNetscapeCookieLine).join('\n');
  return header + '\n' + lines + '\n';
}
