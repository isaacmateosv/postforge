#!/bin/bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Runs as root at the end of the PostForge package install. Never fails the install once the project is in
# place: a log explains anything that needs a manual step.
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
rsync -a "$SOURCE/" "$TARGET/" || { echo "Could not copy the project to $TARGET"; exit 1; }
chown -R "$CONSOLE_USER":staff "$TARGET"
chmod 700 "$TARGET"
echo "PostForge installed at $TARGET."

# Install and open the app as the logged-in user (it needs their GUI session). Best effort.
if [ -x "$TARGET/tray/install.sh" ]; then
  if launchctl asuser "$USER_ID" sudo -u "$CONSOLE_USER" -H /bin/bash "$TARGET/tray/install.sh"; then
    echo "PostForge.app installed and opened."
  else
    echo "Could not install the app automatically. Run $TARGET/install.sh in Terminal."
  fi
fi
exit 0
