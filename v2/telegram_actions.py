# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Host-side Telegram adapter for the shared local composer."""
from datetime import datetime, timedelta
from pathlib import Path
import secrets
import sys
from urllib.parse import quote
from urllib.request import Request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts/lib"))
import composer
import pmlib
import whatsapp_pending
from postforge_v2 import OPENER

MAX_FILE = 20_000_000


class Actions:
    def __init__(self, env, call, token, status):
        self.env, self.call, self.token, self.status = env, call, token, status

    def options(self):
        return composer.options(self.env)

    def preview(self, data):
        return composer.preview(self.env, data)

    def revise(self, identifier, edited=None):
        return composer.revise(self.env, identifier, edited)

    def submit(self, identifier, mode):
        return composer.submit(self.env, identifier, mode)

    def approve_status(self, identifier):
        if not whatsapp_pending.approve(identifier, source="telegram-review"):
            raise pmlib.PMError("This Status is no longer waiting for approval.")

    def tick(self):
        whatsapp_pending.process(self.env)

    def time_value(self, value):
        zone = composer.plan_post.ZoneInfo(self.env.get("PM_TIMEZONE", "America/Guayaquil"))
        now = datetime.now(zone)
        if value in ("today", "tomorrow"):
            when = (now + timedelta(days=value == "tomorrow")).replace(
                hour=19 if value == "today" else 9, minute=0, second=0, microsecond=0)
        else:
            when = datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=zone)
        if when < now + composer.plan_post.MIN_SCHEDULE_LEAD:
            raise pmlib.PMError("Choose a time at least five minutes in the future.")
        return when.isoformat()

    def tag(self, value):
        return pmlib.final_tag(value)

    def has_video(self, paths):
        return any(Path(path).suffix.lower() in pmlib.VIDEO_EXT for path in paths)

    def is_image(self, path):
        return Path(path).suffix.lower() in pmlib.IMAGE_EXT

    def discard(self, data):
        root = (Path(pmlib.UPLOADS_DIR) / "telegram-intake").resolve()
        files = data.get("media", []) + ([data["cover_image"]] if data.get("cover_image") else [])
        for path in files:
            candidate = Path(path).resolve()
            if candidate.parent == root:
                candidate.unlink(missing_ok=True)

    def download(self, message):
        file = (message.get("photo") or [{}])[-1] if message.get("photo") else (
            message.get("video") or message.get("document") or {})
        if type(file.get("file_size")) is int and file["file_size"] > MAX_FILE:
            raise pmlib.PMError("Telegram bot downloads support up to 20 MB. Use the desktop app for larger files.")
        metadata = self.call("getFile", file_id=file["file_id"])
        length = metadata.get("file_size")
        remote = metadata.get("file_path", "")
        path = Path(remote)
        if (type(length) is not int or not 0 < length <= MAX_FILE or path.is_absolute()
                or ".." in path.parts or path.suffix.lower() not in pmlib.IMAGE_EXT | pmlib.VIDEO_EXT):
            raise pmlib.PMError("Use a supported image or video up to 20 MB. Use the desktop app for larger files.")
        folder = Path(pmlib.UPLOADS_DIR) / "telegram-intake"
        folder.mkdir(parents=True, mode=0o700, exist_ok=True)
        target = folder / (secrets.token_hex(16) + path.suffix.lower())
        url = "https://api.telegram.org/file/bot" + self.token + "/" + quote(remote, safe="/")
        try:
            with OPENER.open(Request(url), timeout=90) as response, target.open("xb") as output:
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_FILE:
                        raise ValueError
                    output.write(chunk)
                if total != length:
                    raise ValueError
            return str(target)
        except Exception:
            target.unlink(missing_ok=True)
            raise pmlib.PMError("Telegram media download failed. Try again or use the desktop app.") from None
