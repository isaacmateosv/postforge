#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""JSON-over-stdin bridge. Never opens a network listener or returns credentials."""
import contextlib
import io
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts/lib"))
import composer
import pmlib
import manage_posts


def dispatch(operation, payload):
    env = pmlib.load_env()
    if operation == "options":
        result = composer.options(env)
        raw = env.get("FRONTEND_URL", env.get("POSTIZ_LOCAL_URL", "http://localhost:4200"))
        parsed = urlsplit(raw)
        if (parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                or not parsed.hostname or parsed.scheme not in ("https", "http")
                or (parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1"))):
            raise pmlib.PMError("Configure a valid Postiz origin.")
        result["calendar_url"] = raw.rstrip("/") + "/launches"
        result["version"] = (ROOT / "VERSION").read_text().strip()
        result["workspace"] = str(ROOT)
        return result
    if operation == "preview":
        return composer.preview(env, payload)
    if operation == "revise":
        return composer.revise(env, payload["review_id"], payload.get("edited"))
    if operation == "submit":
        return composer.submit(env, payload["review_id"], payload["mode"])
    if operation in ("cleanup_preview", "cleanup"):
        client = pmlib.Postiz(env)
        return (manage_posts.snapshot(env, payload["scope"], client) if operation == "cleanup_preview"
                else manage_posts.clear(env, payload, client))
    if operation == "help":
        language = "es" if payload.get("language") == "es" else "en"
        level = "technical" if payload.get("technical") else "quick"
        return {"markdown": (ROOT / "docs/help" / (level + "-" + language + ".md")).read_text()}
    if operation == "approve_status":
        import host_agent
        import whatsapp_pending
        host_agent.start()
        identifier = whatsapp_pending.approve(payload["id"], source="desktop-review")
        if not identifier:
            raise pmlib.PMError("This Status is no longer waiting for approval.")
        return {"approved": identifier}
    if operation.startswith("telegram_"):
        import telegram_settings
        if operation == "telegram_resume":
            if telegram_settings.active(telegram_settings.configuration()):
                import host_agent
                host_agent.start()
            return telegram_settings.status()
        actions = {"telegram_status": lambda: telegram_settings.status(),
                   "telegram_inspect": lambda: telegram_settings.inspect(payload),
                   "telegram_detect": lambda: telegram_settings.detect(payload),
                   "telegram_save": lambda: telegram_settings.save(payload)}
        if operation in actions:
            return actions[operation]()
    raise pmlib.PMError("Unknown desktop operation.")


def main():
    try:
        message = json.loads(sys.stdin.buffer.read(1_048_577))
        with contextlib.redirect_stdout(io.StringIO()):
            result = dispatch(message["operation"], message.get("payload") or {})
        response = {"ok": True, "result": result}
    except Exception as error:
        response = {"ok": False, "error": str(error)[:1200] if isinstance(error, (pmlib.PMError, ValueError))
                    else "The local planner could not complete this request. Check local services and setup."}
    print(json.dumps(response, ensure_ascii=False))


if __name__ == "__main__":
    main()
