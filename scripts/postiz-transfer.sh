#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Export / rehearse / import Postiz's own data for the move to the Air (DEPLOY-M1.md §8).
# Implementation: scripts/lib/postiz_transfer.py   Help: ./scripts/postiz-transfer.sh --help
exec python3 "$(cd "$(dirname "$0")" && pwd)/lib/postiz_transfer.py" "$@"
