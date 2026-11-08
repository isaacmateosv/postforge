#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""WhatsApp Status (Stories) broadcaster via Evolution API.

Scope guardrail: posts ONLY to status@broadcast. It never sends DMs or group messages.

Why it is built this way (Evolution v2.3.7 + Baileys 7.0.0-rc.9, see docs/reconnect/whatsapp.md):
  * statusJidList entries MUST be full JIDs (<digits>@s.whatsapp.net). Bare digits decode
    to an empty JID inside Baileys: no recipient devices, ~60 s stall per batch, and the
    status reaches nobody. That was the Oct-25 "2 hour hang".
  * Evolution splits the list into batches of 10 and Baileys serializes them behind one
    per-account mutex, so one request costs (#recipients / 10) sequential relays and the
    HTTP call only returns at the end. If the client gives up, Evolution keeps sending.
  * allContacts:true is NOT on-demand: it expands to every contact with a pushName.
  * Stock Evolution drops WhatsApp's receipts for statuses (it only uses
    message-receipt.update to mark incoming chats read), so every sent status stays PENDING.
    patches/evolution/status-receipts.js, applied when the container boots, stores them in
    evolution."MessageUpdate"; --history counts them and --viewers lists them.
  * Baileys delivers a status only to the devices of the JIDs in statusJidList (minus the
    sending device), so the account’s own number is always added, uncounted. Without it the
    phone never gets the post: no "My status" entry, no viewer list, no delete from the phone.
"""
import argparse
import json
import math
import os
import re
import shutil
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmlib  # noqa: E402
from pmlib import PMError, info, warn  # noqa: E402
from whatsapp_pending import STATUS_PART_SECONDS  # noqa: E402

VIP_FILE = os.path.join(pmlib.ROOT, "config", "whatsapp", "vip-list.txt")
EVO_BATCH = 10
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".3gp"}
MAX_VIDEO_SECONDS = STATUS_PART_SECONDS
MAX_STATUS_VIDEO_BYTES = 6 * 1024 * 1024
MAX_STATUS_VIDEO_SIDE = 1280
MAX_SIDE = 1920
LOG_FILE = "whatsapp-status.jsonl"
STATUS_KINDS = {"conversation": "text", "extendedTextMessage": "text",
                "imageMessage": "image", "videoMessage": "video"}
# 2026-10-30 18:50 EC: the receipts patch went live. Older statuses have no receipt data.
RECEIPTS_SINCE = 1793404200
STATUS_TEXT_SQL = ("replace(left(coalesce(m.message->'extendedTextMessage'->>'text', m.message->>'conversation', "
                   "m.message->'imageMessage'->>'caption', m.message->'videoMessage'->>'caption', ''), 60), "
                   "E'\\n', ' ')")


def evo(env, path):
    return "http://localhost:8080" + path


def evo_headers(env):
    key = env.get("AUTHENTICATION_API_KEY")
    if not key:
        raise PMError("AUTHENTICATION_API_KEY is missing from .env")
    return {"apikey": key}


# ----------------------------------------------------------------------------
# Audience
# ----------------------------------------------------------------------------

def to_jid(raw, default_cc):
    """Normalize a phone number / JID to <digits>@s.whatsapp.net, or None if unusable."""
    raw = raw.strip()
    if not raw:
        return None
    if "@" in raw:
        user, server = raw.split("@", 1)
        if server != "s.whatsapp.net":
            return None
        raw = user.split(":")[0]
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0") and default_cc:
        digits = default_cc + digits.lstrip("0")
    if len(digits) < 8 or len(digits) > 15:
        return None
    return digits + "@s.whatsapp.net"


def read_number_file(path, default_cc):
    if not os.path.exists(path):
        raise PMError("Audience file not found: " + path)
    jids, bad = [], []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            jid = to_jid(line, default_cc)
            (jids if jid else bad).append(jid or line)
    if bad:
        warn("Skipped %d unusable entries in %s: %s" % (len(bad), path, ", ".join(bad[:5])))
    return jids


def owner_jid(env, instance):
    status, data = pmlib.http("GET", evo(env, "/instance/fetchInstances?instanceName=" + instance),
                              evo_headers(env), timeout=30)
    if status == 200 and isinstance(data, list) and data:
        return data[0].get("ownerJid") or ""
    return ""


def all_contacts(env, instance, default_cc):
    status, data = pmlib.http("POST", evo(env, "/chat/findContacts/" + instance),
                              evo_headers(env), {}, timeout=120)
    if status >= 400 or not isinstance(data, list):
        raise PMError("findContacts failed (HTTP %s): %s" % (status, str(data)[:300]))
    jids = []
    for contact in data:
        jid = contact.get("remoteJid", "")
        if contact.get("isGroup") or not jid.endswith("@s.whatsapp.net"):
            continue  # skip groups, @lid duplicates, newsletters
        norm = to_jid(jid, default_cc)
        if norm:
            jids.append(norm)
    return jids


def resolve_audience(args, env, instance):
    default_cc = env.get("WA_DEFAULT_COUNTRY_CODE", "593")
    if args.to_file:
        label, jids = "file:" + args.to_file, read_number_file(args.to_file, default_cc)
    elif args.to == "test":
        raw = env.get("WA_TEST_RECIPIENTS", "")
        label, jids = "test", [j for j in (to_jid(x, default_cc) for x in raw.split(",")) if j]
    elif args.to == "vip":
        label, jids = "vip", read_number_file(VIP_FILE, default_cc)
    elif args.to == "all":
        label, jids = "all", all_contacts(env, instance, default_cc)
    else:
        label = "explicit"
        jids = [j for j in (to_jid(x, default_cc) for x in args.to.split(",")) if j]

    own = owner_jid(env, instance).split(":")[0].split("@")[0]
    unique = []
    seen = set()
    for jid in jids:
        if jid in seen or (own and jid.startswith(own + "@")):
            continue
        seen.add(jid)
        unique.append(jid)
    if not unique:
        raise PMError("Audience '%s' resolved to zero valid recipients." % label)
    return label, unique, (own + "@s.whatsapp.net" if own else None)


# ----------------------------------------------------------------------------
# Media
# ----------------------------------------------------------------------------

def prepare_image(src, tmp):
    """Return a JPEG (≤ MAX_SIDE px) suitable for a WhatsApp status."""
    ext = os.path.splitext(src)[1].lower()
    if ext not in IMAGE_EXT:
        raise PMError("Unsupported image type '%s' (use JPG/PNG/HEIC/WEBP)." % ext)
    return pmlib.to_jpeg(src, tmp, MAX_SIDE)


def prepare_video(src, tmp):
    """Return an H.264/AAC MP4 ≤ 60 s that WhatsApp status accepts (transcode only if needed)."""
    ext = os.path.splitext(src)[1].lower()
    if ext not in VIDEO_EXT:
        raise PMError("Unsupported video type '%s' (use MP4/MOV/WEBM)." % ext)
    duration = pmlib.ffprobe(src)[0] if pmlib.which("ffprobe") else 0
    if duration > MAX_VIDEO_SECONDS:
        warn("Video is %.0fs; WhatsApp statuses allow %ds, trimming to the first %ds."
             % (duration, MAX_VIDEO_SECONDS, MAX_VIDEO_SECONDS))
    return pmlib.to_mp4(src, tmp, MAX_VIDEO_SECONDS, MAX_STATUS_VIDEO_SIDE, max_bytes=MAX_STATUS_VIDEO_BYTES)


def prepare_media(kind, src):
    """Return (content, staged_path): the value Evolution should load (container path or
    URL) and the host file this call created under data/postiz-uploads (or None)."""
    if src.startswith(("http://", "https://")):
        return src, None  # Baileys downloads it from inside the container
    src = os.path.expanduser(src)
    if not os.path.isfile(src):
        raise PMError("Media file not found: " + src)
    tmp = tempfile.mkdtemp(prefix="pm-status-")
    try:
        ready = prepare_image(src, tmp) if kind == "image" else prepare_video(src, tmp)
        rel = pmlib.stage_into_uploads(ready, "whatsapp")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    staged = os.path.join(pmlib.UPLOADS_DIR, rel)
    created = None if os.path.abspath(staged) == os.path.abspath(src) else staged
    container_path = "/media/" + rel.replace(os.sep, "/")
    probe = pmlib.run(["docker", "exec", "pm-evolution-api", "sh", "-c",
                       "test -r '%s' && echo ok" % container_path], check=False)
    if probe != "ok":
        raise PMError("Evolution cannot read %s (is ./data/postiz-uploads mounted at /media? "
                      "run ./publish-machine.sh start)" % container_path)
    return container_path, created


# ----------------------------------------------------------------------------
# Sending
# ----------------------------------------------------------------------------

def build_payload(args, content, jids):
    if args.image or args.video:
        payload = {"type": "image" if args.image else "video", "content": content, "statusJidList": jids}
        if args.text:
            payload["caption"] = args.text
        return payload
    return {"type": "text", "content": args.text,
            "backgroundColor": args.bg, "font": args.font, "statusJidList": jids}


def post_status(env, instance, payload, timeout):
    """POST /message/sendStatus with a heartbeat. Returns (outcome, http_status, message_id, detail)."""
    result = {}

    def worker():
        try:
            result["resp"] = pmlib.http("POST", evo(env, "/message/sendStatus/" + instance),
                                        evo_headers(env), payload, timeout)
        except Exception as exc:  # socket timeouts surface here
            result["err"] = exc

    start = time.time()
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    while thread.is_alive():
        thread.join(30)
        if thread.is_alive():
            info("      … Evolution still relaying (%s elapsed)" % pmlib.elapsed(start))
    if "err" in result:
        exc = result["err"]
        if "timed out" in str(exc).lower():
            return "client_timeout", None, None, str(exc)
        return "error", None, None, str(exc)
    status, data = result["resp"]
    if status >= 400 or not isinstance(data, dict):
        detail = data.get("response", data) if isinstance(data, dict) else data
        return "error", status, None, str(detail)[:500]
    return "sent", status, (data.get("key") or {}).get("id"), ""


def chunked(items, size):
    if size <= 0 or size >= len(items):
        return [items]
    return [items[i:i + size] for i in range(0, len(items), size)]


def logged_sends():
    """Map message id -> this script's log record (recipients, seconds)."""
    path = os.path.join(pmlib.LOGS_DIR, LOG_FILE)
    records = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("message_id"):
                    records[rec["message_id"]] = rec
    return records


def show_history(env, limit):
    # received/viewed: distinct recipients with any receipt / a read receipt, the primary phone excluded
    receipts = ("(SELECT count(DISTINCT u.participant) FROM evolution.\"MessageUpdate\" u "
                "WHERE u.\"messageId\" = m.id AND u.participant IS DISTINCT FROM i.\"ownerJid\"%s)")
    rows = pmlib.psql(
        "SELECT to_char(to_timestamp(m.\"messageTimestamp\") AT TIME ZONE 'America/Guayaquil', "
        "'YYYY-MM-DD HH24:MI'), m.key->>'id', m.\"messageType\", m.\"messageTimestamp\", "
        + receipts % "" + ", " + receipts % " AND u.status = 'READ'" + ", " + STATUS_TEXT_SQL + " "
        "FROM evolution.\"Message\" m JOIN evolution.\"Instance\" i ON i.id = m.\"instanceId\" "
        "WHERE m.key->>'remoteJid' = 'status@broadcast' AND (m.key->>'fromMe')::boolean "
        "ORDER BY m.\"messageTimestamp\" DESC LIMIT %d;" % limit, env)
    if not rows:
        info("No statuses recorded by Evolution yet.")
        return
    sends = logged_sends()
    row_fmt = "%-16s  %-22s  %-5s  %-10s  %-7s  %-8s  %-6s  %s"
    info(row_fmt % ("sent (EC time)", "message id", "kind", "recipients", "seconds", "received", "viewed", "text"))
    for row in rows:
        when, mid, mtype, stamp, received, viewed, text = (row + [""] * 7)[:7]  # psql strips an empty caption
        if int(stamp or 0) < RECEIPTS_SINCE:
            received = viewed = "n/a"
        rec = sends.get(mid, {})
        info(row_fmt % (when, mid, STATUS_KINDS.get(mtype, mtype), rec.get("recipients", "-"),
                        rec.get("seconds", "-"), received, viewed, text))
    info("\nreceived/viewed: people whose phone sent WhatsApp a receipt (the primary phone not counted).\n"
         "A view only shows if both phones have read receipts on (Settings > Privacy > Read receipts).\n"
         "n/a = sent before receipts were recorded. Who viewed: --viewers <message id>.\n"
         "recipients/seconds come from logs/%s ('-' = not sent by this script)." % LOG_FILE)


def show_viewers(env, message_id):
    if not re.match(r"^[A-Za-z0-9]{8,40}$", message_id):
        raise PMError("Not a message id: " + message_id)
    rows = pmlib.psql(
        "SELECT u.participant, coalesce(max(c.\"pushName\"), ''), "
        "bool_or(u.status = 'READ'), bool_or(u.participant = i.\"ownerJid\") "
        "FROM evolution.\"Message\" m JOIN evolution.\"Instance\" i ON i.id = m.\"instanceId\" "
        "JOIN evolution.\"MessageUpdate\" u ON u.\"messageId\" = m.id "
        "LEFT JOIN evolution.\"Contact\" c ON c.\"instanceId\" = m.\"instanceId\" AND c.\"remoteJid\" = u.participant "
        "WHERE m.key->>'id' = '%s' AND m.key->>'remoteJid' = 'status@broadcast' "
        "GROUP BY u.participant, i.\"ownerJid\" ORDER BY 3 DESC, 2;" % message_id, env)
    if not rows:
        info("No receipts recorded for %s yet. Receipts arrive when a recipient's phone gets or opens\n"
             "the status; statuses sent before %s have none." % (message_id, "2026-10-30 18:50"))
        return
    viewed = 0
    for participant, name, read, own in ((r + [""] * 4)[:4] for r in rows):
        number = participant.split("@")[0]
        label = "viewed" if read == "t" else "received"
        viewed += read == "t" and own != "t"
        info("  %-8s  %-16s  %s%s" % (label, number, name, "  (primary phone)" if own == "t" else ""))
    info("%d viewed. A view only shows if both phones have read receipts on." % viewed)


def main():
    parser = argparse.ArgumentParser(
        prog="broadcast-story.sh",
        description="Post a WhatsApp Status (text, image or video) to a chosen audience.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "audiences (all except test need --yes):\n"
            "  --to test   WA_TEST_RECIPIENTS from .env (default)\n"
            "  --to vip    config/whatsapp/vip-list.txt (one number per line)\n"
            "  --to all    every saved WhatsApp contact\n"
            "  --to 593...,593...  explicit numbers   |   --to-file PATH\n\n"
            "examples:\n"
            "  ./scripts/broadcast-story.sh --dry-run --to all\n"
            "  ./scripts/broadcast-story.sh \"¡Rollos de canela listos para tu pedido! 🥐\"\n"
            "  ./scripts/broadcast-story.sh --image data/postiz-uploads/rolls.jpg \"Fresh today\"\n"
            "  ./scripts/broadcast-story.sh --video ~/Movies/oven.mov --to vip --yes\n"
            "  ./scripts/broadcast-story.sh --to all --yes \"Pedidos abiertos para el fin de semana 🥐\"\n"
            "  ./scripts/broadcast-story.sh --history\n"
            "  ./scripts/broadcast-story.sh --viewers 3EB08BF293DA1EECFB3EE2\n"
        ),
    )
    parser.add_argument("text", nargs="?", help="status text, or the caption for image/video")
    parser.add_argument("--to", default=None, help="test | vip | all | comma-separated numbers")
    parser.add_argument("--to-file", help="file with one number per line")
    media = parser.add_mutually_exclusive_group()
    media.add_argument("--image", help="image path or http(s) URL")
    media.add_argument("--video", help="video path or http(s) URL")
    parser.add_argument("--bg", default="#128C7E", help="text status background color (default #128C7E)")
    parser.add_argument("--font", type=int, default=1, choices=range(1, 6), help="text status font 1-5")
    parser.add_argument("--chunk-size", type=int, default=0,
                        help="split into N-recipient requests (each becomes its OWN status post); "
                             "default 0 = one request, one status")
    parser.add_argument("--timeout", type=int, default=0, help="seconds to wait per request (default: auto)")
    parser.add_argument("--dry-run", action="store_true", help="resolve audience and media; send nothing")
    parser.add_argument("--yes", action="store_true", help="confirm sending to any audience except test")
    parser.add_argument("--history", nargs="?", const=15, type=int, metavar="N",
                        help="list the last N statuses recorded by Evolution, with receipts")
    parser.add_argument("--viewers", metavar="ID", help="who received / viewed the status with this message id")
    args = parser.parse_args()

    env = pmlib.load_env()
    args.to = args.to or env.get("WA_STATUS_AUDIENCE", "all")
    instance = env.get("WA_INSTANCE", "status-engine")

    if args.history:
        show_history(env, args.history)
        return 0
    if args.viewers:
        show_viewers(env, args.viewers)
        return 0
    if not (args.text or args.image or args.video):
        raise PMError("Give the status text, or --image / --video. Nothing is sent without content you chose.")

    info("======================================================")
    info("  WHATSAPP STATUS BROADCAST")
    info("======================================================")

    status, state = pmlib.http("GET", evo(env, "/instance/connectionState/" + instance), evo_headers(env), timeout=15)
    conn = state.get("instance", {}).get("state") if isinstance(state, dict) else None
    if conn != "open":
        raise PMError("WhatsApp instance '%s' is not connected (state=%s). Start the stack / re-link the phone."
                      % (instance, conn or status))

    info("[1/3] Resolving audience...")
    label, jids, own_jid = resolve_audience(args, env, instance)
    own = [own_jid] if own_jid else []
    batches = math.ceil((len(jids) + len(own)) / float(EVO_BATCH))
    info("      Audience '%s': %d recipients%s (%d Evolution relays of %d)."
         % (label, len(jids), " + the account’s own phone" if own else "", batches, EVO_BATCH))
    if not own:
        warn("Could not read the account’s own number: this status will not show in its My status list.")
    if label != "test" and not args.yes and not args.dry_run:
        raise PMError("Audience '%s' reaches %d real people. Get the exact content approved first, then "
                      "re-run with --yes (or use --dry-run)." % (label, len(jids)))

    info("[2/3] Preparing content...")
    content = staged = None
    if args.image or args.video:
        kind = "image" if args.image else "video"
        content, staged = prepare_media(kind, args.image or args.video)
        info("      %s ready: %s" % (kind.capitalize(), content))
    else:
        info("      Text status: %s" % args.text)

    groups = chunked(jids, args.chunk_size)
    if len(groups) > 1:
        warn("--chunk-size %d -> %d separate status posts (each recipient sees one; your own "
             "'My status' list will show %d entries)." % (args.chunk_size, len(groups), len(groups)))

    if args.dry_run:
        sample = build_payload(args, content, (own + groups[0])[:3])
        info("[3/3] DRY RUN - nothing sent. First request would be:")
        info("      POST /message/sendStatus/%s  (%d requests, %d recipients)" % (instance, len(groups), len(jids)))
        info("      %s ... (+%d more recipients)" % (str(sample)[:400], max(0, len(own) + len(groups[0]) - 3)))
        if staged:
            os.remove(staged)
            info("      (media validated inside Evolution; staged copy removed)")
        return 0

    info("[3/3] Sending...")
    failed = []
    # Marks the send as in progress: `stop` and the menu bar app warn before turning the machine off.
    with pmlib.Job("whatsapp-status", "%s: %s" % (label, (args.text or content or "")[:60])) as job:
        for idx, group in enumerate(groups, 1):
            payload = build_payload(args, content, own + group)
            timeout = args.timeout or (120 + 20 * math.ceil(len(payload["statusJidList"]) / float(EVO_BATCH)))
            start = time.time()
            if len(groups) > 1:
                info("      Request %d/%d: %d recipients" % (idx, len(groups), len(group)))
            outcome, http_status, msg_id, detail = post_status(env, instance, payload, timeout)
            took = round(time.time() - start, 1)
            pmlib.append_log(LOG_FILE, {
                "audience": label, "recipients": len(group), "request": "%d/%d" % (idx, len(groups)),
                "type": payload["type"], "text": (args.text or "")[:120],
                "media": content, "outcome": outcome, "http_status": http_status,
                "message_id": msg_id, "seconds": took, "detail": detail[:300],
            })
            if outcome == "sent":
                info("      ✔ Sent: id=%s (%d recipients, %ss). Who viewed it: --viewers %s"
                     % (msg_id, len(group), took, msg_id))
            elif outcome == "client_timeout":
                warn("Stopped waiting after %ss. Evolution keeps relaying in the background; check "
                     "./scripts/broadcast-story.sh --history in a few minutes." % took)
                failed.extend(group)
                job.linger = 20 * batches  # Evolution keeps relaying in the background
            else:
                warn("Request failed (HTTP %s): %s" % (http_status, detail))
                failed.extend(group)

    if failed:
        retry = os.path.join(pmlib.LOGS_DIR, "status-retry-%s.txt" % time.strftime("%Y%m%d-%H%M%S"))
        with open(retry, "w", encoding="utf-8") as fh:
            fh.write("\n".join(failed) + "\n")
        warn("%d recipients unconfirmed. Retry only them with: --to-file %s" % (len(failed), retry))
        return 1
    info("======================================================")
    info("  DONE. Results logged to logs/%s" % LOG_FILE)
    info("======================================================")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PMError as exc:
        print("✖ " + str(exc), file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        print("\n✖ Interrupted. If a request was in flight, Evolution may still finish it "
              "(check --history).", file=sys.stderr)
        sys.exit(130)
