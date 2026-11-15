#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$HOME/Applications/PostForge.app"
LEGACY_APP="$HOME/Applications/Publish Machine.app"
SYSTEM_APPS="${POSTFORGE_SYSTEM_APPLICATIONS:-/Applications}"
PURGE=false
ASSUME_YES=false
QUIT_APP=true
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --purge-data) PURGE=true ;;
    --dry-run) DRY_RUN=true; ASSUME_YES=true ;;
    --yes) ASSUME_YES=true ;;        # the PostForge app has already asked for confirmation
    --keep-app-running) QUIT_APP=false ;;  # the app quits itself when this finishes
    *) echo "Usage: $0 [--purge-data] [--yes] [--keep-app-running] [--dry-run]" >&2; exit 2 ;;
  esac
done

echo "=== PostForge uninstall ==="
echo "This removes the PostForge desktop apps and stops their publishing services."
echo "Scheduled posts stop until services are restored. Published social content and shared tools are not removed."
if [ "$PURGE" = true ]; then
  echo "WARNING: --purge-data permanently removes the PostForge project, its credentials (.env), databases, media,"
  echo "WhatsApp session, logs, exports and app settings. Shared Docker images stay installed. Without a backup this cannot be undone."
  if [ "$ASSUME_YES" = false ] && [ "$DRY_RUN" = false ]; then
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

case "$DIR" in
  ""|"/"|"$HOME"|"$HOME/"|"/usr/local/share/postforge")
    echo "✖ Run uninstall from your user project directory." >&2; exit 1 ;;
esac
[ -f "$DIR/docker-compose.yml" ] || { echo "✖ PostForge Compose file is missing." >&2; exit 1; }

if [ "$DRY_RUN" = true ]; then
  echo "DRY RUN: no services, applications or data will be changed."
  echo "App candidates: $HOME/Applications/PostForge Desktop.app; /Applications/PostForge Desktop.app; $APP; $LEGACY_APP"
  echo "Only bundles with PostForge's matching identity are removed."
  if [ "$PURGE" = true ]; then
    echo "Private data scope: $DIR/.env, data, run, logs, exports, backups, private overrides and PostForge settings."
    echo "A Git source checkout is preserved; a private installed runtime folder is removed."
  else
    echo "Private data preserved: $DIR"
  fi
  exit 0
fi

# Never interrupt an in-flight Status, backup or publication.
python3 -B - "$DIR" <<'GUARD'
from pathlib import Path
import sys
sys.path.insert(0,str(Path(sys.argv[1])/'scripts/lib'))
import operation_guard
try:operation_guard.assert_idle(sys.argv[1])
except ValueError as error:raise SystemExit(str(error))
GUARD

echo "STEP 1/3 Stopping services"
cd "$DIR"
if ! docker info >/dev/null 2>&1; then
  echo "✖ Start Docker Desktop, then retry so PostForge can remove its containers." >&2
  exit 1
fi
compose_args=(down --remove-orphans)
if [ "$PURGE" = true ]; then compose_args+=(--volumes); fi
if ! docker compose "${compose_args[@]}"; then
  echo "✖ Docker cleanup failed. Resolve the Docker error and retry." >&2
  exit 1
fi
python3 -B "$DIR/scripts/host_agent.py" stop
if [ -f "$DIR/run/wa-inbox.pid" ]; then
  read -r inbox_pid < "$DIR/run/wa-inbox.pid" || true
  case "$inbox_pid" in
    ""|*[!0-9]*) ;;
    *) if ps -p "$inbox_pid" -o command= | grep -Fq "$DIR/scripts/lib/wa_inbox.py"; then
         kill "$inbox_pid" 2>/dev/null || true
       fi ;;
  esac
  rm -f "$DIR/run/wa-inbox.pid"
fi

if [ "$PURGE" = true ] && { [ -e /usr/local/share/postforge ] || [ -L /usr/local/share/postforge ] ||
     pkgutil --pkg-info com.postforge.publish-machine >/dev/null 2>&1; }; then
  echo "Removing the system installer files (administrator approval required)"
  /usr/bin/osascript -e 'do shell script "if [ -e /usr/local/share/postforge ] || [ -L /usr/local/share/postforge ]; then /bin/rm -rf /usr/local/share/postforge || exit; fi; if /usr/sbin/pkgutil --pkg-info com.postforge.publish-machine >/dev/null 2>&1; then /usr/sbin/pkgutil --forget com.postforge.publish-machine; fi" with administrator privileges' || {
    echo "✖ System installer cleanup failed. Approve it and retry." >&2
    exit 1
  }
fi

echo "STEP 2/3 Removing the app"
if [ "$QUIT_APP" = true ]; then
  osascript -e 'quit app id "local.postforge.desktop"' >/dev/null 2>&1 || true
  osascript -e 'quit app id "local.postforge.tray"' >/dev/null 2>&1 || true
  osascript -e 'quit app id "local.publish-machine.tray"' >/dev/null 2>&1 || true
fi
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
"$LSREGISTER" -u "$APP" >/dev/null 2>&1 || true
for candidate in "$HOME/Applications/PostForge Desktop.app" "$SYSTEM_APPS/PostForge Desktop.app" "$APP" "$LEGACY_APP"; do
  [ -d "$candidate" ] || continue
  identity=$(python3 -B - "$candidate/Contents/Info.plist" <<'IDENTITY'
import plistlib,sys
try:
    with open(sys.argv[1],'rb') as stream:print(plistlib.load(stream).get('CFBundleIdentifier',''))
except (OSError,ValueError,plistlib.InvalidFileException):pass
IDENTITY
)
  case "$identity" in
    local.postforge.desktop|local.postforge.tray|local.publish-machine.tray)
      if [ -w "$candidate" ]; then
        rm -rf "$candidate"
      elif [ "$candidate" = "/Applications/PostForge Desktop.app" ]; then
        /usr/bin/osascript -e 'do shell script "/bin/rm -rf /Applications/\"PostForge Desktop.app\" || exit; /usr/sbin/pkgutil --forget local.postforge.desktop >/dev/null 2>&1 || true" with administrator privileges' || { echo "App removal needs administrator approval." >&2; exit 1; }
      else
        echo "Cannot remove $candidate. Check its file permissions." >&2; exit 1
      fi ;;
    *) echo "Skipped $candidate: its bundle identity does not match PostForge." ;;
  esac
done
if [ "$PURGE" = true ]; then
  for bundle in local.postforge.desktop local.postforge.tray local.publish-machine.tray; do
    defaults delete "$bundle" >/dev/null 2>&1 || true
    rm -rf "$HOME/Library/Caches/$bundle" "$HOME/Library/Saved Application State/$bundle.savedState"
  done
  rm -f "$HOME/Library/Logs/PostForge-install.log"
fi

echo "STEP 3/3 Removing project files"
if [ "$PURGE" = true ]; then
  cd "$HOME"
  if git -C "$DIR" rev-parse --show-toplevel >/dev/null 2>&1; then
    rm -rf "$DIR/data" "$DIR/run" "$DIR/logs" "$DIR/exports" "$DIR/backups" "$DIR/tunnel"
    rm -f "$DIR/.env" "$DIR/docker-compose.override.yml" "$DIR/config/whatsapp/vip-list.txt"
    echo "Private data removed; Git source checkout preserved at $DIR."
  else
    rm -rf "$DIR"
  fi
  rm -rf "$HOME/Library/Application Support/local.postforge.desktop" "$HOME/Library/WebKit/local.postforge.desktop"
  rm -f "$HOME/Library/Preferences/local.postforge.desktop.plist"
else
  echo "Project files and private data are preserved at $DIR."
fi

echo "PostForge uninstalled."
