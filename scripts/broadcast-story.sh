#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# WhatsApp Status (Stories) broadcaster via Evolution API — status@broadcast only.
# Implementation: scripts/lib/broadcast_story.py   Help: ./scripts/broadcast-story.sh --help
# caffeinate -i keeps the Mac from idle-sleeping mid-run (closing the lid still sleeps it).
KEEP_AWAKE=$(command -v caffeinate || true)
exec $KEEP_AWAKE python3 "$(cd "$(dirname "$0")" && pwd)/lib/broadcast_story.py" "$@"
