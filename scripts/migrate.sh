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
  echo "Usage: $0 export [private-folder] | import <private-folder> [--skip-installer] [--replace] [--stop-first]"
  exit 2
}

# The PostForge app shows these lines as progress: "STEP n/total text".
step() { echo "STEP $1/$2 $3"; }

export_bundle() (
  local out="${1:-$DEFAULT_OUT}" package archive
  echo "=== PostForge migration export ==="
  [ -f "$DIR/.env" ] || { echo "✖ There is no .env to back up at $DIR/.env." >&2; exit 1; }
  docker info >/dev/null 2>&1 || { echo "✖ Start Docker Desktop and try again." >&2; exit 1; }
  umask 077
  mkdir -m 700 "$out" || { echo "✖ Choose a new backup folder." >&2; exit 1; }
  trap 'rm -rf "$out"' EXIT
  trap 'exit 1' HUP INT TERM

  step 1 4 "Encrypting credentials and gateway settings"
  python3 "$DIR/scripts/credentials.py" export "$out/credentials.env.enc" --include-gateway
  unset PM_PASSPHRASE
  step 2 4 "Exporting Postiz data"
  archive="$out/postiz-$(date +%Y%m%d-%H%M%S).tar"
  "$DIR/scripts/postiz-transfer.sh" export "$archive"
  step 3 4 "Verifying backup"
  "$DIR/scripts/postiz-transfer.sh" rehearse "$archive"
  step 4 4 "Finishing"
  package="PostForge-$(tr -d '[:space:]' < "$DIR/VERSION").pkg"
  if [ -f "$DIR/dist/$package" ] && [ -f "$DIR/dist/$package.sha256" ]; then
    if (cd "$DIR/dist" && shasum -a 256 -c "$package.sha256" >/dev/null); then
      cp "$DIR/dist/$package" "$DIR/dist/$package.sha256" "$out/"
    fi
  fi
  cat > "$out/README.txt" <<'EOF'
PostForge private migration handoff

Copy this folder privately. The Postiz archive contains channel tokens and
media. The passphrase protects credentials.env.enc and gateway.enc (if present).
Keep the gateway file with the rest of this backup.

On the destination Mac, install the included PostForge package if present,
or get the matching version from https://github.com/isaacmateosv/postforge/releases.
Open Docker Desktop, then use PostForge > Backup & Move > Restore.
Terminal: ~/postforge/scripts/migrate.sh import <this folder> --skip-installer

Telegram bot token, private owner, language, heartbeat and enabled preference travel
inside credentials.env.enc. Telegram restores paused. Stop the old host agent,
then open Telegram settings in the Rust app and explicitly enable it on this host.
Do not run two receivers for the same bot. Conversation state is not migrated.

Link WhatsApp again by QR. Verify pending posts in Postiz after moving:
the archive carries Postiz records and media, and excludes Temporal jobs.
EOF
  trap - EXIT
  echo "Migration bundle ready: $out"
)

import_bundle() (
  local source="" skip_installer=false replace=false stop_first=false credentials package postiz target arg work gateway_work="" created_override=""
  for arg in "$@"; do
    case "$arg" in
      --skip-installer) skip_installer=true ;;
      --replace) replace=true ;;
      --stop-first) stop_first=true ;;
      -*) usage ;;
      *) [ -z "$source" ] || usage; source="$arg" ;;
    esac
  done
  [ -d "$source" ] || { echo "Migration folder not found: $source" >&2; exit 1; }
  credentials=$(find "$source" -maxdepth 1 -name 'credentials.env.enc' -type f -print -quit)
  package=$(find "$source" -maxdepth 1 -name 'PostForge-*.pkg' -type f -print -quit)
  postiz=$(find "$source" -maxdepth 1 -name 'postiz-*.tar' -type f -print -quit)
  [ -n "$credentials" ] && [ -n "$postiz" ] && { [ -n "$package" ] || [ "$skip_installer" = true ]; } || {
    echo "Migration folder needs credentials.env.enc and a Postiz export. Install PostForge separately and use --skip-installer if the backup has no installer." >&2
    exit 1
  }
  echo "=== PostForge migration import ==="
  docker info >/dev/null 2>&1 || { echo "✖ Start Docker Desktop and try again." >&2; exit 1; }
  if [ "$skip_installer" = false ]; then
    [ -f "$package.sha256" ] || { echo "✖ Installer checksum is missing." >&2; exit 1; }
    (cd "$source" && shasum -a 256 -c "$(basename "$package").sha256")
    sudo installer -pkg "$package" -target /
    target="$HOME/postforge"
  else
    target="$DIR"
  fi
  [ -f "$target/scripts/credentials.py" ] || { echo "✖ PostForge install not found at $target." >&2; exit 1; }

  mkdir -p "$target/run"
  work=$(mktemp -d "$target/run/restore.XXXXXX")
  cleanup() {
    rm -rf "$work"
    if [ -n "$gateway_work" ]; then rm -rf "$gateway_work"; fi
  }
  trap cleanup EXIT
  trap 'exit 1' HUP INT TERM
  step 1 3 "Validating backup credentials"
  args=(import "$credentials" --output "$work/incoming")
  if [ -e "$source/gateway.enc" ] || [ -L "$source/gateway.enc" ]; then
    [ -f "$target/scripts/gateway_backup.py" ] || { echo "✖ Install a PostForge version with gateway backup support first." >&2; exit 1; }
    mkdir -p "$target/data"
    gateway_work=$(mktemp -d "$target/data/.gateway-restore.XXXXXX")
    args+=(--gateway-stage "$gateway_work/incoming")
  fi
  python3 "$target/scripts/credentials.py" "${args[@]}"
  unset PM_PASSPHRASE
  if [ "$stop_first" = true ] && [ -f "$target/.env" ]; then
    "$target/postforge.sh" stop --force --keep-docker
  fi
  if [ -n "$gateway_work" ]; then
    # A running Authelia keeps the old database open across directory renames.
    local active_auth
    active_auth=$(docker ps --filter label=com.docker.compose.service=postforge-auth -q)
    if [ -n "$active_auth" ]; then
      echo "✖ Stop the running PostForge gateway before restoring gateway settings." >&2
      exit 1
    fi
    if [ -L "$target/data/gateway" ] || { [ -e "$target/data/gateway" ] && [ ! -d "$target/data/gateway" ]; }; then
      echo "✖ The destination gateway path must be a local directory." >&2
      exit 1
    fi
  fi
  # The restored .env holds Telegram paused. Stop this host's old receiver first.
  python3 "$target/scripts/host_agent.py" stop
  step 2 3 "Restoring Postiz and gateway data"
  if [ -e "$target/.env" ]; then cp -p "$target/.env" "$work/previous"; fi
  trap '
    if [ -e "$work/previous" ]; then
      mv -f "$work/previous" "$target/.env" || { echo "Previous credentials are in $work" >&2; exit 1; }
    else
      rm -f "$target/.env"
    fi
    if [ -n "$created_override" ]; then rm -f "$created_override"; fi
    if [ -n "$gateway_work" ]; then
      if [ ! -e "$gateway_work/incoming" ]; then
        rm -rf "$target/data/gateway" || { echo "Previous gateway settings are in $gateway_work" >&2; exit 1; }
      fi
      if [ -d "$gateway_work/previous" ]; then
        mv "$gateway_work/previous" "$target/data/gateway" || { echo "Previous gateway settings are in $gateway_work" >&2; exit 1; }
      fi
    fi
    cleanup
  ' EXIT
  if [ -n "$gateway_work" ]; then
    if [ -d "$target/data/gateway" ]; then mv "$target/data/gateway" "$gateway_work/previous"; fi
    mv "$gateway_work/incoming" "$target/data/gateway"
  fi
  mv -f "$work/incoming" "$target/.env"
  if [ -n "$gateway_work" ]; then
    # A fresh destination must route ngrok through the restored gateway.
    local override has_override=false
    for override in compose.override.yaml compose.override.yml docker-compose.override.yaml docker-compose.override.yml; do
      if [ -e "$target/$override" ] || [ -L "$target/$override" ]; then has_override=true; fi
    done
    if [ "$has_override" = false ]; then
      [ -f "$target/v2/compose.gateway.yml" ] || { echo "✖ The gateway Compose file is missing." >&2; exit 1; }
      ln -s v2/compose.gateway.yml "$target/docker-compose.override.yml"
      created_override="$target/docker-compose.override.yml"
    fi
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$target/scripts" python3 - "$target/.env" <<'PYTHON'
import sys
from pathlib import Path
from tunnel_url import check_gateway_config, read_setting, private_write
from network_settings import restore_provider

env = Path(sys.argv[1])
override = env.parent / "docker-compose.override.yml"
previous = override.read_bytes() if override.exists() else None
try:
    restore_provider(env)
    check_gateway_config(env, read_setting(env.read_text(), "NGROK_DOMAIN"))
except (OSError, ValueError, KeyError, RuntimeError) as error:
    if previous is not None: private_write(override, previous, env.parent / "run")
    else: override.unlink(missing_ok=True)
    sys.exit(f"Error: Gateway route could not be verified. {error}")
PYTHON
  fi
  args=(import "$postiz")
  if [ "$replace" = true ]; then args+=(--replace); fi
  "$target/scripts/postiz-transfer.sh" "${args[@]}"
  trap cleanup EXIT
  step 3 3 "Finishing"
  echo "Import complete. Turn PostForge on, verify pending posts, and link WhatsApp again by QR on the destination Mac."
)

case "${1:-}" in
  export) shift; export_bundle "$@" ;;
  import) shift; [ "$#" -ge 1 ] || usage; import_bundle "$@" ;;
  *) usage ;;
esac
