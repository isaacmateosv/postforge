#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Configure the optional PostForge Telegram worker without echoing its token."""
import argparse
import getpass
import os
import re
import sys
import tempfile
from pathlib import Path

from telegram_worker import TelegramError, is_owner, telegram

ROOT = Path(__file__).resolve().parent.parent


def private_write(path, value, mode):
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value + "\n")
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save(directory, token, owner, language, minutes):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink() or (os.name != "nt" and directory.stat().st_mode & 0o077):
        raise ValueError("The Telegram settings directory must be private (mode 700 on macOS and Linux).")
    # The interactive worker runs as the local user.
    private_write(directory / "token", token, 0o600)
    private_write(directory / "settings.env",
                  f"TELEGRAM_TRANSPORT=host\nTELEGRAM_BOT_ID={token.split(':', 1)[0]}\nTELEGRAM_OWNER_ID={owner}\nTELEGRAM_LANGUAGE={language}\n"
                  f"TELEGRAM_HEARTBEAT_MINUTES={minutes}", 0o600)


def pending_owners(updates):
    owners = set()
    for update in updates:
        message = update.get("message") or {}
        owner = (message.get("from") or {}).get("id")
        text = message.get("text", "")
        if type(owner) is int and owner > 0 and is_owner(message, owner) and text.strip() == "/start":
            owners.add(owner)
    return owners


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-id", type=int, help="numeric Telegram user ID; omit to detect a pending private /start")
    parser.add_argument("--language", choices=("en", "es"), default="en")
    parser.add_argument("--heartbeat", type=int, default=0, metavar="MINUTES")
    args = parser.parse_args()
    if args.heartbeat != 0 and not 5 <= args.heartbeat <= 1440:
        parser.error("Use 0 to turn the heartbeat off, or 5–1440 minutes.")
    if args.owner_id is not None and args.owner_id < 1:
        parser.error("The owner ID must be positive.")
    if not sys.stdin.isatty():
        parser.error("Run this from an interactive terminal so the token stays hidden.")
    try:
        token = getpass.getpass("BotFather token (hidden): ").strip()
        if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{25,}", token):
            raise ValueError("The token format is invalid.")
        bot = telegram(token, "getMe")
        if telegram(token, "getWebhookInfo").get("url"):
            raise ValueError("This bot has an active webhook. Use a dedicated bot or remove its webhook first.")
        owner = args.owner_id
        if owner is None:
            input("Send /start to this bot in your private Telegram chat, then press Enter. ")
            owners = pending_owners(telegram(token, "getUpdates", timeout=0, limit=100,
                                             allowed_updates=["message", "callback_query"]))
            if len(owners) != 1:
                raise ValueError("Could not identify one owner. Provide your numeric Telegram ID with --owner-id.")
            owner = owners.pop()
        if input(f"Configure @{bot['username']} for Telegram user {owner}? [y/N] ").strip().lower() != "y":
            return 0
        commands = [
            {"command": "start", "description": "Abrir PostForge" if args.language == "es" else "Open PostForge"},
            {"command": "new", "description": "Nueva publicación o anuncio" if args.language == "es" else "New post or announcement"},
            {"command": "status", "description": "Revisar servicios" if args.language == "es" else "Check services"},
            {"command": "cancel", "description": "Descartar el plan actual" if args.language == "es" else "Discard current plan"},
            {"command": "help", "description": "Mostrar el menú" if args.language == "es" else "Show the menu"},
        ]
        telegram(token, "setMyCommands", commands=commands, scope={"type": "chat", "chat_id": owner})
        save(ROOT / "run/telegram", token, owner, args.language, args.heartbeat)
        print("Telegram settings saved. On macOS run ./postforge.sh telegram start, then send /new in your private chat.")
        return 0
    except TelegramError:
        parser.exit(1, "Telegram could not validate the bot. Check the token, connectivity, and any other running poller.\n")
    except (OSError, ValueError, EOFError, KeyError) as error:
        parser.exit(1, f"Telegram setup: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
