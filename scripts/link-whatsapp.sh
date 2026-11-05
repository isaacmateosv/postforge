#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Link the organization’s WhatsApp to Evolution (QR scan). Does nothing if it is already linked.
# Implementation: scripts/lib/link_whatsapp.py   Help: ./scripts/link-whatsapp.sh --help
exec python3 "$(cd "$(dirname "$0")" && pwd)/lib/link_whatsapp.py" "$@"
