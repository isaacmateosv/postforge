#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Installs the built app into ~/Applications and binds it to this project path.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(cd "$HERE/.." && pwd)"
SOURCE="$HERE/build/PostForge.app"
TARGET="$HOME/Applications/PostForge.app"
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister

[ -x "$SOURCE/Contents/MacOS/PostForgeTray" ] || {
  echo "✖ Bundled menu-bar app is missing" >&2
  exit 1
}
mkdir -p "$HOME/Applications"
osascript -e 'quit app id "local.postforge.tray"' > /dev/null 2>&1 || true
osascript -e 'quit app id "local.publish-machine.tray"' > /dev/null 2>&1 || true
sleep 1

# Old "Publish Machine" bundles keep the previous icon registered, so remove them.
for stale in "$HOME/Applications/Publish Machine.app" "$HERE/build/Publish Machine.app"; do
  if [ -d "$stale" ]; then
    "$LSREGISTER" -u "$stale" > /dev/null 2>&1 || true
    rm -rf "$stale"
  fi
done

# The build output shares the bundle id; leaving it registered lets macOS pick its icon instead of the installed app's.
"$LSREGISTER" -u "$SOURCE" > /dev/null 2>&1 || true
rm -rf "$TARGET"
cp -R "$SOURCE" "$TARGET"
python3 - "$TARGET/Contents/Info.plist" "$PROJECT" <<'PY'
import plistlib
import sys

path, project = sys.argv[1:]
with open(path, "rb") as fh:
    data = plistlib.load(fh)
data["PMProjectDir"] = project
with open(path, "wb") as fh:
    plistlib.dump(data, fh, sort_keys=False)
PY
codesign --force --sign - "$TARGET"

# Re-register so Finder and the Dock read the new icon instead of the cached one.
"$LSREGISTER" -f "$TARGET" > /dev/null 2>&1 || true
touch "$TARGET"
# Register the new artwork without closing the user's Finder windows or restarting the Dock.
# An old notification badge can remain cached until the next login.
sleep 1
open "$TARGET"
echo "Installed: $TARGET"
