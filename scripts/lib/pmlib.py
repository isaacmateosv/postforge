# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Shared helpers for the Publish Machine host scripts.

Stdlib only, Python 3.9 compatible (macOS system python3): no backslashes inside
f-string expressions, no match statements, no `X | Y` type unions.
"""
import json
import math
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.client import HTTPException  # imported by name: this module defines http()
import uuid
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOADS_DIR = os.path.join(ROOT, "data", "postiz-uploads")
LOGS_DIR = os.path.join(ROOT, "logs")
RUN_DIR = os.path.join(ROOT, "run")  # live state for the menu bar app; safe to delete while stopped
JOBS_DIR = os.path.join(RUN_DIR, "jobs")


class PMError(Exception):
    """A user-facing failure: printed without a traceback."""


def load_env():
    """Read ROOT/.env (KEY=VALUE lines); real environment variables take precedence."""
    env = {}
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                env[key.strip()] = value
    for key, value in os.environ.items():
        env[key] = value
    return env


GEMINI_OFF = "Gemini is switched off, so nothing was sent to Google (GEMINI_ENABLED=true in .env turns it on)."


def gemini_enabled(env):
    """Gemini (Google's cloud AI) runs only with GEMINI_ENABLED=true in .env; off since Google's
    policy warning of 2026-10-31."""
    return env.get("GEMINI_ENABLED", "").strip().lower() == "true"


def info(msg):
    print(msg, flush=True)


def warn(msg):
    print("⚠ " + msg, file=sys.stderr, flush=True)


def http(method, url, headers=None, body=None, timeout=60):
    """Return (status, parsed_json_or_text). `body` may be a dict (sent as JSON) or bytes."""
    headers = dict(headers or {})
    data = None
    if isinstance(body, (dict, list)):
        data = json.dumps(body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    elif body is not None:
        data = body
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise PMError("Cannot reach " + url.split("?")[0] + ": " + str(exc.reason))
    except (socket.timeout, TimeoutError):
        raise PMError("Request to " + url.split("?")[0] + " timed out after %ss" % timeout)
    except (HTTPException, ConnectionError) as exc:  # e.g. a container closing mid-request
        raise PMError("Connection to " + url.split("?")[0] + " failed: " + (str(exc) or type(exc).__name__))
    text = raw.decode("utf-8", "replace")
    try:
        return status, json.loads(text)
    except ValueError:
        return status, text


def multipart(fields, file_field, file_path, mime=None):
    """Encode a multipart/form-data body. Returns (content_type, body_bytes)."""
    boundary = "----pm" + uuid.uuid4().hex
    mime = mime or mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    parts = []
    for name, value in fields.items():
        parts.append(
            ("--" + boundary + "\r\n"
             'Content-Disposition: form-data; name="' + name + '"\r\n\r\n'
             + str(value) + "\r\n").encode("utf-8")
        )
    with open(file_path, "rb") as fh:
        payload = fh.read()
    parts.append(
        ("--" + boundary + "\r\n"
         'Content-Disposition: form-data; name="' + file_field + '"; filename="'
         + os.path.basename(file_path) + '"\r\n'
         "Content-Type: " + mime + "\r\n\r\n").encode("utf-8")
    )
    parts.append(payload + b"\r\n")
    parts.append(("--" + boundary + "--\r\n").encode("utf-8"))
    return "multipart/form-data; boundary=" + boundary, b"".join(parts)


def run(cmd, check=True):
    """Run a command, return stdout (stripped). Raises PMError on failure when check=True."""
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and proc.returncode != 0:
        raise PMError("Command failed: " + " ".join(cmd[:4]) + " ...\n" + proc.stderr.strip()[-800:])
    return proc.stdout.strip()


def psql(sql, env):
    """Run SQL inside pm-postgres and return rows as lists of strings (unaligned, tab-separated)."""
    out = run([
        "docker", "exec", "-i", "pm-postgres", "psql",
        "-U", env.get("POSTGRES_USER", "postiz"), "-d", env.get("POSTGRES_DB", "postiz"),
        "-t", "-A", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-c", sql,
    ])
    return [line.split("\t") for line in out.splitlines() if line]


def which(binary):
    return shutil.which(binary) is not None


class Job(object):
    """Marks work in progress as run/jobs/<kind>-<pid>.json, so `publish-machine.sh stop` and the
    menu bar app warn before turning the machine off under it. Set `linger` (seconds) before the
    block ends to keep the marker that long after exit: Evolution may still be relaying a status."""

    def __init__(self, kind, label):
        self.path = os.path.join(JOBS_DIR, "%s-%d.json" % (kind, os.getpid()))
        self.record = {"kind": kind, "label": label[:80], "pid": os.getpid(), "since": int(time.time())}
        self.linger = 0

    def _write(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.record, fh)

    def __enter__(self):
        os.makedirs(JOBS_DIR, exist_ok=True)
        self._write()
        return self

    def __exit__(self, *exc):
        if self.linger > 0:
            self.record.update(pid=None, until=int(time.time() + self.linger))
            self._write()
        elif os.path.exists(self.path):
            os.remove(self.path)
        return False


def active_jobs():
    """Jobs whose process is alive or whose linger time has not passed; stale markers are removed."""
    jobs = []
    if not os.path.isdir(JOBS_DIR):
        return jobs
    now = time.time()
    for name in sorted(os.listdir(JOBS_DIR)):
        path = os.path.join(JOBS_DIR, name)
        try:
            with open(path, encoding="utf-8") as fh:
                job = json.load(fh)
        except (OSError, ValueError):
            continue
        if pid_alive(job.get("pid")) or (job.get("until") or 0) > now:
            jobs.append(job)
        else:
            try:
                os.remove(path)
            except OSError:
                pass
    return jobs


def pid_alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        try:
            handle = kernel.OpenProcess(0x1000, False, int(pid))
        except (ValueError, OverflowError):
            return False
        if not handle:
            return ctypes.get_last_error() == 5
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
    except PermissionError:
        return True  # exists, owned by another user
    except (ProcessLookupError, ValueError, OverflowError):
        return False
    return True


def ffprobe(path):
    """Return (duration_seconds, video_codec, audio_codec, width, height) for a media file."""
    out = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_entries", "format=duration:stream=codec_type,codec_name,width,height", path,
    ])
    data = json.loads(out or "{}")
    vcodec = acodec = None
    width = height = 0
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and vcodec is None:
            vcodec = stream.get("codec_name")
            width, height = stream.get("width") or 0, stream.get("height") or 0
        elif stream.get("codec_type") == "audio" and acodec is None:
            acodec = stream.get("codec_name")
    duration = float(data.get("format", {}).get("duration") or 0)
    return duration, vcodec, acodec, width, height


def whatsapp_scratch():
    path = os.path.join(RUN_DIR, "wa-cache")
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def stage_into_uploads(src, subdir):
    """Copy a host file into data/postiz-uploads/<subdir>/ (no-op if already inside uploads).

    Returns the path relative to data/postiz-uploads.
    """
    src = os.path.abspath(src)
    uploads = os.path.abspath(UPLOADS_DIR)
    if src.startswith(uploads + os.sep):
        return os.path.relpath(src, uploads)
    dest_dir = os.path.join(uploads, subdir)
    os.makedirs(dest_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(dest_dir, stamp + "-" + os.path.basename(src).replace(" ", "_"))
    shutil.copy2(src, dest)
    return os.path.relpath(dest, uploads)


def append_log(name, record):
    os.makedirs(LOGS_DIR, exist_ok=True)
    record = dict(record)
    record.setdefault("at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    with open(os.path.join(LOGS_DIR, name), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def elapsed(start):
    secs = int(time.time() - start)
    return "%dm%02ds" % (secs // 60, secs % 60) if secs >= 60 else "%ds" % secs


# ----------------------------------------------------------------------------
# Postiz (Public API: <POSTIZ_LOCAL_URL>/api/public/v1, header Authorization: <org apiKey>)
# ----------------------------------------------------------------------------

# Even drafts are validated against the provider's settings DTO (Postiz v2.25.3,
# dtos/posts/providers-settings/*.dto.js). Minimal values for the required fields;
# the reviewer can change them in the Postiz editor before approving.
PROVIDER_DEFAULTS = {
    "instagram": {"post_type": "post"},
    "instagram-standalone": {"post_type": "post"},
    "facebook": {"post_type": "post"},
    # UPLOAD sends the video to the TikTok app inbox, where the owner finishes and publishes it within
    # 24 h (TikTok allows 5 pending per day; privacy_level is ignored on UPLOAD). DIRECT_POST from an
    # app TikTok hasn't audited can only be private. .env can switch both (draft_settings).
    "tiktok": {"privacy_level": "SELF_ONLY", "duet": False, "stitch": False, "comment": True,
               "autoAddMusic": "no", "brand_content_toggle": False, "brand_organic_toggle": False,
               "content_posting_method": "UPLOAD"},
    "youtube": {"type": "public", "selfDeclaredMadeForKids": "no"},
}


def ollama_text_prompt(model, prompt):
    if model.startswith("qwen3:"):
        return {"prompt": prompt + "\n/no_think", "think": False}
    return {"prompt": prompt}


def ollama_final_text(data):
    value = (data.get("response") or "").strip()
    value = re.sub(r"<think>.*?</think>", "", value, flags=re.DOTALL | re.IGNORECASE).strip()
    leaked = re.match(r"^(?:(?:okay|alright)[, ]*\s*)?(?:I need to|let me (?:think|break|tackle)|let's tackle)\b",
                      value, flags=re.IGNORECASE)
    return "" if "<think>" in value.lower() or leaked else value


def final_tag(value):
    value = (value or "").strip()
    if not value:
        return ""
    tag = "#" + value.removeprefix("#")
    if not re.fullmatch(r"#\w{1,60}", tag):
        raise PMError("Use one hashtag of up to 60 letters, numbers or underscores, without spaces.")
    return tag


def remove_final_tag(caption, tag):
    if not tag:
        return caption
    pattern = r"(?<![\w#])" + re.escape(tag) + r"(?!\w)"
    caption = re.sub(r"^[ \t]*" + pattern + r"[ \t]+", "", caption, flags=re.IGNORECASE | re.MULTILINE)
    return re.sub(r"[ \t]*" + pattern, "", caption, flags=re.IGNORECASE).rstrip()


def apply_final_tag(caption, tag):
    if not tag:
        return caption
    caption = remove_final_tag(caption, tag)
    if not caption:
        return tag
    last_line = caption.rsplit("\n", 1)[-1]
    separator = " " if re.fullmatch(r"#\w+(?:[ \t]+#\w+)*", last_line) else "\n\n"
    return caption + separator + tag


YOUTUBE_TITLE_LIMIT = 100


def youtube_title_line(content):
    lines = re.sub(r"#\S+|[<>]", "", content).splitlines()
    return next((" ".join(line.split()) for line in lines if line.strip()), "")


def youtube_title_fits(title, short=False):
    budget = YOUTUBE_TITLE_LIMIT
    return len(title) >= 2 and len(title.encode("utf-16-le")) // 2 <= budget


def youtube_title(content, short=False):
    """Format the title and fall back to a whole-word cut if it is too long."""
    title = youtube_title_line(content)
    suffix = ""
    if len(title) < 2:
        return "Untitled video" + suffix
    if not youtube_title_fits(title, short):
        budget = YOUTUBE_TITLE_LIMIT - len(suffix) - 1
        truncated = title.encode("utf-16-le")[:budget * 2].decode("utf-16-le", errors="ignore")
        whole = truncated.rsplit(" ", 1)[0] if " " in truncated else truncated
        title = whole.rstrip(" ,;:–-") + "…"
    return title + suffix


def youtube_description(caption, tag=""):
    """Keep topic hashtags; reserve the final position for the business or fallback tag."""
    tag=final_tag(tag)
    body=remove_final_tag(caption,tag) if tag else caption
    body=re.sub(r"(?:\s*#shorts)+\s*$","",body,flags=re.IGNORECASE).rstrip()
    return apply_final_tag(body,tag or "#shorts")


def draft_settings(identifier, content, env=None, short=False):
    settings = dict(PROVIDER_DEFAULTS.get(identifier, {}))
    if identifier == "tiktok" and env:
        # Once TikTok has audited the app: TIKTOK_POSTING_METHOD=DIRECT_POST and
        # TIKTOK_PRIVACY_LEVEL=PUBLIC_TO_EVERYONE publish directly instead of via the inbox.
        method = (env.get("TIKTOK_POSTING_METHOD") or "").strip().upper()
        if method in ("UPLOAD", "DIRECT_POST"):
            settings["content_posting_method"] = method
        privacy = (env.get("TIKTOK_PRIVACY_LEVEL") or "").strip().upper()
        if privacy in ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY"):
            settings["privacy_level"] = privacy
    if identifier == "youtube":
        settings["title"] = youtube_title(content, short)
    return settings


class Postiz:
    def __init__(self, env):
        self.env = env
        self.base = env.get("POSTIZ_LOCAL_URL", "http://localhost:4200").rstrip("/") + "/api/public/v1"
        rows = psql('SELECT id, name, "apiKey" FROM "Organization" WHERE "apiKey" IS NOT NULL '
                    'ORDER BY "createdAt" LIMIT 1;', env)
        if not rows:
            raise PMError("No Postiz organization with an API key found.")
        self.org_id, self.org_name, self._key = rows[0]

    def _call(self, method, path, body=None, headers=None, timeout=120):
        hdrs = {"Authorization": self._key}
        hdrs.update(headers or {})
        status, data = http(method, self.base + path, hdrs, body, timeout)
        if status >= 400:
            msg = data.get("msg") or data.get("message") if isinstance(data, dict) else data
            raise PMError("Postiz " + method + " " + path + " -> HTTP " + str(status) + ": " + str(msg)[:500])
        return data

    def integrations(self):
        """Connected, enabled channels usable for drafts."""
        items = self._call("GET", "/integrations")
        return [i for i in items if not i.get("disabled")]

    def pick_integration(self, wanted=None):
        """Choose a channel by id / provider / name substring, else the first connected one."""
        items = self.integrations()
        if not items:
            raise PMError(
                "No social channel is connected in Postiz, so a draft has nowhere to live.\n"
                "  Connect one (Instagram, Facebook, TikTok, YouTube...) at\n"
                "  https://" + self.env.get("NGROK_DOMAIN", "<NGROK_DOMAIN>") + "/launches  -> 'Add Channel',\n"
                "  then re-run this command."
            )
        if wanted:
            w = wanted.lower()
            for item in items:
                if w in (item.get("id", "").lower(), (item.get("identifier") or "").lower()) \
                        or w in (item.get("name") or "").lower():
                    return item
            raise PMError("No connected channel matches '" + wanted + "'. Available: "
                          + ", ".join((i.get("identifier") or "?") + ":" + (i.get("name") or "?") for i in items))
        return items[0]

    def upload(self, path):
        """Upload a local file to the Postiz media library. Returns {'id', 'path', ...}."""
        ctype, body = multipart({}, "file", path)
        try:
            return self._call("POST", "/upload", body, {"Content-Type": ctype}, timeout=600)
        except PMError as exc:
            raise PMError("%s (file %s, %.1f MB; Postiz takes images up to 10 MB and videos up to 1 GB)"
                          % (exc, os.path.basename(path), os.path.getsize(path) / 1048576.0))

    def create_draft(self, integration, content, media=None, when=None, settings=None, short=False, *, schedule=False):
        """Stage a draft, or schedule a post when explicitly requested by a caller.
        Settings override the provider defaults. Returns the created post list."""
        merged = draft_settings(integration.get("identifier") or "", content, self.env, short)
        merged.update(settings or {})
        if when is None:
            when = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=1)
        body = {
            "type": "schedule" if schedule else "draft",
            "date": when.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "shortLink": False,
            "tags": [],
            "posts": [{
                "integration": {"id": integration["id"]},
                "value": [{"content": content, "image": media or []}],
                "settings": merged,
            }],
        }
        return self._call("POST", "/posts", body)



# ----------------------------------------------------------------------------
# Media normalization (macOS sips for images, ffmpeg for video)
# ----------------------------------------------------------------------------

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".3gp"}


IMAGE_MAX_BYTES = 9 * 1024 * 1024  # Postiz's limit is 10 MB per image


def normalize_media(src, tmp):
    """Return (kind, path) where path is a social-network friendly JPEG/PNG or H.264 MP4.
    TikTok needs this: Postiz treats any upload that isn't .mp4 as a photo."""
    ext = os.path.splitext(src)[1].lower()
    if ext in IMAGE_EXT:
        # Postiz refuses images over 10 MB (and answers HTTP 500); camera PNGs and big JPEGs get resized.
        small = os.path.getsize(src) <= IMAGE_MAX_BYTES
        return "image", (src if ext in (".jpg", ".jpeg", ".png") and small else to_jpeg(src, tmp))
    if ext in VIDEO_EXT:
        return "video", to_mp4(src, tmp)
    raise PMError("Unsupported media type '%s' (images: JPG/PNG/HEIC/WEBP, videos: MP4/MOV/WEBM)." % ext)


def display_dimensions(path, width, height):
    """Use display orientation, including phones that store rotation metadata."""
    rotation = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                    "stream_tags=rotate:stream_side_data=rotation", "-of", "default=nw=1:nk=1", path], check=False)
    if any(r.strip().lstrip("-") in ("90", "270") for r in (rotation or "").splitlines()):
        return height, width
    return width, height


def is_short(path):
    """True for a YouTube Short: vertical or square, at most 3 minutes."""
    duration, _, _, width, height = ffprobe(path)
    width, height = display_dimensions(path, width, height)
    return 0 < duration <= 180 and height >= width


def youtube_short(identifier, kind, path):
    """YouTube posts must be one video; returns True for a Short (and says which it is)."""
    if identifier != "youtube":
        return False
    if kind != "video":
        raise PMError("YouTube posts must be a video (.mp4); photos can't be posted there.")
    short = is_short(path)
    info("      YouTube: " + ("a Short (vertical or square, up to 3 min)." if short
                             else "not a Short (Shorts are vertical or square, up to 3 min); a regular video."))
    return short


def to_jpeg(src, out_dir, max_side=1920):
    """Convert/resize any macOS-readable image (PNG/HEIC/WEBP/TIFF...) to an 85% JPEG."""
    out = os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0] + ".jpg")
    if sys.platform == "darwin" and which("sips"):
        run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85",
             "-Z", str(max_side), src, "--out", out])
    else:
        run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", src, "-frames:v", "1",
             "-vf", f"scale={max_side}:{max_side}:force_original_aspect_ratio=decrease",
             "-q:v", "2", out])
    return out


def to_mp4(src, out_dir, max_seconds=None, max_side=1920, *, max_bytes=None):
    """Return src if it already is an H.264/AAC MP4 within limits, else a transcoded copy."""
    if not which("ffprobe") or not which("ffmpeg"):
        raise PMError("ffmpeg/ffprobe are required for video (brew install ffmpeg).")
    duration, vcodec, acodec, width, height = ffprobe(src)
    if vcodec is None:
        raise PMError("No video stream found in " + src)
    ext = os.path.splitext(src)[1].lower()
    too_long = bool(max_seconds) and duration > max_seconds
    fits_bytes = max_bytes is None or os.path.getsize(src) <= max_bytes
    if (ext == ".mp4" and vcodec == "h264" and acodec in (None, "aac")
            and not too_long and fits_bytes and max(width, height) <= max_side):
        return src
    out = os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0] + ".mp4")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src]
    if too_long:
        cmd += ["-t", str(max_seconds)]
    rate_limit = []
    if max_bytes is not None:
        seconds = max(1, min(duration, max_seconds or duration))
        # Allow for audio, MP4 overhead and encoder bitrate variation.
        video_kbps = max(100, int(max_bytes * 8 * 0.8 / seconds / 1000) - 96)
        rate_limit = ["-maxrate", f"{video_kbps}k", "-bufsize", f"{video_kbps}k"]
    cmd += [
        "-vf", "scale='min(%d,iw)':'min(%d,ih)':force_original_aspect_ratio=decrease,"
               "scale=trunc(iw/2)*2:trunc(ih/2)*2" % (max_side, max_side),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", *rate_limit, "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out,
    ]
    info("      Transcoding video to H.264/AAC MP4 (%s, %.0fs, %dx%d)..." % (vcodec, duration, width, height))
    run(cmd)
    if max_bytes is not None and os.path.getsize(out) > max_bytes:
        raise PMError("Prepared video exceeds the safe size for WhatsApp Status.")
    return out


def split_story_video(path, folder):
    """Prepare balanced Story clips under 60 seconds without dropping the tail."""
    duration = ffprobe(path)[0]
    if duration <= 60:
        return [path]
    count = math.ceil(duration / 59.5)
    span = duration / count
    parts = []
    for index in range(count):
        target = os.path.join(folder, "story-%02d.mp4" % (index + 1))
        run(["ffmpeg", "-nostdin", "-y", "-v", "error",
             "-ss", str(index * span), "-i", path, "-t", str(span),
             "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", target])
        if not 3 <= ffprobe(target)[0] <= 60:
            raise PMError("Could not prepare a Story clip between 3 and 60 seconds.")
        parts.append(target)
    return parts
