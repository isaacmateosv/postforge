#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Remove PostForge history older than the retention window.

The window is PM_RETENTION_DAYS in .env (default 30 days; the PostForge menu changes it) unless --days
is given. Dry-run by default. Use --apply only after reviewing the listed files.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DAYS = 30
ROOTS = (
    os.path.join(ROOT, "data", "postiz-uploads"),
    os.path.join(ROOT, "logs"),
    os.path.join(ROOT, "run", "wa-confirmations"),
    os.path.join(ROOT, "run", "wa-cache"),
)


def configured_days():
    """PM_RETENTION_DAYS from .env, or the 30-day default when it is missing or invalid."""
    try:
        with open(os.path.join(ROOT, ".env"), encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("PM_RETENTION_DAYS="):
                    value = int(line.split("=", 1)[1].strip().strip("\"'"))
                    return value if value >= 1 else DEFAULT_DAYS
    except (OSError, ValueError):
        pass
    return DEFAULT_DAYS


def referenced_media():
    """Fail closed: without a verified database snapshot, retain all uploaded media."""
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'lib'))
    import pmlib
    env = pmlib.load_env()
    try:
        result = subprocess.run([
            'docker', 'exec', 'pm-postgres', 'psql', '-U', env.get('POSTGRES_USER', 'postiz'),
            '-d', env.get('POSTGRES_DB', 'postiz'), '-tA', '-v', 'ON_ERROR_STOP=1', '-c',
            "SELECT coalesce(image::text, '[]') FROM public.\"Post\" WHERE \"deletedAt\" IS NULL;"
        ], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return None
        references = result.stdout
        queue_path = os.path.join(ROOT, 'run', 'whatsapp-pending.json')
        if os.path.exists(queue_path):
            with open(queue_path, encoding='utf-8') as source:
                queue = json.load(source)
            if not isinstance(queue, list) or not all(isinstance(item, dict) for item in queue):
                return None
            references += json.dumps([item for item in queue if item.get("status") != "sent"])
        for path in glob.glob(os.path.join(ROOT, 'run', 'wa-confirmations', '*.json')):
            with open(path, encoding='utf-8') as source:
                references += json.dumps(json.load(source))
        return urllib.parse.unquote(references)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def expired_confirmations(root, cutoff):
    for path in glob.glob(os.path.join(root, "*.json")):
        try:
            if os.path.getmtime(path) >= cutoff:
                continue
            with open(path, encoding="utf-8") as source:
                scheduled = datetime.fromisoformat(json.load(source)["result"]["when_utc"].replace("Z", "+00:00"))
            if scheduled.tzinfo is not None and scheduled.timestamp() < cutoff:
                yield path
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            continue


def candidates(cutoff, whatsapp_only=False):
    references = referenced_media()
    for root in ROOTS:
        if not os.path.isdir(root):
            continue
        if root.endswith('wa-confirmations'):
            yield from expired_confirmations(root, cutoff)
            # Only sweep abandoned, old confirmation media with no metadata.
            for folder in glob.glob(os.path.join(root, "*")):
                if os.path.isdir(folder) and not os.path.islink(folder) and not os.path.exists(folder + ".json"):
                    for directory, _, filenames in os.walk(folder):
                        for name in filenames:
                            path = os.path.join(directory, name)
                            try:
                                if os.path.getmtime(path) < cutoff:
                                    yield path
                            except OSError:
                                continue
            continue
        uploads = root.endswith('postiz-uploads')
        if whatsapp_only:
            if uploads:
                root = os.path.join(root, "whatsapp-pending")
            elif not root.endswith('wa-cache'):
                continue
        for directory, _, filenames in os.walk(root):
            for name in filenames:
                path = os.path.join(directory, name)
                try:
                    if uploads and (references is None or name in references):
                        continue
                    if os.path.getmtime(path) < cutoff:
                        yield path
                except OSError:
                    continue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="delete the listed files")
    parser.add_argument("--days", type=int, default=None,
                        help="retain this many days (default: PM_RETENTION_DAYS, else 30)")
    parser.add_argument("--whatsapp-cache", action="store_true", help="limit cleanup to PostForge-owned WhatsApp staging")
    parser.add_argument("--json", action="store_true", help="print one JSON summary instead of the file list")
    args = parser.parse_args()
    days = args.days if args.days is not None else configured_days()
    if days < 1:
        parser.error("--days must be at least 1")
    cutoff = time.time() - days * 86400
    files = list(candidates(cutoff, whatsapp_only=args.whatsapp_cache))
    size = 0
    for path in files:
        try:
            size += os.path.getsize(path)
        except OSError:
            pass
        if not args.json:
            print(("delete " if args.apply else "would delete ") + os.path.relpath(path, ROOT))
        if args.apply:
            try:
                os.remove(path)
                if path.endswith(".json") and os.path.basename(os.path.dirname(path)) == "wa-confirmations":
                    # Remove only that confirmation’s owned sibling folder.
                    shutil.rmtree(os.path.splitext(path)[0], ignore_errors=True)
            except OSError as exc:
                if not args.json:
                    print("  could not delete: %s" % exc)
    if args.apply:
        for root in ROOTS:
            if args.whatsapp_cache and root.endswith('postiz-uploads'):
                root = os.path.join(root, 'whatsapp-pending')
            elif args.whatsapp_cache and root.endswith('logs'):
                continue
            for directory, subdirectories, _ in os.walk(root, topdown=False):
                for name in subdirectories:
                    path = os.path.join(directory, name)
                    try:
                        os.rmdir(path)
                    except OSError:
                        pass
    if args.json:
        print(json.dumps({"days": days, "files": len(files), "bytes": size, "applied": args.apply}))
    else:
        print("%s %d file(s) older than %d days" % ("Deleted" if args.apply else "Found", len(files), days))


if __name__ == "__main__":
    main()
