# Udemy Downloader Architecture

## Overview

The Udemy Downloader is a comprehensive system for downloading Udemy courses with DRM support. It consists of three main components that work together seamlessly:

1. **Chrome Extension** - User interface
2. **Native Desktop Companion** - Bridge and orchestrator
3. **Udemy Downloader** - Core download engine

## System Architecture

```
┌─────────────────────────────────────┐
│      Chrome Extension               │
│   (extension/popup.html/js)         │
│                                     │
│  • User interface for config        │
│  • Extract Chrome cookies           │
│  • Send commands to native host     │
└──────────────┬──────────────────────┘
               │
               │ Chrome Native Messaging
               │ (stdio/JSON-RPC)
               ↓
┌─────────────────────────────────────┐
│    Native Desktop Companion         │
│    (native_host/host.py)            │
│                                     │
│  • Pairing server (HTTP)            │
│  • Spawn downloader subprocess      │
│  • Stream logs to extension         │
│  • Folder picker dialogs            │
└──────────────┬──────────────────────┘
               │
               │ subprocess.Popen
               │
               ↓
┌─────────────────────────────────────┐
│     Udemy Downloader                │
│     (main.py)                       │
│                                     │
│  • Download course content          │
│  • DRM decryption (widevine)        │
│  • Video/audio processing (ffmpeg)  │
│  • Subtitle conversion              │
└─────────────────────────────────────┘
```

## Component Details

### 1. Chrome Extension (`extension/`)

**Files:**
- `manifest.json` - Extension configuration (permissions, host permissions)
- `popup.html` - User interface
- `popup.js` - Logic for UI, cookie extraction, Native Messaging
- `background.js` - Service worker for message routing

**Key Features:**
- Clean, modern UI with form controls
- Cookie extraction via Chrome Cookies API
- Converts cookies to Netscape format
- Persistent settings via `chrome.storage.local`
- Real-time log streaming from native host

**Permissions:**
- `nativeMessaging` - Communicate with desktop app
- `storage` - Save user preferences
- `activeTab` - Access current tab info
- `cookies` - Extract Udemy cookies
- Host permissions for `*.udemy.com` and `localhost`

### 2. Native Desktop Companion (`native_host/host.py`)

**Purpose:** Bridge between browser extension and downloader CLI

**Compiled Binaries:**
- Windows: `bin/serp-companion.exe`
- macOS: `bin/serp-companion`
- Linux: `bin/serp-companion` (same as macOS)

**Key Functions:**

#### Message Handlers
- `companion.ping` - Health check
- `companion.info` - Return tool versions (ffmpeg, aria2c, yt-dlp)
- `companion.openLog` - Open log file in default editor
- `companion.pickFolder` - Native folder picker dialog
- `udemy.start` - Spawn downloader with parameters
- `udemy.cancel` - Kill running download job

#### Pairing Server
- Runs on `127.0.0.1` with candidate ports: `[60123, 53123, 54123, 55123, 56123, 47123, 42123, 23123]`
- Extension calls `/pair?extId=<chrome_ext_id>` to register
- Writes Native Messaging manifest JSON
- Updates registry (Windows) or file system (macOS/Linux)

#### Authentication Flow
1. **Cookies-first mode (default):**
   - Extension extracts cookies → writes `cookies.txt`
   - Passes `--browser file` to downloader
   - If job fails and bearer token provided, retries with `-b <token>`

2. **Browser mode:**
   - Uses `--browser chrome` (downloader extracts cookies itself)

3. **Bearer token only:**
   - User unchecks "Use cookies"
   - Passes bearer via environment var `UDEMY_BEARER`

#### Job Management
- Tracks active jobs by UUID
- Spawns downloader with detached stdio (avoids deadlocks)
- Tails log file and streams lines to extension
- Cleans up zombie processes on cancel (Windows: `taskkill /T /F`)

### 3. Udemy Downloader (`main.py`)

**Purpose:** Core download engine with DRM support

**Compiled Binaries:**
- Windows: `bin/udemy-downloader.exe`
- macOS: `bin/udemy-downloader`

**Key Features:**
- Download video, audio, subtitles, assets
- DRM decryption via Widevine CDM
- DASH/HLS stream parsing
- Concurrent segment downloads (aria2c)
- H.265 encoding support
- Chapter filtering
- Quality selection

**Authentication Methods:**
1. Browser cookies (`--browser chrome|firefox|edge|brave|...`)
2. Cookies file (`--browser file` + `cookies.txt`)
3. Bearer token (`-b <token>` or env `UDEMY_BEARER`)

**Dependencies:**
- Python 3.x with packages from `requirements.txt`
- ffmpeg (video/audio processing)
- aria2c (concurrent downloads)
- shaka-packager (DRM/DASH)
- yt-dlp (stream extraction)

## Data Flow

### Typical Download Flow

1. **User Action:**
   - User opens extension popup
   - Pastes Udemy course URL
   - Configures quality, captions, output folder
   - Clicks "Start"

2. **Extension Processing:**
   - Extracts cookies via `chrome.cookies.getAll()`
   - Converts to Netscape format
   - Sends `udemy.start` message to native host

3. **Native Host Processing:**
   - Receives JSON message via stdin
   - Writes `cookies.txt` to disk
   - Builds command: `udemy-downloader.exe -c <url> --browser file -o <outdir> ...`
   - Spawns subprocess with detached stdio
   - Creates timestamped log file
   - Starts log tail thread

4. **Downloader Execution:**
   - Authenticates with Udemy API (cookies)
   - Fetches course metadata
   - Downloads lectures (videos, subtitles, assets)
   - Decrypts DRM content (if keys in `keyfile.json`)
   - Merges video/audio with ffmpeg
   - Writes to output directory

5. **Log Streaming:**
   - Downloader writes to log file
   - Native host tail thread reads new lines
   - Sends `job.log` events to extension
   - Extension displays in popup log panel

6. **Completion:**
   - Downloader exits with code 0 (success) or non-zero (error)
   - Native host sends `job.completed` or `job.failed` event
   - If failure and bearer token available, retries once with bearer

## Platform Support

### Windows (Primary)

**Installer:** Inno Setup (`packaging/windows/installer.iss`)

**Installation Process:**
1. Installs to `%ProgramFiles%\SERP Companion\`
2. Copies binaries:
   - `bin/serp-companion.exe`
   - `bin/udemy-downloader.exe`
   - `tools/*` (ffmpeg, aria2c, yt-dlp, shaka-packager)
3. Writes registry key: `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.serp.companion`
4. Creates manifest: `<AppDir>\com.serp.companion.json`
5. Launches pairing server
6. Opens Chrome Web Store

**Build Command:**
```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\dev.ps1 -Release
```

**Output:**
- `dist-installer/SERP-Companion-Setup.exe`
- `dist-installer/SERP-Companion-Setup.zip`

### macOS (Supported)

**Build Command:** `make macos-release` (or `make macos-installer`)

**Installation Process (PKG):**
1. PyInstaller builds `bin/serp-companion` and `bin/udemy-downloader`.
2. `serpcompanion.app` is staged under `build/macos/`.
3. `dist-installer/serpcompanion.pkg` installs the app into `/Applications`, writes `/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.serp.companion.json`, and installs `/Library/LaunchAgents/com.serp.companion.pairserver.plist`.
4. Optional tools placed in `tools/` are bundled into the app.

**Dev Mode (no installer):**
- Run `packaging/macos/build.sh`.
- Register the manifest manually with `native_host/install_host_macos.sh -e <EXT_ID>` or via the extension’s “Pair Desktop” button.

### Linux (Supported)

**Build:** Same as macOS (Unix-like)

**Manifest Location:**
`~/.config/google-chrome/NativeMessagingHosts/com.serp.companion.json`

## File Locations

### Development Mode (Running from Source)

```
udemy-downloader/
├── extension/              # Chrome extension source
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.js
│   └── background.js
├── native_host/           # Native messaging host
│   ├── host.py           # Main host script
│   ├── run-host.bat      # Windows launcher (dev)
│   └── run-host.sh       # Unix launcher (dev)
├── main.py               # Downloader entry point
├── keyfile.json          # DRM keys (user-provided)
├── cookies.txt           # Generated by extension
├── logs/                 # Download logs
│   └── YYYY-MM-DD-HH-MM-SS.log
├── out_dir/              # Downloaded courses
│   └── <course-name>/
└── tools/                # Bundled executables
    ├── ffmpeg.exe
    ├── aria2c.exe
    ├── yt-dlp.exe
    └── shaka-packager.exe
```

### Production Mode (Installed)

**Windows:**
```
C:\Program Files\SERP Companion\
├── bin\
│   ├── serp-companion.exe
│   └── udemy-downloader.exe
├── tools\
│   ├── ffmpeg.exe
│   ├── aria2c.exe
│   ├── yt-dlp.exe
│   └── shaka-packager.exe
├── com.serp.companion.json    # Native Messaging manifest
├── keyfile.json               # User must provide
├── cookies.txt                # Generated at runtime
└── logs\                      # Runtime logs
```

**macOS (after PKG install):**
```
/Applications/serpcompanion.app/
~/Library/Application Support/Google/Chrome/NativeMessagingHosts/
└── com.serp.companion.json
```

## Configuration Files

### `keyfile.json` (DRM Keys)

User must obtain and provide decryption keys for DRM content:

```json
{
  "key_id": "0123456789abcdef0123456789abcdef",
  "key": "fedcba9876543210fedcba9876543210"
}
```

### `com.serp.companion.json` (Native Messaging Manifest)

```json
{
  "name": "com.serp.companion",
  "description": "SERP Companion Native Host",
  "path": "/path/to/serp-companion.exe",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://kjeahghmchmcjnmhmbmlfcgkhjmkcpie/"
  ]
}
```

### `cookies.txt` (Netscape Cookie Format)

```
# Netscape HTTP Cookie File
# This file was generated by SERP Companion
.udemy.com	TRUE	/	FALSE	1234567890	access_token	xxx
.udemy.com	TRUE	/	TRUE	1234567890	client_id	xxx
```

## Build Process

### Windows Build Pipeline

1. **Setup virtualenv:**
   ```powershell
   python -m venv venv
   venv\Scripts\pip install -r requirements.txt pyinstaller
   ```

2. **Build binaries:**
   ```powershell
   packaging\windows\build.bat
   ```
   - Creates `bin/serp-companion.exe` (from `serp-companion.spec`)
   - Creates `bin/udemy-downloader.exe` (from `udemy-downloader.spec`)

3. **Bundle tools:**
   - Place `ffmpeg.exe`, `aria2c.exe`, `yt-dlp.exe`, `shaka-packager.exe` in `tools/`

4. **Compile installer:**
   - Open `packaging/windows/installer.iss` in Inno Setup
   - Click Build → Compile
   - Output: `dist-installer/SERP-Companion-Setup.exe`

5. **Quick release build:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File packaging\windows\dev.ps1 -Release
   ```
   - Does all above steps + zips installer

### macOS Build Pipeline

1. **Quick build + installer:**
   ```bash
   # Update packaging/macos/config.mk with your Chrome extension ID first
   make macos-release
   ```
   - Creates universal binaries in `bin/`
   - Bundles any helpers found under `tools/`
   - Produces `dist-installer/serpcompanion.pkg`

2. **Manual (dev) build only:**
   ```bash
   packaging/macos/build.sh
   native_host/install_host_macos.sh -e <EXT_ID>  # if you skip the PKG
   ```

## Troubleshooting

### Common Issues

1. **"Cannot connect to native host"**
   - Extension not paired → Click "Pair Desktop" in popup
   - Manifest file missing/wrong path → Check registry (Win) or `~/Library/...` (Mac)
   - Companion not running → Start with `--pair-server` flag

2. **"Packaged EXE not found"**
   - Windows requires `bin/udemy-downloader.exe`
   - Run `packaging/windows/build.bat` to create it

3. **"No cookies found"**
   - Not logged into Udemy in Chrome → Login first
   - Wrong browser selected → Use "chrome" or enable "Use cookies" toggle

4. **DRM content fails**
   - Missing `keyfile.json` → User must provide keys (legal reasons)
   - Wrong keys → Verify key_id and key match the content

5. **"Job failed" immediately**
   - Check log file for errors
   - Verify tools are available: `ffmpeg --version`, `aria2c --version`
   - Try with `--log-level DEBUG`

## Security Considerations

1. **Cookie Storage:**
   - Cookies written to `cookies.txt` in app directory
   - File contains authentication tokens
   - Should be protected from unauthorized access

2. **Bearer Tokens:**
   - Passed via environment variable `UDEMY_BEARER`
   - Not logged to files
   - User responsible for keeping secure

3. **DRM Keys:**
   - User-provided in `keyfile.json`
   - Not distributed with app (legal reasons)
   - Required for encrypted content

4. **Subprocess Security:**
   - Windows: Creates process in new group with no console window
   - Prevents DLL injection attacks
   - Isolated from parent process

## Performance Optimization

1. **Concurrent Downloads:**
   - Default: 10 segments at once
   - Configurable: `-cd 1-30`
   - Uses aria2c for parallel HTTP requests

2. **Log Streaming:**
   - Detached stdio to prevent backpressure
   - Tail log file instead of pipes
   - Non-blocking queue for events

3. **Tool Bundling:**
   - Prepends `tools/` to PATH
   - Avoids system-wide installation requirement
   - Ensures version compatibility

## Future Enhancements

- [ ] Linux native installer (AppImage, deb, rpm)
- [ ] Multi-course batch downloads
- [ ] Resume interrupted downloads
- [ ] Automatic key extraction (if legally possible)
- [ ] Course catalog browser in extension
- [ ] Download progress bar in extension
- [ ] Video quality preview before download
- [ ] Automatic tool updates (ffmpeg, yt-dlp)

## License

MIT License - See `LICENSE` file

## Credits

- Original DRM code: [Jayapraveen/Drm-Dash-stream-downloader](https://github.com/Jayapraveen/Drm-Dash-stream-downloader)
- PSSH extraction: [alastairmccormack/pywvpssh](https://github.com/alastairmccormack/pywvpssh)
- VTT conversion: [lbrayner/vtt-to-srt](https://github.com/lbrayner/vtt-to-srt)
- Udemy API info: [r0oth3x49/udemy-dl](https://github.com/r0oth3x49/udemy-dl)
