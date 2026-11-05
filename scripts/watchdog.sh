#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Read-only live health watchdog. Exits non-zero on a degraded runtime.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

command -v docker >/dev/null 2>&1 || { echo "Watchdog: docker CLI missing." >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "Watchdog: Docker daemon unavailable." >&2; exit 1; }

state_json=$(python3 "$DIR/scripts/lib/machine_state.py" --json)
STATE_JSON="$state_json" python3 - <<'PY'
import json
import os
import sys

state = json.loads(os.environ["STATE_JSON"])
problems = []
if state.get("state") != "on":
    problems.append("machine state is %s" % state.get("state"))
services = state.get("services", {})
for name in ("postiz", "evolution", "scheduler", "tunnel"):
    if services.get(name) is not True:
        problems.append("%s is not healthy" % name)
if services.get("whatsapp") != "open":
    problems.append("whatsapp is not open")
if problems:
    print("Watchdog: FAIL")
    for problem in problems:
        print("  - " + problem)
    sys.exit(1)
print("Watchdog: PASS")
print("  state=on postiz=ok evolution=ok scheduler=ok whatsapp=open tunnel=ok")
PY
