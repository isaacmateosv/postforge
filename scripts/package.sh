#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Builds the single installation bundle for another Mac:
# dist/PostForge-<version>.pkg.
# Code, docs, logo, config, and a prebuilt portable menu-bar app. Never inside: .env, data/, exports/
# (Postiz export), logs/, run/, backups/, tunnel/, Git metadata, docs/site/.git (the public site is pushed from
# this Mac) or dist/ itself.
# .env and the Postiz export travel separately (AirDrop) and stay private.
#   ./scripts/package.sh        build the installer package and list what's in it
set -euo pipefail
export COPYFILE_DISABLE=1

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$DIR/VERSION")"
OUT="$DIR/dist/PostForge-$VERSION.pkg"
mkdir -p "$DIR/dist"
"$DIR/tray/build.sh" --portable > /dev/null

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/postforge-pkg.XXXXXX")"
SCRIPTS="$STAGE-scripts"
RESOURCES="$STAGE-resources"
COMPONENT="$STAGE-component.pkg"
trap 'rm -rf "$STAGE" "$SCRIPTS" "$RESOURCES" "$COMPONENT"' EXIT
mkdir -p "$STAGE/usr/local/share/postforge"
mkdir -p "$SCRIPTS"
mkdir -p "$RESOURCES"
cp "$DIR/scripts/pkg-postinstall.sh" "$SCRIPTS/postinstall"
chmod 755 "$SCRIPTS/postinstall"
COPYFILE_DISABLE=1 rsync -a \
  --include '.env.example' --exclude '.env' --exclude '.env.*' --exclude 'data/' --exclude 'exports/' --exclude 'logs/' \
  --exclude 'run/' --exclude 'backups/' --exclude 'tunnel/' \
  --exclude 'config/whatsapp/vip-list.txt' --exclude '__PROJECT_DIR__/' \
  --exclude 'desktop/target/' --exclude 'desktop/dist/' --exclude 'desktop/gen/' \
  --exclude 'dist/' --exclude '.git' --exclude '*compose.override.y*ml' --exclude 'docs/site/.git/' --exclude '.checkpoint/' \
  --exclude 'PROGRESS.md' --exclude '.DS_Store' --exclude '._*' --exclude '__pycache__/' --exclude '*.pyc' \
  "$DIR/" "$STAGE/usr/local/share/postforge/"
find "$STAGE" -name '._*' -exec rm -rf {} +
xattr -cr "$STAGE" 2>/dev/null || true
# List only this package's files. The system payload directory can retain files
# from an older installer, and copying the entire directory would resurrect them.
(cd "$STAGE/usr/local/share/postforge" && find . \( -type f -o -type l \) -print0) > "$SCRIPTS/payload-files"

COPYFILE_DISABLE=1 pkgbuild --root "$STAGE" \
  --filter '(^|/)(\.DS_Store|\.svn|CVS|\._[^/]*)(/|$)' \
  --identifier "com.postforge.publish-machine" \
  --version "$VERSION" \
  --install-location "/" \
  --scripts "$SCRIPTS" \
  "$COMPONENT" >/dev/null

{
  cat "$DIR/COPYRIGHT"
  printf '\n\n'
  cat "$DIR/LICENSE"
  printf '\n\n--- PostForge disclaimer and third-party notice ---\n\n'
  cat "$DIR/NOTICE.md"
} > "$RESOURCES/License.txt"
cat > "$RESOURCES/distribution.xml" <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="1">
  <title>PostForge</title>
  <welcome file="welcome.html" mime-type="text/html"/>
  <readme file="readme.html" mime-type="text/html"/>
  <license file="License.txt" mime-type="text/plain"/>
  <conclusion file="conclusion.html" mime-type="text/html"/>
  <background file="background.png" alignment="bottomleft" scaling="none"/>
  <options customize="never" require-scripts="true" hostArchitectures="arm64,x86_64"/>
  <allowed-os-versions>
    <os-version min="13.0"/>
  </allowed-os-versions>
  <domains enable_anywhere="true" enable_currentUserHome="false" enable_localSystem="true"/>
  <choices-outline>
    <line choice="default"/>
  </choices-outline>
  <choice id="default" visible="false">
    <pkg-ref id="com.postforge.publish-machine"/>
  </choice>
  <pkg-ref id="com.postforge.publish-machine" version="__VERSION__" onConclusion="none">PostForge-component.pkg</pkg-ref>
</installer-gui-script>
XML
sed -i '' "s/__VERSION__/$VERSION/" "$RESOURCES/distribution.xml"
for page in welcome readme conclusion; do
  sed "s/__VERSION__/$VERSION/g" "$DIR/scripts/installer/$page.html" > "$RESOURCES/$page.html"
done
# The installer window shows the app icon, taken from the freshly built app.
sips -s format png "$DIR/tray/build/PostForge.app/Contents/Resources/PostForge.icns" --out "$RESOURCES/background.png" >/dev/null 2>&1 \
  && sips -Z 150 "$RESOURCES/background.png" >/dev/null 2>&1 || rm -f "$RESOURCES/background.png"
[ -f "$RESOURCES/background.png" ] || sed -i '' '/<background /d' "$RESOURCES/distribution.xml"
cp "$COMPONENT" "$RESOURCES/PostForge-component.pkg"
productbuild --distribution "$RESOURCES/distribution.xml" \
  --package-path "$RESOURCES" \
  --resources "$RESOURCES" "$OUT" >/dev/null

# Refuse to hand over a bundle that leaked a secret or private data.
leaks=$(pkgutil --payload-files "$COMPONENT" | grep -E '(^|/)(\.env$|\.git/|\.checkpoint/|data/|exports/|logs/|run/|backups/|tunnel/|__PROJECT_DIR__/|config/whatsapp/vip-list\.txt)' || true)
if [ -n "$leaks" ]; then
  rm -f "$OUT"
  echo "✖ Bundle would contain private files, removed it:" >&2
  echo "$leaks" >&2
  exit 1
fi

(cd "$DIR/dist" && shasum -a 256 "$(basename "$OUT")" > "$(basename "$OUT").sha256")
echo "✔ $OUT ($(du -h "$OUT" | cut -f1)), checksum in $(basename "$OUT").sha256"
echo "  This is the macOS installer package. It installs the project at ~/postforge."
echo "  Carry separately, privately: .env and the Postiz export (./scripts/postiz-transfer.sh export)."
echo "  On the new Mac: double-click $(basename "$OUT"), then add .env and run ~/postforge/install.sh"
