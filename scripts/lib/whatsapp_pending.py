# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Approval-gated WhatsApp Status queue used by the WhatsApp door."""
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pmlib
import file_lock

STATUS_PART_SECONDS = 60
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


@contextmanager
def _queue_lock():
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    with file_lock.exclusive(QUEUE_FILE + ".lock"):
        yield


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
    with _queue_lock():
        items = _read()
        items.append(item)
        _write(items)
    return item["id"]


def approve(item_id=None, source="explicit-whatsapp-command"):
    with _queue_lock():
        items = _read()
        candidates = [i for i in items if i.get("status") == "pending"]
        if item_id:
            candidates = [i for i in candidates if i.get("id") == item_id]
        if not candidates:
            return None
        item = candidates[-1]
        item["approved"] = True
        item["approval_source"] = source
        item["approved_at"] = int(time.time())
        _write(items)
        return item["id"]


def _due(item):
    try:
        when = datetime.fromisoformat(item["when"].replace("Z", "+00:00"))
    except (AttributeError, KeyError, TypeError, ValueError):
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= when.astimezone(timezone.utc)


def video_part_count(duration):
    return max(1, math.ceil(duration / STATUS_PART_SECONDS))


def _video_parts(path, folder):
    count = video_part_count(pmlib.ffprobe(path)[0])
    if count == 1:
        return [path]
    parts = []
    for index in range(count):
        out = os.path.join(folder, "part-%02d.mp4" % (index + 1))
        pmlib.run(["ffmpeg", "-y", "-v", "error", "-ss", str(index * STATUS_PART_SECONDS), "-i", path,
                   "-t", str(STATUS_PART_SECONDS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out])
        parts.append(out)
    return parts


def _send_item(item):
    script = os.path.join(pmlib.ROOT, "scripts", "lib", "broadcast_story.py")
    audience = pmlib.load_env().get("WA_STATUS_AUDIENCE", "all")
    with tempfile.TemporaryDirectory(prefix="status-", dir=pmlib.whatsapp_scratch()) as folder:
        commands = []
        for path in item.get("media") or []:
            if os.path.splitext(path)[1].lower() == ".mp4":
                commands.extend(("--video", part) for part in _video_parts(path, folder))
            else:
                commands.append(("--image", path))
        for flag, path in commands or [(None, None)]:
            args = [sys.executable, script, "--to", audience]
            if audience != "test":
                args.append("--yes")
            if flag:
                args.extend((flag, path))
            if item.get("caption"):
                args.append(item["caption"])
            subprocess.run(args, check=True)


def _ready(item):
    return (item.get("status") == "pending" and item.get("approved")
            and item.get("approval_source") in ("explicit-whatsapp-command", "desktop-review", "telegram-review") and _due(item))


def _claim(item_id):
    with _queue_lock():
        items = _read()
        for item in items:
            if item["id"] == item_id and _ready(item):
                # A disconnect can happen after WhatsApp accepted a relay. Record
                # the attempt before sending, including across worker restarts.
                item.update(status="sending", attempt_at=int(time.time()))
                _write(items)
                return item
    return None


def _finish(item_id, **outcome):
    with _queue_lock():
        items = _read()
        for item in items:
            if item["id"] == item_id and item.get("status") == "sending":
                item.update(outcome)
                _write(items)
                return


def recover_interrupted():
    """Called after acquiring the exclusive WhatsApp worker lock."""
    with _queue_lock():
        items = _read()
        interrupted = [item for item in items if item.get("status") == "sending"]
        for item in interrupted:
            item.update(status="needs_review", review_reason="send_interrupted", review_at=int(time.time()))
        if interrupted:
            _write(items)
        return len(interrupted)


def process(env, dry_run=False):
    if not dry_run:
        for candidate in _read():
            if not _ready(candidate):
                continue
            item = _claim(candidate["id"])
            if item is None:
                continue
            try:
                _send_item(item)
            except Exception as error:
                _finish(item["id"], status="needs_review", review_reason="delivery_unconfirmed",
                        review_at=int(time.time()))
                print("WhatsApp Status %s needs review after an unconfirmed send (%s)."
                      % (item["id"], type(error).__name__), flush=True)
            else:
                _finish(item["id"], status="sent", sent_at=int(time.time()))
    return [item for item in _read() if item.get("status") == "pending"]
