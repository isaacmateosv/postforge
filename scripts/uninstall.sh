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
echo "This removes PostForge.app and stops its services."
if [ "$PURGE" = true ]; then
  echo "WARNING: --purge-data permanently removes the PostForge project, its credentials (.env), databases, media,"
  echo "WhatsApp session, logs, exports and app settings. Shared Docker images stay installed. Without a backup this cannot be undone."
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

case "$DIR" in
  ""|"/"|"$HOME"|"$HOME/"|"/usr/local/share/postforge")
    echo "✖ Run uninstall from your user project directory." >&2; exit 1 ;;
esac
[ -f "$DIR/docker-compose.yml" ] || { echo "✖ PostForge Compose file is missing." >&2; exit 1; }

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
  osascript -e 'quit app id "local.postforge.tray"' >/dev/null 2>&1 || true
  osascript -e 'quit app id "local.publish-machine.tray"' >/dev/null 2>&1 || true
fi
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
"$LSREGISTER" -u "$APP" >/dev/null 2>&1 || true
rm -rf "$APP" "$LEGACY_APP"
if [ "$PURGE" = true ]; then
  for bundle in local.postforge.tray local.publish-machine.tray; do
    defaults delete "$bundle" >/dev/null 2>&1 || true
    rm -rf "$HOME/Library/Caches/$bundle" "$HOME/Library/Saved Application State/$bundle.savedState"
  done
  rm -f "$HOME/Library/Logs/PostForge-install.log"
fi

echo "STEP 3/3 Removing project files"
if [ "$PURGE" = true ]; then
  cd "$HOME"
  rm -rf "$DIR"
else
  echo "Project files and private data are preserved at $DIR."
fi

echo "PostForge uninstalled."
