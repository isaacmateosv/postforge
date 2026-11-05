#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Caption A/B: the same sample topics through each caption engine (DEPLOY-M1.md §2 option 1).

Every engine gets create_draft.py's exact prompt. Ollama models also get its options (context
2048, temperature 0.7, keep_alive 0), so each caption loads the model the way a real draft does.
For each caption it records the time, Ollama's memory for the loaded model (/api/ps, sampled
while it writes) and the prompt's rules: emojis, hashtags, sentences, language, and whether the caption adds unsupported numbers or contact details. Nothing is posted or staged.
Results: logs/caption-ab/<date>.json.

    ./scripts/caption-ab.sh                                  llama3 8B, llama3.2 3B (+ Gemini if GEMINI_ENABLED=true)
    ./scripts/caption-ab.sh --models llama3.2:3b --no-gemini one model only (e.g. on the Air)
"""
import argparse
import json
import os
import re
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmlib  # noqa: E402
from create_draft import PROMPT, PROMPT_ES, build_prompt, finish  # noqa: E402
from pmlib import PMError, info, warn  # noqa: E402

GEMINI_API = "https://generativelanguage.googleapis.com"
OUT_DIR = os.path.join(pmlib.LOGS_DIR, "caption-ab")
DEFAULT_MODELS = ["llama3.2:3b", "llama3:8b-instruct-q4_K_M"]
OPTIONS = {"temperature": 0.5, "num_predict": 260, "num_ctx": 2048}  # = create_draft.py

TOPICS = [
    ("Spanish", "Taller de fotografía el sábado 14 a las 10:00"),
    ("Spanish", "Nuevas bicicletas disponibles para alquiler"),
    ("Spanish", "Jornada de atención veterinaria preventiva"),
    ("English", "Applications are open for the beginner ceramics workshop"),
    ("English", "New bike tune-up appointments available this month"),
    ("English", "Community book exchange this Saturday"),
]

EMOJI = re.compile("[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF☀-➿⭐⭕]")
HASHTAG = re.compile(r"#\w+")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
CONTACT = re.compile(r"@\w|www\.|https?://|\.com\b|\+?\d[\d -]{7,}\d")
SENTENCE_END = re.compile(r"[.!?…]+(?=\s|$)")
WORDS = {
    "Spanish": set("el la los las de del que y en para con tu tus nuestro nuestra nuestros nuestras por "
                   "una un es te ya al lo se más".split()),
    "English": set("the and to of for with your our a an is in this that it on at you we are".split()),
}


def checks(text, topic, lang):
    """The prompt's rules, checked mechanically: {rule: passed}."""
    lines = text.splitlines()
    tag_lines = [i for i, line in enumerate(lines) if HASHTAG.search(line)]
    body = "\n".join(lines[:tag_lines[0]] if tag_lines else lines)
    tags = HASHTAG.findall(text)
    words = re.findall(r"[a-záéíóúñü]+", body.lower())
    other = "English" if lang == "Spanish" else "Spanish"
    sentences = [s for s in SENTENCE_END.split(EMOJI.sub("", body)) if re.search(r"\w", s)]
    invented = (set(NUMBER.findall(body)) - set(NUMBER.findall(topic))
                or ("$" in body and "$" not in topic) or ("%" in body and "%" not in topic)
                or bool(CONTACT.search(body)))
    return {
        "at most 2 emojis": len(EMOJI.findall(text)) <= 2,
        "3 to 5 hashtags": 3 <= len(tags) <= 5,
        "hashtags on one line after a blank line": len(tag_lines) == 1 and tag_lines[0] > 0
                                                  and not lines[tag_lines[0] - 1].strip(),
        "1 to 3 sentences": 1 <= len(sentences) <= 3,
        "right language": sum(w in WORDS[lang] for w in words) > sum(w in WORDS[other] for w in words),
        "no details beyond the topic": not invented,

    }


class MemorySampler(threading.Thread):
    """Polls Ollama's /api/ps while a caption is written; keeps the largest size seen for the model."""

    def __init__(self, base, model):
        super().__init__(daemon=True)
        self.base, self.model, self.done = base, model, threading.Event()
        self.size = self.vram = 0
        self.context = None

    def run(self):
        while not self.done.is_set():
            try:
                _, data = pmlib.http("GET", self.base + "/api/ps", timeout=5)
                for entry in (data or {}).get("models", []) if isinstance(data, dict) else []:
                    if entry.get("name") == self.model or entry.get("model") == self.model:
                        if entry.get("size", 0) > self.size:
                            self.size, self.vram = entry.get("size", 0), entry.get("size_vram", 0)
                            self.context = entry.get("context_length")
            except PMError:
                pass
            self.done.wait(0.2)


def ollama_caption(base, model, topic, lang, env):
    pmlib.http("POST", base + "/api/generate", body={"model": model, "keep_alive": 0}, timeout=60)  # start unloaded
    sampler = MemorySampler(base, model)
    sampler.start()
    started = time.time()
    try:
        status, data = pmlib.http("POST", base + "/api/generate", body={
            "model": model, "prompt": build_prompt(topic, lang), "stream": False,
            "keep_alive": 0, "options": OPTIONS}, timeout=600)
    finally:
        sampler.done.set()
        sampler.join()
    if status != 200 or not isinstance(data, dict):
        raise PMError("Ollama returned HTTP %s: %s" % (status, str(data)[:200]))
    tokens, gen_ns = data.get("eval_count", 0), data.get("eval_duration", 0)
    return {
        "caption": finish(data.get("response", ""), lang, env, topic),
        "seconds": round(time.time() - started, 2),
        "load_seconds": round(data.get("load_duration", 0) / 1e9, 2),
        "tokens": tokens,
        "tokens_per_s": round(tokens / (gen_ns / 1e9), 1) if gen_ns else None,
        "memory_bytes": sampler.size, "gpu_bytes": sampler.vram, "context": sampler.context,
    }


def gemini_caption(env, topic, lang):
    if not pmlib.gemini_enabled(env):
        raise PMError(pmlib.GEMINI_OFF)
    key = env.get("GEMINI_API_KEY", "")
    model = env.get("GEMINI_MODEL", "gemini-flash-latest")
    gen = {"temperature": OPTIONS["temperature"]}
    level = env.get("GEMINI_THINKING_LEVEL", "low").strip()
    if level:
        gen["thinkingConfig"] = {"thinkingLevel": level}
    body = {"contents": [{"role": "user", "parts": [{"text": build_prompt(topic, lang)}]}],
            "generationConfig": gen}
    url = GEMINI_API + "/v1beta/models/%s:generateContent" % model
    started = time.time()
    for attempt, pause in enumerate((0, 10, 30), 1):
        if pause:
            warn("      Gemini busy (HTTP %s); retrying in %ds (attempt %d/3)..." % (status, pause, attempt))
            time.sleep(pause)
        status, data = pmlib.http("POST", url, {"x-goog-api-key": key}, body, timeout=300)
        if status == 400 and "thinking" in str(data).lower() and "thinkingConfig" in gen:
            gen.pop("thinkingConfig")  # this model does not accept thinkingLevel; use its default
            status, data = pmlib.http("POST", url, {"x-goog-api-key": key}, body, timeout=300)
        if status not in (500, 503):  # no retry on 429 (quota or rate limit): it only adds requests
            break
    if status != 200:
        raise PMError("Gemini returned HTTP %s: %s" % (status, str(data)[:200]))
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        raise PMError("Gemini returned no caption: %s" % str(data)[:200])
    usage = data.get("usageMetadata", {})
    return {
        "caption": finish("".join(p.get("text", "") for p in parts if not p.get("thought")), lang, env, topic),
        "seconds": round(time.time() - started, 2),
        "tokens": usage.get("candidatesTokenCount"), "thinking_tokens": usage.get("thoughtsTokenCount"),
        "model_version": data.get("modelVersion", model),
    }


def run_engine(name, kind, write):
    info("\n=== %s ===" % name)
    results = []
    for index, (lang, topic) in enumerate(TOPICS):
        try:
            result = write(topic, lang)
            result["checks"] = checks(result["caption"], topic, lang)
            passed = sum(result["checks"].values())
            info("  %2d. %-7s %5.1f s  rules %d/%d  %s" % (index + 1, lang, result["seconds"], passed,
                                                         len(result["checks"]), result["caption"].split("\n")[0][:60]))
        except PMError as exc:
            result = {"error": str(exc)}
            warn("  %2d. %s" % (index + 1, exc))
        results.append(dict(result, topic=topic, lang=lang))
    return {"engine": name, "kind": kind, "results": results}


def summarize(engine):
    ok = [r for r in engine["results"] if "error" not in r]
    if not ok:
        return {"captions": 0}
    rules = [v for r in ok for v in r["checks"].values()]
    summary = {
        "captions": len(ok), "failed": len(engine["results"]) - len(ok),
        "median_seconds": sorted(r["seconds"] for r in ok)[len(ok) // 2],
        "rules_passed_pct": round(100.0 * sum(rules) / len(rules)),
        "per_rule": {rule: sum(r["checks"][rule] for r in ok) for rule in ok[0]["checks"]},
    }
    if engine["kind"] == "ollama":
        summary["peak_memory_gib"] = round(max(r["memory_bytes"] for r in ok) / 2 ** 30, 2)
        summary["all_on_gpu"] = all(r["gpu_bytes"] == r["memory_bytes"] for r in ok if r["memory_bytes"])
        speeds = sorted(r["tokens_per_s"] for r in ok if r["tokens_per_s"])
        summary["median_tokens_per_s"] = speeds[len(speeds) // 2] if speeds else None
        summary["median_load_seconds"] = sorted(r["load_seconds"] for r in ok)[len(ok) // 2]
    return summary


def main():
    parser = argparse.ArgumentParser(prog="caption-ab.sh", description=__doc__.split("\n")[0],
                                     epilog=__doc__.split("\n", 1)[1], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS, help="Ollama models to compare")
    parser.add_argument("--no-gemini", action="store_true", help="leave Gemini out")
    args = parser.parse_args()

    env = pmlib.load_env()
    base = env.get("OLLAMA_HOST_URL", "http://localhost:11434").rstrip("/")
    status, tags = pmlib.http("GET", base + "/api/tags", timeout=10)
    installed = {m.get("name") for m in tags.get("models", [])} if isinstance(tags, dict) else set()
    missing = [m for m in args.models if m not in installed and m + ":latest" not in installed]
    if missing:
        raise PMError("Not downloaded in Ollama: %s (ollama pull <model>)" % ", ".join(missing))
    use_gemini = not args.no_gemini
    if use_gemini and not pmlib.gemini_enabled(env):
        warn("Gemini is switched off (GEMINI_ENABLED in .env); leaving it out.")
        use_gemini = False
    if use_gemini and env.get("GEMINI_API_KEY", "") in ("", "your_gemini_api_key_here"):
        warn("GEMINI_API_KEY is not set; leaving Gemini out.")
        use_gemini = False

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, time.strftime("%Y%m%d-%H%M") + ".json")
    created = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    runs = [(m, "ollama", lambda topic, lang, m=m: ollama_caption(base, m, topic, lang, env)) for m in args.models]
    if use_gemini:
        runs.append((env.get("GEMINI_MODEL", "gemini-flash-latest"), "gemini",
                     lambda topic, lang: gemini_caption(env, topic, lang)))
    engines = []
    for name, kind, write in runs:
        engine = run_engine(name, kind, write)
        engine["summary"] = summarize(engine)
        engines.append(engine)
        with open(path, "w", encoding="utf-8") as fh:  # after each engine, so a slow API can't cost the rest
            json.dump({"created_at": created, "ollama_options": OPTIONS,
                       "prompts": {"English and others": PROMPT, "Spanish": PROMPT_ES},
                       "topics": TOPICS, "engines": engines}, fh, ensure_ascii=False, indent=1)

    info("\n%-28s %9s %9s %8s %7s %6s" % ("engine", "median s", "tokens/s", "memory", "rules", "fails"))
    for engine in engines:
        s = engine["summary"]
        memory = "%.2f GiB" % s["peak_memory_gib"] if "peak_memory_gib" in s else "cloud"
        info("%-28s %9s %9s %8s %6s%% %6s" % (engine["engine"][:28], s.get("median_seconds"),
                                            s.get("median_tokens_per_s", "-"), memory,
                                            s.get("rules_passed_pct"), s.get("failed")))
    info("\nResults: %s" % path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PMError as exc:
        print("✖ " + str(exc), file=sys.stderr)
        sys.exit(1)
