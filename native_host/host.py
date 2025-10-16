import sys
import os
import json
import struct
import subprocess
import threading
import uuid
import time
from queue import Queue, Full, Empty
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

# Asynchronous event queue to avoid blocking the child process if Chrome isn't reading
EV_QUEUE: Queue = Queue(maxsize=500)


def _send_response(req_id: str, ok: bool, result=None, error=None):
    msg = {"kind": "response", "id": req_id, "ok": ok}
    if ok:
        msg["result"] = result
    else:
        msg["error"] = error or "unknown_error"
    _write_message(msg)

def _send_event(ev_type: str, payload: dict):
    try:
        EV_QUEUE.put_nowait({"kind": "event", "type": ev_type, **payload})
    except Full:
        # Drop if UI isn't consuming; child process must not block
        pass


def _writer_loop():
    while True:
        try:
            msg = EV_QUEUE.get(timeout=0.5)
        except Empty:
            continue
        try:
            _write_message(msg)
        except Exception:
            # If writing fails (disconnected extension), drop and continue
            pass


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
BIN_DL_UNIX = ROOT / 'bin' / 'udemy-downloader'
TOOLS_DIR = ROOT / 'tools'
COOKIES_PATH = ROOT / 'cookies.txt'
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
        # Diagnostics for where we expect binaries
        "root": str(ROOT),
        "bin_dir": str(BIN_DIR) if getattr(sys, 'frozen', False) else None,
        "packaged_exe_expected": str(BIN_DL_WIN if os.name == 'nt' else BIN_DL_UNIX),
        "packaged_exe_exists": (BIN_DL_WIN.exists() if os.name == 'nt' else BIN_DL_UNIX.exists()),
        # Legacy fields (kept for compatibility in UI)
        "main_py_exists": MAIN_PY.exists(),
        "main_py": str(MAIN_PY),
        "packaged_exe": (str(BIN_DL_WIN) if os.name == 'nt' and BIN_DL_WIN.exists() else (str(BIN_DL_UNIX) if sys.platform == 'darwin' and BIN_DL_UNIX.exists() else None)),
    }
    _send_response(req.get("id"), True, result)


def handle_open_log(req):
    payload = req.get("payload") or {}
    p = payload.get("path")
    if not p:
        _send_response(req.get("id"), False, error="missing_path")
        return
    try:
        path = Path(p)
        if not path.exists():
            _send_response(req.get("id"), False, error="not_found")
            return
        try:
            if os.name == 'nt':
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(path)])
            else:
                subprocess.Popen(['xdg-open', str(path)])
        except Exception as e:
            _send_response(req.get("id"), False, error=f"open_failed:{e}")
            return
        _send_response(req.get("id"), True, {"opened": str(path)})
    except Exception as e:
        _send_response(req.get("id"), False, error=f"exception:{e}")


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

    # Prevent multiple concurrent jobs to avoid zombie processes and racing logs
    try:
        for jid, rec in list(JOBS.items()):
            pr = rec.get('proc')
            if pr and pr.poll() is None:
                _send_event("job.active", {"jobId": jid})
                _send_response(req.get("id"), False, error=f"job_active:{jid}")
                return
    except Exception:
        pass

    # On Windows we require the packaged downloader exe. No Python fallback.
    if os.name == 'nt':
        if not BIN_DL_WIN.exists():
            _send_response(req.get("id"), False, error=f"packaged_exe_not_found:{str(BIN_DL_WIN)}")
            return

    job_id = str(uuid.uuid4())
    # Prefer packaged downloader on Windows/macOS if available; Python fallback for dev
    if os.name == 'nt':
        args = [str(BIN_DL_WIN), "-c", course_url]
    elif sys.platform == 'darwin' and BIN_DL_UNIX.exists():
        args = [str(BIN_DL_UNIX), "-c", course_url]
    else:
        args = [PYTHON_FOR_MAIN, "-u", str(MAIN_PY), "-c", course_url]

    # If cookies were provided inline, write them to cookies.txt and prefer file cookies
    cookies_txt = payload.get("cookiesTxt")
    wrote_cookies = False
    if isinstance(cookies_txt, str) and len(cookies_txt) > 0:
        try:
            COOKIES_PATH.write_text(cookies_txt, encoding='utf-8')
            wrote_cookies = True
            _send_event("host.cookies_saved", {"path": str(COOKIES_PATH), "bytes": len(cookies_txt)})
        except Exception as e:
            _send_event("host.cookies_save_failed", {"error": str(e)})

    # Determine browser mode. Default to chrome if no cookies were passed in.
    use_browser = payload.get("browser")
    if not use_browser:
        use_browser = "file" if wrote_cookies else "chrome"
    if use_browser:
        args += ["--browser", use_browser]
    prefer_cookies = bool(payload.get("preferCookies", True))
    if prefer_cookies and use_browser == "file":
        args += ["--cookies-first"]

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

    # Default to DEBUG to aid troubleshooting unless UI payload overrides
    log_level = payload.get("logLevel", "DEBUG")
    args += ["--log-level", log_level]

    creationflags = 0
    if os.name == 'nt':
        # Do not pop a console window; put process in its own group for easier termination
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)

    env = os.environ.copy()
    # Prepend bundled tools to PATH to avoid user setup
    if TOOLS_DIR.exists():
        env['PATH'] = str(TOOLS_DIR) + os.pathsep + env.get('PATH', '')
    # Ensure Python unbuffered output for immediate line flush when running .py in dev
    env['PYTHONUNBUFFERED'] = '1'

    # Optional bearer token (fallback or primary). We set env always; downloader will honor --cookies-first
    bearer = payload.get("bearer")
    if isinstance(bearer, str) and len(bearer) > 0:
        env['UDEMY_BEARER'] = bearer

    def _spawn(args_to_use, env_to_use):
        try:
            pr = subprocess.Popen(
                args_to_use,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creationflags,
                env=env_to_use,
            )
            return pr, None
        except Exception as e:
            return None, e

    # Prepare deterministic log file path so we can tail it without relying on pipes
    try:
        logs_dir = ROOT / 'logs'
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / (time.strftime('%Y-%m-%d-%I-%M-%S') + '.log')
        # Create the file up front so it exists immediately
        try:
            log_file.touch(exist_ok=True)
        except Exception:
            pass
        env['UDEMY_LOG_DIR'] = str(logs_dir)
        env['UDEMY_LOG_FILE'] = str(log_file)
    except Exception:
        log_file = None

    # Spawn child with stdio detached from our pipes to avoid backpressure deadlocks
    def _spawn_detached(args_to_use, env_to_use):
        try:
            pr = subprocess.Popen(
                args_to_use,
                cwd=str(ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                creationflags=creationflags,
                env=env_to_use,
            )
            return pr, None
        except Exception as e:
            return None, e

    proc, err = _spawn_detached(args, env)
    if err:
        _send_response(req.get("id"), False, error=f"spawn_failed: {err}")
        return

    JOBS[job_id] = {"proc": proc, "start": time.time(), "args": args}

    # Start tailer of the log file (if available) to stream lines to UI
    def _tail_log(job_id: str, path: str):
        if not path:
            return
        try:
            # Wait for file to become non-empty for a short time
            for _ in range(50):
                try:
                    if os.path.getsize(path) >= 0:
                        break
                except Exception:
                    pass
                time.sleep(0.1)
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                # Stream appended lines
                while True:
                    line = f.readline()
                    if not line:
                        # Check if process ended
                        try:
                            if proc.poll() is not None:
                                break
                        except Exception:
                            pass
                        time.sleep(0.2)
                        continue
                    _send_event("job.log", {"jobId": job_id, "line": line.rstrip()})
        except Exception as e:
            _send_event("job.log", {"jobId": job_id, "line": f"[host] log tail error: {e}"})

    if log_file:
        threading.Thread(target=_tail_log, args=(job_id, str(log_file)), daemon=True).start()

    def _waiter():
        rc = proc.wait()
        if rc == 0:
            _send_event("job.completed", {"jobId": job_id, "code": rc})
            JOBS.pop(job_id, None)
            return
        # Non-zero: If bearer provided and we preferred cookies-first, retry once with explicit -b
        if bearer and prefer_cookies:
            try_args = [a for a in args if a != "--cookies-first"]
            try_args += ["-b", bearer]
            _send_event("job.retry_bearer", {"jobId": job_id, "code": rc, "args": try_args})
            proc2, err2 = _spawn(try_args, env)
            if err2:
                _send_event("job.failed", {"jobId": job_id, "code": rc, "error": f"retry_spawn_failed:{err2}"})
                JOBS.pop(job_id, None)
                return
            JOBS[job_id] = {"proc": proc2, "start": time.time(), "args": try_args}
            _stream_thr = threading.Thread(target=_stream_proc_output, args=(job_id, proc2), daemon=True)
            _stream_thr.start()
            rc2 = proc2.wait()
            if rc2 == 0:
                _send_event("job.completed", {"jobId": job_id, "code": rc2})
            else:
                _send_event("job.failed", {"jobId": job_id, "code": rc2})
            JOBS.pop(job_id, None)
            return
        else:
            _send_event("job.failed", {"jobId": job_id, "code": rc})
            JOBS.pop(job_id, None)

    threading.Thread(target=_waiter, daemon=True).start()

    _send_response(req.get("id"), True, {"jobId": job_id})
    started_payload = {"jobId": job_id, "args": args, "cwd": str(ROOT)}
    if log_file:
        started_payload["logFile"] = str(log_file)
    _send_event("job.started", started_payload)


def handle_udemy_cancel(req):
    payload = req.get("payload") or {}
    job_id = payload.get("jobId")
    if not job_id or job_id not in JOBS:
        _send_response(req.get("id"), False, error="unknown_job")
        return
    proc = JOBS[job_id]["proc"]
    try:
        if os.name == 'nt':
            # Terminate entire process tree (downloader + yt-dlp/ffmpeg children)
            try:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
            try:
                proc.kill()
            except Exception:
                pass
        else:
            try:
                proc.terminate()
            except Exception:
                pass
        _send_response(req.get("id"), True, {"jobId": job_id})
        _send_event("job.canceled", {"jobId": job_id})
    except Exception as e:
        _send_response(req.get("id"), False, error=f"cancel_failed: {e}")


def handle_pick_folder(req):
    """Show a native folder selection dialog and return the chosen path.
    Response: { ok: true, result: { path: "..." } } or { ok: true } when canceled.
    """
    try:
        payload = req.get("payload") or {}
        start_in = payload.get("startIn") or ""
        if not start_in or not os.path.isdir(start_in):
            try:
                start_in = str(Path.home())
            except Exception:
                start_in = os.getcwd()

        # 1) Try Tkinter (cross-platform)
        chosen = None
        tk_err = None
        try:
            import tkinter as _tk  # type: ignore
            from tkinter import filedialog as _fd  # type: ignore
            root = _tk.Tk()
            root.withdraw()
            try:
                # Keep dialog on top where possible
                try:
                    root.attributes('-topmost', True)
                except Exception:
                    pass
                chosen = _fd.askdirectory(initialdir=start_in, title='Select output folder')
            finally:
                try:
                    root.destroy()
                except Exception:
                    pass
            if chosen:
                chosen = str(chosen)
        except Exception as e:
            tk_err = e

        # 2) OS-specific fallbacks if Tk failed or was unavailable
        if not chosen:
            try:
                if os.name == 'nt':
                    # PowerShell FolderBrowserDialog fallback
                    ps = (
                        "Add-Type -AssemblyName System.Windows.Forms; "
                        "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                        f"$f.Description = 'Select output folder'; $f.SelectedPath = '{start_in.replace('\\', '/') }'; "
                        "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::WriteLine($f.SelectedPath) }"
                    )
                    out = subprocess.check_output(['powershell', '-NoProfile', '-Command', ps], text=True, timeout=120)
                    out = (out or '').strip()
                    if out:
                        chosen = out
                elif sys.platform == 'darwin':
                    # AppleScript choose folder
                    osa = (
                        'set theFolder to POSIX path of (choose folder with prompt "Select output folder")\n'
                        'do shell script "printf %s \\\"" & theFolder & "\\\""'
                    )
                    out = subprocess.check_output(['osascript', '-e', osa], text=True, timeout=120)
                    out = (out or '').strip()
                    if out:
                        chosen = out
                else:
                    # Linux: zenity or kdialog if available
                    def _which(x):
                        from shutil import which
                        return which(x) is not None
                    if _which('zenity'):
                        out = subprocess.check_output(['zenity', '--file-selection', '--directory', '--title=Select output folder', f'--filename={start_in}/'], text=True, timeout=120)
                        out = (out or '').strip()
                        if out:
                            chosen = out
                    elif _which('kdialog'):
                        out = subprocess.check_output(['kdialog', '--getexistingdirectory', start_in], text=True, timeout=120)
                        out = (out or '').strip()
                        if out:
                            chosen = out
            except Exception:
                pass

        # Respond
        if chosen and isinstance(chosen, str) and len(chosen) > 0:
            _send_response(req.get("id"), True, {"path": chosen})
        else:
            # Treat cancel/no-selection as ok with no result (UI will ignore)
            _send_response(req.get("id"), True, {})
    except Exception as e:
        _send_response(req.get("id"), False, error=f"pick_failed:{e}")


HANDLERS = {
    "companion.ping": handle_ping,
    "companion.info": handle_info,
    # Open a file (e.g., current log) in the OS default app
    # Payload: { path: "C:\\...\\logs\\....log" }
    "companion.openLog": handle_open_log,
    # Ask OS to show a folder picker and return the selected path
    # Payload: { startIn: "C:\\..." }
    "companion.pickFolder": handle_pick_folder,
    "udemy.start": handle_udemy_start,
    "udemy.cancel": handle_udemy_cancel,
}


def _manifest_path_win() -> Path:
    # Default manifest next to app root (works for installed + dev)
    return ROOT / 'com.serp.companion.json'


def _manifest_path_macos() -> Path:
    return Path.home() / 'Library' / 'Application Support' / 'Google' / 'Chrome' / 'NativeMessagingHosts' / 'com.serp.companion.json'


def _manifest_path() -> Path:
    if os.name == 'nt':
        return _manifest_path_win()
    elif sys.platform == 'darwin':
        return _manifest_path_macos()
    else:
        # Linux default Chrome location
        return Path.home() / '.config' / 'google-chrome' / 'NativeMessagingHosts' / 'com.serp.companion.json'


def _write_manifest(ext_ids):
    if getattr(sys, 'frozen', False):
        exe_path = str(Path(sys.executable))
    else:
        if os.name == 'nt':
            exe_path = str((ROOT / 'native_host' / 'run-host.bat'))
        else:
            exe_path = str((ROOT / 'native_host' / 'run-host.sh'))
    manifest_file = _manifest_path()
    allowed = [f"chrome-extension://{eid}/" for eid in ext_ids]
    data = {
        "name": "com.serp.companion",
        "description": "SERP Companion Native Host",
        "path": exe_path,
        "type": "stdio",
        "allowed_origins": allowed,
    }
    # Ensure parent exists for non-Windows (Windows writes to ROOT)
    try:
        manifest_file.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
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


def _register_manifest(manifest_path: Path):
    if os.name == 'nt':
        return _register_manifest_win(manifest_path)
    else:
        # On macOS/Linux, writing the manifest file at the correct path is sufficient.
        try:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            ok = manifest_path.exists()
            return (ok, None) if ok else (False, 'manifest_write_failed')
        except Exception as e:
            return False, f'manifest_error:{e}'


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
                'manifest': str(_manifest_path()),
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
                ok, err = _register_manifest(mf)
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


def _try_bind_pair_server(ports):
    for p in ports:
        try:
            httpd = HTTPServer(("127.0.0.1", p), PairHandler)
            return httpd, p
        except PermissionError as e:
            _send_event("host.pair_server_error", {"port": p, "error": f"permission:{e}"})
        except OSError as e:
            # e.g., EADDRINUSE or other bind errors
            _send_event("host.pair_server_error", {"port": p, "error": f"oserror:{e}"})
    return None, None


def run_pair_server(port=None):
    # Candidates in case the default is excluded/reserved on the system
    candidates = []
    if port:
        try:
            candidates = [int(port)]
        except Exception:
            candidates = []
    if not candidates:
        candidates = [60123, 53123, 54123, 55123, 56123, 47123, 42123, 23123]

    httpd, bound = _try_bind_pair_server(candidates)
    if not httpd:
        # Couldn't bind any candidate; exit gracefully without crashing the host
        _send_event("host.pair_server_failed", {"candidates": candidates})
        return

    _send_event("host.pair_server", {"addr": f"http://127.0.0.1:{bound}"})
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    # Start async writer thread for event messages
    t_writer = threading.Thread(target=_writer_loop, daemon=True)
    t_writer.start()

    _send_event("host.ready", {
        "root": str(ROOT),
        "bin": str(BIN_DIR) if getattr(sys, 'frozen', False) else None,
        "packagedExe": str(BIN_DL_WIN if os.name == 'nt' else BIN_DL_UNIX),
        "packagedExeExists": (BIN_DL_WIN.exists() if os.name == 'nt' else BIN_DL_UNIX.exists()),
    })
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
    if len(sys.argv) > 1 and (sys.argv[1] in ('--pair-server', 'pair', 'pair-server') or sys.argv[1].startswith('--pair-server=')):
        # Allow optional explicit port via CLI or environment
        sel_port = None
        for i, arg in enumerate(sys.argv[1:], start=1):
            if arg.startswith('--pair-server='):
                try:
                    sel_port = int(arg.split('=', 1)[1])
                except Exception:
                    sel_port = None
            if arg in ('--pair-port', '--port') and i + 1 < len(sys.argv):
                try:
                    sel_port = int(sys.argv[i + 1])
                except Exception:
                    sel_port = None
        if sel_port is None:
            try:
                env_p = os.getenv('COMPANION_PAIR_PORT')
                if env_p:
                    sel_port = int(env_p)
            except Exception:
                sel_port = None
        run_pair_server(port=sel_port)
    else:
        main()
