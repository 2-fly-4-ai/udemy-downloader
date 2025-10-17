# macOS Installer Guide

This project now ships a single macOS installer (`serpcompanion.pkg`) that drops the desktop companion into `/Applications`, registers the Chrome native-messaging manifest, and boots the pair server automatically. The drag-and-drop DMG flow has been removed.

## Build Overview

```bash
# 1. Optional: tweak packaging/macos/config.mk (extension ID, future settings)
# 2. Build the PyInstaller binaries, assemble the app bundle, and emit the PKG
make macos-release        # equivalent to make macos-installer
```

Outputs:
- `dist-installer/serpcompanion.pkg`
- `bin/serp-companion`, `bin/udemy-downloader` (for local testing)

## Configuration

`packaging/macos/config.mk` holds build-time settings:

```
EXTENSION_ID = ajklnonoeaemaeidgfkeelkjlcdccdjl
```

Update this file if the Chrome Web Store ID changes. Use `EXTENSION_ID=... make macos-release` when you need a one-off build for a different ID (for example, a dev profile).

To bundle command-line helpers, drop macOS binaries into `repo-root/tools/` (e.g., `ffmpeg`, `yt-dlp`, `aria2c`, `packager`) before invoking the Make target. They will be copied into `serpcompanion.app/Contents/Resources/tools` and deployed alongside the app.

## Installer Actions

When a user runs the PKG:
- `/Applications/serpcompanion.app` (from the staged bundle) is installed.
- `/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.serp.companion.json` is written with the embedded extension ID.
- `/Library/LaunchAgents/com.serp.companion.pairserver.plist` is installed and bootstrapped for the console user so the companion’s `--pair-server` endpoint is live immediately.
- `Contents/Resources/uninstall.sh` is available inside the app bundle for cleanup (`sudo "/Applications/serpcompanion.app/Contents/Resources/uninstall.sh"`).

Gatekeeper signing/notarization is still manual—codesign the app/PKG and submit for notarization as part of release packaging.

## Development Notes

- `make macos-installer` is an alias for `make macos-release` if you only need the PKG.
- `make clean-macos` removes build artifacts: `build/macos/` and `dist-installer/serpcompanion.pkg`.
- For manual dev testing without the PKG, you can still run `packaging/macos/build.sh` and load the extension unpacked; register the host with `native_host/install_host_macos.sh -e <EXTENSION_ID>` if you skip the installer.

## Testing Checklist

- [ ] Installer completes without prompts beyond standard macOS warnings.
- [ ] `/Applications/serpcompanion.app` launches and logs appear under `~/Library/Logs/SERP Companion` (if applicable).
- [ ] Manifest exists at `/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.serp.companion.json`.
- [ ] Chrome extension can Ping/Info immediately after install.
- [ ] Pair server LaunchAgent is running (`launchctl list | grep com.serp.companion.pairserver`).
- [ ] Uninstall script removes the LaunchAgent, manifest, and app.
- [ ] Optional tools bundled in `tools/` are executable within the app.
- [ ] Codesign/notarization succeeds (if applied).
