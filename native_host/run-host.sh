#!/usr/bin/env bash
set -euo pipefail

# Run the host in dev mode on macOS/Linux. Tries venv first.

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

if [[ -x "$repo_root/venv/bin/python3" ]]; then
  py="$repo_root/venv/bin/python3"
elif [[ -x "$repo_root/venv/bin/python" ]]; then
  py="$repo_root/venv/bin/python"
else
  py="python3"
fi

exec "$py" -u "$script_dir/host.py"

