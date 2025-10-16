#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 -e <EXTENSION_ID> [-p <path-to-serp-companion>]

Writes the Chrome Native Messaging host manifest for SERP Companion on macOS.

Defaults:
- Looks for binary at repo-root/bin/serp-companion if -p is not provided
- Writes manifest to:
  ~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.serp.companion.json

Examples:
  $0 -e abcdefghijklmnopqrstuuvwxyz
  $0 -e abcdefghijklmnopqrstuuvwxyz -p "/Applications/SERP Companion/bin/serp-companion"
EOF
}

ext_id=""
exe_path=""

while getopts ":e:p:h" opt; do
  case "$opt" in
    e) ext_id="$OPTARG" ;;
    p) exe_path="$OPTARG" ;;
    h) usage; exit 0 ;;
    *) usage; exit 1 ;;
  esac
done

if [[ -z "$ext_id" ]]; then
  echo "Missing -e <EXTENSION_ID>" 1>&2
  usage
  exit 1
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -z "$exe_path" ]]; then
  exe_path="$repo_root/bin/serp-companion"
fi

if [[ ! -x "$exe_path" ]]; then
  echo "Host binary not found or not executable: $exe_path" 1>&2
  exit 1
fi

dest_dir="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
mkdir -p "$dest_dir"
manifest="$dest_dir/com.serp.companion.json"

cat > "$manifest" <<JSON
{
  "name": "com.serp.companion",
  "description": "SERP Companion Native Host",
  "path": "${exe_path}",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://${ext_id}/"
  ]
}
JSON

echo "Wrote manifest: $manifest"
echo "Restart Chrome if it was open."

