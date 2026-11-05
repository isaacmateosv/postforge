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

# Caption A/B 2026-10-30 (scripts/caption-ab.sh, logs/caption-ab/): small models follow examples
# better than rules and drift into English when the instructions are in English, so Spanish has its
# own prompt; and the call to action was their most common mistake (a shop to visit, odd verb
# forms). So the model writes one or two sentences and topic hashtags, and the call to action and
# brand hashtags are fixed text added here. The owner's blind test set the facts and voice: no shop
# (orders are picked up or sent by Uber courier), premium tone, Ecuadorian Spanish.
# CAPTION_CTA_ES / CAPTION_CTA_EN in .env replace the call to action.
CTA = {
    "Spanish": "Haz tu pedido por WhatsApp y retíralo o recíbelo con Uber.",
    "English": "Order on WhatsApp, then pick it up or have it delivered by Uber.",
}
CTA_SETTING = {"Spanish": "CAPTION_CTA_ES", "English": "CAPTION_CTA_EN"}
# These networks have no text-only posts; Postiz would accept the draft and fail when publishing.
NEEDS_MEDIA = {"instagram": "Instagram", "instagram-standalone": "Instagram", "tiktok": "TikTok",
               "youtube": "YouTube"}
BRAND_TAGS = {
    "Spanish": ["#AlmaDulce", "#ReposteríaGourmet", "#BajoPedido"],
    "English": ["#AlmaDulce", "#GourmetPastry", "#MadeToOrder"],
}

PROMPT = """You write Instagram and Facebook captions for Alma Dulce Bakery, a gourmet, avant-garde pastry kitchen in Ecuador that works only to order. Everything is fresh: baked the same day, with sourdough cared for daily. Its voice is refined and warm: a premium experience at accessible prices.

Example topic: Chocolate raspberry cake, made to order
Example caption:
Dark chocolate and fresh raspberries in a cake made for your special moments. 🍫
#ChocolateCake #Raspberries #Celebrations

Example topic: Mother's Day orders until Thursday
Example caption:
Surprise mom with something handmade, with all the care she deserves. 💐 We take orders until Thursday.
#MothersDay #HandmadeGifts #Pastry

Now write ONE caption in {lang} about: {topic}
- 1 or 2 short sentences about the topic. At most 2 emojis, only ones that fit the product; if unsure, none.
- Don't say how to order and don't mention a shop, store or neighborhood: we add that part.
- Use only the facts in the topic: don't invent prices, dates, times or addresses.
- On the next line, 3 to 5 hashtags about the topic.
Return only the caption, with no preamble or quotation marks."""

PROMPT_ES = """Escribes publicaciones para Instagram y Facebook de Alma Dulce Bakery, una repostería gourmet de vanguardia en Ecuador que trabaja solo bajo pedido. Todo es fresco: se hornea el mismo día y la masa madre se cuida a diario. Su estilo es elegante y cálido: una experiencia premium a precios accesibles.

Ejemplo de tema: Torta de chocolate y frambuesa por encargo
Ejemplo de publicación:
Chocolate intenso y frambuesas frescas en una torta pensada para tus momentos especiales. 🍫
#TortaDeChocolate #Frambuesas #Celebraciones

Ejemplo de tema: Pedidos para el Día de la Madre hasta el jueves
Ejemplo de publicación:
Sorprende a mamá con un detalle hecho a mano, con todo el cariño que merece. 💐 Recibimos pedidos hasta el jueves.
#DiaDeLaMadre #RegalosHechosAMano #Repostería

Ahora escribe UNA publicación sobre: {topic}
- Español de Ecuador. De 1 a 2 frases cortas sobre el tema. Máximo 2 emojis, solo si encajan con el producto; si dudas, ninguno.
- No escribas cómo pedir ni menciones un local, una tienda o un barrio: eso lo agregamos nosotros.
- No uses las palabras "dulces" ni "recoger".
- Usa solo los datos del tema: no inventes precios, fechas, horarios ni direcciones.
- En la línea siguiente, de 3 a 5 hashtags en español sobre el tema.
Devuelve solo la publicación, sin introducción ni comillas."""

PREAMBLE = re.compile(r"^¡?(here(?:'s| is)|sure|caption|aquí (?:tienes|está)|claro|por supuesto)\b[^\n]*:\s*\n+",
                      re.IGNORECASE)
HASHTAG = re.compile(r"#\w+")
TRAILING_TAGS = re.compile(r"(?:\s*#\w+)+\s*$")
SEPARATOR = re.compile(r"\s*[_=*~—–-]{3,}\s*")
SENTENCE = re.compile(r"[^.!?…]+(?:[.!?…]+|$)")
ORDER_CHANNEL = re.compile(r"\b(whatsapp|uber|dm|inbox|mensaje|message)\b", re.IGNORECASE)
# Emoji guard (owner's blind test 2026-10-31: 🍎 for figs, 🥭/🥔 for pan de yuca, 🍰 for guaguas, 💔 for
# Día de Difuntos, 🚚 for deliveries; "if unsure, better none"). Kept: always-safe ones, and food or
# occasion emojis only when the topic or caption names that thing. Everything else goes.
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B50\u2B55]\uFE0F?(?:\u200D[\U0001F000-\U0001FAFF\u2600-\u27BF]\uFE0F?)*")
EMOJI_SWAP = {"🚚": "🛵", "🚛": "🛵", "📦": "🛵", "💔": "🤍"}
# Sentences that copy the prompt's rules into the caption (the 3B did), and claims of baking in the
# mornings: the owner bakes fresh the same day, not necessarily in the morning.
INSTRUCTION_ECHO = re.compile(r"frases? cortas?|sobre el tema|short sentences?|about the topic|\bemojis?\b|"
                              r"\bhashtags?\b|español de ecuador|si dudas|if unsure", re.IGNORECASE)
MORNING_CLAIM = re.compile(r"(every|each) morning|mornings|(todas las|cada|por las|en las) mañanas?", re.IGNORECASE)
EMOJI_ALWAYS = set("❤🤍🧡💛🫶✨🌟🙂😊😋🥰📲")
EMOJI_IF = {
    "🍞": ("pan", "guagua", "bread", "sourdough", "masa madre", "loaf", "loaves"),
    "🥐": ("croissant", "cachito"), "🎂": ("torta", "cumple", "pastel", "cake", "birthday"),
    "🧁": ("cupcake", "magdalena"), "🍪": ("galleta", "cookie"), "☕": ("café", "cafe", "coffee"),
    "🍵": ("té ", "tea "), "🍫": ("chocolate", "cacao"), "🍓": ("fresa", "frutilla", "strawberr"),
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
    words = (topic + " " + text).lower()
    kept = []

    def judge(match):
        emoji = EMOJI_SWAP.get(match.group(0), match.group(0))
        base = emoji.replace("\uFE0F", "")
        fits = base in EMOJI_ALWAYS or any(w in words for w in EMOJI_IF.get(base, ()))
        if not fits or len(kept) >= 2:
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
    """A model's answer as a caption: no preamble or wrapping quotes, only emojis that fit (at most 2),
    no repeated sentence, no sentence of its own on how to order (unless that's all it wrote), then
    the fixed call to action, then the hashtags (the topic's, then the brand's) on one line after a
    blank line, at most 8, no repeats. Empty if the model wrote no sentence."""
    body, tags = split_hashtags(PREAMBLE.sub("", text.strip()).strip().strip('"').strip())
    body = re.sub(r"[ \t]{2,}", " ", fitting_emojis(body, topic)).strip()
    body = drop_repeats(body, topic)
    if not re.search(r"\w", body):
        return ""  # nothing but emojis or punctuation survived
    lines = ("".join(s for s in SENTENCE.findall(line) if not ORDER_CHANNEL.search(s)).strip()
             for line in body.splitlines())
    kept = "\n".join(line for line in lines if line)
    if not re.search(r"\w", kept):
        kept = ""  # only emojis or punctuation were left
    if not body:
        return ""
    lang = language(lang)
    cta = (env or {}).get(CTA_SETTING.get(lang, ""), "").strip() or CTA.get(lang, "")
    if not kept:
        cta = ""  # a topic about ordering: the model's sentences are the call to action
    body = kept or body
    unique = []
    for tag in tags[:5] + BRAND_TAGS.get(lang, []):
        if tag.lower() not in {t.lower() for t in unique}:
            unique.append(tag)
    caption = body + ("\n" + cta if cta else "")
    return caption + ("\n\n" + " ".join(unique[:8]) if unique else "")


def ollama_caption(env, topic, lang):
    base = env.get("OLLAMA_HOST_URL", "http://localhost:11434").rstrip("/")
    model = env.get("LOCAL_LLM_MODEL", "llama3.2:3b")  # picked in the owner's blind test, 2026-10-31
    seconds = 0.0
    for attempt in (1, 2):  # a second try when the guards leave nothing usable
        try:
            status, data = pmlib.http("POST", base + "/api/generate", body={
                "model": model,
                "prompt": build_prompt(topic, lang),
                "stream": False,
                "keep_alive": 0,  # evict from unified memory as soon as the caption is done
                # captions need < 1k tokens; a 2048 context halves the KV cache (target: 8 GB MacBook Air)
                # 0.5: steadier wording from small models (the A/B saw "se desploman por la ciudad" at 0.7)
                "options": {"temperature": 0.5, "num_predict": 260, "num_ctx": 2048},
            }, timeout=600)
        except PMError:
            raise PMError("Ollama is not reachable at %s. Run ./publish-machine.sh start." % base)
        if status != 200 or not isinstance(data, dict):
            raise PMError("Ollama returned HTTP %s: %s" % (status, str(data)[:300]))
        seconds += data.get("total_duration", 0) / 1e9
        text = finish(data.get("response", ""), lang, env, topic)
        if text:
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
