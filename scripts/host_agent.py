#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Local Status dispatcher and optional owner-only Telegram worker."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts/lib"))
sys.path.insert(0, str(ROOT / "v2"))
import file_lock
import pmlib
import composer
import whatsapp_pending

FOLDER = ROOT / "run" / "host-agent"
PID = FOLDER / "pid"
STOP = FOLDER / "stop"


def settings():
    from telegram_settings import configuration
    return configuration(ROOT)


def running():
    try:
        pid = int(PID.read_text())
        if not pmlib.pid_alive(pid):
            return None
        try:
            with file_lock.exclusive(str(FOLDER / "lock"), blocking=False):
                return None
        except (BlockingIOError, PermissionError):
            return pid
    except (OSError, ValueError):
        return None


def start():
    FOLDER.mkdir(mode=0o700, parents=True, exist_ok=True)
    if running():
        return
    STOP.unlink(missing_ok=True)
    from telegram_settings import active, atomic_write
    config = settings()
    if active(config):
        try:
            check = subprocess.run(["docker", "ps", "--filter", "label=com.docker.compose.project=postforge",
                                    "--filter", "label=com.docker.compose.service=postforge-telegram",
                                    "--format", "{{.ID}}"], capture_output=True, text=True, timeout=5)
            if check.returncode != 0:
                raise pmlib.PMError("Docker must be reachable to verify the legacy Telegram poller is stopped.")
            import re
            legacy = [line for line in check.stdout.splitlines() if re.fullmatch(r"[a-f0-9]{12,64}", line)]
            if legacy:
                subprocess.run(["docker", "stop", *legacy], check=True, capture_output=True, timeout=30)
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            raise pmlib.PMError("Verify that the old Docker Telegram poller is stopped before starting the host agent.") from None
        atomic_write(ROOT / "run/telegram/token", config["TELEGRAM_BOT_TOKEN"] + "\n")
    # The child also locks for its full lifetime, including concurrent launch attempts.
    log = FOLDER / "worker.log"
    fd = os.open(log, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    with os.fdopen(fd, "ab") as output:
        flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS} if os.name == "nt" else {"start_new_session": True}
        subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "run"],
                         cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                         env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"), **flags)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if running():
            return
        time.sleep(0.1)
    raise pmlib.PMError("The local agent did not start. Check run/host-agent/worker.log.")


def run():
    FOLDER.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with file_lock.exclusive(str(FOLDER / "lock"), blocking=False):
            PID.write_text(str(os.getpid()))
            PID.chmod(0o600)
            try:
                config = settings()
                token = ROOT / "run/telegram/token"
                from telegram_settings import active, atomic_write
                if active(config):
                    atomic_write(token, config["TELEGRAM_BOT_TOKEN"] + "\n")
                if token.is_file() and active(config):
                    import telegram_worker
                    import postforge_v2
                    env = pmlib.load_env()
                    postforge_v2.PROBES.update({
                        "Postiz API": env.get("POSTIZ_LOCAL_URL", "http://localhost:4200") + "/api/",
                        "Evolution API": "http://localhost:8080/",
                        "Ollama": env.get("OLLAMA_HOST_URL", "http://localhost:11434") + "/api/version"
                    })
                    os.environ.update({key: value for key, value in config.items() if key != "TELEGRAM_BOT_TOKEN"})
                    os.environ["TELEGRAM_TOKEN_FILE"] = str(token)
                    os.environ["POSTFORGE_HOST_WORKER"] = "1"
                    os.environ["POSTFORGE_STOP_FILE"] = str(STOP)
                    telegram_worker.STATE = FOLDER / "telegram.json"
                    telegram_worker.run()
                else:
                    while not STOP.exists():
                        whatsapp_pending.process(pmlib.load_env())
                        for _ in range(15):
                            if STOP.exists():
                                break
                            time.sleep(1)
            finally:
                PID.unlink(missing_ok=True)
    except (BlockingIOError, PermissionError):
        return


def stop():
    pid = running()
    if pid:
        STOP.touch(mode=0o600)
        deadline = time.monotonic() + 40
        while running() and time.monotonic() < deadline:
            time.sleep(0.1)
        if running():
            raise pmlib.PMError("Agent is still stopping. Try again shortly.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "stop", "restart", "status", "run"))
    action = parser.parse_args().command
    if action == "run":
        run()
    elif action == "start":
        start()
    elif action == "stop":
        stop()
    elif action == "restart":
        stop()
        start()
    else:
        print(json.dumps({"running": bool(running()), "telegram_configured": bool(settings().get("TELEGRAM_OWNER_ID"))}))


if __name__ == "__main__":
    main()
