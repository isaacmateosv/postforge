#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Read-only source/package recheck for local use and CI.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"
LIVE=false
[ "${1:-}" = "--live" ] && LIVE=true

echo "=== PostForge recheck ==="
echo "--- Shell syntax ---"
while IFS= read -r file; do
  bash -n "$file"
done < <(find . \( -path './run' -o -path './data' -o -path './logs' -o -path './dist' -o -path './.git' \
  -o -path './tray/build' -o -path './docs/site' \) -prune -o -name '*.sh' -type f -print)
echo "  shell syntax: ok"

echo "--- Python syntax ---"
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import pathlib

excluded = {".git", "data", "logs", "run", "dist", "__pycache__"}
files = [
    path for path in pathlib.Path(".").rglob("*.py")
    if not any(part in excluded for part in path.parts)
]
for path in files:
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("  python syntax: ok (%d files)" % len(files))
PY

echo "--- Compose configuration ---"
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  if [ -f .env ]; then
    docker compose config --quiet
  else
    temp_env="$(mktemp)"
    trap 'rm -f "$temp_env"' EXIT
    cp .env.example "$temp_env"
    docker compose --env-file "$temp_env" config --quiet
    rm -f "$temp_env"
    trap - EXIT
  fi
  echo "  compose configuration: ok"
else
  echo "  Docker daemon unavailable; compose runtime check deferred"
fi

echo "--- Sensitive-file boundary ---"
private=$(find . -path './.git' -prune -o \( -name '.env' -o -name 'vip-list.txt' \) -print)
if [ -n "$private" ]; then
  echo "  private runtime files present locally (not a failure):"
  printf '%s\n' "$private" | sed 's#^\./##'
else
  echo "  no private runtime files found"
fi

echo "--- Tracked-file boundary ---"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  tracked=$(git ls-files | grep -E '(^|/)(\.env$|\.env\.[^e]|[^/]*\.enc$|vip-list\.txt$|(data|exports|logs|run|backups|tunnel|dist)/)' || true)
  if [ -n "$tracked" ]; then
    echo "  ✖ private or generated files are tracked by git:" >&2
    printf '%s\n' "$tracked" >&2
    exit 1
  fi
  secrets=$(git grep -nIE '(AIza[0-9A-Za-z_-]{30,}|sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|[0-9]{8,10}:AA[A-Za-z0-9_-]{30,}|EAA[A-Za-z0-9]{40,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)' -- . ':!scripts/recheck.sh' || true)
  if [ -n "$secrets" ]; then
    echo "  ✖ possible credentials in tracked files (values hidden):" >&2
    printf '%s\n' "$secrets" | cut -d: -f1,2 >&2
    exit 1
  fi
  echo "  no private files tracked, no credential patterns found"
else
  echo "  not a git checkout; skipped"
fi

echo "--- Version and app bundle ---"
version="$(tr -d '[:space:]' < VERSION)"
if ! printf '%s' "$version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$'; then
  echo "  ✖ VERSION must look like 1.2.3 or 1.2.3-pre.1 (found '$version')" >&2
  exit 1
fi
for asset in PostForgeTrayTemplate-Tight-54.png PostForgeTrayTemplate-Tight-36.png PostForgeTrayTemplate.svg PostForgeTrayWhite.svg PostForgeAppForeground.svg; do
  [ -f "tray/assets/$asset" ] || { echo "  ✖ missing tray/assets/$asset" >&2; exit 1; }
done
if command -v plutil >/dev/null 2>&1; then plutil -lint tray/Info.plist >/dev/null; fi
grep -q "^## \[$version\]" CHANGELOG.md || { echo "  ✖ CHANGELOG.md has no section for $version" >&2; exit 1; }
echo "  version $version: VERSION, CHANGELOG, Info.plist and tray assets are consistent"

if "$LIVE"; then
  "$DIR/scripts/watchdog.sh"
else
  echo "  live watchdog: skipped (use --live)"
fi

echo "Recheck: passed."
