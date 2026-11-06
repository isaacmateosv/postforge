#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""WhatsApp door for hands-free posting: what you send to your own chat ("Message yourself") on the
primary phone becomes Postiz drafts, like the menu bar's New Post window (same engine: plan_post.py).

- Reads only your own chat and replies only there. It never writes to anyone else.
- Acts only on messages that name a network and a time: a text, a photo or video caption, or a voice
  note. Photos and videos sent up to 10 minutes before the instruction go with it. Notes to yourself
  that name no network are ignored.
- Voice notes are transcribed on this Mac with whisper.cpp (Spanish or English, detected); the reply
  quotes what it understood, so you can check it.
- Drafts only (HITL): you review and approve them on the Postiz calendar.
- Messages sent while the stack was off are handled at the next start.

    ./scripts/wa-inbox.sh            keep listening (publish-machine.sh start runs it in the background)
    ./scripts/wa-inbox.sh --once     one pass, then exit
    ./scripts/wa-inbox.sh --dry-run  show what it would do: no drafts, no replies, nothing marked done
"""
import argparse
import base64
import fcntl
import html
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmlib  # noqa: E402
import plan_post  # noqa: E402
import whatsapp_pending  # noqa: E402
from pmlib import PMError  # noqa: E402
from wa_settings import redis_text  # noqa: E402

EVO = "http://localhost:8080"
STATE_FILE = os.path.join(pmlib.RUN_DIR, "wa-inbox.json")
LOCK_FILE = os.path.join(pmlib.RUN_DIR, "wa-inbox.lock")
CONFIRM_DIR = os.path.join(pmlib.RUN_DIR, "wa-confirmations")
REPLY_MARK = "🤖 Publish Machine"  # its own replies start with this, so it never acts on them
MEDIA_WINDOW = 10 * 60  # seconds a photo or video waits for its instruction
SETTLE = 5  # seconds to wait for the rest of an album before acting
POLL_SECONDS = 15
STREAM_VIDEO_LIMIT = 256 * 1024 * 1024
TEXT_TYPES = ("conversation", "extendedTextMessage")
MEDIA_TYPES = ("imageMessage", "videoMessage")
# Provider vocabulary improves recognition of channel names.
VOCABULARY = "Instagram, TikTok, YouTube Shorts, Facebook, Threads, WhatsApp."
POST_VERB = re.compile(r"\b(publica\w*|public\w*|sub[ei]\w*|programa\w*|postea\w*|comparte\w*|post|publish|schedule|share|upload)\b",
                       re.IGNORECASE)
APPROVE_WHATSAPP = re.compile(r"^(?:aprobar|aprueba|approve)\s+(?:whatsapp|wa)(?:\s+([a-f0-9]{12}))?$",
                              re.IGNORECASE)
APPROVE_PLAN = re.compile(r"^(?:aprobar|aprueba|approve)\s+(?:plan|publicaci[oó]n|post)(?:\s+([a-f0-9]{12}|\d+|latest|último))?$",
                          re.IGNORECASE)
REJECT_PLAN = re.compile(r"^(?:rechazar|rechaza|reject|decline)\s+(?:plan|publicaci[oó]n|post)(?:\s+([a-f0-9]{12}|\d+|latest|último))?$",
                         re.IGNORECASE)
ES_DATES = {"Mon": "lun", "Tue": "mar", "Wed": "mié", "Thu": "jue", "Fri": "vie", "Sat": "sáb", "Sun": "dom",
            "Jan": "ene", "Apr": "abr", "Aug": "ago", "Dec": "dic"}
EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/heic": ".heic",
              "video/mp4": ".mp4", "video/quicktime": ".mov", "audio/ogg": ".ogg", "audio/mpeg": ".mp3",
              "audio/mp4": ".m4a", "audio/aac": ".aac"}
stopping = False


def approval_text(text):
    """Allow WhatsApp inline-code formatting around an approval command."""
    value = text.strip()
    if len(value) >= 2 and value[0] == value[-1] == "`":
        value = value.strip("`").strip()
    return value


def log(text):
    print("[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), text), flush=True)


def evo_call(env, method, path, body=None, timeout=120):
    headers = {"apikey": env.get("AUTHENTICATION_API_KEY", "")}
    return pmlib.http(method, EVO + path, headers, body=body, timeout=timeout)


def own_identity(env):
    """(instance name, instance id, own number, own chat ids: phone JID and LID)."""
    name = env.get("WA_INSTANCE", "status-engine")
    rows = pmlib.psql("SELECT id, \"ownerJid\" FROM evolution.\"Instance\" WHERE name = '%s'"
                      % re.sub(r"[^\w-]", "", name), env)
    if not rows or len(rows[0]) < 2 or "@" not in rows[0][1]:
        raise PMError("WhatsApp isn't linked (no owner on instance '%s')" % name)
    instance_id, owner = rows[0][0], rows[0][1]
    number = owner.split("@")[0].split(":")[0]
    if not re.fullmatch(r"[0-9a-f-]{36}", instance_id) or not number.isdigit():
        raise PMError("Unexpected instance data")
    jids = {number + "@s.whatsapp.net"}
    raw = pmlib.run(["docker", "exec", "pm-redis", "redis-cli", "-n", "1", "HGET",
                     "evolution:instance:" + instance_id, "lid-mapping-" + number], check=False)
    lid = redis_text(raw).split("@")[0].split(":")[0] if raw else ""
    if lid.isdigit():
        jids.add(lid + "@lid")
    return name, instance_id, number, jids


def messages_since(env, instance_id, jids, since):
    chats = ", ".join("'%s'" % j for j in sorted(jids) if re.fullmatch(r"\d+@(s\.whatsapp\.net|lid)", j))
    rows = pmlib.psql(
        # ::jsonb::text keeps it on one line: json_agg puts a newline between rows, and psql output
        # is read line by line.
        "SELECT coalesce(json_agg(t ORDER BY t.ts, t.id), '[]')::jsonb::text FROM ("
        " SELECT m.id, m.key, m.\"messageType\" AS type, m.message, m.\"messageTimestamp\" AS ts"
        " FROM evolution.\"Message\" m WHERE m.\"instanceId\" = '%s' AND (m.key->>'fromMe')::boolean"
        " AND (m.key->>'remoteJid' IN (%s) OR m.key->>'remoteJidAlt' IN (%s))"
        " AND m.\"messageTimestamp\" > %d) t" % (instance_id, chats, chats, int(since)), env)
    return json.loads(rows[0][0]) if rows else []


def text_of(row):
    message = row.get("message") or {}
    if row["type"] == "conversation":
        return message.get("conversation") or ""
    if row["type"] == "extendedTextMessage":
        return (message.get("extendedTextMessage") or {}).get("text") or ""
    if row["type"] in MEDIA_TYPES:
        return (message.get(row["type"]) or {}).get("caption") or ""
    return ""


def media_size(row):
    """WhatsApp encodes protobuf uint64 sizes as integers, strings, or {low, high}."""
    payload = (row.get('message') or {}).get(row.get('type'))
    raw = payload.get('fileLength') if isinstance(payload, dict) else None
    try:
        if isinstance(raw, dict):
            return ((int(raw['high']) & 0xffffffff) << 32) | (int(raw['low']) & 0xffffffff)
        return int(raw) if not isinstance(raw, bool) else None
    except (ValueError, TypeError, KeyError):
        return None


def media_limit(env):
    try:
        return max(1, min(64, int(env.get('WA_MAX_MEDIA_MB', '32')))) * 1024 * 1024
    except (ValueError, TypeError):
        return 32 * 1024 * 1024


def stream_video(row, folder, size):
    payload = row["message"]["videoMessage"]
    metadata = {key: payload.get(key) for key in ("mediaKey", "fileSha256", "directPath")}
    if not all(isinstance(value, str) and value for value in metadata.values()):
        raise PMError("WhatsApp did not provide enough information to download this large video. Use New Post in the Mac app.")
    metadata["size"] = size
    extension = EXTENSIONS.get((payload.get("mimetype") or "").split(";")[0], ".mp4")
    helper = os.path.join(os.path.dirname(__file__), "wa-media-stream.mjs")
    with open(helper, encoding="utf-8") as source:
        command = ["docker", "exec", "-i", "pm-evolution-api",
                   "node", "--input-type=module", "-e", source.read()]
    fd, path = tempfile.mkstemp(suffix=extension, dir=folder)
    complete = False
    try:
        with os.fdopen(fd, "wb") as output:
            result = subprocess.run(command, input=json.dumps(metadata).encode(), stdout=output,
                                    stderr=subprocess.DEVNULL, timeout=240)
        complete = result.returncode == 0 and os.path.getsize(path) == size
        if not complete:
            raise PMError("Could not verify the large WhatsApp video. Resend it or use New Post in the Mac app.")
        return path
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PMError("Could not download the large WhatsApp video. Resend it or use New Post in the Mac app.") from exc
    finally:
        if not complete:
            os.unlink(path)


def download(env, instance, row, folder):
    size = media_size(row)
    limit = media_limit(env)
    if row.get("type") == "videoMessage":
        if size is not None and limit < size <= STREAM_VIDEO_LIMIT:
            return stream_video(row, folder, size)
        if size is not None and size > STREAM_VIDEO_LIMIT:
            limit = STREAM_VIDEO_LIMIT
    if size is None or size < 1 or size > limit:
        es = ui_language() == 'Spanish'
        raise PMError(("Este archivo supera el límite de WhatsApp de %d MB o no informa un tamaño válido. Usa Nueva publicación en la app para Mac para archivos grandes." if es else
                       "This file exceeds the WhatsApp intake limit of %d MB or has no valid size. Use New Post in the Mac app for larger files.") % (limit // (1024 * 1024)))
    status, data = evo_call(env, "POST", "/chat/getBase64FromMediaMessage/" + instance,
                            {"message": {"key": {"id": row["key"]["id"]}}, "convertToMp4": False}, timeout=300)
    if status >= 400 or not isinstance(data, dict) or not data.get("base64"):
        raise PMError("Couldn't download that file from WhatsApp (HTTP %s)" % status)
    encoded = data['base64']
    if not isinstance(encoded, str) or len(encoded) > ((limit + 2) // 3) * 4 + 4:
        raise PMError("WhatsApp media response exceeds the intake limit. Use the Mac app.")
    mime = (data.get("mimetype") or "").split(";")[0].strip()
    path = os.path.join(folder, "%s%s" % (row["key"]["id"], EXTENSIONS.get(mime, ".bin")))
    with open(path, "wb") as fh:
        fh.write(base64.b64decode(encoded))
    return path


def transcribe(env, path):
    """Voice note → text, on this Mac (whisper.cpp; language detected)."""
    model = env.get("PM_WHISPER_MODEL") or os.path.join(pmlib.ROOT, "data", "whisper", "ggml-small.bin")
    whisper = shutil.which("whisper-cli") or "/opt/homebrew/bin/whisper-cli"
    if not os.path.isfile(model) or not os.path.exists(whisper):
        raise PMError("Voice notes need whisper.cpp and data/whisper/ggml-small.bin (./scripts/get-whisper-model.sh)")
    wav = os.path.splitext(path)[0] + ".wav"
    pmlib.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav])
    proc = subprocess.run([whisper, "-m", model, "-f", wav, "-l", "auto", "-nt", "-np", "--prompt", VOCABULARY],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
    if proc.returncode != 0:
        raise PMError("Transcription failed: " + proc.stderr.strip()[-300:])
    return " ".join(line.strip() for line in proc.stdout.splitlines() if line.strip())


def clean_caption(raw_text):
    """Return caption text without Postiz's HTML formatting."""
    text = re.sub(r"</p>\s*<p>", "\n\n", raw_text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def save_confirmation(instruction, media_paths, heard, result, lang):
    request_id = os.urandom(6).hex()
    folder = os.path.join(CONFIRM_DIR, request_id)
    os.makedirs(folder, exist_ok=True)
    staged = []
    record = os.path.join(CONFIRM_DIR, request_id + ".json")
    temporary = record + ".tmp"
    try:
        for index, path in enumerate(media_paths):
            target = os.path.join(folder, "%02d-%s" % (index, os.path.basename(path)))
            shutil.move(path, target)
            staged.append(target)
        with open(temporary, "w", encoding="utf-8") as fh:
            json.dump({"id": request_id, "instruction": instruction, "media": staged,
                       "heard": heard, "lang": lang, "result": result}, fh, ensure_ascii=False, indent=1)
        os.replace(temporary, record)
    except OSError:
        shutil.rmtree(folder, ignore_errors=True)
        if os.path.exists(temporary):
            os.remove(temporary)
        raise
    return request_id


def load_confirmation(request_id=None):
    paths = []
    if request_id:
        paths = [os.path.join(CONFIRM_DIR, request_id + ".json")]
    elif os.path.isdir(CONFIRM_DIR):
        paths = sorted(os.path.join(CONFIRM_DIR, name) for name in os.listdir(CONFIRM_DIR)
                       if name.endswith(".json"))
    for path in reversed(paths):
        try:
            with open(path, encoding="utf-8") as fh:
                return path, json.load(fh)
        except (OSError, ValueError):
            continue
    return None, None


def confirmation_ref(request_id):
    """Return a short, newest-first number for a confirmation."""
    paths = sorted((os.path.join(CONFIRM_DIR, name) for name in os.listdir(CONFIRM_DIR)
                    if name.endswith(".json")),
                   key=lambda path: os.path.getmtime(path), reverse=True) if os.path.isdir(CONFIRM_DIR) else []
    for index, path in enumerate(paths, 1):
        if os.path.splitext(os.path.basename(path))[0] == request_id:
            return str(index)
    return request_id


def resolve_confirmation_ref(reference):
    """Resolve an internal ID, newest-first number, or latest alias."""
    if not reference or reference.lower() in ("latest", "último"):
        return load_confirmation()
    if re.fullmatch(r"[a-f0-9]{12}", reference, re.IGNORECASE):
        return load_confirmation(reference)
    if reference.isdigit() and os.path.isdir(CONFIRM_DIR):
        paths = sorted((os.path.join(CONFIRM_DIR, name) for name in os.listdir(CONFIRM_DIR)
                        if name.endswith(".json")),
                       key=lambda path: os.path.getmtime(path), reverse=True)
        index = int(reference) - 1
        if 0 <= index < len(paths):
            try:
                with open(paths[index], encoding="utf-8") as fh:
                    return paths[index], json.load(fh)
            except (OSError, ValueError):
                return None, None
    return None, None


def remove_confirmation(path):
    try:
        shutil.rmtree(os.path.splitext(path)[0], ignore_errors=True)
        os.remove(path)
    except OSError:
        pass


def reject_confirmation(request_id):
    path, _ = resolve_confirmation_ref(request_id)
    if not path:
        return False
    remove_confirmation(path)
    return True


def send_plan_approval(env, request_id):
    path, confirmation = resolve_confirmation_ref(request_id)
    if not path or not confirmation:
        raise PMError("No pending plan with ID " + request_id)
    instance, _, number, _ = own_identity(env)
    command = approval_command(request_id, confirmation.get("lang", "Spanish"))
    status, _ = evo_call(env, "POST", "/message/sendText/" + instance,
                         {"number": number, "text": command})
    if status >= 400:
        raise PMError("Approval message failed (HTTP %s)" % status)


def ui_language():
    try:
        with open(os.path.join(pmlib.RUN_DIR, "ui-language"), encoding="utf-8") as fh:
            return "Spanish" if fh.read().strip().lower() in ("es", "spanish", "español") else "English"
    except OSError:
        return "English"


def summary(result, lang, heard=None, has_caption=False, confirmation_id=None):
    es = ui_language() == "Spanish"
    names = plan_post.NAMES
    lines = [REPLY_MARK]
    if heard:
        lines.append(("🎙️ Entendí: “%s”" if es else "🎙️ I heard: “%s”") % heard)
    targets = []
    placements = {"feed": ("post", "publicación"), "story": ("story", "historia"),
                  "status": ("Status", "Estado"), "both": ("post + story", "publicación + historia")}
    for target in result.get("targets", []):
        network = target["network"]
        name = names[network]
        if network == "youtube" and result.get("short"):
            name += " (Short)"
        if target.get("placement") in placements:
            name += " · " + placements[target["placement"]][es]
        if target.get("cover_second") is not None:
            seconds = f'{target["cover_second"]:g}'
            name += (" · portada en el segundo " + seconds.replace(".", ",") if es
                     else " · cover at " + seconds + " s")
        elif target.get("cover") == "image":
            name += " · imagen de portada" if es else " · cover image"
        targets.append(name)
    head = (("📝 Verificación para %s: %s" if es else "📝 Verify for %s: %s") if confirmation_id else
            (("✅ Borradores para %s: %s" if es else "✅ Drafts for %s: %s") if result["drafts"] else
             ("📝 Plan para %s: %s" if es else "📝 Plan for %s: %s")))
    when = result["when_local"]
    if es:
        when = " ".join(ES_DATES.get(part, part.lower() if part.isalpha() else part) for part in when.split())
    lines.append(head % (when, ", ".join(targets)))
    if has_caption:
        lines += ["", ("El caption para todas las redes sociales aparece en el siguiente mensaje." if es
                        else "Caption follows in the next message:")]
    if result.get("youtube_title"):
        title = result["youtube_title"]
        count = len(title.encode("utf-16-le")) // 2
        label = "Título de YouTube" if es else "YouTube title"
        lines += ["", f"{label} ({count}/100)", title]
    if result.get("threads_caption"):
        lines += ["", ("Texto para Threads:" if es else "Threads caption:"),
                  clean_caption(result["threads_caption"])]
    lines += ["· " + ("supuse: " if es else "assumed: ") + n for n in result["notes"]]
    lines += ["⚠ " + w for w in result["warnings"]]
    if result.get("review_url"):
        lines += ["", ("Nada se publica sin tu aprobación: revísalos en %s" if es else
                       "Nothing is published without your approval: review them at %s") % result["review_url"]]
    if confirmation_id:
        if es:
            lines += ["", f"Responde `aprobar plan {confirmation_id}` para continuar.",
                      f"Para cambiarlo, responde `rechazar plan {confirmation_id}` y vuelve a enviar tu pedido "
                      "con los archivos. Puedes indicar «solo publicaciones», «solo historias» o "
                      "«publicaciones e historias», y «portada en el segundo 12,5» o «imagen de portada» "
                      "si adjuntas un video y una sola foto."]
        else:
            lines += ["", f"Reply `approve plan {confirmation_id}` to continue.",
                      f"To change it, reply `reject plan {confirmation_id}` and resend your request with its files. "
                      "You can say ‘only posts’, ‘only stories’, or ‘posts and stories’, and ‘cover at 12.5 s’ "
                      "or ‘cover image’ if you attach one video and one photo."]
    return "\n".join(lines)


def approval_command(request_id, lang):
    return ("aprobar plan " if lang == "Spanish" else "approve plan ") + confirmation_ref(request_id)


def hint(error, lang, heard=None):
    es = lang == "Spanish"
    lines = [REPLY_MARK]
    if heard:
        lines.append(("🎙️ Entendí: “%s”" if es else "🎙️ I heard: “%s”") % heard)
    if error.startswith("Say when"):
        lines.append("¿Cuándo? Por ejemplo: “Instagram y TikTok el viernes a las 6 de la tarde; idea: …”" if es
                     else "When? For example: “Instagram and TikTok on Friday at 6pm, about: …”")
    else:
        lines.append("✖ " + error)
    return "\n".join(lines)


def reply(env, instance, number, own_number, text, state, dry_run, timeout=120):
    if number != own_number:  # the door only ever talks to your own chat
        raise PMError("refusing to message anyone but your own chat")
    if dry_run:
        log("would reply:\n" + text)
        return
    status, data = evo_call(env, "POST", "/message/sendText/" + instance, {"number": number, "text": text}, timeout=timeout)
    if status >= 400:
        raise PMError("Reply failed (HTTP %s)" % status)
    sent_id = ((data or {}).get("key") or {}).get("id") if isinstance(data, dict) else None
    if sent_id:
        state["sent"] = (state.get("sent", []) + [sent_id])[-200:]


def act(env, ident, row, instruction, media_rows, folder, state, dry_run, heard=None):
    name, _, number, _ = ident
    tz = plan_post.ZoneInfo(env.get("PM_TIMEZONE", "America/Guayaquil")) if plan_post.ZoneInfo \
        else timezone(timedelta(hours=-5))
    now = datetime.now(tz)
    command, _, _ = plan_post.split_instruction(instruction)
    networks, _ = plan_post.parse_networks(command)
    lang = plan_post.detect_lang(instruction, env.get("CAPTION_LANGUAGE", "Spanish"))
    when, _ = plan_post.parse_when(command, now)
    normalized_instruction = approval_text(instruction)
    approval = APPROVE_WHATSAPP.fullmatch(normalized_instruction)
    if approval:
        item_id = None if dry_run else whatsapp_pending.approve(approval.group(1))
        if ui_language() == "Spanish":
            text = ("✅ Estado de WhatsApp aprobado. Se enviará a la hora programada o en cuanto se pueda si ya pasó."
                    if item_id else "No hay un Estado de WhatsApp pendiente para aprobar.")
        else:
            text = ("✅ WhatsApp Status approved. It will send at the scheduled time or as soon as possible if overdue."
                    if item_id else "There is no pending WhatsApp Status to approve.")
        reply(env, name, number, number, text, state, dry_run)
        if item_id and not dry_run:
            whatsapp_pending.process(env)
        return True
    plan_approval = APPROVE_PLAN.fullmatch(normalized_instruction)
    if plan_approval:
        confirmation_path, confirmation = resolve_confirmation_ref(plan_approval.group(1))
        if not confirmation:
            reply(env, name, number, number, "No hay una publicación pendiente de confirmación.", state, dry_run)
            return True
        try:
            saved_when = (confirmation.get("result") or {}).get("when_utc")
            scheduled = datetime.fromisoformat(saved_when.replace("Z", "+00:00")) if saved_when else None
            if scheduled and scheduled < now + timedelta(minutes=5):
                remove_confirmation(confirmation_path)
                raise PMError("Ese plan ya venció. Envía una hora nueva." if ui_language() == "Spanish"
                              else "That plan has expired. Send a new time.")
            p = plan_post.plan(env, confirmation["instruction"], confirmation.get("media") or [],
                               confirmation.get("lang"), now, ui_lang=ui_language())
            if scheduled:
                p["when"] = scheduled.astimezone(tz)
            override = (confirmation.get("caption_override") or "").strip()
            saved_result = confirmation.get("result") or {}
            if override:  # edited in the PostForge app's WhatsApp window: use it as the exact caption
                p["exact"] = override
            elif saved_result.get("caption"):
                p["reviewed_caption"] = saved_result["caption"]
                p["reviewed_threads_caption"] = saved_result.get("threads_caption")
            with pmlib.Job("draft", "WhatsApp approval: " + confirmation["instruction"][:50]):
                result = plan_post.run(env, p, dry_run)
            caption = clean_caption(result.get("caption") or "")
            result["notes"] = [note for note in result["notes"] if note not in ("WhatsApp Status waits for approval", "El Estado de WhatsApp espera aprobación.")]
            if any(target.get("network") == "whatsapp" for target in result["targets"]):
                result["notes"].append("Estado de WhatsApp aprobado para la hora programada."
                                       if ui_language() == "Spanish" else
                                       "WhatsApp Status approved for the scheduled time.")
            text = summary(result, p["lang"], confirmation.get("heard"), bool(caption))
            if not dry_run:
                pending_id = result.get("whatsapp_pending_id")
                if pending_id:
                    whatsapp_pending.approve(pending_id)
                    whatsapp_pending.process(env)
                remove_confirmation(confirmation_path)
            reply(env, name, number, number, text, state, dry_run)
            if caption:
                reply(env, name, number, number, caption, state, dry_run)
            return True
        except PMError as exc:
            reply(env, name, number, number, hint(str(exc), confirmation.get("lang", lang),
                                                  confirmation.get("heard")), state, dry_run)
            return True
    rejection = REJECT_PLAN.fullmatch(normalized_instruction)
    if rejection:
        removed = reject_confirmation(rejection.group(1))
        text = ("✅ Plan rechazado." if ui_language() == "Spanish" else "✅ Plan rejected.") if removed else (
            "No hay un plan pendiente con esa referencia." if ui_language() == "Spanish"
            else "There is no pending plan with that reference.")
        reply(env, name, number, number, text, state, dry_run)
        return True
    if not networks or not (when or POST_VERB.search(plan_post.plain(command))):
        log("not a post request (needs a network plus a time or a verb like 'publica'): ignored")
        return False
    caption = ""
    confirmation_id = None
    try:
        p = plan_post.plan(env, instruction, [], None, now, ui_lang=ui_language())
        with pmlib.Job("draft", "WhatsApp: " + instruction[:50]):
            p["media"] = [download(env, name, m, folder) for m in media_rows]
            result = plan_post.run(env, p, True)
        caption = clean_caption(result.get("caption") or "")
        confirmation_id = None if dry_run else save_confirmation(instruction, p["media"], heard, result, p["lang"])
        confirmation_ref_id = confirmation_ref(confirmation_id) if confirmation_id else None
        text = summary(result, p["lang"], heard, bool(caption), confirmation_ref_id)
        log("awaiting confirmation %s for %s → %s" %
            (confirmation_id or "dry-run", ", ".join(plan_post.NAMES[n] for n in p["networks"]), result["when_local"]))
    except PMError as exc:
        text = hint(str(exc), lang, heard)
        log("could not plan: %s" % exc)
    reply(env, name, number, number, text, state, dry_run)
    if confirmation_id:
        reply(env, name, number, number, approval_command(confirmation_id, p["lang"]), state, dry_run)
    if caption:
        reply(env, name, number, number, caption, state, dry_run)
    return True


def one_pass(env, state, dry_run):
    ident = own_identity(env)
    name, instance_id, number, jids = ident
    now_ts = time.time()
    whatsapp_pending.process(env, dry_run)
    rows = messages_since(env, instance_id, jids, state["since"] - MEDIA_WINDOW)
    done = set(state.get("done", []))
    sent = set(state.get("sent", []))
    fresh = [r for r in rows if r["id"] not in done and r["key"].get("id") not in sent]
    finished = []
    folder = tempfile.mkdtemp(prefix="intake-", dir=pmlib.whatsapp_scratch())
    try:
        for row in fresh:
            if row["ts"] > now_ts - SETTLE:
                continue  # wait a pass for the rest of an album
            text = text_of(row).strip()
            if text.startswith(REPLY_MARK):
                finished.append(row["id"])
                continue
            heard = None
            if row["type"] == "audioMessage":
                try:
                    heard = transcribe(env, download(env, name, row, folder))
                except PMError as exc:
                    log("voice note not transcribed: %s" % exc)
                text = heard or ""
            elif row["type"] in MEDIA_TYPES and not text:
                continue  # a photo or video waiting for its instruction
            elif row["type"] not in TEXT_TYPES + MEDIA_TYPES:
                finished.append(row["id"])
                continue
            media = [m for m in fresh if m["type"] in MEDIA_TYPES and m["id"] not in finished
                     and row["ts"] - MEDIA_WINDOW <= m["ts"] <= row["ts"] + SETTLE]
            if text and act(env, ident, row, text, media, folder, state, dry_run, heard):
                finished += [m["id"] for m in media]
            finished.append(row["id"])
        finished += [r["id"] for r in fresh if r["type"] in MEDIA_TYPES and r["ts"] < now_ts - MEDIA_WINDOW]
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if not dry_run:
        state["done"] = (state.get("done", []) + [i for i in finished if i not in done])[-500:]
        state["since"] = max(state["since"], now_ts - SETTLE - 1)
        save_state(state)


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"since": time.time() - 60, "done": [], "sent": []}  # first run: from a minute ago


def save_state(state):
    os.makedirs(pmlib.RUN_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    os.replace(tmp, STATE_FILE)


def main():
    global stopping
    parser = argparse.ArgumentParser(prog="wa-inbox.sh", description=__doc__.split("\n")[0],
                                     epilog=__doc__.split("\n", 1)[1], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--idle-notice", action="store_true", help="send an idle notice to your own chat")
    parser.add_argument("--once", action="store_true", help="one pass, then exit")
    parser.add_argument("--dry-run", action="store_true", help="no drafts, no replies, nothing marked done")
    parser.add_argument("--reject-plan", metavar="ID", help="reject a saved confirmation plan")
    parser.add_argument("--send-status-approval", metavar="ID", help="send a specific Status approval to your own chat")
    parser.add_argument("--send-plan-approval", metavar="ID", help="send a plan approval to your own WhatsApp chat")
    args = parser.parse_args()
    if args.idle_notice:
        env = pmlib.load_env()
        instance, _, number, _ = own_identity(env)
        message = ("PostForge está por entrar en modo inactivo. La recepción se pausa hasta que lo enciendas en el Mac."
                   if ui_language() == "Spanish" else
                   "PostForge is about to go idle. Intake will pause until you turn it on at the Mac.")
        reply(env, instance, number, number, REPLY_MARK + "\n" + message, {}, False, timeout=5)
        return 0
    if args.send_status_approval:
        reference = args.send_status_approval
        if not re.fullmatch(r"[a-f0-9]{12}", reference):
            raise PMError("Invalid WhatsApp Status reference")
        env = pmlib.load_env()
        instance, _, number, _ = own_identity(env)
        command = ("aprobar whatsapp " if ui_language() == "Spanish" else "approve whatsapp ") + reference
        reply(env, instance, number, number, command, {}, args.dry_run)
        return 0
    if args.reject_plan or args.send_plan_approval:
        env = pmlib.load_env()
        if args.reject_plan:
            if not reject_confirmation(args.reject_plan):
                raise PMError("No pending plan with ID " + args.reject_plan)
            print("Rejected plan " + args.reject_plan)
        else:
            send_plan_approval(env, args.send_plan_approval)
            print("Sent approval for plan " + args.send_plan_approval)
        return 0
    os.makedirs(pmlib.RUN_DIR, exist_ok=True)
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise PMError("another WhatsApp door worker is already running")
    signal.signal(signal.SIGTERM, lambda *_: globals().__setitem__("stopping", True))
    env = pmlib.load_env()
    state = load_state()
    log("listening to your own chat (dry run)" if args.dry_run else "listening to your own chat")
    if not args.dry_run:
        interrupted = whatsapp_pending.recover_interrupted()
        if interrupted:
            log("%d interrupted WhatsApp Status send(s) held for review" % interrupted)
    next_cleanup = 0
    while True:
        try:
            one_pass(env, state, args.dry_run)
        except PMError as exc:
            log("pass skipped: %s" % exc)
        except Exception as exc:  # keep listening; the log shows what went wrong
            log("pass failed: %s: %s" % (type(exc).__name__, exc))
        if args.once or stopping:
            return 0
        if not args.dry_run and time.monotonic() >= next_cleanup:
            next_cleanup = time.monotonic() + 86400
            try:
                subprocess.run([sys.executable, os.path.join(pmlib.ROOT, "scripts", "retention.py"),
                                "--whatsapp-cache", "--apply", "--json"], timeout=30,
                               stdout=subprocess.DEVNULL, check=True)
            except (OSError, subprocess.SubprocessError):
                log("WhatsApp cache cleanup could not finish")
        for _ in range(POLL_SECONDS):
            if stopping:
                return 0
            time.sleep(1)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PMError as exc:
        print("✖ " + str(exc), file=sys.stderr)
        sys.exit(1)
