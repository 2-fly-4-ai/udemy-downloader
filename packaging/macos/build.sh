#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo_root"

echo "[macOS] Ensuring venv..."
if [[ ! -x "venv/bin/python3" && ! -x "venv/bin/python" ]]; then
  python3 -m venv venv
fi
venv_py="venv/bin/python3"
[[ -x "$venv_py" ]] || venv_py="venv/bin/python"

"$venv_py" -m pip install --upgrade pip >/dev/null
"$venv_py" -m pip install -r requirements.txt pyinstaller >/dev/null

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

