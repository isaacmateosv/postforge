#!/usr/bin/env python3
"""Send optional Telegram warnings and periodic online heartbeats."""
import argparse
import os
import platform
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def env_values():
    values = {}
    try:
        with open(os.path.join(ROOT, ".env"), encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip().strip("\"'")
    except OSError:
        pass
    return values


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--message")
    group.add_argument("--heartbeat", action="store_true")
    args = parser.parse_args()
    env = env_values()
    token = env.get("PM_TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("PM_TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("External pending-work alerts disabled: PM_TELEGRAM_BOT_TOKEN/PM_TELEGRAM_CHAT_ID not configured.")
        return 0
    message = args.message
    if args.heartbeat:
        message = "✅ PostForge online: %s (%s)" % (platform.node() or "Mac", __import__("datetime").datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"))
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=15) as response:
            if response.status >= 300:
                raise RuntimeError("HTTP %s" % response.status)
    except Exception as exc:
        print("Telegram pending-work alert failed: " + str(exc), file=sys.stderr)
        return 1
    print("Telegram message sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
