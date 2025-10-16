#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo_root"

app_dir="SERP Companion"
stage="out/macos/$app_dir"

echo "[macOS] Staging folder..."
rm -rf "$stage" out/macos 2>/dev/null || true
mkdir -p "$stage/bin"

if [[ ! -x "bin/serp-companion" || ! -x "bin/udemy-downloader" ]]; then
  echo "Missing binaries. Run packaging/macos/build.sh first." 1>&2
  exit 1
fi

cp -a bin/serp-companion "$stage/bin/serp-companion"
cp -a bin/udemy-downloader "$stage/bin/udemy-downloader"
chmod +x "$stage/bin/serp-companion" "$stage/bin/udemy-downloader"

# Bundle tools if present (macOS binaries should be placed by maintainers)
if [[ -d tools ]]; then
  mkdir -p "$stage/tools"
  cp -a tools/. "$stage/tools/" || true
  chmod -R +x "$stage/tools" || true
fi

# Include README and keyfile sample if present
cp -f README.md "$stage/" 2>/dev/null || true
cp -f keyfile.json "$stage/" 2>/dev/null || true

mkdir -p dist-installer
volname="SERP Companion"
img_path="dist-installer/SERP-Companion-macOS.dmg"
rm -f "$img_path"

echo "[macOS] Creating DMG..."
hdiutil create -volname "$volname" -srcfolder "$(dirname "$stage")" -ov -fs HFS+ -format UDZO "$img_path"

echo "[macOS] DMG created: $img_path"

