import sys
import os
import json
import struct
import subprocess
import threading
import uuid
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler


# Chrome Native Messaging utilities
def _read_message():
    try:
        raw_length = sys.stdin.buffer.read(4)
        if len(raw_length) == 0:
            return None
        message_length = struct.unpack('<I', raw_length)[0]
        message = sys.stdin.buffer.read(message_length).decode('utf-8')
        if not message:
            return None
        return json.loads(message)
    except Exception:
        return None


def _write_message(obj: dict):
    try:
        encoded = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        sys.stdout.buffer.write(struct.pack('<I', len(encoded)))
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
    except Exception:
        # If we cannot write to stdout, there's nothing else we can do
        pass


def _send_response(req_id: str, ok: bool, result=None, error=None):
    msg = {"kind": "response", "id": req_id, "ok": ok}
    if ok:
        msg["result"] = result
    else:
        msg["error"] = error or "unknown_error"
    _write_message(msg)


def _send_event(ev_type: str, payload: dict):
    _write_message({"kind": "event", "type": ev_type, **payload})


if os.name == 'nt':
    try:
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    except Exception:
        pass


if getattr(sys, 'frozen', False):
    BIN_DIR = Path(sys.executable).parent
    ROOT = BIN_DIR.parent
else:
    ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = ROOT / 'main.py'
BIN_DL_WIN = ROOT / 'bin' / 'udemy-downloader.exe'
TOOLS_DIR = ROOT / 'tools'
VENV_PY_WIN = ROOT / 'venv' / 'Scripts' / 'python.exe'
VENV_PY_NIX = ROOT / 'venv' / 'bin' / 'python'
PYTHON_FOR_MAIN = str(VENV_PY_WIN if VENV_PY_WIN.exists() else (VENV_PY_NIX if VENV_PY_NIX.exists() else sys.executable))

JOBS = {}  # job_id -> { 'proc': Popen, 'start': ts, 'args': list }


def _tool_version(cmd, args=("--version",)):
    try:
        out = subprocess.check_output([cmd, *args], stderr=subprocess.STDOUT, text=True, timeout=5)
        first = out.strip().splitlines()[0]
        return first
    except Exception as e:
        return f"unavailable: {e.__class__.__name__}"


def handle_ping(req):
    _send_response(req.get("id"), True, {"status": "ok"})


def handle_info(req):
    result = {
        "python": sys.version.splitlines()[0],
        "ffmpeg": _tool_version("ffmpeg"),
        "aria2c": _tool_version("aria2c"),
        "yt_dlp": _tool_version("yt-dlp", ("--version",)),
        "main_py_exists": MAIN_PY.exists(),
        "main_py": str(MAIN_PY),
        "packaged_exe": str(BIN_DL_WIN) if BIN_DL_WIN.exists() else None,
    }
    _send_response(req.get("id"), True, result)


def _stream_proc_output(job_id: str, proc: subprocess.Popen):
    try:
        for line in iter(proc.stdout.readline, ''):
            if not line:
                break
            _send_event("job.log", {"jobId": job_id, "line": line.rstrip()})
    except Exception as e:
        _send_event("job.log", {"jobId": job_id, "line": f"[host] stream error: {e}"})


def handle_udemy_start(req):
    payload = req.get("payload") or {}
    course_url = payload.get("courseUrl")
    if not course_url:
        _send_response(req.get("id"), False, error="missing_course_url")
        return

    if not MAIN_PY.exists():
        _send_response(req.get("id"), False, error="main_py_not_found")
        return

    job_id = str(uuid.uuid4())
    # Prefer packaged downloader if available; fallback to Python script
    if os.name == 'nt' and BIN_DL_WIN.exists():
        args = [str(BIN_DL_WIN), "-c", course_url]
    else:
        args = [PYTHON_FOR_MAIN, "-u", str(MAIN_PY), "-c", course_url]

    # Use local Chrome cookies by default for auth if bearer not provided
    use_browser = payload.get("browser", "chrome")
    if use_browser:
        args += ["--browser", use_browser]

    quality = payload.get("quality")
    if isinstance(quality, int):
        args += ["-q", str(quality)]

    if payload.get("downloadCaptions"):
        args += ["--download-captions"]
        lang = payload.get("captionLang")
        if isinstance(lang, str) and lang:
            args += ["-l", lang]

    if payload.get("downloadAssets"):
        args += ["--download-assets"]

    out_dir = payload.get("outDir")
    if isinstance(out_dir, str) and out_dir:
        args += ["-o", out_dir]
    else:
        # Default to a user-writable location to avoid Program Files permission issues
        default_out = Path.home() / "Videos" / "Udemy"
        try:
            default_out.mkdir(parents=True, exist_ok=True)
        except Exception:
            default_out = Path.home() / "Downloads" / "Udemy"
            default_out.mkdir(parents=True, exist_ok=True)
        args += ["-o", str(default_out)]

    # Optional advanced flags
    if payload.get("skipHls"):
        args += ["--skip-hls"]
    if payload.get("keepVtt"):
        args += ["--keep-vtt"]
    if payload.get("continueLectureNumbers"):
        args += ["-n"]
    if payload.get("concurrentDownloads"):
        args += ["-cd", str(int(payload.get("concurrentDownloads")))]

    log_level = payload.get("logLevel", "INFO")
    args += ["--log-level", log_level]

    creationflags = 0
    if os.name == 'nt':
        # Do not pop a console window
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

    env = os.environ.copy()
    # Prepend bundled tools to PATH to avoid user setup
    if TOOLS_DIR.exists():
        env['PATH'] = str(TOOLS_DIR) + os.pathsep + env.get('PATH', '')

    try:
        proc = subprocess.Popen(
            args,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=creationflags,
            env=env,
        )
    except Exception as e:
        _send_response(req.get("id"), False, error=f"spawn_failed: {e}")
        return

    JOBS[job_id] = {"proc": proc, "start": time.time(), "args": args}

    t = threading.Thread(target=_stream_proc_output, args=(job_id, proc), daemon=True)
    t.start()

    def _waiter():
        rc = proc.wait()
        if rc == 0:
            _send_event("job.completed", {"jobId": job_id, "code": rc})
        else:
            _send_event("job.failed", {"jobId": job_id, "code": rc})
        JOBS.pop(job_id, None)

    threading.Thread(target=_waiter, daemon=True).start()

    _send_response(req.get("id"), True, {"jobId": job_id})
    _send_event("job.started", {"jobId": job_id, "args": args})


def handle_udemy_cancel(req):
    payload = req.get("payload") or {}
    job_id = payload.get("jobId")
    if not job_id or job_id not in JOBS:
        _send_response(req.get("id"), False, error="unknown_job")
        return
    proc = JOBS[job_id]["proc"]
    try:
        if os.name == 'nt':
            proc.terminate()
        else:
            proc.terminate()
        _send_response(req.get("id"), True, {"jobId": job_id})
        _send_event("job.canceled", {"jobId": job_id})
    except Exception as e:
        _send_response(req.get("id"), False, error=f"cancel_failed: {e}")


HANDLERS = {
    "companion.ping": handle_ping,
    "companion.info": handle_info,
    "udemy.start": handle_udemy_start,
    "udemy.cancel": handle_udemy_cancel,
}


def _manifest_path_win() -> Path:
    # Default manifest next to app root (works for installed + dev)
    return ROOT / 'com.serp.companion.json'


def _write_manifest(ext_ids):
    exe_path = str(BIN_DIR / 'serp-companion.exe') if getattr(sys, 'frozen', False) else str((ROOT / 'native_host' / 'run-host.bat'))
    manifest_file = _manifest_path_win()
    allowed = [f"chrome-extension://{eid}/" for eid in ext_ids]
    data = {
        "name": "com.serp.companion",
        "description": "SERP Companion Native Host",
        "path": exe_path,
        "type": "stdio",
        "allowed_origins": allowed,
    }
    manifest_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest_file


def _register_manifest_win(manifest_path: Path):
    try:
        import winreg
    except Exception as e:
        return False, f"winreg_unavailable:{e}"
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\\Google\\Chrome\\NativeMessagingHosts\\com.serp.companion")
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, str(manifest_path))
        winreg.CloseKey(key)
        return True, None
    except Exception as e:
        return False, f"reg_error:{e}"


class PairHandler(BaseHTTPRequestHandler):
    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/health':
            payload = {
                'root': str(ROOT),
                'bin': str(BIN_DIR) if getattr(sys, 'frozen', False) else None,
                'manifest': str(_manifest_path_win()),
                'ok': True,
            }
            body = json.dumps(payload).encode('utf-8')
            self.send_response(200)
            self._cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == '/pair':
            qs = parse_qs(parsed.query)
            ext_id = (qs.get('extId') or [None])[0]
            if not ext_id:
                body = json.dumps({'ok': False, 'error': 'missing_extId'}).encode('utf-8')
                self.send_response(400)
                self._cors_headers()
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            try:
                mf = _write_manifest([ext_id])
                ok, err = _register_manifest_win(mf)
                res = {'ok': bool(ok), 'manifest': str(mf)}
                if not ok:
                    res['error'] = err
                body = json.dumps(res).encode('utf-8')
                self.send_response(200 if ok else 500)
                self._cors_headers()
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                body = json.dumps({'ok': False, 'error': f'pair_failed:{e}'}).encode('utf-8')
                self.send_response(500)
                self._cors_headers()
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            return
        self.send_response(404)
        self._cors_headers()
        self.end_headers()


def run_pair_server(port=60123):
    addr = ('127.0.0.1', port)
    httpd = HTTPServer(addr, PairHandler)
    _send_event("host.pair_server", {"addr": f"http://{addr[0]}:{addr[1]}"})
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    _send_event("host.ready", {"root": str(ROOT)})
    while True:
        req = _read_message()
        if req is None:
            break
        typ = req.get("type")
        handler = HANDLERS.get(typ)
        if not handler:
            _send_response(req.get("id"), False, error=f"unknown_type:{typ}")
            continue
        handler(req)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ('--pair-server', 'pair', 'pair-server'):
        run_pair_server()
    else:
        main()
