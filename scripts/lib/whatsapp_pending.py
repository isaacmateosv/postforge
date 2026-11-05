# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Approval-gated WhatsApp Status queue used by the WhatsApp door."""
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone

import pmlib

QUEUE_FILE = os.path.join(pmlib.RUN_DIR, "whatsapp-pending.json")


def _read():
    try:
        with open(QUEUE_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _write(items):
    os.makedirs(pmlib.RUN_DIR, exist_ok=True)
    tmp = QUEUE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, QUEUE_FILE)


def enqueue(caption, media_paths, post_ids, when):
    media = []
    for path in media_paths:
        rel = pmlib.stage_into_uploads(path, "whatsapp-pending")
        media.append(os.path.join(pmlib.UPLOADS_DIR, rel))
    item = {
        "id": uuid.uuid4().hex[:12],
        "created_at": int(time.time()),
        "when": when.isoformat(),
        "caption": caption,
        "media": media,
        "post_ids": post_ids,
        "approved": False,
        "approval_source": None,
        "status": "pending",
    }
    items = _read()
    items.append(item)
    _write(items)
    return item["id"]


def approve(item_id=None):
    items = _read()
    candidates = [i for i in items if i.get("status") == "pending"]
    if item_id:
        candidates = [i for i in candidates if i.get("id") == item_id]
    if not candidates:
        return None
    item = candidates[-1]
    item["approved"] = True
    item["approval_source"] = "explicit-whatsapp-command"
    item["approved_at"] = int(time.time())
    _write(items)
    return item["id"]


def _due(item):
    try:
        when = datetime.fromisoformat(item["when"])
    except (KeyError, TypeError, ValueError):
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= when.astimezone(timezone.utc)


def _video_parts(path):
    duration = pmlib.ffprobe(path)[0]
    if duration <= 60:
        return [path]
    folder = tempfile.mkdtemp(prefix="pm-wa-parts-")
    parts = []
    start = 0.0
    index = 1
    while start < duration:
        out = os.path.join(folder, "part-%02d.mp4" % index)
        pmlib.run(["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-i", path,
                   "-t", "60", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out])
        parts.append(out)
        start += 60
        index += 1
    return parts


def _send_item(item):
    script = os.path.join(pmlib.ROOT, "scripts", "broadcast-story.sh")
    audience = pmlib.load_env().get("WA_STATUS_AUDIENCE", "all")
    media = item.get("media") or []
    commands = []
    temp_folders = []
    for path in media:
        if os.path.splitext(path)[1].lower() == ".mp4":
            parts = _video_parts(path)
            commands.extend(("--video", part) for part in parts)
            if parts != [path]:
                temp_folders.append(os.path.dirname(parts[0]))
        else:
            commands.append(("--image", path))
    if not commands:
        commands = [(None, None)]
    try:
        for flag, path in commands:
            args = [script]
            args.extend(("--to", audience))
            if audience != "test":
                args.append("--yes")
            if flag:
                args.extend((flag, path))
            if item.get("caption"):
                args.append(item["caption"])
            subprocess.run(args, check=True)
    finally:
        for folder in temp_folders:
            shutil.rmtree(folder, ignore_errors=True)


def process(env, dry_run=False):
    items = _read()
    changed = False
    for item in items:
        if item.get("status") != "pending":
            continue
        if not item.get("approved") or item.get("approval_source") != "explicit-whatsapp-command":
            continue
        if not _due(item):
            continue
        if dry_run:
            continue
        _send_item(item)
        item["status"] = "sent"
        item["sent_at"] = int(time.time())
        changed = True
    if changed:
        _write(items)
    return [i for i in items if i.get("status") == "pending"]
