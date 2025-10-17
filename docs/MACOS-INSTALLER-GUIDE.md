# macOS Installer Creation Guide

## Current Status

The macOS build process is **partially complete**:
- ✅ Binary compilation working (`packaging/macos/build.sh`)
- ✅ DMG creation script exists (`packaging/macos/make-dmg.sh`)
- ✅ Native Messaging manifest registration
- ⚠️ No automated installer like Windows Inno Setup

## What We Have vs. What We Need

### Current macOS Build (What Works)

```bash
# Build binaries
packaging/macos/build.sh

# Creates:
# - bin/serp-companion (standalone executable)
# - bin/udemy-downloader (standalone executable)

# Optional: Create DMG
packaging/macos/make-dmg.sh

# Creates:
# - dist-installer/SERP-Companion-macOS.dmg
```

**Manual Registration:**
```bash
# Register Native Messaging host
native_host/install_host_macos.sh -e <EXTENSION_ID>

# Or via extension popup:
# Click "Pair Desktop" button
```

### What We Need (Full Installer)

To match the Windows experience, we need a **complete macOS installer** that:

1. **Packages the app as a proper .app bundle**
2. **Installs to /Applications**
3. **Bundles all dependencies**
4. **Auto-registers Chrome Native Messaging**
5. **Optionally launches and pairs on first run**
6. **Includes uninstaller**

## Option 1: .app Bundle + DMG (Recommended)

This is the standard macOS distribution method.

### Structure Needed

```
SERP Companion.app/
├── Contents/
│   ├── Info.plist              # App metadata
│   ├── MacOS/
│   │   ├── serp-companion      # Main executable
│   │   └── udemy-downloader    # Downloader binary
│   ├── Resources/
│   │   ├── icon.icns           # App icon
│   │   ├── tools/              # Bundled CLI tools
│   │   │   ├── ffmpeg
│   │   │   ├── aria2c
│   │   │   ├── yt-dlp
│   │   │   └── packager
│   │   └── keyfile.json        # Template/placeholder
│   └── Frameworks/             # (if needed for dependencies)
```

### Steps to Create

#### 1. Create .app Bundle Structure

Create a new build script `packaging/macos/create-app-bundle.sh`:

```bash
#!/bin/bash
set -e

APP_NAME="SERP Companion"
BUNDLE_DIR="dist-installer/${APP_NAME}.app"
CONTENTS_DIR="${BUNDLE_DIR}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"
TOOLS_DIR="${RESOURCES_DIR}/tools"

# Clean previous build
rm -rf "${BUNDLE_DIR}"

# Create directory structure
mkdir -p "${MACOS_DIR}"
mkdir -p "${RESOURCES_DIR}"
mkdir -p "${TOOLS_DIR}"

# Copy binaries
cp bin/serp-companion "${MACOS_DIR}/"
cp bin/udemy-downloader "${MACOS_DIR}/"
chmod +x "${MACOS_DIR}/serp-companion"
chmod +x "${MACOS_DIR}/udemy-downloader"

# Copy tools (if they exist)
for tool in ffmpeg aria2c yt-dlp packager; do
    if [ -f "tools/${tool}" ]; then
        cp "tools/${tool}" "${TOOLS_DIR}/"
        chmod +x "${TOOLS_DIR}/${tool}"
    fi
done

# Copy resources
if [ -f "keyfile.json" ]; then
    cp keyfile.json "${RESOURCES_DIR}/"
fi

# Create Info.plist
cat > "${CONTENTS_DIR}/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>serp-companion</string>
    <key>CFBundleIdentifier</key>
    <string>com.serp.companion</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleVersion</key>
    <string>0.1.1</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.1</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

echo "✅ App bundle created: ${BUNDLE_DIR}"
```

#### 2. Create App Icon (Optional but Professional)

```bash
# Create icon from PNG (requires imagemagick or sips)
mkdir -p icon.iconset
# Add various sizes: 16x16, 32x32, 64x64, 128x128, 256x256, 512x512, 1024x1024
iconutil -c icns icon.iconset -o "${RESOURCES_DIR}/icon.icns"
```

Add to Info.plist:
```xml
<key>CFBundleIconFile</key>
<string>icon.icns</string>
```

#### 3. Create Post-Install Script

Create `packaging/macos/post-install.sh` to run after app is copied:

```bash
#!/bin/bash
# Post-install script for SERP Companion
# This runs after the .app is copied to /Applications

APP_PATH="/Applications/SERP Companion.app"
COMPANION_BIN="${APP_PATH}/Contents/MacOS/serp-companion"
MANIFEST_DIR="${HOME}/Library/Application Support/Google/Chrome/NativeMessagingHosts"
MANIFEST_FILE="${MANIFEST_DIR}/com.serp.companion.json"

# Ensure manifest directory exists
mkdir -p "${MANIFEST_DIR}"

# Create Native Messaging manifest
cat > "${MANIFEST_FILE}" << EOF
{
  "name": "com.serp.companion",
  "description": "SERP Companion Native Host",
  "path": "${COMPANION_BIN}",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://YOUR_EXTENSION_ID_HERE/"
  ]
}
EOF

echo "✅ Native Messaging host registered"
echo "📝 Manifest: ${MANIFEST_FILE}"

# Optional: Launch pairing server
"${COMPANION_BIN}" --pair-server &

# Open Chrome Web Store
open "https://chrome.google.com/webstore/category/extensions"
```

#### 4. Create DMG with Installer

Update `packaging/macos/make-dmg.sh` to include:
- .app bundle
- Symlink to /Applications for easy drag-and-drop install
- README with instructions
- Optional: background image, custom icon arrangement

```bash
#!/bin/bash
set -e

APP_NAME="SERP Companion"
DMG_NAME="SERP-Companion-macOS"
VOLUME_NAME="SERP Companion Installer"
SOURCE_DIR="dist-installer"
DMG_OUTPUT="${SOURCE_DIR}/${DMG_NAME}.dmg"
TEMP_DMG="${SOURCE_DIR}/temp.dmg"

# Build app bundle first
./packaging/macos/create-app-bundle.sh

# Create temporary mount point
mkdir -p "${SOURCE_DIR}/dmg-contents"

# Copy app bundle
cp -r "${SOURCE_DIR}/${APP_NAME}.app" "${SOURCE_DIR}/dmg-contents/"

# Create Applications symlink
ln -s /Applications "${SOURCE_DIR}/dmg-contents/Applications"

# Create README
cat > "${SOURCE_DIR}/dmg-contents/README.txt" << EOF
SERP Companion - Udemy Downloader

Installation:
1. Drag "SERP Companion.app" to the Applications folder
2. Open SERP Companion from Applications or Launchpad
3. Install Chrome extension from Web Store
4. Click "Pair Desktop" in extension popup
5. Start downloading!

Requirements:
- macOS 10.13 or later
- Google Chrome
- Active Udemy account

For support: https://github.com/2-fly-4-ai/udemy-downloader
EOF

# Create DMG
hdiutil create -volname "${VOLUME_NAME}" \
    -srcfolder "${SOURCE_DIR}/dmg-contents" \
    -ov -format UDZO "${DMG_OUTPUT}"

# Cleanup
rm -rf "${SOURCE_DIR}/dmg-contents"

echo "✅ DMG created: ${DMG_OUTPUT}"
```

#### 5. Code Signing (For Distribution)

To distribute outside App Store, you need:

```bash
# Sign the app
codesign --force --deep --sign "Developer ID Application: Your Name (TEAM_ID)" \
    "dist-installer/SERP Companion.app"

# Sign the DMG
codesign --force --sign "Developer ID Application: Your Name (TEAM_ID)" \
    "dist-installer/SERP-Companion-macOS.dmg"

# Notarize (required for macOS 10.15+)
xcrun notarytool submit "dist-installer/SERP-Companion-macOS.dmg" \
    --apple-id "your@email.com" \
    --team-id "TEAM_ID" \
    --password "app-specific-password" \
    --wait

# Staple notarization
xcrun stapler staple "dist-installer/SERP-Companion-macOS.dmg"
```

## Option 2: .pkg Installer (Alternative)

macOS also supports `.pkg` installers (like Windows .msi).

### Advantages
- Can run scripts before/after installation
- Can install to system locations with sudo
- More automated than drag-and-drop DMG

### Disadvantages
- Requires `productbuild` and `pkgbuild`
- Users may be wary of .pkg files
- Less common for Mac apps

### Create .pkg

```bash
#!/bin/bash
# Build .pkg installer

# 1. Create component package
pkgbuild --root "dist-installer/SERP Companion.app" \
    --identifier "com.serp.companion" \
    --version "0.1.1" \
    --install-location "/Applications/SERP Companion.app" \
    --scripts "packaging/macos/scripts" \
    "dist-installer/SERP-Companion-Component.pkg"

# 2. Create product archive (optional: adds custom UI)
productbuild --distribution "packaging/macos/distribution.xml" \
    --resources "packaging/macos/resources" \
    --package-path "dist-installer" \
    "dist-installer/SERP-Companion-Installer.pkg"

# 3. Sign the installer
productsign --sign "Developer ID Installer: Your Name (TEAM_ID)" \
    "dist-installer/SERP-Companion-Installer.pkg" \
    "dist-installer/SERP-Companion-macOS.pkg"
```

Create `packaging/macos/distribution.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="1">
    <title>SERP Companion</title>
    <organization>com.serp</organization>
    <domains enable_localSystem="true"/>
    <options customize="never" require-scripts="false" rootVolumeOnly="true" />
    <volume-check>
        <allowed-os-versions>
            <os-version min="10.13" />
        </allowed-os-versions>
    </volume-check>
    <choices-outline>
        <line choice="default">
            <line choice="com.serp.companion"/>
        </line>
    </choices-outline>
    <choice id="default"/>
    <choice id="com.serp.companion" visible="false">
        <pkg-ref id="com.serp.companion"/>
    </choice>
    <pkg-ref id="com.serp.companion" version="0.1.1" onConclusion="none">SERP-Companion-Component.pkg</pkg-ref>
</installer-gui-script>
```

## Option 3: Homebrew Cask (For Developer Audience)

If your users are technical, consider a Homebrew Cask:

```ruby
# serp-companion.rb
cask "serp-companion" do
  version "0.1.1"
  sha256 "abc123..."

  url "https://github.com/2-fly-4-ai/udemy-downloader/releases/download/v#{version}/SERP-Companion-macOS.dmg"
  name "SERP Companion"
  desc "Udemy course downloader with DRM support"
  homepage "https://github.com/2-fly-4-ai/udemy-downloader"

  app "SERP Companion.app"

  postflight do
    system_command "#{appdir}/SERP Companion.app/Contents/MacOS/serp-companion",
                   args: ["--pair-server"],
                   background: true
  end

  uninstall quit: "com.serp.companion"

  zap trash: [
    "~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.serp.companion.json",
    "~/Library/Logs/SERP Companion",
  ]
end
```

Users install with:
```bash
brew install --cask serp-companion
```

## Recommended Approach

**For end-users (non-technical):**
1. Use **Option 1 (.app Bundle + DMG)**
2. Add drag-and-drop installation
3. Include post-install launcher that runs `--pair-server`
4. Code sign and notarize for macOS 10.15+

**For developers/technical users:**
1. Use **Option 3 (Homebrew Cask)**
2. Much simpler distribution
3. Automatic updates via `brew upgrade`

## Complete Build Workflow

Create `packaging/macos/build-release.sh`:

```bash
#!/bin/bash
set -e

echo "🔨 Building SERP Companion for macOS..."

# 1. Build binaries
echo "📦 Step 1: Building binaries..."
./packaging/macos/build.sh

# 2. Create app bundle
echo "📦 Step 2: Creating .app bundle..."
./packaging/macos/create-app-bundle.sh

# 3. Download/bundle tools
echo "📦 Step 3: Bundling tools..."
./packaging/macos/bundle-tools.sh  # (create this script)

# 4. Sign app (if certificates available)
if [ -n "$SIGNING_IDENTITY" ]; then
    echo "✍️  Step 4: Signing app..."
    codesign --force --deep --sign "$SIGNING_IDENTITY" \
        "dist-installer/SERP Companion.app"
fi

# 5. Create DMG
echo "💿 Step 5: Creating DMG..."
./packaging/macos/make-dmg.sh

# 6. Sign DMG (if certificates available)
if [ -n "$SIGNING_IDENTITY" ]; then
    echo "✍️  Step 6: Signing DMG..."
    codesign --force --sign "$SIGNING_IDENTITY" \
        "dist-installer/SERP-Companion-macOS.dmg"
fi

# 7. Notarize (if credentials available)
if [ -n "$APPLE_ID" ]; then
    echo "📝 Step 7: Notarizing..."
    xcrun notarytool submit "dist-installer/SERP-Companion-macOS.dmg" \
        --apple-id "$APPLE_ID" \
        --team-id "$TEAM_ID" \
        --password "$APPLE_PASSWORD" \
        --wait
    xcrun stapler staple "dist-installer/SERP-Companion-macOS.dmg"
fi

echo "✅ Build complete!"
echo "📦 Output: dist-installer/SERP-Companion-macOS.dmg"
```

## Testing Checklist

Before releasing the macOS installer:

- [ ] App launches without errors
- [ ] Native Messaging manifest is created correctly
- [ ] Extension can connect via "Ping"
- [ ] "Info" shows correct tool paths and versions
- [ ] "Start" successfully downloads a course
- [ ] Logs are viewable via "Open Log"
- [ ] App survives system restart
- [ ] Uninstaller removes all files
- [ ] Works on macOS 10.13+ (test on multiple versions)
- [ ] Gatekeeper accepts signed/notarized app (macOS 10.15+)

## Comparison: Windows vs. macOS Installer

| Feature | Windows (Inno Setup) | macOS (Needed) |
|---------|---------------------|----------------|
| Installer format | `.exe` | `.dmg` or `.pkg` |
| Install location | `C:\Program Files\` | `/Applications/` |
| Registry | ✅ Auto-registers | ❌ N/A |
| Manifest creation | ✅ Automated | ⚠️ Manual or post-install script |
| Tool bundling | ✅ Automatic | ⚠️ Need to create |
| Uninstaller | ✅ Built-in | ⚠️ Need to create |
| Code signing | Optional | **Required** for macOS 10.15+ |
| Notarization | N/A | **Required** for macOS 10.15+ |
| Post-install actions | ✅ Pair server + open Web Store | ⚠️ Need to implement |
| Auto-update | ❌ Not implemented | ❌ Not implemented |

## Missing Components (TODO)

To achieve parity with Windows installer:

1. **App Bundle Creation Script** ✅ (provided above)
2. **Tool Bundling Script** (download ffmpeg, aria2c, etc.)
3. **Post-Install Launcher** (auto-run pairing server)
4. **Uninstaller Script** (remove all files and manifest)
5. **Code Signing Setup** (Apple Developer account)
6. **Notarization Automation** (CI/CD integration)
7. **GitHub Actions Workflow** (`.github/workflows/build-macos-installer.yml`)
8. **User Documentation** (installation guide, troubleshooting)

## Next Steps

1. **Create missing scripts:**
   - `packaging/macos/create-app-bundle.sh`
   - `packaging/macos/bundle-tools.sh`
   - `packaging/macos/post-install.sh`

2. **Test on clean macOS system:**
   - Virtual machine or separate Mac
   - Verify installation and pairing

3. **Set up code signing:**
   - Enroll in Apple Developer Program ($99/year)
   - Create Developer ID certificates
   - Configure in Xcode or command line

4. **Automate in CI/CD:**
   - Create GitHub Actions workflow
   - Store signing credentials as secrets
   - Auto-build on release tag

5. **Document for users:**
   - Update README with macOS installation
   - Create video tutorial
   - Add troubleshooting section

## Resources

- [Apple Developer: Distributing Your App for Beta Testing and Releases](https://developer.apple.com/documentation/xcode/distributing-your-app-for-beta-testing-and-releases)
- [How to Make a Mac App DMG Tutorial](https://medium.com/@adrianstanecki/how-to-make-a-dmg-5b398e5259e4)
- [Packaging Mac Software for Distribution](https://developer.apple.com/library/archive/documentation/DeveloperTools/Conceptual/SoftwareDistribution/Introduction/Introduction.html)
- [Notarizing macOS Software Before Distribution](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [Homebrew Cask Documentation](https://docs.brew.sh/Cask-Cookbook)

## Conclusion

The macOS installer requires more setup than Windows but follows Apple's standard practices:

1. **Primary method:** .app bundle in a DMG with drag-to-install
2. **Alternative:** .pkg installer with automated scripts
3. **Developer method:** Homebrew Cask for easy distribution

The key differences from Windows:
- No single "installer builder" like Inno Setup
- Code signing is **mandatory** for modern macOS
- More manual scripting required for automation

However, once set up, the macOS installer provides a professional, native experience that users expect on the platform.
