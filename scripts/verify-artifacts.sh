#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Inspect release artifacts without installing them or running installer scripts.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="${1:-$DIR/tray/build/PostForge.app}"
PKG="${2:-}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export SWIFT_MODULECACHE_PATH="$WORK/ModuleCache"
export CLANG_MODULE_CACHE_PATH="$WORK/ModuleCache"
version="$(tr -d '[:space:]' < "$DIR/VERSION")"
actual=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")
[ "$actual" = "$version" ] || { echo "App version mismatch" >&2; exit 1; }
plutil -lint "$APP/Contents/Info.plist"
codesign --verify --verbose "$APP"
for notice in LICENSE COPYRIGHT NOTICE; do
  cmp "$DIR/${notice/NOTICE/NOTICE.md}" "$APP/Contents/Resources/$notice.txt"
done

for guide in quick-en quick-es technical-en technical-es; do
  cmp "$DIR/docs/help/$guide.md" "$APP/Contents/Resources/Help/$guide.md"
done
for shortcut in 'New post in PostForge' 'Nueva publicación en PostForge'; do
  cmp "$DIR/tray/shortcuts/$shortcut.shortcut" "$APP/Contents/Resources/Shortcuts/$shortcut.shortcut"
done

archs="$(lipo -archs "$APP/Contents/MacOS/PostForgeTray")"
[[ "$archs" == *arm64* && "$archs" == *x86_64* ]] || { echo "Missing universal architecture" >&2; exit 1; }
iconutil -c iconset "$APP/Contents/Resources/PostForge.icns" -o "$WORK/PostForge.iconset"
for size in 16 32 128 256 512; do
  for scale in 1 2; do
    suffix=""; [ "$scale" = 2 ] && suffix="@2x"
    png="$WORK/PostForge.iconset/icon_${size}x${size}${suffix}.png"
    [ -f "$png" ] || { echo "Missing icon representation: $png" >&2; exit 1; }
    pixels="$(sips -g pixelWidth -g pixelHeight "$png" | awk '/pixelWidth:|pixelHeight:/ {print $2}')"
    expected="$((size * scale))"
    [ "$pixels" = "$(printf '%s\n%s' "$expected" "$expected")" ] || { echo "Incorrect icon dimensions: $png" >&2; exit 1; }
  done
done
swiftc -O -o "$WORK/verify-assets" "$DIR/tray/verify-assets.swift"
"$WORK/verify-assets" "$WORK/PostForge.iconset/icon_512x512.png" "$APP/Contents/Resources/PostForgeTray.png"
if [ -n "$PKG" ]; then
  PKG="$(cd "$(dirname "$PKG")" && pwd)/$(basename "$PKG")"
  (cd "$(dirname "$PKG")" && shasum -a 256 -c "$(basename "$PKG").sha256")
  pkgutil --payload-files "$PKG" > "$WORK/payload.txt"
  python3 - "$WORK/payload.txt" <<'PY'
import re, sys, unicodedata
paths = unicodedata.normalize("NFC", open(sys.argv[1]).read()).splitlines()
blocked = re.compile(r'(^|/)(\.env($|\.(?!example$))|(?:docker-)?compose\.override\.ya?ml$|\.git(/|$)|\.checkpoint(/|$)|data(/|$)|exports(/|$)|logs(/|$)|run(/|$)|backups(/|$)|tunnel(/|$)|vip-list\.txt$)')
leaks = [path for path in paths if blocked.search(path)]
if leaks:
    raise SystemExit('Unexpected private/generated payload entries: ' + ', '.join(leaks[:10]))
for required in ('scripts/component_updates.py', 'scripts/gateway_backup.py', 'v2/compose.gateway.yml', 'v2/telegram_worker.py', 'scripts/lib/wa_inbox.py', 'scripts/lib/wa-media-stream.mjs', 'docs/help/technical-es.md', 'tray/shortcuts/New post in PostForge.shortcut', 'tray/shortcuts/Nueva publicación en PostForge.shortcut', 'docs/images/postforge-mark.png', 'tray/assets/PostForgeAppForeground.svg'):
    assert any(path.endswith('/' + required) for path in paths), required
print('PASS: installer payload contains required assets and excludes private runtime data')
PY
  pkgutil --expand-full "$PKG" "$WORK/expanded"
  if find "$WORK/expanded" -name '._*' -print -quit | grep -q .; then
    echo "Installer expands to AppleDouble sidecar files" >&2; exit 1
  fi
  bundled="$(find "$WORK/expanded" -path '*/Payload/usr/local/share/postforge/tray/build/PostForge.app/Contents/Info.plist' -print -quit)"
  [ -n "$bundled" ] || { echo "Installer is missing its app" >&2; exit 1; }
  [ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$bundled")" = "$version" ] || { echo "Packaged app version mismatch" >&2; exit 1; }
fi
printf 'Artifact verification passed for PostForge %s\n' "$version"
