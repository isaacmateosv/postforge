#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Switch the public Postiz URL and roll it back if the new endpoint fails."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit, urljoin

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/lib"))
import file_lock
import shutil
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
    content = re.sub(r"(?m)^[ \t]*POSTFORGE_GATEWAY_HOST[ \t]*=[^\r\n]*",
                     lambda _: f"POSTFORGE_GATEWAY_HOST={host}", content)
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
            [shutil.which("curl") or "curl", "--silent", "--fail", "--max-time", "5",
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
    env = {key: value for key, value in os.environ.items() if key not in (*URL_KEYS, "POSTFORGE_GATEWAY_HOST")}
    result = subprocess.run(
        ["docker", "compose", "--env-file", str(path), *args],
        cwd=path.parent, env=env, timeout=90, capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError("Docker could not apply the Postiz and ngrok configuration.")
    return result.stdout


def gateway_ready(url):
    try:
        result = subprocess.run(
            [shutil.which("curl") or "curl", "--silent", "--max-time", "5", "--output", os.devnull,
             "--header", "ngrok-skip-browser-warning: true", "--header", "Accept: text/html",
             "--header", "Sec-Fetch-Mode: navigate", "--write-out", "%{http_code} %{redirect_url}",
             url + "/api/"], capture_output=True, text=True, timeout=7, check=True,
        )
        status, _, location = result.stdout.partition(" ")
        target = urlsplit(urljoin(url, location))
        if (status not in ("302", "303", "307", "308")
                or (target.scheme, target.netloc) != ("https", urlsplit(url).netloc)
                or not (target.path == "/authelia" or target.path.startswith("/authelia/"))):
            return False
        portal = subprocess.run(
            [shutil.which("curl") or "curl", "--silent", "--max-time", "5", "--output", os.devnull,
             "--header", "ngrok-skip-browser-warning: true", "--write-out", "%{http_code}",
             url + "/authelia/"], capture_output=True, text=True, timeout=7, check=True,
        )
        return portal.stdout == "200"
    except (subprocess.SubprocessError, OSError, ValueError):
        return False


def wait_until_ready(local, public, expected, *, gated=False):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        public_ready = public is None or (gateway_ready(public) if gated else probe(public) == expected)
        if probe(local) == expected and public_ready:
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


def check_gateway_config(path, host):
    services = json.loads(compose(path, "config", "--format", "json"))["services"]
    proxy = services.get("postforge-gateway", {})
    tunnel = services.get("ngrok", {})
    auth = services.get("postforge-auth")

    command=tunnel.get("command", [])
    direct=any(value in ("postforge-gateway:8080", "http://postforge-gateway:8080") for value in command)
    named=str(tunnel.get("image", "")).startswith("cloudflare/cloudflared@sha256:") and command[-1:]==["run"]
    if (auth is None or not host or not (direct or named)
            or proxy.get("environment", {}).get("POSTFORGE_GATEWAY_HOST") != host
            or proxy.get("ports") or auth.get("ports")):
        raise RuntimeError("The effective tunnel and gateway configuration does not protect Postiz.")


def apply_services(path, gated, host, *, preserve_connector=False):
    if gated:
        check_gateway_config(path, host)
        compose(path, "up", "-d", "--no-deps", "--force-recreate", "postforge-auth", "postforge-gateway")
    compose(path, "up", "-d", "--no-deps", "postiz")
    if preserve_connector:
        compose(path, "up", "-d", "--no-deps", "--no-recreate", "ngrok")
    else:
        compose(path, "up", "-d", "--no-deps", "ngrok")


def switch(path, value):
    host, url = normalize(value)
    run = path.parent / "run"
    run.mkdir(mode=0o700, exist_ok=True)
    backup = run / "tunnel-url.previous"
    gateway_backup = run / "tunnel-gateway.previous"
    gateway = path.parent / "data/gateway/configuration.yml"
    with file_lock.exclusive(str(run / "tunnel-url.lock"), blocking=False):
        if backup.exists() or gateway_backup.exists():
            raise ValueError(f"A previous switch needs recovery. Check the tunnel recovery files in {run} before retrying.")
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
        gated = gateway.exists() or gateway.is_symlink()
        if gated:
            if gateway.is_symlink() or not gateway.is_file():
                raise ValueError("The gateway configuration must be a local file.")
            from v2.gateway_setup import update_hostname

            gateway_original = gateway.read_bytes()
            gateway_updated = json.dumps(update_hostname(json.loads(gateway_original), host), indent=2)
            if not previous_url or not gateway_ready(previous_url):
                raise ValueError("Verify the existing public gateway before changing the tunnel.")
            previous_host, _ = normalize(previous_url)
            check_gateway_config(path, previous_host)
            previously_public = previous_url
        else:
            previously_public = previous_url if previous_url and probe(previous_url) == expected else None
        compose(path, "config", "--quiet")
        private_write(backup, original, run)
        try:
            if gated:
                private_write(gateway_backup, gateway_original, run)
                compose(path, "stop", "ngrok")
                private_write(gateway, (gateway_updated + "\n").encode(), gateway.parent)
            private_write(path, updated, run)
            print("STEP 1/2 Restarting Postiz and ngrok", flush=True)
            apply_services(path, gated, host)
            print("STEP 2/2 Verifying the tunnel and scheduler", flush=True)
            wait_until_ready(local, url, expected, gated=gated)
        except (Exception, KeyboardInterrupt) as failure:
            print("Restoring the previous tunnel configuration.", flush=True)
            try:
                if gated:
                    compose(path, "stop", "ngrok")
                    private_write(gateway, gateway_original, gateway.parent)
                private_write(path, original, run)
                apply_services(path, gated, previous_host if gated else host)
                wait_until_ready(local, previously_public, expected, gated=gated)
            except (Exception, KeyboardInterrupt) as rollback_error:
                raise RuntimeError(f"Automatic recovery failed. The previous settings are in {run}.") from rollback_error
            gateway_backup.unlink(missing_ok=True)
            backup.unlink()
            raise RuntimeError("Tunnel change failed. The previous settings and services were restored.") from failure
        gateway_backup.unlink(missing_ok=True)
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
        provider=read_setting(path.read_text(),"PM_TUNNEL_PROVIDER","ngrok")
        if args.url is not None and provider=="trycloudflare":
            raise ValueError("Temporary hostnames are assigned by Cloudflare. Use the app's Public URL & Tunnel controls to rotate or synchronize them.")
        if args.url is not None and provider=="cloudflare" and path==ROOT/".env":
            import network_settings
            print(network_settings.apply({"provider":"cloudflare","custom_domain":args.url,"confirm":True})["url"])
        else:print(switch(path, args.url) if args.url is not None else read_setting(path.read_text(), "FRONTEND_URL"))
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"✖ {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
