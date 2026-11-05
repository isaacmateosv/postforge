#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Hands-free posting: your media plus one sentence become one Postiz DRAFT per network, scheduled at
the time you said. HITL: drafts only. You review, edit and approve them on the Postiz calendar.

    ./scripts/plan-post.sh --media guaguas.mp4 "Instagram y TikTok el viernes a las 6 de la tarde; idea: guaguas de higo solo hasta el domingo"
    ./scripts/plan-post.sh --media torta.jpg 'Facebook mañana 9am texto: "Nuestra torta de chocolate 🍫"'
    ./scripts/plan-post.sh --dry-run ...   show the plan, create nothing
    ./scripts/plan-post.sh --json ...      machine-readable result (menu bar app, WhatsApp door)

The networks and the time are read with rules, not AI, from the part before your idea or text:
- networks: Instagram/insta/IG, Facebook/FB, TikTok, YouTube/Shorts, "todas"/"all";
- days: hoy/mañana/pasado mañana, weekdays, "5 de noviembre", "5/11", "today", "tomorrow", "Nov 5";
- times: "18:00", "6pm", "6 de la tarde", "a las 6" (1-7 means pm), mediodía, "en la noche".
The caption comes from your idea ("idea:", "sobre", "about", "la idea es"), written by the local
model with the brand rules and the fixed order line. Your exact words ("texto:", "caption:", or in
quotes) are kept as written. Times are the bakery's (PM_TIMEZONE, default America/Guayaquil).
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmlib  # noqa: E402
from create_draft import NEEDS_MEDIA, ollama_caption  # noqa: E402
from pmlib import PMError, info  # noqa: E402
import whatsapp_pending  # noqa: E402

try:
    from zoneinfo import ZoneInfo
except ImportError:  # python < 3.9
    ZoneInfo = None

NETWORKS = {  # network: (words that name it, Postiz identifiers)
    "instagram": (("instagram", "insta", "ig", "reel", "reels"), ("instagram", "instagram-standalone")),
    "facebook": (("facebook", "fb", "face"), ("facebook",)),
    "tiktok": (("tiktok", "tik tok"), ("tiktok",)),
    "youtube": (("youtube", "yt", "shorts", "youtube short"), ("youtube",)),
    "threads": (("threads",), ("threads",)),
    "whatsapp": (("whatsapp", "whats app", "wa"), ()),
}
ALL_WORDS = re.compile(r"\b(todas las redes|en todas|todas partes|todos lados|post everywhere|everywhere|all networks|all platforms)\b")
TEXT_APPROVED = re.compile(r"\b(?:only text approved|solo texto aprobado)\b")
MIN_SCHEDULE_LEAD = timedelta(minutes=5)
NAMES = {"instagram": "Instagram", "facebook": "Facebook", "tiktok": "TikTok", "youtube": "YouTube",
         "threads": "Threads", "whatsapp": "WhatsApp"}
NUMBER_WORDS = {"una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
                "nueve": 9, "diez": 10, "once": 11, "doce": 12, "one": 1, "two": 2, "three": 3, "four": 4,
                "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
WEEKDAYS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6,
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
          "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
          "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
          "september": 9, "october": 10, "november": 11, "december": 12, "ene": 1, "jan": 1, "feb": 2,
          "abr": 4, "apr": 4, "ago": 8, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12, "dec": 12}
MONTH = "(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + ")"
PERIOD = r"(?:de|en|por) la (manana|tarde|noche)|in the (morning|afternoon|evening)|at (night)"
PERIOD_HOUR = {"manana": 9, "morning": 9, "tarde": 15, "afternoon": 15, "noche": 19, "evening": 19, "night": 19}
EXACT_MARK = re.compile(r"\b(?:texto|text|caption|copy|que diga)\s*:\s*", re.IGNORECASE)
# "idea:" typed, or "Idea, …" / "Idea. …" as speech transcribes it.
IDEA_MARK = re.compile(r"\b(?:la idea es(?: que)?|con la idea de(?: que)?|sobre|about|saying|diciendo)\b\s*"
                       r"|\b(?:idea|tema)\b\s*[:,.\-–—]\s*", re.IGNORECASE)
QUOTED = re.compile(r"[\"“”«»]([^\"“”«»]{3,})[\"“”«»]")
DEFAULT_HOUR = 18  # a day without a time: 18:00, said in the plan so you can change it while reviewing


def plain(text):
    """Lowercase, no accents: rules match "mañana", "manana" and "Mañana" alike. Same length as text."""
    out = []
    for ch in text.lower():
        base = unicodedata.normalize("NFKD", ch)
        out.append(base[0] if base and base[0].isascii() else ch)
    return "".join(out)


def split_instruction(text):
    """(command part, exact caption or None, idea or None). Networks and times are read only from the
    command part, so dates inside your idea ("entregas el sábado 31") don't become the schedule."""
    quoted = QUOTED.search(text)
    exact_mark = EXACT_MARK.search(text)
    idea_mark = IDEA_MARK.search(text)
    if quoted and (not exact_mark or quoted.start() < exact_mark.start()):
        return text[:quoted.start()] + " " + text[quoted.end():], quoted.group(1).strip(), None
    if exact_mark:
        return text[:exact_mark.start()], text[exact_mark.end():].strip(" \"“”") or None, None
    if idea_mark:
        return text[:idea_mark.start()], None, text[idea_mark.end():].strip(" ;,.:") or None
    return text, None, None


def parse_networks(command):
    words = plain(command)
    found = []
    for network, (names, _) in NETWORKS.items():
        hits = [m.start() for name in names for m in re.finditer(r"\b" + re.escape(name) + r"\b", words)]
        if hits:
            found.append((min(hits), network))
    if not found and ALL_WORDS.search(words):
        return list(NETWORKS), True
    return [network for _, network in sorted(found)], False


def parse_when(command, now):
    """Datetime (bakery time) for the command, plus the assumptions made. None if it gives no time."""
    words = plain(command)
    clock = re.sub(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", lambda m: str(NUMBER_WORDS[m.group(1)]), words)
    clock = re.sub(r"\b(\d{1,2}) y media\b", r"\1:30", re.sub(r"\b(\d{1,2}) y cuarto\b", r"\1:15", clock))
    notes = []
    weekday = re.search(r"\b(" + "|".join(WEEKDAYS) + r")\b", words)

    day = None
    m = re.search(r"\b(\d{1,2}) (?:de )?" + MONTH + r"\b", words) or re.search(r"\b" + MONTH + r"\.? (\d{1,2})\b", words)
    if m:
        a, b = m.groups()
        day = _date(now, *((MONTHS[b], int(a)) if a.isdigit() else (MONTHS[a], int(b))))
    elif re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", words):
        m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", words)
        day = _date(now, int(m.group(2)), int(m.group(1)), m.group(3))  # day/month, as in Ecuador
    elif re.search(r"\bpasado manana\b", words):
        day = now.date() + timedelta(days=2)
    elif re.search(r"(?<!la )(?<!esta )\bmanana\b|\btomorrow\b", words):  # not "por la mañana" (morning)
        day = now.date() + timedelta(days=1)
    elif re.search(r"\b(hoy|today|tonight|esta noche|esta tarde|this afternoon|this evening)\b", words):
        day = now.date()
    elif weekday:
        day = now.date() + timedelta(days=(WEEKDAYS[weekday.group(1)] - now.weekday()) % 7)

    hour = minute = None
    ampm = None
    found = re.search(PERIOD, clock)
    period = next(g for g in found.groups() if g) if found else None
    m = re.search(r"\b(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)?", clock)
    if m:
        hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
    else:
        m = re.search(r"\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)(?=\W|$)", clock)
        if m:
            hour, minute, ampm = int(m.group(1)), 0, m.group(2)
        else:
            m = re.search(r"\b(\d{1,2})\s*(?:h|hrs?|horas)\b(?!\s+de)|\ba las? (\d{1,2})\b|\b(\d{1,2}) (?=" + PERIOD + ")", clock)
            if m:
                hour, minute = int(next(g for g in m.groups() if g)), 0
    if hour is not None:
        if hour > 23 or minute > 59:
            hour = minute = None
        elif ampm and ampm.startswith("p") and hour < 12:
            hour += 12
        elif ampm and ampm.startswith("a") and hour == 12:
            hour = 0
        elif not ampm and period in ("tarde", "noche", "afternoon", "evening", "night") and hour < 12:
            hour += 12
        elif not ampm and not period and 1 <= hour <= 7:
            notes.append("“%d” read as %d:00 (afternoon)" % (hour, hour + 12))
            hour += 12
        elif not ampm and not period and 8 <= hour <= 11 and not m.group(0).count(":"):
            notes.append("“%d” read as %02d:00 (morning)" % (hour, hour))
    if hour is None and re.search(r"\b(mediodia|medio dia|noon)\b", words):
        hour, minute = 12, 0
    elif hour is None and re.search(r"\b(medianoche|midnight)\b", words):
        hour, minute = 0, 0
    elif hour is None and (period or re.search(r"\b(esta noche|tonight|esta tarde|this afternoon|this evening)\b", words)):
        hour, minute = PERIOD_HOUR[period or ("noche" if re.search(r"noche|tonight|evening", words) else "tarde")], 0
        notes.append("no exact time: %02d:00" % hour)

    if day is None and hour is None:
        if re.search(r"\b(ahora|ahorita|now|asap|cuanto antes|lo antes posible|de inmediato)\b", words):
            return _round_up(now + timedelta(minutes=15)), ["as soon as you approve it"]
        return None, notes
    if day is None:
        day = now.date()
    if hour is None:
        hour, minute = DEFAULT_HOUR, 0
        notes.append("no time given: %02d:00" % DEFAULT_HOUR)
    when = datetime(day.year, day.month, day.day, hour, minute, tzinfo=now.tzinfo)
    if when < now + MIN_SCHEDULE_LEAD:
        return None, ["requested time has passed or is too soon; rescheduling requires confirmation"]
    return when, notes


def _date(now, month, day, year=None):
    """A date from day and month; without a year, the next one that isn't in the past."""
    try:
        if year:
            return datetime(int(year) + (2000 if len(year) == 2 else 0), month, day).date()
        date = datetime(now.year, month, day).date()
    except ValueError:
        return None
    return date.replace(year=now.year + 1) if date < now.date() else date


def _round_up(when):
    """The next quarter hour."""
    when = when.replace(second=0, microsecond=0)
    return when + timedelta(minutes=(15 - when.minute % 15) % 15)


def detect_lang(text, default):
    words = re.findall(r"[a-záéíóúñ]+", text.lower())
    es = sum(w in ("el", "la", "de", "que", "y", "en", "los", "las", "para", "con", "nuestro", "nuestra", "una", "del", "por") for w in words)
    en = sum(w in ("the", "and", "to", "of", "for", "with", "our", "a", "is", "this", "on", "at") for w in words)
    return "English" if en > es else ("Spanish" if es > en else default)


def media_problem(network, kinds):
    """Why this network can't take these files, or None."""
    videos, photos = kinds.count("video"), kinds.count("image")
    if network == "youtube" and not (videos == 1 and photos == 0):
        return "YouTube takes exactly one video"
    if network == "tiktok" and not ((videos == 1 and photos == 0) or (videos == 0 and 1 <= photos <= 35)):
        return "TikTok takes one video or photos (not both)"
    if network == "instagram" and not 1 <= len(kinds) <= 10:
        return "Instagram takes 1 to 10 photos or videos"
    if network == "threads" and len(kinds) > 20:
        return "Threads takes up to 20 photos or videos"
    if network == "whatsapp" and len(kinds) > 1:
        return "WhatsApp Status takes one photo or video per status"
    return None


def placement(command, network):
    """Return the requested Meta placement, or both for the default."""
    words = plain(command)
    if network not in ("instagram", "facebook"):
        return None
    story = bool(re.search(r"\b(story|stories|historia|historias)\b", words))
    feed = bool(re.search(r"\b(feed|publicacion|publicaciones)\b", words))
    only_story = bool(re.search(r"\b(only|solo|just)\s+(story|stories|historia|historias)\b", words))
    only_feed = bool(re.search(r"\b(only|solo|just)\s+(feed|post|publicacion|publicaciones)\b", words))
    if only_story or (story and not feed):
        return "story"
    if only_feed or (feed and not story):
        return "feed"
    return "both"


def threads_caption(env, caption, lang):
    """Condense a caption with the local model while preserving complete thoughts and hashtags."""
    if len(caption) <= 500:
        return caption
    base = env.get("OLLAMA_HOST_URL", "http://localhost:11434").rstrip("/")
    model = env.get("LOCAL_LLM_MODEL", "llama3.2:3b")
    prompt = (
        "Rewrite the caption below for a Threads post. Return only the finished caption, no quotes "
        "or explanation. It must be at most 500 characters, use complete sentences, preserve the "
        "language, product facts, call to action, and the most relevant hashtags. Remove repetition "
        "and less important details rather than cutting a sentence or hashtag in half.\n\n"
        "Language: %s\nCaption:\n%s" % (lang, caption)
    )
    for attempt in (1, 2):
        status, data = pmlib.http("POST", base + "/api/generate", body={
            "model": model,
            "prompt": prompt + ("\n\nBe more concise than the previous attempt." if attempt == 2 else ""),
            "stream": False,
            "keep_alive": 0,
            "options": {"temperature": 0.3, "num_predict": 220, "num_ctx": 2048},
        }, timeout=600)
        if status != 200 or not isinstance(data, dict):
            raise PMError("Ollama returned HTTP %s while shortening the Threads caption: %s"
                          % (status, str(data)[:300]))
        shortened = (data.get("response") or "").strip().strip('"')
        if shortened and len(shortened) <= 500:
            return shortened
    raise PMError("The model could not produce a complete Threads caption within 500 characters.")


def plan(env, text, media_paths, lang_arg, now):
    command, exact, idea = split_instruction(text)
    networks, said_all = parse_networks(command)
    if not networks:
        raise PMError("Say where: Instagram, Facebook, TikTok or YouTube (or \"todas\").")
    when, notes = parse_when(command, now)
    if when is None:
        if notes and notes[-1].startswith("requested time"):
            raise PMError("The requested time has passed or is less than 5 minutes away. "
                          "No post was created. Please send a new future time.")
        raise PMError("Say when: e.g. \"el viernes a las 6 de la tarde\", \"mañana 9am\", \"hoy 18:00\", or \"ahora\".")
    lang = lang_arg or detect_lang(idea or exact or text, env.get("CAPTION_LANGUAGE", "Spanish"))
    return {"networks": networks, "said_all": said_all, "command": command, "when": when, "notes": notes, "exact": exact,
            "idea": idea, "lang": lang, "media": media_paths,
            "text_approved": bool(TEXT_APPROVED.search(command))}


def run(env, p, dry_run):
    result = {"when_local": p["when"].strftime("%a %d %b %Y %H:%M"), "when_utc": p["when"].astimezone(timezone.utc).isoformat(),
              "networks": p["networks"], "lang": p["lang"], "notes": list(p["notes"]), "warnings": [], "drafts": [],
              "dry_run": dry_run}
    postiz = pmlib.Postiz(env)
    connected = postiz.integrations()
    targets = []
    for network in p["networks"]:
        ids = NETWORKS[network][1]
        channels = [c for c in connected if (c.get("identifier") or "") in ids]
        if network == "whatsapp":
            targets.append((network, None, None))
            continue
        if not channels:
            if not p["said_all"]:
                result["warnings"].append("%s isn't connected in Postiz: skipped" % NAMES[network])
            continue
        targets += [(network, c, placement(p["command"], network)) for c in channels]
    if not targets:
        raise PMError("None of those networks is connected in Postiz yet (Launches → Add Channel).")

    tmp = tempfile.mkdtemp(prefix="pm-plan-")
    try:
        ready = [pmlib.normalize_media(os.path.expanduser(path), tmp) for path in p["media"]]
        kinds = [kind for kind, _ in ready]
        short = kinds == ["video"] and pmlib.is_short(ready[0][1])
        shorts_requested = re.search(r"\byou\s*tube\s+shorts?\b", p["command"], re.IGNORECASE)
        usable = []
        for network, channel, _ in targets:
            if not kinds:
                if network in ("facebook", "threads") and not p["text_approved"]:
                    problem = "%s text-only draft skipped: add 'only text approved' to allow it" % NAMES[network]
                else:
                    problem = ("%s needs a photo or video" % NAMES[network]
                               if channel and channel.get("identifier") in NEEDS_MEDIA else None)
            else:
                problem = media_problem(network, kinds)
                if not problem and network == "youtube" and shorts_requested and not short:
                    problem = ("YouTube Shorts require a vertical or square video of at most 3 minutes"
                               if p["lang"] != "Spanish" else
                               "YouTube Shorts requiere un video vertical o cuadrado de hasta 3 minutos")
            if problem:
                result["warnings"].append(problem + ": skipped")
            else:
                usable.append((network, channel, placement(p["command"], network)))
        if not usable:
            raise PMError("Nothing to draft: " + "; ".join(result["warnings"]))

        if p["exact"]:
            caption, source = p["exact"], "your text"
        elif p["idea"]:
            caption, model, _ = ollama_caption(env, p["idea"], p["lang"])
            source = "written by %s from your idea" % model
        else:
            caption = ("✍️ Escribe aquí el texto de esta publicación." if p["lang"] == "Spanish"
                       else "✍️ Write this post's text here.")
            source = "placeholder: you gave no idea or text"
            result["warnings"].append("no idea or text given: the drafts have a placeholder caption")
        result.update({"caption": caption, "caption_source": source, "short": short,
                       "targets": [{"network": n, "channel": c.get("name") if c else "WhatsApp Status",
                                    "placement": place} for n, c, place in usable]})
        if dry_run:
            return result

        thread_caption = threads_caption(env, caption, p["lang"]) if any(
            network == "threads" for network, _, _ in usable) else caption
        if thread_caption != caption:
            result["warnings"].append("Threads caption rewritten by the local model to fit 500 characters")
        media = []
        for kind, path in ready:
            uploaded = postiz.upload(path)
            media.append({"id": uploaded["id"], "path": uploaded["path"]})
        when_utc = p["when"].astimezone(timezone.utc)
        whatsapp_requested = any(network == "whatsapp" for network, _, _ in usable)
        whatsapp_post_ids = []
        for network, channel, target_placement in usable:
            if network == "whatsapp":
                result["drafts"].append({"network": network, "channel": "WhatsApp Status", "post_id": None,
                                         "pending": True})
                continue
            target_caption = thread_caption if network == "threads" else caption
            placements = ("feed", "story") if target_placement == "both" else (target_placement,)
            for item_placement in placements:
                settings = {"post_type": "story"} if item_placement == "story" else None
                created = postiz.create_draft(channel, target_caption, media, when=when_utc,
                                             settings=settings, short=(network == "youtube" and short))
                post_id = created[0]["postId"] if created else None
                if post_id:
                    whatsapp_post_ids.append(post_id)
                result["drafts"].append({"network": network, "channel": channel.get("name"),
                                         "placement": item_placement, "post_id": post_id})
                pmlib.append_log("drafts.jsonl", {"source": "plan-post", "post_id": post_id,
                                                  "channel": channel.get("identifier"), "placement": item_placement,
                                                  "integration_id": channel.get("id"), "when": result["when_utc"],
                                                  "media": [m["path"] for m in media], "caption": target_caption[:500]})
        if whatsapp_requested and not dry_run:
            pending_id = whatsapp_pending.enqueue(caption, [path for _, path in ready], whatsapp_post_ids, when_utc)
            result["whatsapp_pending_id"] = pending_id
            result["notes"].append("WhatsApp Status waits for approval")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    result["review_url"] = "https://%s/launches" % env.get("NGROK_DOMAIN", "<NGROK_DOMAIN>")
    return result


def show(result):
    head = "Plan (nothing created)" if result["dry_run"] else "Drafts created"
    info("%s for %s (bakery time)" % (head, result["when_local"]))
    for t in result.get("targets", []):
        done = next((d for d in result["drafts"] if d["channel"] == t["channel"]
                     and d["network"] == t["network"]), None)
        extra = " (Short)" if t["network"] == "youtube" and result.get("short") else ""
        info("  • %s: %s%s%s" % (NAMES[t["network"]], t["channel"], extra, ("  → draft " + str(done["post_id"])) if done else ""))
    if result.get("caption"):
        info("\nCaption (%s):\n%s\n" % (result["caption_source"], result["caption"]))
    for note in result["notes"]:
        info("  · assumed: " + note)
    for warning in result["warnings"]:
        info("  ⚠ " + warning)
    if result.get("review_url"):
        info("\nNothing is published yet. Review, edit and approve them on the calendar: " + result["review_url"])


def main():
    parser = argparse.ArgumentParser(prog="plan-post.sh", description=__doc__.split("\n")[0],
                                     epilog=__doc__.split("\n", 1)[1], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("instruction", help="where, when, and your idea or exact text, in one sentence")
    parser.add_argument("--media", action="append", default=[], help="a photo or video (repeat for several)")
    parser.add_argument("--lang", help="caption language (default: the language of your idea)")
    parser.add_argument("--dry-run", action="store_true", help="show the plan; create nothing")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    args = parser.parse_args()

    out = sys.stdout
    if args.json:
        sys.stdout = sys.stderr  # progress lines (e.g. "Transcoding video...") must not mix with the JSON
    env = pmlib.load_env()
    for path in args.media:
        if not os.path.isfile(os.path.expanduser(path)):
            raise PMError("Media file not found: " + path)
    zone = env.get("PM_TIMEZONE", "America/Guayaquil")
    tz = ZoneInfo(zone) if ZoneInfo else timezone(timedelta(hours=-5))
    p = plan(env, args.instruction, args.media, args.lang, datetime.now(tz))
    result = run(env, p, args.dry_run)
    if args.json:
        out.write(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    else:
        show(result)
    return 0


if __name__ == "__main__":
    try:
        with pmlib.Job("draft", "plan-post " + " ".join(sys.argv[1:])[:60]):
            sys.exit(main())
    except PMError as exc:
        if "--json" in sys.argv:
            sys.__stdout__.write(json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n")
        else:
            print("✖ " + str(exc), file=sys.stderr)
        sys.exit(1)
