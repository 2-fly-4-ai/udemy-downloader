#!/usr/bin/env python3
"""Generate the macOS postinstall script for the PKG."""

from __future__ import annotations

import argparse
import stat
from pathlib import Path
from textwrap import dedent


def _build_script(bundle_name: str, extension_id: str, launch_agent_path: str, launch_agent_label: str) -> str:
    return dedent(
        f"""#!/bin/bash
        set -euo pipefail

        APP_PATH="/Applications/{bundle_name}"
        HOST_BIN="$APP_PATH/Contents/MacOS/serp-companion"
        MANIFEST_DIR="/Library/Application Support/Google/Chrome/NativeMessagingHosts"
        MANIFEST_FILE="$MANIFEST_DIR/com.serp.companion.json"
        LAUNCH_AGENT_PATH="{launch_agent_path}"
        LAUNCH_AGENT_LABEL="{launch_agent_label}"

        mkdir -p "$MANIFEST_DIR"
        cat > "$MANIFEST_FILE" <<JSON
        {{
          "name": "com.serp.companion",
          "description": "SERP Companion Native Host",
          "path": "$HOST_BIN",
          "type": "stdio",
          "allowed_origins": [
            "chrome-extension://{extension_id}/"
          ]
        }}
JSON

        chmod 644 "$MANIFEST_FILE"
        chown root:wheel "$MANIFEST_FILE" 2>/dev/null || true

        mkdir -p "/Library/LaunchAgents"
        cat > "$LAUNCH_AGENT_PATH" <<PLIST
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{launch_agent_label}</string>
            <key>ProgramArguments</key>
            <array>
                <string>/Applications/{bundle_name}/Contents/MacOS/serp-companion</string>
                <string>--pair-server</string>
            </array>
            <key>RunAtLoad</key>
            <true/>
            <key>KeepAlive</key>
            <dict>
                <key>SuccessfulExit</key>
                <false/>
            </dict>
        </dict>
        </plist>
PLIST

        chmod 644 "$LAUNCH_AGENT_PATH"
        chown root:wheel "$LAUNCH_AGENT_PATH" 2>/dev/null || true

        console_user=$(/usr/bin/stat -f '%Su' /dev/console 2>/dev/null || echo "")
        if [[ -n "$console_user" && "$console_user" != "root" ]]; then
            console_uid=$(id -u "$console_user")
            /bin/launchctl bootout "gui/$console_uid" "$LAUNCH_AGENT_PATH" 2>/dev/null || true
            /bin/launchctl bootstrap "gui/$console_uid" "$LAUNCH_AGENT_PATH" 2>/dev/null || true
        fi

        exit 0
        """
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("extension_id")
    parser.add_argument("bundle_name")
    parser.add_argument("launch_agent_path")
    parser.add_argument("launch_agent_label")
    args = parser.parse_args()

    script = _build_script(
        bundle_name=args.bundle_name,
        extension_id=args.extension_id,
        launch_agent_path=args.launch_agent_path,
        launch_agent_label=args.launch_agent_label,
    )

    args.out.write_text(script)
    args.out.chmod(args.out.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


if __name__ == "__main__":
    main()
