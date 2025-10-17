macOS Packaging
================

The Makefile now handles the entire macOS workflow: build the binaries, bundle tools, stage the `.app`, and generate a ready-to-install PKG. The DMG flow documented previously has been retired.

## Quick Start

```bash
# 1. Verify packaging/macos/config.mk contains your Chrome extension ID
# 2. Optionally copy helper binaries into tools/
make macos-release        # or make macos-installer
```

Artifacts:
- `dist-installer/serpcompanion.pkg`
- `bin/serp-companion`, `bin/udemy-downloader`
- Staged bundle under `build/macos/serpcompanion.app`

## Bundling Optional Tools

Create a `tools/` folder at the repo root and drop macOS builds of:
- `ffmpeg`
- `yt-dlp`
- `aria2c`
- `packager` (Shaka Packager)

Any executables in `tools/` are copied into `serpcompanion.app/Contents/Resources/tools` during the build and shipped with the PKG. Ensure they are executable (`chmod +x tools/*`).

## PKG Post-Install Actions

The generated PKG:
- Installs the app to `/Applications/serpcompanion.app`
- Writes `/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.serp.companion.json`
- Installs `/Library/LaunchAgents/com.serp.companion.pairserver.plist` and bootstraps it for the console user
- Drops `Contents/Resources/uninstall.sh` for cleanup

Codesign/notarize the PKG (and optionally the app bundle) before distributing releases.

## Development Mode (Manual)

If you only need binaries without packaging:

```bash
packaging/macos/build.sh
native_host/install_host_macos.sh -e <EXTENSION_ID>   # optional manual manifest registration
```

This keeps the old developer workflow intact for quick local testing.
