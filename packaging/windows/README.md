Windows One‑Click Installer Plan

Goal
- Ship a single installer (Inno Setup) that:
  - Installs the native host + downloader binaries (no Python/pip required)
  - Bundles ffmpeg/aria2c/shaka‑packager in a local tools folder
  - Registers the Chrome Native Messaging host to work with your extension ID

Build Steps (for maintainers)
1) Build frozen binaries with PyInstaller
   - Option A (local venv): `python -m venv venv && venv\\Scripts\\pip install -r requirements.txt pyinstaller`
   - Option B (CI/system Python): Ensure `pip install -r requirements.txt pyinstaller` ran in the current Python
   - Run: `packaging\\windows\\build.bat` (auto-detects venv or system Python)
   - Outputs: `bin\\serp-companion.exe`, `bin\\udemy-downloader.exe`

2) Prepare tools folder (repo root)
   - Place `ffmpeg.exe` (and required DLLs) under repo root `tools\\` (e.g., `tools\\ffmpeg.exe`)
   - Place `aria2c.exe` under repo root (already present) or into `tools\\`
   - Place `shaka-packager.exe` under repo root `tools\\` (rename to `packager.exe` if desired)

3) Set extension ID in installer script
   - Edit `packaging\\windows\\installer.iss` → set `#define MyExtensionId "<your_id>"`

4) Build the installer
   - Open `packaging\\windows\\installer.iss` in Inno Setup Compiler and build
   - Distribute the generated `SERP-Companion-Setup.exe`

Install Experience (for users)
- Run the installer and click Next
- It registers the Native Messaging host and places binaries in `C:\\Program Files\\SERP Companion` (default)
- After install, it can open the Chrome Web Store page to install the extension
- The extension can immediately connect and start jobs; no Python/pip required

Notes
- The host prefers the frozen `bin\\udemy-downloader.exe` if present; otherwise it falls back to Python `main.py`
- The host prepends `{app}\\tools` to PATH, so included tools are used automatically
- DRM keys still need to be provided by the user (`keyfile.json` in `{app}`)

Path assumptions for Inno Setup
- Relative paths in `installer.iss` are resolved from the script directory `packaging\\windows\\`.
- The script now expects binaries in repo root `bin\\` and tools in repo root `tools\\` (handled via `..\\..\\` paths).
- If you get a "Source file ... does not exist" error, ensure `bin\\serp-companion.exe` and `bin\\udemy-downloader.exe` exist in the repo root and that tools are under `tools\\`.
