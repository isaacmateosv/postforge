# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared, reviewed posting workflow for Rust desktop and Telegram."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import time
from datetime import datetime, timezone

import file_lock
import plan_post
import pmlib

TICKET_AGE = 24 * 3600
PIPELINE_REVISION = 3
ID = re.compile(r"[a-f0-9]{32}")
FIELDS = ("body", "mode", "networks", "post_at", "media", "placement", "cover_image",
          "cover_second", "final_tag", "language", "text_confirmed", "whatsapp_background", "youtube_mode")
VIDEO_EXT = pmlib.VIDEO_EXT


def directory():
    path = Path(pmlib.RUN_DIR) / "composer-plans"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def write_record(path, value):
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def path_for(identifier):
    if not isinstance(identifier, str) or not ID.fullmatch(identifier):
        raise pmlib.PMError("Invalid review reference.")
    return directory() / (identifier + ".json")


def load_ticket(identifier):
    try:
        ticket = json.loads(path_for(identifier).read_text())
    except (OSError, ValueError):
        raise pmlib.PMError("This preview is unavailable. Prepare a fresh plan.") from None
    if time.time() > ticket["created_at"] + TICKET_AGE:
        raise pmlib.PMError("This preview expired. Prepare a fresh plan.")
    return ticket


def fields(value):
    data = {key: value[key] for key in FIELDS if key in value}
    body = data.get("body")
    if not isinstance(body, str) or not body.strip() or len(body) > 20000:
        raise pmlib.PMError("Enter an idea or exact caption, up to 20,000 characters.")
    if data.get("mode") not in ("idea", "exact"):
        raise pmlib.PMError("Choose an idea or exact caption.")
    networks = data.get("networks")
    if not isinstance(networks, list) or not networks or any(n not in plan_post.NETWORKS for n in networks):
        raise pmlib.PMError("Choose supported destinations.")
    media = data.get("media", [])
    if not isinstance(media, list) or len(media) > 10:
        raise pmlib.PMError("Attach up to ten media files.")
    for item in media + ([data["cover_image"]] if data.get("cover_image") else []):
        if not isinstance(item, str) or not Path(item).is_file():
            raise pmlib.PMError("An attached file is missing. Choose it again.")
        if Path(item).suffix.lower() not in pmlib.IMAGE_EXT | pmlib.VIDEO_EXT:
            raise pmlib.PMError("Choose an image or video file.")
    if not media:
        if not data.get("text_confirmed") or not set(networks) <= {"facebook", "threads", "whatsapp"}:
            raise pmlib.PMError("Confirm text-only destinations: Facebook posts, Threads posts, or WhatsApp Status.")
    if data.get("youtube_mode", "auto") not in ("auto", "shorts", "regular"):
        raise pmlib.PMError("Choose a YouTube format.")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", data.get("whatsapp_background", "#128C7E")):
        raise pmlib.PMError("Choose a valid WhatsApp background color.")
    data["body"] = body.strip()
    data["networks"] = list(dict.fromkeys(networks))
    data["media"] = [str(Path(item).resolve()) for item in media]
    if data.get("cover_image"):
        data["cover_image"] = str(Path(data["cover_image"]).resolve())
    return data


def signature(data):
    files = []
    for path in data["media"] + ([data["cover_image"]] if data.get("cover_image") else []):
        info = os.stat(path)
        files.append([path, info.st_size, info.st_mtime_ns])
    encoded = json.dumps([data, files], sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_plan(env, data):
    try:
        zone = plan_post.ZoneInfo(env.get("PM_TIMEZONE", "America/Guayaquil")) if plan_post.ZoneInfo else timezone.utc
    except KeyError:
        raise pmlib.PMError("Timezone data is unavailable. Install Python tzdata and check PM_TIMEZONE.") from None
    try:
        when = datetime.fromisoformat(data["post_at"])
        if when.tzinfo is None:
            when = when.replace(tzinfo=zone)
    except (KeyError, TypeError, ValueError):
        raise pmlib.PMError("Choose a valid local date and time.") from None
    now = datetime.now(zone)
    if when < now + plan_post.MIN_SCHEDULE_LEAD:
        raise pmlib.PMError("Choose a time at least five minutes in the future.")
    lang = plan_post.detect_lang(data["body"], env.get("CAPTION_LANGUAGE", "Spanish"))
    ui = "Spanish" if data.get("language") == "es" else "English"
    local = when.astimezone(zone)
    command = " and ".join(data["networks"]) + local.strftime(" %Y-%m-%d at %I:%M %p") + "; caption: review"
    p = plan_post.plan(env, command, data["media"], lang, now,
                       placement_override=data.get("placement", "both"),
                       cover_image=data.get("cover_image"), cover_second=data.get("cover_second"),
                       ui_lang=ui, text_networks=data["networks"] if not data["media"] else None)
    p["when"] = when
    p["exact"] = data["body"] if data["mode"] == "exact" else None
    p["idea"] = data["body"] if data["mode"] == "idea" else None
    p["final_tag"] = data.get("final_tag", env.get("CAPTION_FINAL_TAG", ""))
    p["youtube_mode"] = data.get("youtube_mode", "auto")
    p["youtube_trim"] = p["youtube_mode"] in ("auto", "shorts")
    p["whatsapp_background"] = data.get("whatsapp_background", "#128C7E")
    return p


def preview(env, value):
    data = fields(value)
    p = build_plan(env, data)
    data["post_at"] = p["when"].isoformat()
    expected = signature(data)
    with pmlib.Job("compose-preview", "Prepare a plan"):
        result = plan_post.run(env, p, True)
        result["public_origin"] = env.get("FRONTEND_URL", "")
    if signature(data) != expected:
        raise pmlib.PMError("An attached file changed while preparing the preview. Prepare a fresh plan.")
    family = secrets.token_hex(16)
    write_record(path_for(family), {"state": "review", "created_at": time.time()})
    return issue_ticket(data, result, family, expected)


def issue_ticket(data, result, family, expected):
    identifier = secrets.token_hex(16)
    ticket = {"created_at": time.time(), "fields": data, "plan": result,
              "family": family, "signature": expected, "pipeline_revision": PIPELINE_REVISION}
    write_record(path_for(identifier), ticket)
    return {"review_id": identifier, "plan": result}


def revise(env, identifier, edited=None, youtube_title=None, regenerate_title=False, post_at=None):
    ticket = load_ticket(identifier)
    with file_lock.exclusive(str(path_for(ticket["family"])) + ".lock"):
        state = json.loads(path_for(ticket["family"]).read_text())
        if state["state"] != "review":
            raise pmlib.PMError("This plan has already been submitted. Check the calendar.")
        if ticket.get("pipeline_revision") != PIPELINE_REVISION:
            raise pmlib.PMError("The planner changed. Check saved posts, then prepare a fresh plan. / El planificador cambió. Revisa las publicaciones guardadas y prepara otro plan.")
        data = ticket["fields"]
        if signature(data) != ticket["signature"]:
            raise pmlib.PMError("An attached file changed. Prepare a fresh plan.")
        instruction = ("idea: " if data["mode"] == "idea" else "caption: ") + data["body"]
        if post_at is not None:
            data = dict(data, post_at=post_at)
            delivery = build_plan(env, data)
            result = dict(copy.deepcopy(ticket["plan"]),
                          when_utc=delivery["when"].astimezone(timezone.utc).isoformat(),
                          when_local=delivery["when"].strftime("%a %d %b %Y %H:%M"))
            return issue_ticket(data, result, ticket["family"], signature(data))
        if regenerate_title:
            result = copy.deepcopy(ticket["plan"])
            if not result.get("youtube_title"):
                raise pmlib.PMError("This plan has no YouTube destination.")
            with pmlib.Job("compose-title", "Try another YouTube title"):
                result["youtube_title"] = plan_post.reviewed_youtube_title(
                    env, result["caption"], None, result["lang"], result.get("short", False),
                    force=True, tag=result.get("final_tag", ""), previous=result["youtube_title"])
            result["youtube_title_manual"] = True
        elif youtube_title is not None:
            if not isinstance(youtube_title, str) or not youtube_title.strip() or len(youtube_title.strip().encode("utf-16-le")) // 2 > 100:
                raise pmlib.PMError("YouTube titles must contain 1–100 characters. / El título de YouTube debe tener entre 1 y 100 caracteres.")
            title = plan_post.tagged_youtube_title(youtube_title.strip(), ticket["plan"].get("final_tag", ""), strict=True)
            result = dict(copy.deepcopy(ticket["plan"]), youtube_title=title, youtube_title_manual=True)
        else:
            with pmlib.Job("compose-caption", "Revise a caption"):
                result = plan_post.revise_copy(env, ticket["plan"], instruction, edited)
        return issue_ticket(data, result, ticket["family"], ticket["signature"])


def submit(env, identifier, mode):
    if mode not in ("draft", "schedule"):
        raise pmlib.PMError("Choose drafts or direct scheduling.")
    ticket = load_ticket(identifier)
    family_path = path_for(ticket["family"])
    with file_lock.exclusive(str(Path(pmlib.RUN_DIR) / "tunnel-url.lock")), file_lock.exclusive(str(family_path) + ".lock"):
        state = json.loads(family_path.read_text())
        if state["state"] == "completed":
            return dict(state["receipt"], already_submitted=True)
        if state["state"] != "review":
            raise pmlib.PMError("Submission needs review. Check Postiz before preparing another batch.")
        if ticket.get("pipeline_revision") != PIPELINE_REVISION:
            raise pmlib.PMError("The planner changed. Check saved posts, then prepare a fresh plan. / El planificador cambió. Revisa las publicaciones guardadas y prepara otro plan.")
        if ticket["plan"].get("public_origin", "") != env.get("FRONTEND_URL", ""):
            raise pmlib.PMError("The public URL changed. Prepare a fresh plan. / La URL pública cambió. Prepara un plan nuevo.")
        data = fields(ticket["fields"])
        if signature(data) != ticket["signature"]:
            raise pmlib.PMError("An attached file changed. Prepare a fresh plan.")
        p = build_plan(env, data)
        for source, target in (("caption", "reviewed_caption"), ("threads_caption", "reviewed_threads_caption"),
                               ("youtube_title", "reviewed_youtube_title")):
            if ticket["plan"].get(source):
                p[target] = ticket["plan"][source]
        p["final_tag"] = ticket["plan"].get("final_tag", "")
        targets = [target for target in ticket["plan"]["targets"] if target["network"] != "whatsapp"]
        if any(not target.get("integration_id") for target in targets):
            raise pmlib.PMError("Prepare a fresh preview to confirm the connected accounts.")
        p["reviewed_integrations"] = list({target["integration_id"] for target in targets})
        write_record(family_path, {"state": "submitting", "created_at": time.time()})
        try:
            with pmlib.Job("compose-submit", "Submit a reviewed plan"):
                result = plan_post.run(env, p, False, schedule=(mode == "schedule"))
        except Exception:
            write_record(family_path, {"state": "needs_review", "created_at": time.time()})
            raise
        write_record(family_path, {"state": "completed", "created_at": time.time(), "receipt": result})
        return result


def options(env):
    client = pmlib.Postiz(env)
    channels = client.integrations()
    networks = []
    for network, (_, identifiers) in plan_post.NETWORKS.items():
        matches = [c for c in channels if c.get("identifier") in identifiers]
        if matches or network == "whatsapp":
            networks.append({"id": network, "name": plan_post.NAMES[network],
                             "accounts": [c.get("name", network) for c in matches],
                             "text": network in ("facebook", "threads", "whatsapp")})
    return {"networks": networks, "timezone": env.get("PM_TIMEZONE", "America/Guayaquil"),
            "final_tag": pmlib.final_tag(env.get("CAPTION_FINAL_TAG", ""))}
