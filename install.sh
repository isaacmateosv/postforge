#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Installs PostForge on this Mac from an unpacked bundle (DEPLOY-M1.md §7 step 6).
# It checks the prerequisites, protects .env, installs the bundled menu bar app, then runs doctor.
# It starts nothing: no containers, no WhatsApp link (runbook steps 8–10, with you).
#   ./install.sh           install
#   ./install.sh --check   check only; verify the bundled app without installing it
# Bash 3.2 compatible (macOS /bin/bash).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK=false
[ "${1:-}" = "--check" ] && CHECK=true
fails=0
ok()  { echo "  ✔ $1"; }
bad() { echo "  ✖ $1"; fails=$((fails + 1)); }

echo "=== PostForge install ($([ "$CHECK" = true ] && echo "check only" || echo "install")) ==="
echo "--- Prerequisites (generic macOS install) ---"
arch="$(uname -m)"
if [ "$arch" = "arm64" ] || [ "$arch" = "x86_64" ]; then
  ok "Supported architecture: $arch"
else
  bad "Unsupported architecture: $arch"
fi
major=$(sw_vers -productVersion | cut -d. -f1)
[ "$major" -ge 15 ] && ok "macOS $(sw_vers -productVersion)" || bad "macOS $(sw_vers -productVersion): current Docker Desktop needs macOS 15 or later"
xcode-select -p > /dev/null 2>&1 && ok "Command Line Tools" || bad "Command Line Tools missing: xcode-select --install"
[ -d /Applications/Docker.app ] && ok "Docker Desktop installed" || bad "Docker Desktop missing: install Docker Desktop for your Mac architecture"
if command -v ollama > /dev/null 2>&1; then
  ok "Ollama installed"
elif [ "$CHECK" = true ]; then
  bad "Ollama missing: install it from ollama.com (needed for local captions)"
else
  echo "  · Ollama missing; the install phase will install it with Homebrew"
fi
if command -v ffmpeg > /dev/null 2>&1; then
  ok "ffmpeg"
elif [ "$CHECK" = true ]; then
  bad "ffmpeg missing: brew install ffmpeg"
else
  echo "  · ffmpeg missing; the install phase will install it with Homebrew"
fi

if [ "$CHECK" = false ]; then
  echo "--- Local media and AI tools ---"
  if ! command -v brew > /dev/null 2>&1; then
    bad "Homebrew missing: install it from brew.sh to auto-install ffmpeg and whisper.cpp"
  else
    if ! command -v ffmpeg > /dev/null 2>&1; then
      brew install ffmpeg
    fi
    if ! command -v whisper-cli > /dev/null 2>&1; then
      brew install whisper-cpp
    fi
    if ! command -v ollama > /dev/null 2>&1; then
      brew install ollama
    fi
    if command -v ollama > /dev/null 2>&1; then
      if ! pgrep -x ollama > /dev/null 2>&1; then
        ollama serve > /dev/null 2>&1 &
        sleep 2
      fi
      model="${LOCAL_LLM_MODEL:-llama3.2:3b}"
      ollama pull "$model"
      ok "Ollama model: $model"
    fi
    if command -v whisper-cli > /dev/null 2>&1; then
      "$DIR/scripts/get-whisper-model.sh"
      ok "whisper.cpp model"
    fi
    command -v ffmpeg > /dev/null 2>&1 && ok "ffmpeg ready"
  fi
fi

echo "--- Project ---"
[ "$DIR" = "$HOME/postforge" ] && ok "project at ~/postforge" \
  || echo "  · project at $DIR (the standard install path is ~/postforge)"
if [ -f "$DIR/.env" ]; then
  if [ "$CHECK" = false ]; then chmod 600 "$DIR/.env"; fi
  ok ".env present"
else
  bad ".env missing: AirDrop it into $DIR (it travels separately, never in the bundle)"
fi
chmod +x "$DIR/publish-machine.sh" "$DIR/postforge.sh" "$DIR"/scripts/*.sh "$DIR/tray/build.sh"

echo "--- Menu bar app ---"
if [ -x "$DIR/tray/build/PostForge.app/Contents/MacOS/PostForgeTray" ] || [ -x "$DIR/tray/build/Publish Machine.app/Contents/MacOS/PublishMachineTray" ]; then
  if [ "$CHECK" = false ]; then
    "$DIR/tray/install.sh" && ok "bundled app installed in ~/Applications" || bad "app install failed"
  else
    ok "bundled app present (no compiler needed)"
  fi
elif command -v swiftc > /dev/null 2>&1; then
  "$DIR/tray/build.sh" --install > /dev/null && ok "app built and installed" || bad "app build failed: ./tray/build.sh"
else
  bad "bundled app missing and Swift compiler unavailable"
fi

echo "--- Doctor ---"
"$DIR/publish-machine.sh" doctor || fails=$((fails + 1))

echo ""
if [ "$fails" -gt 0 ]; then
  echo "Install: $fails step(s) need attention (above)."
  exit 1
fi
echo "Install: done. Next (DEPLOY-M1.md §7): restore the Postiz export, ./postforge.sh start,"
echo "then link WhatsApp with ./scripts/link-whatsapp.sh."
