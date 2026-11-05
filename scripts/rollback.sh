#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Restore a local rollback snapshot created under run/rollback/.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAPSHOT="${1:-}"

if [ -z "$SNAPSHOT" ] || [ ! -d "$DIR/$SNAPSHOT" ]; then
  echo "Usage: ./scripts/rollback.sh run/rollback/YYYYMMDD-HHMMSS" >&2
  exit 2
fi

case "$SNAPSHOT" in
  run/rollback/*) ;;
  *) echo "✖ Refusing snapshots outside run/rollback/" >&2; exit 2 ;;
esac

if [ -e "$DIR/$SNAPSHOT/.env" ] || find "$DIR/$SNAPSHOT" -type f \( -name '*.aof' -o -name '*.rdb' -o -name '*.mp4' \) | grep -q .; then
  echo "✖ Snapshot contains prohibited runtime or credential data" >&2
  exit 1
fi

echo "This restores code, configuration and saved local image tags (when present); it does not restore .env, databases, media, logs, or WhatsApp state."
read -r -p "Restore $SNAPSHOT? [y/N] " answer
case "$answer" in
  y|Y|yes|YES) ;;
  *) echo "Rollback cancelled."; exit 1 ;;
esac

if ! docker info >/dev/null 2>&1; then
  echo "✖ Docker is unavailable; stop the machine first, then retry." >&2
  exit 1
fi
if [ -f "$DIR/$SNAPSHOT/images.json" ]; then
  python3 "$DIR/scripts/image_rollback.py" restore "$DIR/$SNAPSHOT/images.json"
fi
"$DIR/publish-machine.sh" stop --force

while IFS= read -r relative; do
  case "$relative" in MANIFEST.txt|images.json) continue ;; esac
  mkdir -p "$DIR/$(dirname "$relative")"
  cp "$DIR/$SNAPSHOT/$relative" "$DIR/$relative"
done < <(cd "$DIR/$SNAPSHOT" && find . -type f -not -name MANIFEST.txt -print | sed 's#^\./##')

chmod +x "$DIR/publish-machine.sh" "$DIR"/scripts/*.sh "$DIR"/tray/*.sh
"$DIR/publish-machine.sh" start
echo "Rollback complete. Verify with ./publish-machine.sh status"
