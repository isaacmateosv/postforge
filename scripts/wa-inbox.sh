#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# WhatsApp door: what you send to your own chat becomes Postiz drafts (HITL). Implementation:
# scripts/lib/wa_inbox.py. Help: ./scripts/wa-inbox.sh --help. publish-machine.sh start/stop runs it.
exec python3 "$(cd "$(dirname "$0")" && pwd)/lib/wa_inbox.py" "$@"
