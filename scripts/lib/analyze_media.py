#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Cloud path of the Dual-AI design: Google Gemini inspects an image or video and writes
the caption; media + caption are staged in Postiz as a DRAFT (HITL guardrail).

Images up to 15 MB go inline (request bodies must stay under 20 MB after base64); videos
and larger files use the Gemini Files API (resumable upload, polled until ACTIVE, deleted
afterwards). The model comes from GEMINI_MODEL (default gemini-flash-latest).
Switched off unless .env has GEMINI_ENABLED=true; until then it stops before sending anything.
"""
import argparse
import base64
import json
import mimetypes
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmlib  # noqa: E402
from pmlib import IMAGE_EXT, VIDEO_EXT, PMError, info, warn  # noqa: E402
from create_draft import drop_repeats, fitting_emojis  # noqa: E402  (same guards as local captions)

API = "https://generativelanguage.googleapis.com"
INLINE_LIMIT = 15 * 1024 * 1024

PROMPT = """Analyze this {kind} for a social media post and fill in the JSON fields.
Use only visible facts and the operator's context. Avoid inventing brand, pricing, or contact details.
- description: what is shown in 1-2 sentences.
- caption: 1-3 short sentences in {lang}, with at most 2 relevant emojis.
- hashtags: 5-8 relevant hashtags.
- alt_text: a concise accessibility description (max 125 characters).
- suggested_platforms: which of instagram, facebook, tiktok, youtube_shorts, whatsapp_status fit best.
- quality_notes: anything a human should check before posting, or "none".{hint}"""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "description": {"type": "STRING"},
        "caption": {"type": "STRING"},
        "hashtags": {"type": "ARRAY", "items": {"type": "STRING"}},
        "alt_text": {"type": "STRING"},
        "suggested_platforms": {"type": "ARRAY", "items": {"type": "STRING"}},
        "quality_notes": {"type": "STRING"},
    },
    "required": ["description", "caption", "hashtags", "alt_text", "suggested_platforms", "quality_notes"],
}


def resolve_input(arg, latest):
    if latest:
        candidates = []
        for base, _dirs, files in os.walk(pmlib.UPLOADS_DIR):
            for name in files:
                if os.path.splitext(name)[1].lower() in IMAGE_EXT | VIDEO_EXT:
                    full = os.path.join(base, name)
                    candidates.append((os.path.getmtime(full), full))
        if not candidates:
            raise PMError("No images/videos found under data/postiz-uploads.")
        return max(candidates)[1]
    path = os.path.expanduser(arg)
    if not os.path.isfile(path):
        alt = os.path.join(pmlib.UPLOADS_DIR, arg)
        if os.path.isfile(alt):
            return alt
        raise PMError("Media file not found: %s (also looked in data/postiz-uploads/)" % arg)
    return path


def gemini_error(status, data):
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        return "Gemini HTTP %s: %s" % (status, data["error"].get("message", "")[:400])
    return "Gemini HTTP %s: %s" % (status, str(data)[:400])


def upload_to_gemini(key, path, mime):
    """Resumable upload to the Gemini Files API. Returns the file resource once ACTIVE."""
    size = os.path.getsize(path)
    start = urllib.request.Request(
        API + "/upload/v1beta/files", method="POST",
        data=json.dumps({"file": {"display_name": os.path.basename(path)}}).encode("utf-8"),
        headers={
            "x-goog-api-key": key,
            "Content-Type": "application/json",
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(size),
            "X-Goog-Upload-Header-Content-Type": mime,
        })
    try:
        with urllib.request.urlopen(start, timeout=60) as resp:
            upload_url = resp.headers.get("X-Goog-Upload-URL")
        with open(path, "rb") as fh:
            payload = fh.read()
        finish = urllib.request.Request(upload_url, method="POST", data=payload, headers={
            "Content-Length": str(size),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        })
        with urllib.request.urlopen(finish, timeout=900) as resp:
            meta = json.loads(resp.read().decode("utf-8"))["file"]
    except urllib.error.HTTPError as exc:
        raise PMError("Gemini file upload failed: HTTP %s %s" % (exc.code, exc.read()[:300]))
    except urllib.error.URLError as exc:
        raise PMError("Gemini file upload failed: %s" % exc.reason)

    deadline = time.time() + 300
    while meta.get("state") == "PROCESSING":
        if time.time() > deadline:
            raise PMError("Gemini is still processing the video after 5 minutes.")
        time.sleep(3)
        status, meta = pmlib.http("GET", API + "/v1beta/" + meta["name"], {"x-goog-api-key": key}, timeout=30)
        if status != 200:
            raise PMError(gemini_error(status, meta))
    if meta.get("state") != "ACTIVE":
        raise PMError("Gemini could not process the file (state=%s)." % meta.get("state"))
    return meta


def analyze(env, path, kind, lang, hint):
    if not pmlib.gemini_enabled(env):
        raise PMError(pmlib.GEMINI_OFF)
    key = env.get("GEMINI_API_KEY", "")
    if not key or key == "your_gemini_api_key_here":
        raise PMError("GEMINI_API_KEY is not set in .env")
    model = env.get("GEMINI_MODEL", "gemini-flash-latest")
    mime = mimetypes.guess_type(path)[0] or ("image/jpeg" if kind == "image" else "video/mp4")
    uploaded = None
    if kind == "image" and os.path.getsize(path) <= INLINE_LIMIT:
        with open(path, "rb") as fh:
            media_part = {"inlineData": {"mimeType": mime, "data": base64.b64encode(fh.read()).decode("ascii")}}
    else:
        info("      Uploading %s to the Gemini Files API..." % kind)
        uploaded = upload_to_gemini(key, path, mime)
        media_part = {"fileData": {"mimeType": mime, "fileUri": uploaded["uri"]}}

    gen = {"responseMimeType": "application/json", "responseSchema": SCHEMA, "temperature": 0.7}
    # Low thinking cut a caption request from ~430 to ~30 tokens on gemini-3.8-flash.
    level = env.get("GEMINI_THINKING_LEVEL", "low").strip()
    if level:
        gen["thinkingConfig"] = {"thinkingLevel": level}
    body = {
        "contents": [{"role": "user", "parts": [
            media_part,
            {"text": PROMPT.format(kind=kind, lang=lang, hint=("\nContext from the owner: " + hint) if hint else "")},
        ]}],
        "generationConfig": gen,
    }
    url = API + "/v1beta/models/%s:generateContent" % model
    started = time.time()
    try:
        for attempt, pause in enumerate((0, 20, 60), 1):
            if pause:
                warn("Gemini busy (HTTP %s); retrying in %ds (attempt %d/3)..." % (status, pause, attempt))
                time.sleep(pause)
            status, data = pmlib.http("POST", url, {"x-goog-api-key": key}, body, timeout=300)
            if status == 400 and "thinking" in str(data).lower() and "thinkingConfig" in gen:
                gen.pop("thinkingConfig")  # this model does not accept thinkingLevel; use its default
                status, data = pmlib.http("POST", url, {"x-goog-api-key": key}, body, timeout=300)
            if status not in (500, 503):  # no retry on 429 (quota or rate limit): it only adds requests
                break
    finally:
        if uploaded:
            pmlib.http("DELETE", API + "/v1beta/" + uploaded["name"], {"x-goog-api-key": key}, timeout=30)
    if status != 200:
        raise PMError(gemini_error(status, data))
    try:
        parts = data["candidates"][0]["content"]["parts"]
        result = json.loads("".join(p.get("text", "") for p in parts if not p.get("thought")))
    except (KeyError, IndexError, ValueError):
        reason = (data.get("candidates") or [{}])[0].get("finishReason") or data.get("promptFeedback")
        raise PMError("Gemini returned no usable analysis (reason: %s)." % reason)
    return result, data.get("usageMetadata", {}), data.get("modelVersion", model), round(time.time() - started, 1)


def compose_post(result):
    tags = []
    for tag in result.get("hashtags") or []:
        tag = "#" + tag.strip().lstrip("#").replace(" ", "")
        if len(tag) > 1 and tag.lower() not in (t.lower() for t in tags):
            tags.append(tag)
    caption = (result.get("caption") or "").strip()
    caption = drop_repeats(re.sub(r"[ \t]{2,}", " ", fitting_emojis(caption, result.get("description") or "")).strip())
    return caption + ("\n\n" + " ".join(tags) if tags else "")


def main():
    parser = argparse.ArgumentParser(
        prog="analyze-media.sh",
        description="Gemini looks at an image/video, writes the caption, and stages a Postiz DRAFT.",
        epilog=(
            "examples:\n"
            "  ./scripts/analyze-media.sh data/postiz-uploads/croissants.jpg\n"
            "  ./scripts/analyze-media.sh --latest --lang Spanish\n"
            "  ./scripts/analyze-media.sh ~/Movies/oven.mov --hint \"new pumpkin bread, $4.50\"\n"
            "  ./scripts/analyze-media.sh --dry-run photo.heic"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", nargs="?", help="image/video path (absolute, relative, or inside data/postiz-uploads)")
    parser.add_argument("--latest", action="store_true", help="use the newest media file in data/postiz-uploads")
    parser.add_argument("--channel", help="Postiz channel id/provider/name (default: first connected)")
    parser.add_argument("--lang", default=None, help="caption language (default: CAPTION_LANGUAGE or English)")
    parser.add_argument("--hint", help="extra context for the caption (price, promo, event...)")
    parser.add_argument("--settings", type=json.loads, default=None,
                        help='provider settings JSON merged over the defaults, e.g. \'{"post_type": "story"}\'')
    parser.add_argument("--dry-run", action="store_true", help="analyze only; stage nothing in Postiz")
    args = parser.parse_args()
    if not args.path and not args.latest:
        parser.error("give a media path or --latest")

    env = pmlib.load_env()
    if not pmlib.gemini_enabled(env):
        raise PMError(pmlib.GEMINI_OFF)  # before any work (analyze() checks too)
    lang = args.lang or env.get("CAPTION_LANGUAGE", "English")

    info("======================================================")
    info("  CLOUD MULTIMODAL PIPELINE (Gemini -> Postiz DRAFT)")
    info("======================================================")
    src = resolve_input(args.path, args.latest)
    info("[1/4] Media: %s" % src)

    postiz = channel = None
    if not args.dry_run:
        postiz = pmlib.Postiz(env)
        channel = postiz.pick_integration(args.channel)  # fail fast before spending tokens
        info("      Target channel: %s (%s)" % (channel.get("name"), channel.get("identifier")))

    tmp = tempfile.mkdtemp(prefix="pm-analyze-")
    try:
        kind, ready = pmlib.normalize_media(src, tmp)
        short = pmlib.youtube_short(channel.get("identifier") if channel else "", kind, ready)
        info("[2/4] Asking %s to analyze the %s..." % (env.get("GEMINI_MODEL", "gemini-flash-latest"), kind))
        result, usage, version, seconds = analyze(env, ready, kind, lang, args.hint)
        post_text = compose_post(result)
        info("      model=%s  %ss  tokens: prompt=%s output=%s total=%s" % (
            version, seconds, usage.get("promptTokenCount"), usage.get("candidatesTokenCount"),
            usage.get("totalTokenCount")))
        info("\n--- WHAT GEMINI SEES ---\n%s" % result.get("description", ""))
        info("\n--- DRAFT POST ---\n%s" % post_text)
        info("\nAlt text : %s" % result.get("alt_text", ""))
        info("Platforms: %s" % ", ".join(result.get("suggested_platforms") or []))
        info("Check    : %s\n" % result.get("quality_notes", ""))

        if args.dry_run:
            info("[3/4] Dry run: nothing uploaded or staged.")
            return 0

        info("[3/4] Uploading media to the Postiz library...")
        uploaded = postiz.upload(ready)
        info("      %s" % uploaded["path"])
        info("[4/4] Staging DRAFT in Postiz (HITL: requires manual approval)...")
        created = postiz.create_draft(channel, post_text, [{"id": uploaded["id"], "path": uploaded["path"]}],
                                      settings=args.settings, short=short)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    post_id = created[0]["postId"] if created else None
    pmlib.append_log("drafts.jsonl", {
        "source": "analyze-media", "post_id": post_id, "channel": channel.get("identifier"),
        "integration_id": channel.get("id"), "model": version, "media": uploaded["path"],
        "tokens": usage.get("totalTokenCount"), "caption": post_text[:500],
        "alt_text": result.get("alt_text"), "quality_notes": result.get("quality_notes"),
    })
    info("      ✔ Draft %s created." % post_id)
    info("======================================================")
    info("  HITL ACTIVE: review & approve the draft in Postiz:")
    info("  https://%s/launches" % env.get("NGROK_DOMAIN", "<NGROK_DOMAIN>"))
    info("======================================================")
    return 0


if __name__ == "__main__":
    try:
        with pmlib.Job("media-draft", " ".join(sys.argv[1:])):  # `stop` and the menu bar app warn while it runs
            sys.exit(main())
    except PMError as exc:
        print("✖ " + str(exc), file=sys.stderr)
        sys.exit(2)
