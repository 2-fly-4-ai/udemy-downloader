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
    const url = $('url').value.trim();
    if (!url) { log('Enter a course URL'); return; }
    const useCookies = $('useCookies').checked;
    const bearer = $('bearer')?.value?.trim() || '';

    const payload = {
      courseUrl: url,
      downloadAssets: $('assets').checked,
      downloadCaptions: $('captions').checked,
      captionLang: 'en',
      preferCookies: true,
    };
    const q = $('quality').value.trim();
    if (q) payload.quality = parseInt(q, 10);
    const out = $('outDir') ? $('outDir').value.trim() : '';
    if (out) payload.outDir = out;
    // Persist last used output directory
    try { chrome.storage?.local?.set({ outDir: out }).catch?.(() => {}); } catch (_) {}

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
  // Load last used output directory
  try {
    const saved = await chrome.storage?.local?.get?.('outDir');
    if (saved && saved.outDir && $('outDir')) $('outDir').value = saved.outDir;
  } catch (_) {}
  // Attempt auto-pair across candidate ports (no-op if server not running)
  try {
    const id = chrome.runtime.id;
    await tryPair(id);
  } catch (_) { /* ignore */ }
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
