#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Guided private migration: export on the old Mac, import on the new Mac.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M)"
DEFAULT_OUT="$HOME/Desktop/PostForge-migration-$STAMP"

usage() {
  echo "Usage: $0 export [private-folder] | import <private-folder> [--skip-installer] [--replace]"
  exit 2
}

# The PostForge app shows these lines as progress: "STEP n/total text".
step() { echo "STEP $1/$2 $3"; }

export_bundle() {
  local out="${1:-$DEFAULT_OUT}" package export
  echo "=== PostForge migration export ==="
  [ -f "$DIR/.env" ] || { echo "✖ There is no .env to back up at $DIR/.env." >&2; exit 1; }
  docker info >/dev/null 2>&1 || { echo "✖ Docker Desktop is not running. Open it (or turn PostForge on), then try again." >&2; exit 1; }
  mkdir -p "$out"
  chmod 700 "$out"
  step 1 4 "Encrypting credentials"
  python3 "$DIR/scripts/credentials.py" export "$out/credentials.env.enc"
  step 2 4 "Exporting Postiz data"
  "$DIR/scripts/postiz-transfer.sh" export
  export=$(ls -t "$DIR"/exports/postiz-*.tar | head -1)
  cp "$export" "$out/"
  step 3 4 "Building the installer (about a minute)"
  command -v swiftc >/dev/null 2>&1 || { echo "✖ The Swift compiler is missing. Run: xcode-select --install" >&2; exit 1; }
  "$DIR/scripts/package.sh" >/dev/null
  package="$DIR/dist/PostForge-$(tr -d '[:space:]' < "$DIR/VERSION").pkg"
  cp "$package" "$package.sha256" "$out/"
  step 4 4 "Finishing"
  chmod 600 "$out"/*
  cat > "$out/README.txt" <<EOF
PostForge private migration handoff

Copy this folder privately to the destination Mac.
Files:
  credentials.env.enc  encrypted .env (requires your passphrase)
  postiz-*.tar         Postiz account/channels/posts/media export
  PostForge-*.pkg      sanitized macOS installer package

Never upload this folder to a public repository or chat.
Do not copy WhatsApp session state or Redis data. Link WhatsApp again by QR
on the destination Mac.

To restore: double-click the .pkg, then open PostForge > Backup & Move > Restore,
or run: ~/postforge/scripts/migrate.sh import <this folder>
EOF
  chmod 600 "$out/README.txt"
  echo "Migration bundle ready: $out"
  echo "Copy this folder privately. Nothing was sent or published."
}

import_bundle() {
  local source="" skip_installer=false replace=false credentials package postiz target candidate arg
  for arg in "$@"; do
    case "$arg" in
      --skip-installer) skip_installer=true ;;
      --replace) replace=true ;;
      *) source="$arg" ;;
    esac
  done
  [ -d "$source" ] || { echo "Migration folder not found: $source" >&2; exit 1; }
  credentials=$(find "$source" -maxdepth 1 -name 'credentials.env.enc' -type f -print -quit)
  package=$(find "$source" -maxdepth 1 -name 'PostForge-*.pkg' -type f -print -quit)
  postiz=$(find "$source" -maxdepth 1 -name 'postiz-*.tar' -type f -print -quit)
  [ -n "$credentials" ] && [ -n "$postiz" ] && { [ -n "$package" ] || [ "$skip_installer" = true ]; } || {
    echo "Migration folder must contain credentials.env.enc, a package, and a Postiz export." >&2
    exit 1
  }
  echo "=== PostForge migration import ==="
  if [ "$skip_installer" = false ]; then
    sudo installer -pkg "$package" -target /
  fi

  target=""
  for candidate in "$HOME/postforge" "$HOME/publish-machine"; do
    if [ -f "$candidate/publish-machine.sh" ] && [ -f "$candidate/scripts/credentials.py" ]; then
      target="$candidate"
      break
    fi
  done
  [ -n "$target" ] || {
    echo "No active PostForge install found at ~/postforge or ~/publish-machine." >&2
    exit 1
  }

  step 1 3 "Restoring credentials"
  python3 "$target/scripts/credentials.py" import "$credentials"
  step 2 3 "Restoring Postiz data"
  mkdir -p "$target/exports"
  cp "$postiz" "$target/exports/"
  if [ "$replace" = true ]; then
    "$target/scripts/postiz-transfer.sh" import "$target/exports/$(basename "$postiz")" --replace
  else
    "$target/scripts/postiz-transfer.sh" import "$target/exports/$(basename "$postiz")"
  fi
  step 3 3 "Refreshing the app"
  "$target/install.sh"
  echo "Import complete. Next: turn PostForge on, then link WhatsApp again by QR (./scripts/link-whatsapp.sh)."
}

case "${1:-}" in
  export) shift; export_bundle "$@" ;;
  import) shift; [ "$#" -ge 1 ] || usage; import_bundle "$@" ;;
  *) usage ;;
esac
