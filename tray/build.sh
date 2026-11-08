#!/bin/bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Builds the PostForge menu bar app: tray/build/PostForge.app (universal x86_64 + arm64, macOS 13+, ad-hoc signed).
# Needs only the Swift compiler from Xcode or the Command Line Tools (xcode-select --install).
#   ./tray/build.sh            build
#   ./tray/build.sh --portable build a relocatable app for the installation bundle
#   ./tray/build.sh --install  build, copy to ~/Applications and open it
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(cd "$HERE/.." && pwd)"
APP="$HERE/build/PostForge.app"
PORTABLE=false
[ "${1:-}" = "--portable" ] && PORTABLE=true

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
export SWIFT_MODULECACHE_PATH="$tmpdir/ModuleCache"
export CLANG_MODULE_CACHE_PATH="$tmpdir/ModuleCache"

swiftc -O -target x86_64-apple-macos13.0 \
  -o "$tmpdir/PostForgeTray_x86_64" "$HERE/PostForgeTray.swift"
swiftc -O -target arm64-apple-macos13.0 \
  -o "$tmpdir/PostForgeTray_arm64" "$HERE/PostForgeTray.swift"
lipo -create -output "$APP/Contents/MacOS/PostForgeTray" \
  "$tmpdir/PostForgeTray_x86_64" "$tmpdir/PostForgeTray_arm64"

# App icon: the colorful foreground on a blue squircle, always composed from the SVG so it can never drift from the artwork.
ASSETS="$HERE/assets"
swiftc -O -o "$tmpdir/compose-app-icon" "$HERE/compose-app-icon.swift"
iconset="$tmpdir/PostForge.iconset"
mkdir -p "$iconset"
for size in 16 32 128 256 512; do
  "$tmpdir/compose-app-icon" "$ASSETS/PostForgeAppForeground.svg" "$iconset/icon_${size}x${size}.png" "$size"
  "$tmpdir/compose-app-icon" "$ASSETS/PostForgeAppForeground.svg" "$iconset/icon_${size}x${size}@2x.png" "$((size * 2))"
done
iconutil -c icns "$iconset" -o "$APP/Contents/Resources/PostForge.icns"

# Offline legal notices are part of the signed app bundle.
cp "$PROJECT/LICENSE" "$APP/Contents/Resources/LICENSE.txt"
cp "$PROJECT/COPYRIGHT" "$APP/Contents/Resources/COPYRIGHT.txt"
cp "$PROJECT/NOTICE.md" "$APP/Contents/Resources/NOTICE.txt"
mkdir -p "$APP/Contents/Resources/Help"
cp "$PROJECT"/docs/help/*.md "$APP/Contents/Resources/Help/"
mkdir -p "$APP/Contents/Resources/Shortcuts"
cp "$HERE"/shortcuts/*.shortcut "$APP/Contents/Resources/Shortcuts/"

# Menu bar glyph: the black template mask at 54px for a crisp 18pt item; the app tints it for light and dark bars.
cp "$ASSETS/PostForgeTrayTemplate-Tight-54.png" "$APP/Contents/Resources/PostForgeTray.png"

if [ "$PORTABLE" = true ]; then
  sed "s#__PROJECT_DIR__#__PROJECT_DIR__#" "$HERE/Info.plist" > "$APP/Contents/Info.plist"
else
  sed "s#__PROJECT_DIR__#$PROJECT#" "$HERE/Info.plist" > "$APP/Contents/Info.plist"
fi
VERSION="$(tr -d '[:space:]' < "$PROJECT/VERSION")"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" -c "Set :CFBundleVersion $VERSION" "$APP/Contents/Info.plist"
codesign --force --sign - "$APP"
echo "Built: $APP (universal x86_64 + arm64; drives $PROJECT)"

[ "${1:-}" = "--install" ] && exec "$HERE/install.sh"
exit 0
