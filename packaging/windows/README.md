Windows One‑Click Installer Plan

Goal
- Ship a single installer (Inno Setup) that:
  - Installs the native host + downloader binaries (no Python/pip required)
  - Bundles ffmpeg/aria2c/shaka‑packager in a local tools folder
  - Registers the Chrome Native Messaging host to work with your extension ID

Build Steps (for maintainers)
1) Build frozen binaries with PyInstaller
   - Quick: `powershell -ExecutionPolicy Bypass -File packaging\\windows\\dev.ps1 -Setup -Build`
   - Manual Option A (local venv): `python -m venv venv && venv\\Scripts\\pip install -r requirements.txt pyinstaller`
   - Manual Option B (system Python/CI): Ensure `pip install -r requirements.txt pyinstaller` ran in the current Python
   - Or run: `packaging\\windows\\build.bat` (auto-detects venv or system Python)
   - Outputs: `bin\\serp-companion.exe`, `bin\\udemy-downloader.exe`

2) Prepare tools folder (repo root)
   - Place `ffmpeg.exe` (and required DLLs) under repo root `tools\\` (e.g., `tools\\ffmpeg.exe`)
   - Place `aria2c.exe` under repo root (already present) or into `tools\\`
   - Place `shaka-packager.exe` under repo root `tools\\` (rename to `packager.exe` if desired)

3) Set extension ID in installer script
   - Edit `packaging\\windows\\installer.iss` → set `#define MyExtensionId "<your_id>"`

4) Build the installer
   - Option A: `powershell -ExecutionPolicy Bypass -File packaging\\windows\\dev.ps1 -Installer`
   - Option B: Open `packaging\\windows\\installer.iss` in Inno Setup Compiler and build
   - Distribute the generated `SERP-Companion-Setup.exe`

5) One-shot Release build (binaries + installer + zip)
   - `powershell -ExecutionPolicy Bypass -File packaging\\windows\\dev.ps1 -Release`
   - Outputs:
     - `bin\\serp-companion.exe`, `bin\\udemy-downloader.exe`
     - `dist-installer\\SERP-Companion-Setup.exe`
     - `dist-installer\\SERP-Companion-Setup.zip`

6) GitHub Release (CI)
   - Tag and push: `git tag v0.1.0 && git push origin v0.1.0`
   - Or run Actions workflow manually: `release-windows` with inputs `tag_name` and optional `release_name`
   - The workflow builds binaries, compiles the installer, zips it, and attaches both files to the GitHub Release

Install Experience (for users)
- Run the installer and click Next
- It registers the Native Messaging host and places binaries in `C:\\Program Files\\SERP Companion` (default)
- After install, it can open the Chrome Web Store page to install the extension
- The extension can immediately connect and start jobs; no Python/pip required

Notes
- The host requires the frozen `bin\\udemy-downloader.exe` on Windows (no Python `main.py` fallback). If it’s missing, jobs fail with `packaged_exe_not_found`.
- The host prepends `{app}\\tools` to PATH, so included tools are used automatically
- DRM keys still need to be provided by the user (`keyfile.json` in `{app}`)

Troubleshooting
- If the popup shows `[err] packaged_exe_not_found: <path>`, verify that path exists on disk. Expected path: `{app}\\bin\\udemy-downloader.exe`.
- Click “Info” in the popup to see diagnostics (`packaged_exe_expected`, `packaged_exe_exists`, `root`, `bin_dir`).
- Antivirus can quarantine PyInstaller EXEs. Restore/quarantine‑exclude the EXEs, or rebuild and hot‑replace:
  - `powershell -ExecutionPolicy Bypass -File packaging\\windows\\dev.ps1 -Build -HotReplace`
- To rebuild the full installer:
  - `powershell -ExecutionPolicy Bypass -File packaging\\windows\\dev.ps1 -Release`

Dev shortcuts
- Hot replace installed EXEs after code changes: `powershell -ExecutionPolicy Bypass -File packaging\\windows\\dev.ps1 -Build -HotReplace`
- Start pair server manually after replacement: `powershell -ExecutionPolicy Bypass -File packaging\\windows\\dev.ps1 -Pair`
- Zip the installer for release: `powershell -ExecutionPolicy Bypass -File packaging\\windows\\dev.ps1 -Zip`

Path assumptions for Inno Setup
- Relative paths in `installer.iss` are resolved from the script directory `packaging\\windows\\`.
- The script now expects binaries in repo root `bin\\` and tools in repo root `tools\\` (handled via `..\\..\\` paths).
- If you get a "Source file ... does not exist" error, ensure `bin\\serp-companion.exe` and `bin\\udemy-downloader.exe` exist in the repo root and that tools are under `tools\\`.
WSL note
- From WSL, invoke Windows PowerShell so Windows tools (cmd.exe, Inno Setup) are available:
  - `REPO_WIN=$(wslpath -w "$PWD") && powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$REPO_WIN\packaging\windows\dev.ps1" -Release`
  - Running `powershell` inside WSL uses Linux PowerShell and will not find `cmd.exe`/Windows Python.
