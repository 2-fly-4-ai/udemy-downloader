Quickest way to run the Chrome Extension + Desktop Companion

Option A — One‑Click Installer (for users)
- Build (maintainer):
  - Locally: `python -m venv venv && venv\Scripts\pip install -r requirements.txt pyinstaller` then `packaging\windows\build.bat`
  - Or via GitHub Actions: trigger workflow `build-windows-exe` and download artifacts (`bin\serp-companion.exe`, `bin\udemy-downloader.exe`)
  - Put `ffmpeg.exe`, `yt-dlp.exe`, `aria2c.exe`, `shaka-packager.exe` into `tools\`
  - Edit `packaging\windows\installer.iss` and set:
    - `#define MyExtensionId "<your_webstore_or_dev_id>"`
    - `#define MyExtensionSlug "<your_webstore_slug>"` (optional but recommended)
  - Build installer in Inno Setup → get `SERP-Companion-Setup.exe`
- Install (user):
  - Run `SERP-Companion-Setup.exe`
  - Installer auto‑registers the Native Messaging host
  - It opens the Chrome Web Store page for your extension (if slug provided). Install the extension
  - Click the extension → “Ping” then “Info” to verify host/tools
  - Paste a Udemy course URL
  - Optional: check “Use cookies (extract…)” to generate `cookies.txt` automatically
  - Optional: paste a bearer token; the host will retry with it if cookies fail
  - Click “Start”

Option B — Dev Mode (no installer)
- Chrome installed and logged into Udemy
- Python 3 installed. Create and populate venv:
  - Windows: `python -m venv venv && venv\Scripts\pip install -r requirements.txt`
  - macOS/Linux: `python3 -m venv venv && venv/bin/pip install -r requirements.txt`
- Load extension: Chrome → `chrome://extensions` → Load unpacked `extension/`
- Register host: `powershell -ExecutionPolicy Bypass -File native_host\install_host.ps1 -ExtensionId <YOUR_EXTENSION_ID>` → restart Chrome
- Click “Ping” and “Info” to verify, then “Start” with a course URL

Option C — macOS Build + Installer
- Configure `packaging/macos/config.mk` with your Chrome extension ID.
- Build on macOS: `make macos-release`
  - Produces `dist-installer/serpcompanion.pkg` plus refreshed binaries in `bin/`
  - Place macOS versions of `ffmpeg`, `yt-dlp`, `aria2c`, `packager`, etc. into `tools/` before running the Make target if you want them bundled.
- Install (user):
  - Run the PKG (requires admin). It copies the app into `/Applications`, registers the native messaging manifest, and launches the pair server automatically.
  - Install the Chrome extension from the Web Store and click “Ping” / “Info” to verify connectivity.
- Dev mode (no installer): still supported via `packaging/macos/build.sh` + `native_host/install_host_macos.sh -e <YOUR_EXTENSION_ID>` if you need a manual workflow.

Notes
- Authentication uses `--browser chrome`; ensure you’re logged into Udemy in Chrome
- The popup can extract cookies and pass them to the downloader as `cookies.txt` and will prefer those first. If a bearer token is provided, the host will retry with bearer only if the cookies run fails.
- DRM content requires `keyfile.json` in install directory (or repo root in dev mode)
- Downloads default to `~/Videos/Udemy` (falls back to `~/Downloads/Udemy`)
- Popup now has “Cancel” and “Info” buttons; Info shows tool versions and paths
- Pair server binds on 127.0.0.1 using candidate ports [60123, 53123, 54123, 55123, 56123, 47123, 42123, 23123]. If 60123 is reserved/excluded on your system (common with Hyper‑V/WSL), the server falls back automatically and the popup tries all candidates when you click “Pair”.
