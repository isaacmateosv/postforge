#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Schedule a macOS wake shortly before the next queued publication."""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "run", "schedule-wake.json")


def load_env():
    values = {}
    path = os.path.join(ROOT, ".env")
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip().strip("\"'")
    except OSError:
        pass
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--at", required=True, help="publication time in UTC, YYYY-MM-DDTHH:MM:SSZ")
    args = parser.parse_args()
    try:
        at = datetime.strptime(args.at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        print("Invalid publication time: " + args.at, file=sys.stderr)
        return 2

    env = load_env()
    try:
        lead = max(5, int(env.get("PM_WAKE_LEAD_MINUTES", "15")))
    except ValueError:
        lead = 15
    wake = at - timedelta(minutes=lead)
    if wake <= datetime.now(timezone.utc):
        return 0

    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    try:
        with open(STATE, encoding="utf-8") as fh:
            previous = json.load(fh)
    except (OSError, ValueError, TypeError):
        previous = {}
    if previous.get("publication_at") == args.at:
        return 0

    local = wake.astimezone().strftime("%m/%d/%y %H:%M:%S")
    result = subprocess.run(
        ["/usr/bin/pmset", "schedule", "wakeorpoweron", local],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if result.returncode != 0:
        print("Could not schedule Mac wake: " + (result.stderr.strip() or result.stdout.strip()), file=sys.stderr)
        return result.returncode
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump({"publication_at": args.at, "wake_at": wake.isoformat()}, fh)
    print("Scheduled Mac wake for " + local)
    return 0


if __name__ == "__main__":
    sys.exit(main())
