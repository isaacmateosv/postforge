#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Safe maintenance for dependency checks and explicitly approved container updates.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
SNAPSHOT="run/rollback/$STAMP"

snapshot() {
  mkdir -p "$DIR/$SNAPSHOT/scripts/lib" "$DIR/$SNAPSHOT/tray" "$DIR/$SNAPSHOT/config/whatsapp" \
    "$DIR/$SNAPSHOT/.github/workflows"
  for f in docker-compose.yml publish-machine.sh install.sh README.md SETUP.md ROLLBACK.md \
           AUTHORS.md NOTICE.md LICENSE .gitignore; do
    cp "$DIR/$f" "$DIR/$SNAPSHOT/$f"
  done
  for f in scripts/retention.py scripts/credentials.py scripts/tunnel_url.py scripts/migrate.sh scripts/recheck.sh \
           scripts/watchdog.sh scripts/package.sh scripts/rollback.sh scripts/uninstall.sh \
           scripts/maintenance.sh scripts/wa-inbox.sh scripts/plan-post.sh scripts/component_updates.py scripts/image_rollback.py; do
    cp "$DIR/$f" "$DIR/$SNAPSHOT/$f"
  done
  for f in "$DIR"/scripts/lib/*.py; do cp "$f" "$DIR/$SNAPSHOT/scripts/lib/"; done
  cp "$DIR"/tray/*.swift "$DIR"/tray/*.sh "$DIR"/tray/Info.plist "$DIR/$SNAPSHOT/tray/"
  cp -R "$DIR/tray/assets" "$DIR/$SNAPSHOT/tray/"
  cp "$DIR/config/whatsapp/vip-list.example.txt" "$DIR/$SNAPSHOT/config/whatsapp/"
  cp "$DIR"/.github/workflows/*.yml "$DIR/$SNAPSHOT/.github/workflows/"
  printf 'created_at=%s\ncredentials_included=false\nruntime_data_included=false\n' "$STAMP" \
    > "$DIR/$SNAPSHOT/MANIFEST.txt"
  chmod 600 "$DIR/$SNAPSHOT/MANIFEST.txt"
  python3 "$DIR/scripts/image_rollback.py" save "$DIR/$SNAPSHOT/images.json"
  echo "Rollback snapshot: $SNAPSHOT"
}

check() {
  local json=false
  [ "${1:-}" = "--json" ] && json=true
  if "$json"; then
    python3 "$DIR/scripts/component_updates.py"
    return 0
  fi
  local brew_updates=""
  if command -v brew >/dev/null 2>&1; then
    brew_updates=$(brew outdated 2>/dev/null || true)
  fi
  echo "=== Publish Machine maintenance check ==="
  echo "--- Declared container images ---"
  docker compose config --images
  echo "--- Current container images ---"
  docker compose images
  echo "--- Host tools ---"
  docker --version
  docker compose version
  ollama --version 2>/dev/null || echo "Ollama version unavailable"
  if command -v brew >/dev/null 2>&1; then
    echo "--- Homebrew updates (not applied) ---"
    printf '%s\n' "${brew_updates:-none}"
  fi
  echo "--- Current health ---"
  "$DIR/publish-machine.sh" status
  echo "No updates were applied."
}

update() {
  local apply=false yes=false arg
  for arg in "$@"; do
    [ "$arg" = "--apply" ] && apply=true
    [ "$arg" = "--yes" ] && yes=true
  done
  "$apply" || {
    echo "Refusing to update without explicit --apply." >&2
    exit 2
  }
  docker info >/dev/null
  docker compose config --quiet
  if ! "$yes"; then
    printf 'Create a rollback snapshot and update the declared Docker stack? [y/N] '
    read -r answer
    case "$answer" in y|Y|yes|YES) ;; *) echo "Update cancelled."; exit 1 ;; esac
  fi
  echo "STEP 1/5 Creating rollback snapshot"
  snapshot
  echo "STEP 2/5 Downloading declared images (services stay online)"
  docker compose pull
  echo "STEP 3/5 Restarting services"
  "$DIR/publish-machine.sh" stop --force
  "$DIR/publish-machine.sh" start
  echo "STEP 4/5 Checking health"
  "$DIR/scripts/watchdog.sh" || { echo "Health check failed. Recovery: ./scripts/rollback.sh $SNAPSHOT" >&2; exit 1; }
  echo "STEP 5/5 Update complete"
  "$DIR/publish-machine.sh" status
  echo "Update completed. If health is not fully restored, use ./scripts/rollback.sh $SNAPSHOT"
}

case "${1:-check}" in
  check) shift; check "$@" ;;
  snapshot) snapshot ;;
  update) shift; update "$@" ;;
  *) echo "Usage: ./scripts/maintenance.sh {check|snapshot|update --apply}" >&2; exit 2 ;;
esac
