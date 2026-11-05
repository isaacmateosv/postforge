#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$HOME/Applications/PostForge.app"
LEGACY_APP="$HOME/Applications/Publish Machine.app"
PURGE=false
ASSUME_YES=false
QUIT_APP=true
for arg in "$@"; do
  case "$arg" in
    --purge-data) PURGE=true ;;
    --yes) ASSUME_YES=true ;;        # the PostForge app has already asked for confirmation
    --keep-app-running) QUIT_APP=false ;;  # the app quits itself when this finishes
    *) echo "Usage: $0 [--purge-data] [--yes] [--keep-app-running]" >&2; exit 2 ;;
  esac
done

echo "=== PostForge uninstall ==="
echo "This removes the installed project and PostForge.app."
if [ "$PURGE" = true ]; then
  echo "WARNING: --purge-data permanently removes the PostForge project, its credentials (.env), databases, media,"
  echo "WhatsApp session, logs, exports, Docker images and app settings. Without a backup this cannot be undone."
  if [ "$ASSUME_YES" = false ]; then
    read -r -p "Type PURGE to continue: " confirmation
    [ "$confirmation" = "PURGE" ] || { echo "Uninstall cancelled." >&2; exit 1; }
  fi
else
  echo "Private data will be preserved in the project directory unless you choose --purge-data."
fi

if [ "$ASSUME_YES" = false ]; then
  read -r -p "Continue? [y/N] " confirmation
  case "$confirmation" in
    y|Y|yes|YES) ;;
    *) echo "Uninstall cancelled."; exit 0 ;;
  esac
fi

echo "STEP 1/3 Stopping services"
if [ -f "$DIR/docker-compose.yml" ] && command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  if [ "$PURGE" = true ]; then
    docker compose -f "$DIR/docker-compose.yml" down --remove-orphans --volumes --rmi all || true
  else
    docker compose -f "$DIR/docker-compose.yml" down --remove-orphans || true
  fi
fi

echo "STEP 2/3 Removing the app"
if [ "$QUIT_APP" = true ]; then
  osascript -e 'quit app id "local.postforge.tray"' >/dev/null 2>&1 || true
  osascript -e 'quit app id "local.publish-machine.tray"' >/dev/null 2>&1 || true
fi
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
"$LSREGISTER" -u "$APP" >/dev/null 2>&1 || true
rm -rf "$APP" "$LEGACY_APP"
if [ "$PURGE" = true ]; then
  defaults delete local.postforge.tray >/dev/null 2>&1 || true
  rm -rf "$HOME/Library/Caches/local.postforge.tray" "$HOME/Library/Saved Application State/local.postforge.tray.savedState"
fi

echo "STEP 3/3 Removing project files"
if [ "$PURGE" = true ]; then
  case "$DIR" in
    ""|"/"|"$HOME"|"$HOME/") echo "✖ Refusing to delete '$DIR'." >&2; exit 1 ;;
  esac
  [ -f "$DIR/docker-compose.yml" ] && [ -f "$DIR/scripts/uninstall.sh" ] || { echo "✖ $DIR does not look like a PostForge project." >&2; exit 1; }
  cd "$HOME"
  rm -rf "$DIR"
else
  rm -f "$DIR/.env"
  rm -rf "$DIR/data" "$DIR/logs" "$DIR/run" "$DIR/exports" "$DIR/backups" "$DIR/tunnel" "$DIR/dist"
  rm -rf "$DIR/tray/build"
fi

echo "PostForge uninstalled."
if [ "$PURGE" = false ]; then
  echo "The source/configuration directory remains at $DIR; review or delete it manually if no longer needed."
fi
