# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Outbound-only Telegram status and heartbeat worker. No publishing actions."""
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from postforge_v2 import OPENER, services

STATE = Path("/state/telegram.json")


class TelegramError(Exception):
    def __init__(self, retry_after=0):
        self.retry_after = retry_after


def telegram(token, method, **payload):
    url = f"https://api.telegram.org/bot{token}/{method}"
    request = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        with OPENER.open(request, timeout=35 if method == "getUpdates" else 8) as response:
            result = json.loads(response.read(1_048_576))
        if result.get("ok") is True:
            return result["result"]
    except urllib.error.HTTPError as exc:
        with exc:
            try:
                delay = json.loads(exc.read(4096)).get("parameters", {}).get("retry_after", 0)
            except (ValueError, AttributeError):
                delay = 0
        raise TelegramError(delay if isinstance(delay, int) else 0) from None
    except (OSError, ValueError, KeyError, AttributeError):
        pass
    # urllib errors can contain the URL, including the bot token.
    raise TelegramError() from None


def is_owner(message, owner):
    return (message.get("chat", {}).get("type") == "private"
            and message.get("chat", {}).get("id") == owner
            and message.get("from", {}).get("id") == owner)


def send_status(call, owner, es, heartbeat=False):
    title = ("PostForge sigue activo" if heartbeat else "Estado de PostForge") if es else (
        "PostForge heartbeat" if heartbeat else "PostForge status")
    checks = services()
    lines = [f"{name}: {('disponible' if up else 'sin respuesta') if es else ('reachable' if up else 'unreachable')}"
             for name, up in checks.items()]
    note = ("La sesión de WhatsApp y el programador no se verifican aquí." if es else
            "WhatsApp pairing and the scheduler are not checked here.")
    call("sendMessage", chat_id=owner, text="\n".join([title, *lines, note]),
         reply_markup={"inline_keyboard": [[{"text": "Actualizar estado" if es else "Refresh status",
                                             "callback_data": "status"}]]})


def handle(call, update, owner, es):
    if message := update.get("message"):
        if is_owner(message, owner):
            command = message.get("text", "").split(maxsplit=1)
            if command and command[0] in ("/start", "/status"):
                send_status(call, owner, es)
    elif callback := update.get("callback_query"):
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        if (chat.get("type") == "private" and chat.get("id") == owner
                and (callback.get("from") or {}).get("id") == owner
                and callback.get("data") == "status"):
            call("answerCallbackQuery", callback_query_id=callback["id"])
            send_status(call, owner, es)


def save_state(state):
    temporary = STATE.with_suffix(".tmp")
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as handle:
        json.dump(state, handle)
    temporary.replace(STATE)


def run():
    try:
        token = Path(os.environ["TELEGRAM_TOKEN_FILE"]).read_text(encoding="utf-8").strip()
        owner = int(os.environ["TELEGRAM_OWNER_ID"])
        minutes = int(os.environ.get("TELEGRAM_HEARTBEAT_MINUTES", "0"))
        if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{25,}", token) or owner < 1 or minutes not in range(0, 1441):
            raise ValueError
        if 0 < minutes < 5:
            raise ValueError
        configured_bot = os.environ.get("TELEGRAM_BOT_ID")
        if configured_bot and token.split(":", 1)[0] != configured_bot:
            raise ValueError
    except (KeyError, OSError, ValueError):
        raise SystemExit("Configure the Telegram token file, numeric owner ID and heartbeat (0 or 5–1440 minutes).") from None
    es = os.environ.get("TELEGRAM_LANGUAGE") == "es"

    def call(method, **payload):
        return telegram(token, method, **payload)

    conversation = None
    actions = None
    if os.environ.get("POSTFORGE_HOST_WORKER") == "1":
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts/lib"))
        import composer
        import pmlib
        from telegram_actions import Actions
        from telegram_flow import Conversation
        actions = Actions(pmlib.load_env(), call, token, lambda: send_status(call, owner, es))
        conversation = Conversation(STATE.with_name("conversation-" + token.split(":", 1)[0] + ".json"),
                                    owner, es, actions, call, composer.write_record)

    state = {"offset": 0, "heartbeat": 0}
    if STATE.exists():
        try:
            state.update(json.loads(STATE.read_text(encoding="utf-8")))
            if any(type(state[key]) is not int or state[key] < 0 for key in ("offset", "heartbeat")):
                raise ValueError
        except (OSError, ValueError, TypeError):
            raise SystemExit("Telegram state is unreadable. Repair the state file before restarting.") from None
    bot_id = token.split(":", 1)[0]
    if state.get("bot_id", bot_id) != bot_id:
        state = {"offset": 0, "heartbeat": 0}
    if state.get("owner_id", owner) != owner:
        state["heartbeat"] = 0
    state.update(bot_id=bot_id, owner_id=owner)
    save_state(state)
    delay = 1
    stop_file = os.environ.get("POSTFORGE_STOP_FILE")

    def stopping():
        return bool(stop_file and Path(stop_file).exists())

    while not stopping():
        try:
            now = int(time.time())
            if actions:
                actions.tick()
            if minutes and now >= state["heartbeat"] + minutes * 60:
                send_status(call, owner, es, heartbeat=True)
                state["heartbeat"] = now
                save_state(state)
            updates = call("getUpdates", offset=state["offset"], timeout=25, limit=25,
                           allowed_updates=["message", "callback_query"])
            for update in updates:
                if conversation:
                    conversation.handle(update)
                else:
                    handle(call, update, owner, es)
                state["offset"] = update["update_id"] + 1
                save_state(state)
            delay = 1
        except TelegramError as exc:
            wait = max(delay, min(exc.retry_after, 900))
            print(f"Telegram is unavailable; retrying in {wait}s.", flush=True)
            for _ in range(wait):
                if stopping():
                    return
                time.sleep(1)
            delay = min(delay * 2, 60)
