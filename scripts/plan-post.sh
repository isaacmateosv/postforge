#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Hands-free posting: media + one sentence -> one Postiz DRAFT per network at that time (HITL).
# Implementation: scripts/lib/plan_post.py. Help: ./scripts/plan-post.sh --help
# caffeinate -i keeps the Mac from idle-sleeping mid-run (closing the lid still sleeps it).
KEEP_AWAKE=$(command -v caffeinate || true)
exec $KEEP_AWAKE python3 "$(cd "$(dirname "$0")" && pwd)/lib/plan_post.py" "$@"
