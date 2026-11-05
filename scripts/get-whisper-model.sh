#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Voice notes for the WhatsApp door: installs whisper.cpp and downloads its multilingual "small" model
# (≈466 MB, from huggingface.co/ggerganov/whisper.cpp) into data/whisper/, checking its SHA-1.
# Run once per Mac (the model never travels in the transfer bundle).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="$DIR/data/whisper/ggml-small.bin"
SHA1="55356645c2b361a969dfd0ef2c5a50d530afd8d5"

command -v whisper-cli > /dev/null || brew install whisper-cpp
if [ -f "$MODEL" ] && [ "$(shasum -a 1 "$MODEL" | cut -d' ' -f1)" = "$SHA1" ]; then
  echo "✔ $MODEL already there"
  exit 0
fi
mkdir -p "$(dirname "$MODEL")"
curl -L --fail --retry 3 -o "$MODEL.part" "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"
if [ "$(shasum -a 1 "$MODEL.part" | cut -d' ' -f1)" != "$SHA1" ]; then
  rm -f "$MODEL.part"
  echo "✖ checksum mismatch: download removed" >&2
  exit 1
fi
mv "$MODEL.part" "$MODEL"
echo "✔ $MODEL"
