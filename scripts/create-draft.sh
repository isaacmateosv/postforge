#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Local Llama-3 caption -> Postiz DRAFT (HITL). Implementation: scripts/lib/create_draft.py
# Help: ./scripts/create-draft.sh --help
# caffeinate -i keeps the Mac from idle-sleeping mid-run (closing the lid still sleeps it).
KEEP_AWAKE=$(command -v caffeinate || true)
exec $KEEP_AWAKE python3 "$(cd "$(dirname "$0")" && pwd)/lib/create_draft.py" "$@"
