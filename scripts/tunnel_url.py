#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Switch the public Postiz URL and roll it back if the new endpoint fails."""
import argparse
import fcntl
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
URL_KEYS = ("NGROK_DOMAIN", "FRONTEND_URL", "NEXT_PUBLIC_BACKEND_URL", "MAIN_URL")


def normalize(value):
    value = value.strip()
    if "://" not in value:
        value = "https://" + value
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    labels = host.split(".")
    if (parsed.scheme != "https" or parsed.netloc.lower() != host or parsed.path not in ("", "/")
            or "?" in value or "#" in value or len(host) > 253 or len(labels) < 2
            or not re.fullmatch(r"[a-z][a-z0-9-]*", labels[-1])
            or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                   for label in labels)):
        raise ValueError("Use an HTTPS domain without credentials, a port, or a path.")
    return host, "https://" + host


def updated_config(content, host, url):
    for key, value in zip(URL_KEYS, (host, url, url + "/api", url)):
        content, count = re.subn(rf"(?m)^[ \t]*{key}[ \t]*=[^\r\n]*", f"{key}={value}", content)
        if count != 1:
            raise ValueError(f"Expected exactly one {key} entry in .env.")
    return content


def private_write(path, content, work):
    fd, temporary = tempfile.mkstemp(dir=work, prefix=".tunnel-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def probe(url):
    try:
        response = subprocess.run(
            ["/usr/bin/curl", "--silent", "--fail", "--max-time", "5",
             "--max-filesize", "4096", "--header", "ngrok-skip-browser-warning: true",
             "--write-out", "\n%{http_code}", url.rstrip("/") + "/api/"],
            capture_output=True, timeout=7, check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    body, _, status = response.rpartition(b"\n")
    return body if status == b"200" and body else None


def compose(path, *args):
    # The lifecycle CLI may have exported the previous .env values.
    env = {key: value for key, value in os.environ.items() if key not in URL_KEYS}
    result = subprocess.run(
        ["docker", "compose", "--env-file", str(path), *args],
        cwd=path.parent, env=env, timeout=90, capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError("Docker could not apply the Postiz and ngrok configuration.")


def wait_until_ready(local, public, expected):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if probe(local) == expected and (public is None or probe(public) == expected):
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/lib/machine_state.py"), "--check-scheduler"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12,
            )
            if result.returncode == 0:
                return
        time.sleep(3)
    raise RuntimeError("Postiz, the scheduler, or the public HTTPS endpoint failed verification.")


def read_setting(content, key, default=""):
    match = re.search(rf"(?m)^[ \t]*{key}[ \t]*=(.*)$", content)
    return match[1].strip().strip("\"'") if match else default


def switch(path, value):
    host, url = normalize(value)
    run = path.parent / "run"
    run.mkdir(mode=0o700, exist_ok=True)
    backup = run / "tunnel-url.previous"
    with (run / "tunnel-url.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another tunnel change is running.") from exc
        if backup.exists():
            raise ValueError(f"A previous switch needs recovery. Restore {backup} as .env before retrying.")
        original = path.read_bytes()
        content = original.decode("utf-8")
        previous_url = read_setting(content, "FRONTEND_URL")
        # Keep the original line endings and all unrelated settings.
        updated = updated_config(content, host, url).encode("utf-8")
        if updated == original:
            print("Tunnel URL is already configured.", flush=True)
            return url
        local = read_setting(content, "POSTIZ_LOCAL_URL", "http://localhost:4200")
        expected = probe(local)
        if expected is None:
            raise ValueError("Turn PostForge on and wait for local Postiz before changing the tunnel.")
        previously_public = previous_url if previous_url and probe(previous_url) == expected else None
        compose(path, "config", "--quiet")
        private_write(backup, original, run)
        try:
            private_write(path, updated, run)
            print("STEP 1/2 Restarting Postiz and ngrok", flush=True)
            compose(path, "up", "-d", "--no-deps", "postiz", "ngrok")
            print("STEP 2/2 Verifying the tunnel and scheduler", flush=True)
            wait_until_ready(local, url, expected)
        except (Exception, KeyboardInterrupt) as failure:
            print("Restoring the previous tunnel configuration.", flush=True)
            try:
                private_write(path, original, run)
                compose(path, "up", "-d", "--no-deps", "postiz", "ngrok")
                wait_until_ready(local, previously_public, expected)
            except (Exception, KeyboardInterrupt) as rollback_error:
                raise RuntimeError(f"Automatic recovery failed. The previous settings are in {backup}.") from rollback_error
            backup.unlink()
            raise RuntimeError("Tunnel change failed. The previous settings and services were restored.") from failure
        backup.unlink()
        return url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        path = args.env_file.resolve()
        print(switch(path, args.url) if args.url is not None else read_setting(path.read_text(), "FRONTEND_URL"))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"✖ {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
