#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Read or safely update the public tunnel URL in .env."""
import argparse
import os
import re
import sys
from urllib.parse import urlparse


def normalize(value):
    value = value.strip()
    if "://" not in value:
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("use an HTTPS domain, for example https://publish.example.com")
    host = parsed.hostname
    if not host or parsed.port or host.startswith(".") or ".." in host:
        raise ValueError("use a valid HTTPS domain, for example https://publish.example.com")
    if not re.fullmatch(r"[A-Za-z0-9.-]+", host) or "." not in host:
        raise ValueError("use a valid HTTPS domain, for example https://publish.example.com")
    return host.lower(), "https://" + host.lower()


def update(path, value):
    host, url = normalize(value)
    try:
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc

    replacements = {
        "NGROK_DOMAIN": host,
        "FRONTEND_URL": url,
        "NEXT_PUBLIC_BACKEND_URL": url + "/api",
        "MAIN_URL": url,
    }
    for key, replacement in replacements.items():
        pattern = rf"(?m)^{re.escape(key)}=.*$"
        if not re.search(pattern, content):
            raise ValueError(f"{key} is missing from .env")
        content = re.sub(pattern, f"{key}={replacement}", content, count=1)
    temporary = path + ".tmp"
    try:
        with open(temporary, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()
    if not args.url:
        try:
            with open(args.env_file, encoding="utf-8") as fh:
                values = dict(line.rstrip().split("=", 1) for line in fh if "=" in line and not line.startswith("#"))
            print(values.get("FRONTEND_URL", ""))
            return 0
        except OSError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    try:
        print(update(args.env_file, args.url))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
