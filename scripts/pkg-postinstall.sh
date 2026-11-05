#!/bin/bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Runs as root after the payload is installed. Service refresh runs as the logged-in user.
set -uo pipefail

SOURCE="$3/usr/local/share/postforge"
CONSOLE_USER="$(stat -f '%Su' /dev/console)"

if [ "$CONSOLE_USER" = "root" ] || [ -z "$CONSOLE_USER" ]; then
  echo "PostForge package installed. Log in and copy /usr/local/share/postforge to ~/postforge."
  exit 0
fi

HOME_DIR="$(dscl . -read "/Users/$CONSOLE_USER" NFSHomeDirectory | awk '{print $2}')"
USER_ID="$(id -u "$CONSOLE_USER")"
TARGET="$HOME_DIR/postforge"
LEGACY="$HOME_DIR/publish-machine"
LOG="$HOME_DIR/Library/Logs/PostForge-install.log"
mkdir -p "$HOME_DIR/Library/Logs"
exec >> "$LOG" 2>&1
chown "$CONSOLE_USER":staff "$LOG"
echo "=== PostForge package install $(date) ==="

if [ ! -e "$TARGET" ] && [ -d "$LEGACY" ]; then
  mv "$LEGACY" "$TARGET"
  echo "Migrated $LEGACY to $TARGET."
elif [ -d "$LEGACY" ] && [ "$LEGACY" != "$TARGET" ]; then
  BACKUP="$HOME_DIR/publish-machine-backup-$(date +%Y%m%d-%H%M%S)"
  mv "$LEGACY" "$BACKUP"
  echo "Moved the legacy folder to $BACKUP; the active project is $TARGET."
fi

# Upgrades merge into the existing folder: .env, data/, logs/, run/ and exports/ are not in the package
# and rsync never deletes, so they are preserved.
mkdir -p "$TARGET"
rsync -a --from0 --files-from="$(dirname "$0")/payload-files" "$SOURCE/" "$TARGET/" || { echo "Could not copy the project to $TARGET"; exit 1; }
chown -R "$CONSOLE_USER":staff "$TARGET"
chmod 700 "$TARGET"
echo "PostForge installed at $TARGET."

refresh_status=0
if [ -f "$TARGET/.env" ]; then
  launchctl asuser "$USER_ID" sudo -u "$CONSOLE_USER" -H /usr/bin/env \
    PATH=/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:/usr/bin:/bin:/usr/sbin:/sbin \
    /bin/bash "$TARGET/postforge.sh" refresh-installed-services || refresh_status=$?
  if [ "$refresh_status" -ne 0 ]; then
    echo "PostForge was copied, but its services did not refresh successfully. See $LOG."
  fi
fi

# Install and open the app as the logged-in user (it needs their GUI session). Best effort.
if [ -x "$TARGET/tray/install.sh" ]; then
  if launchctl asuser "$USER_ID" sudo -u "$CONSOLE_USER" -H /bin/bash "$TARGET/tray/install.sh"; then
    echo "PostForge.app installed and opened."
  else
    echo "Could not install the app automatically. Run $TARGET/install.sh in Terminal."
  fi
fi
exit "$refresh_status"
