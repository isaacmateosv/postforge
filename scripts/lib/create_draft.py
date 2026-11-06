#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Zero-cost path of the Dual-AI design: native Ollama (Metal GPU) drafts a caption and
the result is staged in Postiz as a DRAFT (HITL guardrail, never auto-published).

Drafts go through the Postiz Public API instead of raw SQL: Postiz itself fills the
NOT NULL relations ("group", integrationId, publishDate, settings JSON) and starts no
publish workflow for DRAFT posts.
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmlib  # noqa: E402
from pmlib import PMError, info  # noqa: E402

# An optional call to action can be configured per language.
CTA_SETTING = {"Spanish": "CAPTION_CTA_ES", "English": "CAPTION_CTA_EN"}
NEEDS_MEDIA = {"instagram": "Instagram", "instagram-standalone": "Instagram", "tiktok": "TikTok",
               "youtube": "YouTube"}

PROMPT = """Write one social media caption in {lang} about: {topic}
- Write like a person talking to their audience. Use at most two short sentences. Lead with a specific detail from the topic, then ask at most one question. Avoid stock openings such as “Enjoy our delicious”.
- Use zero to two emojis only if they fit the subject. Put them after a complete sentence.
- Use only the facts in the topic. Do not invent a business name, prices, dates, locations or contact details.
- Leave one blank line, then add 2 to 4 specific hashtags on one line. Every tag starts with # and contains no spaces, for example #WeekendHike. Skip generic tags and locations not given.
Return only the caption."""

PROMPT_ES = """Escribe una publicación en español de Ecuador sobre: {topic}
- Escribe máximo 28 palabras antes de los hashtags. Una o dos frases naturales, sin saludo ni introducción. Abre con el producto o la ocasión. Una sola pregunta, si aporta.
- Usa el nombre del equipo o la marca tal como se indicó. Evita frases de cajón como «Disfruta de nuestros deliciosos», «la combinación perfecta» o «el regalo perfecto». Cuida la concordancia.
- Ejemplo de tono para otro tema: «¿Qué planta pondrías junto a tu ventana? 🌿». No copies el ejemplo.
- Usa hasta dos emojis solo si aportan al texto. Ponlos al final de una frase completa.
- Usa solo los datos del tema. No inventes frescura, ingredientes, capas, disponibilidad, regalos, precios, fechas, lugares ni datos de contacto.
- Deja una línea en blanco y añade de 2 a 4 hashtags concretos en una sola línea. Cada etiqueta empieza con # y va sin espacios, por ejemplo #RutaDeMontaña. Evita etiquetas genéricas y lugares que no se mencionaron.
Devuelve solo la publicación."""

PREAMBLE = re.compile(r"^¡?(here(?:'s| is)|sure|caption|aquí (?:tienes|está)|claro|por supuesto)\b[^\n]*:\s*\n+",
                      re.IGNORECASE)
HASHTAG = re.compile(r"#\w+")
TRAILING_TAGS = re.compile(r"(?:\s*#\w+)+\s*$")
SEPARATOR = re.compile(r"\s*[_=*~—–-]{3,}\s*")
SENTENCE = re.compile(r"[^.!?…]+(?:[.!?…]+|$)")
ORDER_CHANNEL = re.compile(r"\b(whatsapp|uber|dm|inbox|mensaje|message)\b", re.IGNORECASE)
# Keep contextual emojis only when the topic or caption supports them.
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B50\u2B55]\uFE0F?(?:\u200D[\U0001F000-\U0001FAFF\u2600-\u27BF]\uFE0F?)*")
EMOJI_SWAP = {"🚚": "🛵", "🚛": "🛵", "📦": "🛵", "💔": "🤍"}
# Remove leaked instructions and unsupported claims about recurring morning activity.
INSTRUCTION_ECHO = re.compile(r"frases? cortas?|sobre el tema|short sentences?|about the topic|\bemojis?\b|"
                              r"\bhashtags?\b|español de ecuador|si dudas|if unsure", re.IGNORECASE)
MORNING_CLAIM = re.compile(r"(every|each) morning|mornings|(todas las|cada|por las|en las) mañanas?", re.IGNORECASE)
EMOJI_ALWAYS = set("❤🤍🧡💛🫶✨🌟🙂😊😋🥰📲")
EMOJI_IF = {
    "🍓": ("fresa", "frutilla", "strawberr"),
    "⚽": ("fútbol", "futbol", "football", "soccer", "liga deportiva"),
    "🍞": ("pan", "guagua", "bread", "sourdough", "masa madre", "loaf", "loaves"),
    "🥐": ("croissant", "cachito"), "🎂": ("torta", "cumple", "pastel", "cake", "birthday"),
    "🧁": ("cupcake", "magdalena"), "🍪": ("galleta", "cookie"), "☕": ("café", "cafe", "coffee"),
    "🍵": ("té ", "tea "), "🍫": ("chocolate", "cacao"),
    "🫐": ("arándano", "arandano", "mora", "blueberr", "blackberr"), "🍋": ("limón", "limon", "lemon"),
    "🍯": ("miel", "honey"), "🧀": ("queso", "cheese"), "🥥": ("coco", "coconut"),
    "🍌": ("banano", "guineo", "banana"), "🍊": ("naranja", "orange"), "🍎": ("manzana", "apple"),
    "🎄": ("navidad", "christmas", "holiday", "festiv"), "🎁": ("regalo", "gift", "caja", "box"),
    "🎉": ("cumple", "celebr", "fiesta", "birthday", "party"), "💐": ("madre", "mamá", "mother", "flor", "flower"),
    "🕯": ("difuntos", "day of the dead", "dearly departed", "recuerd", "remember", "memor"),
    "🛵": ("uber", "envío", "envio", "entrega", "domicilio", "deliver"),
    "🚗": ("uber", "envío", "envio", "entrega", "domicilio", "deliver"),
}


def language(lang):
    """'Spanish' or 'English' for the usual spellings, else the language as given."""
    key = lang.strip().lower()
    if key in ("spanish", "español", "espanol", "es"):
        return "Spanish"
    if key in ("english", "inglés", "ingles", "en"):
        return "English"
    return lang.strip()


def build_prompt(topic, lang):
    if language(lang) == "Spanish":
        return PROMPT_ES.format(topic=topic)
    return PROMPT.format(topic=topic, lang=lang)


def split_hashtags(text):
    """(body, hashtags): hashtag-only lines and a trailing run of hashtags move out of the body,
    hashtags inside a sentence stay put, separator lines (____) go."""
    body, tags = [], []
    for line in text.splitlines():
        if SEPARATOR.fullmatch(line):
            continue
        # Repair a split CamelCase tag only on tag-led lines, preserving inline prose.
        if line.lstrip().startswith("#"):
            line = re.sub(r"(#\w+)[ \t]+([A-ZÁÉÍÓÚÜÑ]\w*)(?=[ \t]*(?:#|$))", r"\1\2", line)
        if HASHTAG.search(line) and not HASHTAG.sub("", line).strip(" \t.,;·|-"):
            tags += HASHTAG.findall(line)
        else:
            body.append(line)
    while body and not body[-1].strip():
        body.pop()
    if body:
        tail = TRAILING_TAGS.search(body[-1])
        if tail and tail.start() > 0:
            tags = HASHTAG.findall(tail.group(0)) + tags
            body[-1] = body[-1][:tail.start()].rstrip()
    return "\n".join(body).strip(), tags


def fitting_emojis(text, topic=""):
    """Swap or drop emojis that don't fit (EMOJI_* above); keep at most 2."""
    words = (topic or text).lower()
    kept = []

    def judge(match):
        emoji = EMOJI_SWAP.get(match.group(0), match.group(0))
        base = emoji.replace("\uFE0F", "")
        if base == "🎂" and any(term in words for term in ("frutilla", "fresa", "strawberr")):
            emoji = base = "🍓"
        fits = base in EMOJI_ALWAYS or any(re.search(r"(?<!\w)" + re.escape(w), words) for w in EMOJI_IF.get(base, ()))
        if not fits or emoji in kept or len(kept) >= 2:
            return ""
        kept.append(emoji)
        return emoji

    return EMOJI.sub(judge, text)


def drop_repeats(body, topic=""):
    """Keep the first of repeated sentences (the 3B sometimes says one twice), and drop sentences that
    echo the prompt's rules or claim morning baking (unless the topic says so)."""
    seen, lines = set(), []
    for line in body.splitlines():
        out = []
        for sentence in SENTENCE.findall(line):
            key = re.sub(r"[^\w]+", " ", sentence.lower()).strip()
            if (key and key in seen) or INSTRUCTION_ECHO.search(sentence) or \
                    (MORNING_CLAIM.search(sentence) and not MORNING_CLAIM.search(topic)):
                continue
            seen.add(key)
            out.append(sentence)
        lines.append("".join(out).strip())
    return "\n".join(line for line in lines if line)


def finish(text, lang="English", env=None, topic=""):
    """Clean generated copy and append the operator's optional call to action."""
    body, tags = split_hashtags(PREAMBLE.sub("", text.strip()).strip().strip('"').strip())
    body = re.sub(r"[ \t]{2,}", " ", fitting_emojis(body, topic)).strip()
    body = re.sub(r"[ \t]*((?:" + EMOJI.pattern + r"[ \t]*)+)([.!?])",
                  lambda match: match[2] + " " + match[1].strip(), body)
    body = drop_repeats(re.sub(r"[ \t]+([,.!?;:])", r"\1", body), topic)
    if not re.search(r"\w", body):
        return ""  # nothing but emojis or punctuation survived
    if not EMOJI.search(body) and topic:
        words = topic.lower()
        for emoji, terms in EMOJI_IF.items():
            if any(re.search(r"(?<!\w)" + re.escape(term), words) for term in terms):
                body += " " + emoji
                break
    lang = language(lang)
    cta = (env or {}).get(CTA_SETTING.get(lang, ""), "").strip()
    if cta or not ORDER_CHANNEL.search(topic):
        kept = "\n".join("".join(s for s in SENTENCE.findall(line) if not ORDER_CHANNEL.search(s)).strip()
                         for line in body.splitlines()).strip()
        if re.search(r"\w", kept):
            body = kept
        else:
            cta = ""
    unique = []
    for tag in tags:
        if tag.lower() not in {t.lower() for t in unique}:
            unique.append(tag)
    caption = body + ("\n" + cta if cta else "")
    return caption + ("\n\n" + " ".join(unique[:5]) if unique else "")


def ollama_caption(env, topic, lang, *, previous=None):
    base = env.get("OLLAMA_HOST_URL", "http://localhost:11434").rstrip("/")
    model = env.get("LOCAL_LLM_MODEL", "llama3.2:3b")  # picked in the owner's blind test, 2026-10-31
    seconds = 0.0
    prompt = build_prompt(topic, lang)
    if previous:
        instruction = ("Redacta una alternativa con un inicio diferente. Conserva los hechos del tema."
                       if language(lang) == "Spanish" else
                       "Write an alternative with a different opening. Keep the facts from the topic.")
        prompt += f"\n\n{instruction}\n<previous-caption>\n{previous[:600]}\n</previous-caption>"
    for attempt in (1, 2):  # a second try when the guards leave nothing usable
        try:
            status, data = pmlib.http("POST", base + "/api/generate", body={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "keep_alive": 0,  # evict from unified memory as soon as the caption is done
                # captions need < 1k tokens; a 2048 context halves the KV cache (target: 8 GB MacBook Air)
                # 0.5: steadier wording from small models (the A/B saw "se desploman por la ciudad" at 0.7)
                "options": {"temperature": 0.65 if previous else 0.5, "num_predict": 180, "num_ctx": 2048},
            }, timeout=600)
        except PMError:
            raise PMError("Ollama is not reachable at %s. Run ./publish-machine.sh start." % base)
        if status != 200 or not isinstance(data, dict):
            raise PMError("Ollama returned HTTP %s: %s" % (status, str(data)[:300]))
        seconds += data.get("total_duration", 0) / 1e9
        text = finish(data.get("response", ""), lang, env, topic)
        if text and (not previous or text.casefold() != previous.casefold()):
            return text, model, round(seconds, 1)
    raise PMError("The model's caption didn't pass the checks twice. Try again, or pass your own text with --no-ai.")


def main():
    parser = argparse.ArgumentParser(
        prog="create-draft.sh",
        description="Draft a caption with the local model and stage it in Postiz as a DRAFT.",
        epilog=(
            "examples:\n"
            "  ./scripts/create-draft.sh \"Pumpkin spice croissants are back this weekend\"\n"
            "  ./scripts/create-draft.sh --lang Spanish --media data/postiz-uploads/rolls.jpg \"Cinnamon rolls\"\n"
            "  ./scripts/create-draft.sh --no-ai \"Exact caption text to stage as-is\"\n"
            "  ./scripts/create-draft.sh --channel instagram --dry-run \"Sourdough Sunday\""
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("topic", help="what the post is about (or the literal caption with --no-ai)")
    parser.add_argument("--channel", help="Postiz channel id, provider (instagram, facebook...) or name; "
                                          "default: first connected channel")
    parser.add_argument("--media", help="optional image/video to attach (uploaded to the Postiz library)")
    parser.add_argument("--lang", default=None, help="caption language (default: CAPTION_LANGUAGE or English)")
    parser.add_argument("--no-ai", action="store_true", help="skip Ollama; stage the topic text verbatim")
    parser.add_argument("--settings", type=json.loads, default=None,
                        help='provider settings JSON merged over the defaults, e.g. \'{"post_type": "story"}\'')
    parser.add_argument("--dry-run", action="store_true", help="generate the caption but stage nothing")
    args = parser.parse_args()

    env = pmlib.load_env()
    lang = args.lang or env.get("CAPTION_LANGUAGE", "English")

    info("======================================================")
    info("  LOCAL AI DRAFT PIPELINE (Ollama -> Postiz DRAFT)")
    info("======================================================")

    postiz = pmlib.Postiz(env)
    channel = None
    if not args.dry_run:
        info("[1/4] Selecting Postiz channel...")
        channel = postiz.pick_integration(args.channel)
        info("      %s (%s) id=%s" % (channel.get("name"), channel.get("identifier"), channel.get("id")))
        network = NEEDS_MEDIA.get(channel.get("identifier"))
        if network and not args.media:
            raise PMError("%s posts need a photo or video: add --media <file>." % network)
    else:
        info("[1/4] Dry run: channel selection skipped.")

    if args.no_ai:
        caption, model, seconds = args.topic, "none (--no-ai)", 0
        info("[2/4] Using the provided text verbatim.")
    else:
        info("[2/4] Drafting caption with local %s (Metal GPU, evicted after use)..."
             % env.get("LOCAL_LLM_MODEL", "llama3.2:3b"))
        caption, model, seconds = ollama_caption(env, args.topic, lang)
    info("\n--- CAPTION ---\n%s\n---------------\n" % caption)

    if args.dry_run:
        info("[3/4] Dry run: nothing uploaded or staged.")
        return 0

    media, short = [], False
    if args.media:
        path = os.path.expanduser(args.media)
        if not os.path.isfile(path):
            raise PMError("Media file not found: " + path)
        tmp = tempfile.mkdtemp(prefix="pm-draft-")
        try:
            kind, ready = pmlib.normalize_media(path, tmp)  # JPEG/PNG or H.264 MP4 (TikTok needs .mp4)
            short = pmlib.youtube_short(channel.get("identifier"), kind, ready)
            info("[3/4] Uploading the %s to the Postiz library..." % kind)
            uploaded = postiz.upload(ready)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        media = [{"id": uploaded["id"], "path": uploaded["path"]}]
        info("      %s" % uploaded["path"])
    else:
        info("[3/4] No media attached.")

    info("[4/4] Staging DRAFT in Postiz (HITL: requires manual approval)...")
    created = postiz.create_draft(channel, caption, media, settings=args.settings, short=short)
    post_id = created[0]["postId"] if created else None
    pmlib.append_log("drafts.jsonl", {
        "source": "create-draft", "post_id": post_id, "channel": channel.get("identifier"),
        "integration_id": channel.get("id"), "model": model, "llm_seconds": seconds,
        "media": media[0]["path"] if media else None, "caption": caption[:500],
    })
    info("      ✔ Draft %s created." % post_id)
    info("======================================================")
    info("  HITL ACTIVE: review & approve the draft in Postiz:")
    info("  https://%s/launches" % env.get("NGROK_DOMAIN", "<NGROK_DOMAIN>"))
    info("======================================================")
    return 0


if __name__ == "__main__":
    try:
        with pmlib.Job("draft", " ".join(sys.argv[1:])):  # `stop` and the menu bar app warn while it runs
            sys.exit(main())
    except PMError as exc:
        print("✖ " + str(exc), file=sys.stderr)
        sys.exit(2)
