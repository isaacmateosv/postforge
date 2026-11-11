#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Hands-free posting: your media plus one sentence become one Postiz DRAFT per network, scheduled at
the time you said. HITL: drafts only. You review, edit and approve them on the Postiz calendar.

    ./scripts/plan-post.sh --media demo.mp4 "Instagram y TikTok el viernes a las 6 de la tarde; idea: taller de fotografía solo hasta el domingo"
    ./scripts/plan-post.sh --media torta.jpg 'Facebook mañana 9am texto: "Nuestra torta de chocolate 🍫"'
    ./scripts/plan-post.sh --dry-run ...   show the plan, create nothing
    ./scripts/plan-post.sh --json ...      machine-readable result (menu bar app, WhatsApp door)

The networks and the time are read with rules, not AI, from the part before your idea or text:
- networks: Instagram/insta/IG, Facebook/FB, TikTok, YouTube/Shorts, "todas"/"all";
- days: hoy/mañana/pasado mañana, weekdays, "5 de noviembre", "5/11", "today", "tomorrow", "Nov 5";
- times: "18:00", "6pm", "6 de la tarde", "a las 6" (1-7 means pm), mediodía, "en la noche".
The caption comes from your idea ("idea:", "sobre", "about", "la idea es"), written by the local
model with the brand rules and the fixed order line. Your exact words ("texto:", "caption:", or in
quotes) are kept as written. Times are configured locally (PM_TIMEZONE, default America/Guayaquil).
"""
import argparse
import json
import math
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
import media_links  # noqa: E402

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
ALL_WORDS = re.compile(r"\b(todas las redes|en todas|todas partes|todo(?:s)? (?:lado(?:s)?|sitio(?:s)?)|post everywhere|everywhere|all networks|all platforms)\b")
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
IDEA_MARK = re.compile(r"\b(?:la idea es(?: que)?|con la idea de(?: que)?|escribe sobre|redacta sobre|write about|sobre|about|saying|diciendo)\b\s*"
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
    if (idea_mark and (not exact_mark or idea_mark.start() < exact_mark.start())
            and (not quoted or idea_mark.start() < quoted.start())):
        body = text[idea_mark.end():].strip(" ;,.:")
        literal = QUOTED.fullmatch(body)
        if literal:
            return text[:idea_mark.start()], literal.group(1).strip(), None
        brief, separator, tail = body.rpartition(";")
        if separator and re.search(r"\b(?:post|publish|upload|postea|publica|sube|programa|schedule)\b", plain(tail)):
            return text[:idea_mark.start()] + " " + tail, None, brief.strip() or None
        return text[:idea_mark.start()], None, body or None
    if quoted and (not exact_mark or quoted.start() < exact_mark.start()):
        return text[:quoted.start()] + " " + text[quoted.end():], quoted.group(1).strip(), None
    if exact_mark:
        body = text[exact_mark.end():].strip()
        literal = QUOTED.match(body)
        if literal:
            return text[:exact_mark.start()] + " " + body[literal.end():], literal.group(1).strip(), None
        return text[:exact_mark.start()], body.strip(" \"“”") or None, None
    if idea_mark:
        return text[:idea_mark.start()], None, text[idea_mark.end():].strip(" ;,.:") or None
    idea, separator, command = text.partition(";")
    if (separator and idea.strip() and parse_networks(command)[0]
            and re.search(r"\b(?:postea(?:r)?|publica(?:r)?|sube|post|publish|upload)\b", plain(command))):
        return command.strip(), None, idea.strip()
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
    """Datetime (local time) for the command, plus the assumptions made. None if it gives no time."""
    words = plain(command)
    clock = re.sub(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", lambda m: str(NUMBER_WORDS[m.group(1)]), words)
    clock = re.sub(r"\b(\d{1,2}) y media\b", r"\1:30", re.sub(r"\b(\d{1,2}) y cuarto\b", r"\1:15", clock))
    clock = re.sub(r"\b([ap])\s*\.?\s*m\s*\.?", r"\1m", clock)
    notes = []
    weekday = re.search(r"\b(" + "|".join(WEEKDAYS) + r")\b", words)

    day = None
    m = re.search(r"\b(\d{1,2}) (?:de )?" + MONTH + r"\b", words) or re.search(r"\b" + MONTH + r"\.? (\d{1,2})\b", words)
    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", words)
    if iso:
        day = _date(now, int(iso[2]), int(iso[3]), iso[1])
    elif m:
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
        offset = (WEEKDAYS[weekday.group(1)] - now.weekday()) % 7
        if offset == 0 and re.search(r"\b(?:next|proximo|proxima)\b", words):
            offset = 7
        day = now.date() + timedelta(days=offset)

    if day is None and (m or iso):
        return None, ["invalid calendar date"]

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
            m = re.search(r"\b(\d{1,2})\s*(?:h|hrs?|horas)\b(?!\s+de)|\b(?:a las?|at) (\d{1,2})\b|\b(\d{1,2}) (?=" + PERIOD + ")", clock)
            if m:
                hour, minute = int(next(g for g in m.groups() if g)), 0
    if hour is not None:
        if hour > 23 or minute > 59 or (ampm and not 1 <= hour <= 12):
            return None, ["invalid clock time"]
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


def media_problem(network, kinds, es=False):
    """Why this network can't take these files, or None."""
    videos, photos = kinds.count("video"), kinds.count("image")
    if network == "youtube" and not (videos == 1 and photos == 0):
        return "YouTube admite un solo video" if es else "YouTube takes exactly one video"
    if network == "tiktok" and not ((videos == 1 and photos == 0) or (videos == 0 and 1 <= photos <= 35)):
        return "TikTok admite un video o fotos por separado" if es else "TikTok takes one video or photos (not both)"
    if network == "instagram" and not 1 <= len(kinds) <= 10:
        return "Instagram admite de 1 a 10 fotos o videos" if es else "Instagram takes 1 to 10 photos or videos"
    if network == "threads" and len(kinds) > 20:
        return "Threads admite hasta 20 fotos o videos" if es else "Threads takes up to 20 photos or videos"
    if network == "whatsapp" and len(kinds) > 1:
        return "WhatsApp admite una foto o un video por estado" if es else "WhatsApp Status takes one photo or video per status"
    return None


COVER_SECOND = re.compile(r"\b(?:cover at|portada en(?: el segundo)?)\s+(-?\d+(?:[.,]\d+)?)"
                          r"(?:\s*(?:seconds?|segundos?|s)\b)?(?![\w.,])")
COVER_ATTACHMENT = re.compile(r"\b(?:cover image|foto de portada|imagen de portada)\b")


def placement(command):
    words = plain(command)
    story = bool(re.search(r"\b(story|stories|historia|historias)\b", words))
    feed = bool(re.search(r"\b(feed|posts|publicacion|publicaciones)\b|\bpost (?:and|y|e) stor", words))
    if re.search(r"\b(?:(?:only|solo|just)\s+(?:story|stories|historia|historias)|(?:story|stories) only)\b", words):
        return "story"
    if re.search(r"\b(?:(?:only|solo|just)\s+(?:feed|posts?|publicacion|publicaciones)|(?:feed|posts?) only)\b", words):
        return "feed"
    if story and not feed:
        return "story"
    if feed and not story:
        return "feed"
    return "both"


def draft_placements(network, requested, has_media):
    if network == "whatsapp":
        return ("status",) if requested != "feed" else ()
    if network in ("facebook", "instagram"):
        if requested == "both":
            return ("feed", "story") if has_media else ("feed",)
        return (requested,) if has_media or requested == "feed" else ()
    return ("feed",) if requested != "story" else ()


def cover_mode(env, network, place, image, second, short):
    if place != "feed":
        return None
    if network == "instagram":
        return "image" if image else "frame"
    if network == "youtube" and not short:
        return "image" if image else "frame-image"
    if network == "tiktok" and second is not None:
        if pmlib.draft_settings("tiktok", "", env)["content_posting_method"] == "DIRECT_POST":
            return "frame"
    return None


def threads_caption(env, caption, lang, limit=500):
    """Condense a caption with the local model while preserving complete thoughts and hashtags."""
    if len(caption) <= limit:
        return caption
    base = env.get("OLLAMA_HOST_URL", "http://localhost:11434").rstrip("/")
    model = env.get("LOCAL_LLM_MODEL", "llama3.2:3b")
    prompt = (
        "Rewrite the caption below for a Threads post. Return only the finished caption, no quotes "
        "or explanation. It must be at most %d characters, use complete sentences, preserve the "
        "language, product facts, call to action, and the most relevant hashtags. Remove repetition "
        "and less important details rather than cutting a sentence or hashtag in half.\n\n"
        "Language: %s\nCaption:\n%s" % (limit, lang, caption)
    )
    for attempt in (1, 2):
        status, data = pmlib.http("POST", base + "/api/generate", body={
            "model": model,
            **pmlib.ollama_text_prompt(model, prompt + ("\n\nBe more concise than the previous attempt." if attempt == 2 else "")),
            "stream": False,
            "keep_alive": 0,
            "options": {"temperature": 0.3, "num_predict": 220, "num_ctx": 2048},
        }, timeout=600)
        if status != 200 or not isinstance(data, dict):
            raise PMError("Ollama returned HTTP %s while shortening the Threads caption: %s"
                          % (status, str(data)[:300]))
        shortened = pmlib.ollama_final_text(data).strip('"')
        if shortened and len(shortened) <= limit:
            return shortened
    raise PMError("The model could not produce a complete Threads caption within 500 characters.")


def reviewed_youtube_title(env, caption, idea, lang, short):
    original = pmlib.youtube_title_line(caption)
    if not original or pmlib.youtube_title_fits(original, short):
        return pmlib.youtube_title(caption, short)
    limit = pmlib.YOUTUBE_TITLE_LIMIT
    prompt = (
        f"Write one complete YouTube title in {lang}, at most {limit} characters. "
        "Keep the subject and distinctive details. Use a short phrase that makes sense on its own. "
        "Avoid generic invitations, hashtags, quotation marks, and invented facts. "
        "Return only the title.\n"
        f"Topic: {(idea or '')[:350]}\nCaption: {caption[:600]}"
    )
    model = env.get("LOCAL_LLM_MODEL", "llama3.2:3b")
    try:
        status, data = pmlib.http("POST", env.get("OLLAMA_HOST_URL", "http://localhost:11434").rstrip("/") + "/api/generate",
                                  body={"model": model, **pmlib.ollama_text_prompt(model, prompt),
                                        "stream": False, "keep_alive": 0,
                                        "options": {"temperature": 0.2, "num_predict": 55, "num_ctx": 2048}}, timeout=45)
        if status == 200 and isinstance(data, dict):
            suggestion = pmlib.youtube_title_line(pmlib.ollama_final_text(data).strip('"“”'))
            if pmlib.youtube_title_fits(suggestion, short):
                return pmlib.youtube_title(suggestion, short)
    except PMError:
        pass
    return pmlib.youtube_title(caption, short)


def tagged_threads_caption(env, caption, lang, tag):
    if not tag:
        return threads_caption(env, caption, lang)
    body = pmlib.remove_final_tag(caption, tag)
    shortened = threads_caption(env, body, lang, 500 - len(tag) - 2)
    return pmlib.apply_final_tag(shortened, tag)


def revise_copy(env, snapshot, instruction, edited=None):
    """Update only caption fields on a previously calculated preview."""
    _, exact, idea = split_instruction(instruction)
    lang = snapshot["lang"]
    tag = pmlib.final_tag(snapshot.get("final_tag"))
    if edited is None:
        brief = idea or exact or snapshot.get("caption")
        if not brief:
            raise PMError("No hay un texto para reescribir." if lang == "Spanish" else "There is no caption to rewrite.")
        caption, model, _ = ollama_caption(env, brief, lang, previous=snapshot["caption"])
        source = "written by %s from your idea" % model
    else:
        caption = edited.strip()
        if not caption:
            raise PMError("El texto está vacío." if lang == "Spanish" else "The caption is empty.")
        source = "edited caption"
    caption = pmlib.apply_final_tag(caption, tag)
    networks = {target["network"] for target in snapshot.get("targets", [])}
    threads = tagged_threads_caption(env, caption, lang, tag) if "threads" in networks else caption
    title = (snapshot.get("youtube_title") if snapshot.get("youtube_title_manual") else
             reviewed_youtube_title(env, caption, idea, lang, snapshot.get("short", False))
             if "youtube" in networks else None)
    return dict(snapshot, caption=caption, caption_source=source,
                threads_caption=threads if threads != caption else None, youtube_title=title,
                youtube_caption=pmlib.youtube_description(caption,tag) if "youtube" in networks else None)


def plan(env, text, media_paths, lang_arg, now, *, placement_override=None, cover_image=None,
         cover_second=None, ui_lang=None, text_networks=None):
    command, exact, idea = split_instruction(text)
    lang = lang_arg or detect_lang(idea or exact or text, env.get("CAPTION_LANGUAGE", "Spanish"))
    es = (ui_lang or lang) == "Spanish"
    cover_word = COVER_SECOND.search(plain(command))
    cover_attachment = bool(COVER_ATTACHMENT.search(plain(command))) and cover_image is None
    if cover_word and cover_second is None:
        cover_second = cover_word[1]
    if cover_second is not None:
        try:
            cover_second = float(str(cover_second).replace(",", "."))
            if not math.isfinite(cover_second) or cover_second < 0:
                raise ValueError
        except ValueError:
            raise PMError("Ingresa un segundo de portada válido, desde 0." if es else
                          "Enter a valid cover second, starting at 0.")
    if (cover_image or cover_attachment) and cover_second is not None:
        raise PMError("Elige una imagen de portada o un segundo del video." if es else
                      "Choose a cover image or a video timestamp.")
    schedule = command if not cover_word else command[:cover_word.start()] + command[cover_word.end():]
    networks, said_all = parse_networks(schedule)
    if text_networks is not None:
        if media_paths or not text_networks or not set(text_networks) <= {"facebook", "threads", "whatsapp"}:
            raise PMError("Choose supported text-only destinations without attached media.")
        networks, said_all = list(dict.fromkeys(text_networks)), False
    if not networks:
        raise PMError("Indica en qué red quieres publicar o escribe «en todo lado»." if es else
                      "Choose a network or say ‘post everywhere’.")
    when, notes = parse_when(schedule, now)
    if when is None:
        if notes == ["invalid clock time"]:
            raise PMError("La hora indicada no es válida. Usa, por ejemplo, 19:15 o 7:15 p. m." if es else
                          "That time is invalid. Use a time such as 19:15 or 7:15 pm.")
        if notes == ["invalid calendar date"]:
            raise PMError("La fecha indicada no existe. Revisa el día, mes y año." if es else
                          "That calendar date does not exist. Check the day, month, and year.")
        if notes and notes[-1].startswith("requested time"):
            raise PMError("La hora indicada ya pasó o faltan menos de 5 minutos. Indica una nueva hora."
                          if es else "The requested time has passed or is less than 5 minutes away. "
                          "No post was created. Please send a new future time.")
        raise PMError("Indica cuándo quieres publicar. Por ejemplo, «mañana a las 7:15 p. m.»."
                      if es else "Say when: for example, ‘tomorrow at 7:15 pm’.")
    return {"ui_lang": ui_lang or lang, "placement": "both" if text_networks is not None else placement_override or placement(command),
            "cover_image": cover_image, "cover_attachment": cover_attachment, "cover_second": cover_second,
            "networks": networks, "said_all": said_all, "command": command, "when": when, "notes": notes, "exact": exact,
            "idea": idea, "lang": lang, "media": media_paths,
            "text_approved": text_networks is not None or bool(TEXT_APPROVED.search(command))}


def video_warnings(networks, durations, lang, short=False):
    es = lang == "Spanish"
    warnings = []
    longest = max(durations, default=0)
    if "instagram" in networks and longest > 180:
        warnings.append("Instagram: este reel supera los 3 minutos y no se recomendará a nuevas audiencias."
                        if es else "Instagram: this Reel exceeds three minutes and won’t be recommended to new audiences.")
    if "youtube" in networks and longest > 180 and not short:
        warnings.append("YouTube: el video supera los 3 minutos y se publicaría como video normal."
                        if es else "YouTube: the video exceeds three minutes and would publish as a regular video.")
    if "whatsapp" in networks and longest > whatsapp_pending.STATUS_PART_SECONDS:
        parts = whatsapp_pending.video_part_count(longest)
        warnings.append(f"Estado de WhatsApp: después de aprobarlo, el video se dividirá en {parts} partes de hasta 60 segundos."
                        if es else f"WhatsApp Status: after approval, the video will be split into {parts} parts of up to 60 seconds.")
    return warnings


def run(env, p, dry_run, schedule=False):
    result = {"when_local": p["when"].strftime("%a %d %b %Y %H:%M"), "when_utc": p["when"].astimezone(timezone.utc).isoformat(),
              "networks": p["networks"], "lang": p["lang"], "notes": list(p["notes"]), "warnings": [], "drafts": [],
              "dry_run": dry_run, "scheduled": schedule}
    es = p.get("ui_lang", p["lang"]) == "Spanish"
    requested = p.get("placement") or placement(p["command"])
    image = p.get("cover_image")
    second = p.get("cover_second")
    paths = list(p["media"])
    if p.get("cover_attachment"):
        videos = [path for path in paths if os.path.splitext(path)[1].lower() in pmlib.VIDEO_EXT]
        photos = [path for path in paths if os.path.splitext(path)[1].lower() in pmlib.IMAGE_EXT]
        if len(paths) != 2 or len(videos) != 1 or len(photos) != 1:
            raise PMError("Adjunta un video y una sola foto de portada." if es else
                          "Attach one video and exactly one cover image.")
        image, paths = photos[0], videos
    postiz = pmlib.Postiz(env)
    connected = postiz.integrations()
    if "reviewed_integrations" in p:
        wanted = set(p["reviewed_integrations"])
        if wanted - {channel["id"] for channel in connected}:
            raise PMError("Un destino revisado ya no está conectado. Prepara otro plan." if es else
                          "A reviewed account is no longer connected. Prepare a fresh plan.")
        connected = [channel for channel in connected if channel["id"] in wanted]
    targets = []
    for network in p["networks"]:
        ids = NETWORKS[network][1]
        channels = [c for c in connected if (c.get("identifier") or "") in ids]
        if network == "whatsapp":
            targets.append((network, None, None))
            continue
        if not channels:
            if not p["said_all"]:
                result["warnings"].append(f"{NAMES[network]}: se omitió porque no está conectado en Postiz."
                                          if es else f"{NAMES[network]}: skipped because it is not connected in Postiz.")
            continue
        targets += [(network, c, None) for c in channels]
    if not targets:
        raise PMError("Conecta al menos una de esas redes en Postiz con Add Channel." if es else
                      "Connect at least one of those networks using Add Channel in Postiz.")

    tmp = tempfile.mkdtemp(prefix="pm-plan-")
    try:
        ready = [pmlib.normalize_media(os.path.expanduser(path), tmp) for path in paths]
        kinds = [kind for kind, _ in ready]
        short = kinds == ["video"] and pmlib.is_short(ready[0][1])
        youtube_trim = False
        if kinds == ["video"] and any(n == "youtube" for n, _, _ in targets) and p.get("youtube_trim", True):
            duration, _, _, width, height = pmlib.ffprobe(ready[0][1])
            width, height = pmlib.display_dimensions(ready[0][1], width, height)
            youtube_trim = duration > 179 and height >= width
            short = height >= width
            if youtube_trim:
                result["warnings"].append("YouTube: se preparará una copia de exactamente 2:59; el archivo de las otras redes se conserva completo."
                                          if es else "YouTube: a separate 2:59 copy will be prepared; other destinations keep the full video.")
        if not kinds and not p["text_approved"] and any(n in ("facebook", "threads") for n, _, _ in targets):
            raise PMError(
                "Sin archivos, confirma los destinos del anuncio. Facebook y Threads admiten publicaciones de texto; WhatsApp admite Estados de texto. Instagram requiere una foto o un video. Para confirmar, vuelve a enviar los destinos y la hora con «solo texto aprobado; texto: tu anuncio»."
                if es else
                "Without media, confirm the announcement destinations. Facebook and Threads accept text posts; WhatsApp accepts text Status. Instagram needs a photo or video. Resend the destinations and time with ‘only text approved; caption: your announcement’ to confirm.")
        cover_requested = bool(image) or second is not None
        normalized_cover = None
        if cover_requested:
            if kinds != ["video"]:
                raise PMError("La portada requiere un solo video." if es else "A cover requires exactly one video.")
            if image:
                image = os.path.expanduser(image)
                if not os.path.isfile(image) or os.path.splitext(image)[1].lower() not in pmlib.IMAGE_EXT:
                    raise PMError("Elige un archivo de imagen válido para la portada." if es else
                                  "Choose a valid image file for the cover.")
                cover_dir = os.path.join(tmp, "cover")
                os.mkdir(cover_dir)
                _, normalized_cover = pmlib.normalize_media(image, cover_dir)
            elif second >= pmlib.ffprobe(ready[0][1])[0]:
                raise PMError("El segundo de la portada debe estar dentro del video." if es else
                              "The cover timestamp must be within the video.")
        shorts_requested = (p.get("youtube_mode") == "shorts" or ("youtube_mode" not in p and p.get("youtube_trim", False))) or re.search(r"\byou\s*tube\s+shorts?\b", p["command"], re.IGNORECASE)
        usable = []
        for network, channel, _ in targets:
            places = draft_placements(network, requested, bool(kinds))
            if not places:
                result["warnings"].append(
                    (f"{NAMES[network]}: se omitió porque no admite ese formato con estos archivos." if es else
                     f"{NAMES[network]}: skipped because that placement is unavailable for these files."))
                continue
            if not kinds:
                if network in ("facebook", "threads") and not p["text_approved"]:
                    problem = (f"{NAMES[network]} requiere «solo texto aprobado» para crear un borrador sin archivos"
                               if es else f"{NAMES[network]} requires ‘only text approved’ for a text-only draft")
                else:
                    problem = None
                    if channel and channel.get("identifier") in NEEDS_MEDIA:
                        problem = (f"{NAMES[network]} requiere una foto o un video" if es else
                                   f"{NAMES[network]} needs a photo or video")
            else:
                problem = media_problem(network, kinds, es)
                if not problem and network == "youtube" and p.get("youtube_mode") == "regular" and short:
                    problem = ("YouTube will classify this vertical or square video as a Short; use Automatic or choose a horizontal version"
                               if not es else "YouTube clasificará este video vertical o cuadrado como Short; usa Automático o elige una versión horizontal")
                if not problem and network == "youtube" and shorts_requested and not short:
                    problem = ("YouTube Shorts require a vertical or square video of at most 3 minutes"
                               if not es else
                               "YouTube Shorts requiere un video vertical o cuadrado de hasta 3 minutos")
            if problem:
                result["warnings"].append(problem + (" · se omitió" if es else " · skipped"))
            else:
                usable.extend((network, channel, place) for place in places)
        if not usable:
            raise PMError(("No se pueden crear borradores. " if es else "No drafts can be created. ")
                          + " · ".join(result["warnings"]))
        has_social_posts = any(network != "whatsapp" for network, _, _ in usable)
        gated_media = bool(ready) and str(env.get("FRONTEND_URL", "")).startswith("https://") and os.path.isfile(
            os.path.join(pmlib.ROOT, "data", "gateway", "configuration.yml"))
        media_key = media_links.load_key(os.path.join(pmlib.ROOT, "data", "gateway", "media-signing.key")) if gated_media else None
        media_blocked = gated_media and not media_key
        if has_social_posts and media_key:
            result["notes"].append(
                "Los enlaces de descarga vencen 48 horas después de la hora planificada. Si mueves la publicación más allá, vuelve a preparar sus borradores."
                if es else
                "Media download links expire 48 hours after the planned time. Recreate the drafts if you move publication beyond that time.")
        if has_social_posts and media_blocked:
            result["warnings"].append(
                "El acceso seguro bloquea la descarga de archivos por las redes sociales. "
                "Puedes guardar los borradores, pero no los apruebes en Postiz hasta corregir la entrega."
                if es else
                "The secure gateway blocks social platforms from downloading media. "
                "You can save drafts, but wait to approve them in Postiz until media delivery is fixed.")
        if schedule:
            if not has_social_posts:
                raise PMError("El Estado de WhatsApp requiere su propia aprobación." if es else
                              "WhatsApp Status requires its own approval.")
            if media_blocked:
                raise PMError("La programación directa de archivos está pausada mientras se corrige la entrega por el acceso seguro."
                              if es else "Direct scheduling of media is paused until delivery through the secure gateway is fixed.")

        story_part_count = 1
        if kinds == ["video"] and any(place == "story" for _, _, place in usable):
            duration = pmlib.ffprobe(ready[0][1])[0]
            if duration > 60:
                story_part_count = math.ceil(duration / 59.5)
                result["warnings"].append(
                    f"Facebook e Instagram: se crearán {story_part_count} borradores de historias de menos de un minuto, separados por un minuto. Revisa y aprueba cada parte en orden."
                    if es else
                    f"Facebook and Instagram: this video creates {story_part_count} Story drafts under one minute, scheduled one minute apart. Review and approve each part in order.")

        video_networks = {network for network, _, _ in usable} & {"youtube", "whatsapp"}
        if kinds == ["video"] and any(network == "instagram" and place == "feed" for network, _, place in usable):
            video_networks.add("instagram")
        if video_networks:
            durations = [pmlib.ffprobe(path)[0] for kind, path in ready if kind == "video"]
            result["warnings"].extend(video_warnings(video_networks - ({"youtube"} if youtube_trim else set()), durations, p.get("ui_lang", p["lang"]), short))

        if p.get("reviewed_caption"):
            caption, source = p["reviewed_caption"], "reviewed caption"
        elif p["exact"]:
            caption, source = p["exact"], "your text"
        elif p["idea"]:
            previous = p.get("alternate_caption")
            if previous:
                caption, model, _ = ollama_caption(env, p["idea"], p["lang"], previous=previous)
            else:
                caption, model, _ = ollama_caption(env, p["idea"], p["lang"])
            source = "written by %s from your idea" % model
        else:
            caption = ("✍️ Escribe aquí el texto de esta publicación." if p["lang"] == "Spanish"
                       else "✍️ Write this post's text here.")
            source = "placeholder: you gave no idea or text"
            result["warnings"].append("no idea or text given: the drafts have a placeholder caption")
        modes = [cover_mode(env, n, place, image, second, short) if cover_requested else None
                 for n, _, place in usable]
        if cover_requested and not any(modes):
            result["warnings"].append(
                "La portada elegida no se aplica a estos destinos. Para TikTok en bandeja o YouTube Shorts, configúrala en la plataforma."
                if es else "The selected cover does not apply to these destinations. For TikTok inbox uploads or YouTube Shorts, choose the cover on the platform.")
        if cover_requested and any(modes):
            unsupported = sorted({NAMES[n] for (n, _, place), mode in zip(usable, modes)
                                  if place == "feed" and mode is None})
            if unsupported:
                names = ", ".join(unsupported)
                result["warnings"].append(
                    f"La portada elegida no se aplica a: {names}." if es else
                    f"The selected cover does not apply to: {names}.")
        tag = pmlib.final_tag(p.get("final_tag", env.get("CAPTION_FINAL_TAG", "")))
        caption = pmlib.apply_final_tag(caption, tag)
        thread_caption = caption
        if any(network == "threads" for network, _, _ in usable):
            reviewed_threads = p.get("reviewed_threads_caption")
            thread_caption = (pmlib.apply_final_tag(reviewed_threads, tag) if reviewed_threads else
                              tagged_threads_caption(env, caption, p["lang"], tag))
        youtube_title = None
        if any(network == "youtube" for network, _, _ in usable):
            selected_title = p.get("reviewed_youtube_title")
            if selected_title and not 1 <= len(selected_title.strip()) <= 100:
                raise PMError("YouTube titles must contain 1–100 characters.")
            youtube_title = (selected_title.strip() if selected_title else
                             reviewed_youtube_title(env, caption, p["idea"], p["lang"], short))
        cover_available = kinds == ["video"] and any(
            cover_mode(env, network, place, None, 0, short) for network, _, place in usable)
        result.update({"caption": caption, "caption_source": source, "short": short,
                       "final_tag": tag,
                       "can_rewrite": bool(p["idea"] or p["exact"]),
                       "direct_schedule_available": has_social_posts and not media_blocked,
                       "direct_schedule_blocked_by_gateway": has_social_posts and media_blocked,
                       "youtube_title": youtube_title, "youtube_caption": pmlib.youtube_description(caption,tag) if youtube_title else None, "youtube_trim_seconds": 179 if youtube_trim else None,
                       "whatsapp_background": p.get("whatsapp_background", "#128C7E"),
                       "video_cover_available": cover_available,
                       "video_without_cover": cover_available and not cover_requested,
                       "threads_caption": thread_caption if thread_caption != caption else None,
                       "targets": [{"network": n, "channel": c.get("name") if c else "WhatsApp Status",
                                    "integration_id": c.get("id") if c else None,
                                    "placement": place, "parts": story_part_count if place == "story" else 1, "cover": mode, "cover_second": second if mode else None}
                                   for (n, c, place), mode in zip(usable, modes)]})
        if dry_run:
            return result

        youtube_media = []
        if youtube_trim and any(n == "youtube" for n, _, _ in usable):
            youtube_dir = os.path.join(tmp, "youtube")
            os.mkdir(youtube_dir)
            trimmed = pmlib.to_mp4(ready[0][1], youtube_dir, max_seconds=179)
            if not 178.8 <= pmlib.ffprobe(trimmed)[0] <= 179.05:
                raise PMError("Could not verify the 2:59 YouTube copy. / No se pudo verificar la copia de YouTube de 2:59.")
            uploaded = postiz.upload(trimmed)
            youtube_media = [{"id": uploaded["id"], "path": uploaded["path"]}]
        media = []
        for kind, path in (ready if any(n != "youtube" for n, _, _ in usable) or not youtube_media else []):
            uploaded = postiz.upload(path)
            media.append({"id": uploaded["id"], "path": uploaded["path"]})
        story_media = []
        if story_part_count > 1:
            story_dir = os.path.join(tmp, "stories")
            os.mkdir(story_dir)
            for path in pmlib.split_story_video(ready[0][1], story_dir):
                uploaded = postiz.upload(path)
                story_media.append({"id": uploaded["id"], "path": uploaded["path"]})
        cover_upload = None
        if (normalized_cover and "image" in modes) or "frame-image" in modes:
            cover_file = os.path.join(tmp, "post-cover.jpg")
            source_args = (["-i", normalized_cover] if normalized_cover else
                           ["-ss", str(second), "-i", ready[0][1]])
            pmlib.run(["ffmpeg", "-nostdin", "-loglevel", "error", *source_args, "-frames:v", "1",
                       "-vf", "scale=1280:1280:force_original_aspect_ratio=decrease:force_divisible_by=2",
                       "-q:v", "4", cover_file], check=False)
            if not os.path.isfile(cover_file) or not 0 < os.path.getsize(cover_file) < 2 * 1024 * 1024:
                raise PMError("No se pudo preparar una portada JPEG de menos de 2 MB." if es else
                              "Could not prepare a JPEG cover smaller than 2 MB.")
            cover_upload = postiz.upload(cover_file)
        when_utc = p["when"].astimezone(timezone.utc)
        library_media = media
        library_story_media = story_media
        library_youtube_media = youtube_media
        if media_key and has_social_posts:
            expiry = int((max(when_utc, datetime.now(timezone.utc)) + timedelta(days=2)).timestamp())
            try:
                def signed_items(items):
                    output = [dict(item, path=media_links.signed_url(media_key, env["FRONTEND_URL"], item["path"], expiry)) for item in items]
                    if not all(media_links.serves_media(item["path"]) for item in output):
                        raise PMError("Secure media delivery could not be verified. No posts were created.")
                    return output
                media = signed_items(media)
                story_media = signed_items(story_media)
                youtube_media = signed_items(youtube_media)
                if cover_upload:
                    cover_upload = signed_items([cover_upload])[0]
            except ValueError as exc:
                raise PMError(str(exc)) from exc
        whatsapp_requested = any(network == "whatsapp" for network, _, _ in usable)
        whatsapp_post_ids = []
        for (network, channel, item_placement), mode in zip(usable, modes):
            if network == "whatsapp":
                result["drafts"].append({"network": network, "channel": "WhatsApp Status", "post_id": None,
                                         "placement": "status", "pending": True})
                continue
            target_caption = thread_caption if network == "threads" else pmlib.youtube_description(caption,tag) if network=="youtube" else caption
            settings = {"post_type": "story"} if item_placement == "story" else {}
            if network == "youtube":
                settings["title"] = youtube_title
            target_media = youtube_media if network == "youtube" and youtube_media else media
            if mode and network == "youtube":
                settings["thumbnail"] = {key: cover_upload[key] for key in ("id", "path")}
            elif mode == "image":
                target_media = [dict(media[0], thumbnail=cover_upload["path"])]
            elif mode == "frame":
                target_media = [dict(media[0], thumbnailTimestamp=round(second * 1000))]
            batches = [[item] for item in story_media] if item_placement == "story" and story_media else [target_media]
            for part_index, part_media in enumerate(batches):
                part_time = when_utc + timedelta(minutes=part_index)
                created = postiz.create_draft(channel, target_caption, part_media, when=part_time,
                                             settings=settings, short=(network == "youtube" and short),
                                             **({"schedule": True} if schedule else {}))
                post_id = created[0]["postId"] if created else None
                if post_id:
                    whatsapp_post_ids.append(post_id)
                result["drafts"].append({"network": network, "channel": channel.get("name"),
                                         "placement": item_placement, "post_id": post_id,
                                         "part": part_index + 1, "parts": len(batches)})
                pmlib.append_log("drafts.jsonl", {"source": "plan-post", "post_id": post_id,
                                                  "channel": channel.get("identifier"), "placement": item_placement,
                                                  "integration_id": channel.get("id"), "when": part_time.isoformat(),
                                                  "media": ([library_story_media[part_index]["path"]] if item_placement == "story" and library_story_media
                                                            else [m["path"] for m in (library_youtube_media if network == "youtube" and library_youtube_media else library_media)]), "part": part_index + 1, "parts": len(batches), "caption": target_caption[:500]})
        if whatsapp_requested and not dry_run:
            pending_id = whatsapp_pending.enqueue(caption, [path for _, path in ready], whatsapp_post_ids, when_utc, background=p.get("whatsapp_background", "#128C7E"))
            result["whatsapp_pending_id"] = pending_id
            result["notes"].append("El Estado de WhatsApp espera aprobación." if es else
                                   "WhatsApp Status waits for approval")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    result["review_url"] = "https://%s/launches" % env.get("NGROK_DOMAIN", "<NGROK_DOMAIN>")
    return result


def show(result):
    head = "Plan (nothing created)" if result["dry_run"] else "Drafts created"
    info("%s for %s (local time)" % (head, result["when_local"]))
    for t in result.get("targets", []):
        done = next((d for d in result["drafts"] if d["channel"] == t["channel"]
                     and d["network"] == t["network"] and d.get("placement") == t["placement"]), None)
        extra = " (Short)" if t["network"] == "youtube" and result.get("short") else ""
        info("  • %s: %s (%s)%s%s" % (NAMES[t["network"]], t["channel"], t["placement"], extra, ("  → draft " + str(done["post_id"])) if done else ""))
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
    parser.add_argument("--placement", choices=("both", "feed", "story"), help="override the instruction's placement")
    parser.add_argument("--cover-image", help="image file to use as the video cover")
    parser.add_argument("--cover-second", help="video timestamp in seconds")
    parser.add_argument("--revise-copy", help=argparse.SUPPRESS)
    parser.add_argument("--edited-caption", help=argparse.SUPPRESS)
    parser.add_argument("--reviewed-when", help=argparse.SUPPRESS)
    parser.add_argument("--reviewed-integrations", help=argparse.SUPPRESS)
    parser.add_argument("--schedule", action="store_true", help="schedule reviewed social posts for publication")
    parser.add_argument("--alternate-caption", help=argparse.SUPPRESS)
    parser.add_argument("--final-tag", help=argparse.SUPPRESS)
    parser.add_argument("--reviewed-caption", help=argparse.SUPPRESS)
    parser.add_argument("--reviewed-youtube-title", help=argparse.SUPPRESS)
    parser.add_argument("--reviewed-threads-caption", help=argparse.SUPPRESS)
    parser.add_argument("--text-networks", help="confirmed text-only destinations, comma separated")
    parser.add_argument("--ui-lang", choices=("English", "Spanish"), help="language for placement and cover messages")
    parser.add_argument("--dry-run", action="store_true", help="show the plan; create nothing")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    args = parser.parse_args()

    out = sys.stdout
    if args.json:
        sys.stdout = sys.stderr  # progress lines (e.g. "Transcoding video...") must not mix with the JSON
    env = pmlib.load_env()
    if args.revise_copy:
        if not args.json or args.schedule:
            raise PMError("Caption revision requires JSON preview mode.")
        try:
            snapshot = json.loads(args.revise_copy)
        except ValueError as exc:
            raise PMError("Invalid reviewed plan.") from exc
        out.write(json.dumps(revise_copy(env, snapshot, args.instruction, args.edited_caption), ensure_ascii=False) + "\n")
        return 0
    if args.schedule and (args.dry_run or not args.reviewed_caption or not args.reviewed_when):
        raise PMError("Scheduling requires a reviewed caption and time.")
    for path in args.media:
        if not os.path.isfile(os.path.expanduser(path)):
            raise PMError("Media file not found: " + path)
    zone = env.get("PM_TIMEZONE", "America/Guayaquil")
    tz = ZoneInfo(zone) if ZoneInfo else timezone(timedelta(hours=-5))
    now = datetime.now(tz)
    p = plan(env, args.instruction, args.media, args.lang, now, placement_override=args.placement,
             cover_image=args.cover_image, cover_second=args.cover_second, ui_lang=args.ui_lang,
             text_networks=args.text_networks.split(",") if args.text_networks is not None else None)
    if args.final_tag is not None:
        p["final_tag"] = args.final_tag
    if args.dry_run and args.alternate_caption:
        p["alternate_caption"] = args.alternate_caption
    if args.reviewed_integrations is not None:
        p["reviewed_integrations"] = [item for item in args.reviewed_integrations.split(",") if item]
    if not args.dry_run and args.reviewed_caption:
        p["reviewed_caption"] = args.reviewed_caption
        p["reviewed_threads_caption"] = args.reviewed_threads_caption
        p["reviewed_youtube_title"] = args.reviewed_youtube_title
    if args.reviewed_when and not args.dry_run:
        try:
            when = datetime.fromisoformat(args.reviewed_when.replace("Z", "+00:00"))
            if when.tzinfo is None or when < now + MIN_SCHEDULE_LEAD:
                raise ValueError
        except ValueError as exc:
            raise PMError("La hora revisada ya pasó o faltan menos de 5 minutos. Vuelve a hornear el plan."
                          if p["ui_lang"] == "Spanish" else
                          "The reviewed time is past or less than 5 minutes away. Bake the plan again.") from exc
        p["when"] = when.astimezone(tz)
    result = run(env, p, args.dry_run, schedule=args.schedule)
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
