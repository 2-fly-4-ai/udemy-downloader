#!/usr/bin/env python3
import argparse
import stat
from pathlib import Path
from textwrap import dedent


def main() -> None:
    parser = argparse.ArgumentParser(description="Write Info.plist and uninstall.sh into a .app bundle.")
    parser.add_argument("--bundle", required=True, help="Path to the .app bundle")
    parser.add_argument("--identifier", required=True, help="CFBundleIdentifier")
    parser.add_argument("--name", required=True, help="Display name")
    parser.add_argument("--version", required=True, help="Version string")
    parser.add_argument("--bundle-name", required=True, help="Bundle name (e.g. serpcompanion.app)")
    parser.add_argument("--launch-agent-label", required=True, help="Label used for the LaunchAgent plist")
    args = parser.parse_args()

    bundle_path = Path(args.bundle)
    contents = bundle_path / "Contents"
    resources = contents / "Resources"

    info_plist = dedent(
        f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>CFBundleExecutable</key>
            <string>serp-companion</string>
            <key>CFBundleIdentifier</key>
            <string>{args.identifier}</string>
            <key>CFBundleName</key>
            <string>{args.name}</string>
            <key>CFBundleVersion</key>
            <string>{args.version}</string>
            <key>CFBundleShortVersionString</key>
            <string>{args.version}</string>
            <key>CFBundlePackageType</key>
            <string>APPL</string>
            <key>LSMinimumSystemVersion</key>
            <string>10.13</string>
            <key>NSHighResolutionCapable</key>
            <true/>
        </dict>
        </plist>
        """
    ).strip() + "\n"

    uninstall_sh = dedent(
        f"""\
        #!/bin/bash
        set -euo pipefail

        APP_PATH="/Applications/{args.bundle_name}"
        MANIFEST="/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.serp.companion.json"
        LAUNCH_AGENT="/Library/LaunchAgents/{args.launch_agent_label}.plist"

        console_user=$(/usr/bin/stat -f '%Su' /dev/console 2>/dev/null || echo "")
        if [[ -n "$console_user" && "$console_user" != "root" ]]; then
            console_uid=$(id -u "$console_user")
            /bin/launchctl bootout "gui/$console_uid" "$LAUNCH_AGENT" 2>/dev/null || true
        fi

        rm -f "$LAUNCH_AGENT" 2>/dev/null || true
        rm -f "$MANIFEST" 2>/dev/null || true
        rm -rf "$APP_PATH"

        echo "SERP Companion removed. You may also delete ~/Library/Logs/SERP Companion if present."
        """
    ).strip() + "\n"

    info_path = contents / "Info.plist"
    info_path.write_text(info_plist, encoding="utf-8")

    uninstall_path = resources / "uninstall.sh"
    uninstall_path.write_text(uninstall_sh, encoding="utf-8")
    uninstall_path.chmod(uninstall_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


if __name__ == "__main__":
    main()
