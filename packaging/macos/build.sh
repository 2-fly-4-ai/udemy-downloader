#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo_root"

python_bin="${PYTHON_BIN:-python3.11}"
if ! command -v "$python_bin" >/dev/null 2>&1; then
  python_bin="python3"
fi

echo "[macOS] Using Python interpreter: $python_bin"

need_venv=1
if [[ -x "venv/bin/python3" || -x "venv/bin/python" ]]; then
  need_venv=0
  current="$(venv/bin/python3 --version 2>/dev/null || venv/bin/python --version 2>/dev/null || echo "")"
  target="$("$python_bin" --version 2>/dev/null || echo "")"
  if [[ -n "$current" && -n "$target" && "$current" != "$target" ]]; then
    if [[ "${FORCE_REBUILD_VENV:-0}" == "1" ]]; then
      echo "[macOS] FORCE_REBUILD_VENV=1 and interpreter mismatch ($current vs $target); rebuilding venv"
      rm -rf venv
      need_venv=1
    else
      echo "[macOS] Warning: existing venv built with $current; toolchain requests $target. Continuing with existing env."
    fi
  fi
fi

if [[ $need_venv -eq 1 ]]; then
  "$python_bin" -m venv venv
fi

venv_py="venv/bin/python3"
[[ -x "$venv_py" ]] || venv_py="venv/bin/python"

export PYINSTALLER_CONFIG_DIR="$repo_root/.pyinstaller"
mkdir -p "$PYINSTALLER_CONFIG_DIR"

if ! "$venv_py" -m pip show pyinstaller >/dev/null 2>&1; then
  "$venv_py" -m pip install --upgrade pip >/dev/null
  "$venv_py" -m pip install -r requirements.txt pyinstaller >/dev/null
fi

echo "[macOS] Cleaning old builds..."
rm -rf build dist

echo "[macOS] Building udemy-downloader (console)..."
"$venv_py" -m PyInstaller --clean --noconfirm \
  --onefile \
  --name udemy-downloader \
  main.py

echo "[macOS] Building serp-companion (no console)..."
"$venv_py" -m PyInstaller --clean --noconfirm \
  --onefile \
  --noconsole \
  --name serp-companion \
  native_host/host.py

mkdir -p bin
cp -f dist/udemy-downloader bin/udemy-downloader
cp -f dist/serp-companion bin/serp-companion
chmod +x bin/udemy-downloader bin/serp-companion

echo "[macOS] Done. Binaries in bin/"
