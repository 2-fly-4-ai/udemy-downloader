macOS Packaging

Overview
- Build PyInstaller binaries for macOS (serp-companion and udemy-downloader)
- Bundle optional tools in a `tools/` folder next to the binaries
- Optionally create a DMG or ZIP for distribution
- Register Chrome Native Messaging host either via the Companion’s Pair action or the provided install script

Prereqs
- macOS with Python 3.
- Xcode Command Line Tools (for `hdiutil` and general build tools).
- Optional: Homebrew for installing `ffmpeg`, `aria2`, `shaka-packager`, or to place macOS binaries under `tools/` to bundle.

Build Binaries
```
packaging/macos/build.sh
```
Outputs:
- `bin/serp-companion` (GUI-less app used as Chrome Native Messaging host)
- `bin/udemy-downloader` (CLI downloader)

Bundle Tools (optional)
- Create a `tools/` folder at repo root and place macOS binaries:
  - `tools/ffmpeg`, `tools/yt-dlp`, `tools/aria2c`, `tools/packager` (aka shaka-packager)
  - The Companion prepends `{root}/tools` to PATH when spawning the downloader.

Create DMG (optional)
```
packaging/macos/make-dmg.sh
```
Outputs:
- `dist-installer/SERP-Companion-macOS.dmg`

Register Native Host (macOS)
Option A — From the extension (recommended):
- Click Pair in the popup. On macOS the host writes the Chrome Native Messaging manifest to:
  - `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.serp.companion.json`

Option B — Script:
```
native_host/install_host_macos.sh -e <YOUR_EXTENSION_ID> [-p /path/to/serp-companion]
```
- `-p` is optional; if omitted, it will try to use `bin/serp-companion`

Notes
- Codesigning/notarization is not configured. For distribution outside Gatekeeper warnings, sign binaries and the DMG with your Apple Developer ID.
- Universal2 builds are supported by PyInstaller when invoked on Apple Silicon with appropriate flags; this script builds for the current arch by default.

