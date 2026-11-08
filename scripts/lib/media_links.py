# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Short-lived, file-scoped delivery for social publishing through the gateway."""
from http.client import HTTPException
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sys
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PREFIX = "/postforge-media/"
MAX_AGE = 32 * 86400
MEDIA_PATH = r"/uploads/[0-9]{4}/[0-9]{2}/[0-9]{2}/[A-Za-z0-9_-]{20,100}\.(?:mp4|jpe?g|png|webp)"
LINK = re.compile(PREFIX + r"([0-9]{10})/([0-9a-f]{64})(" + MEDIA_PATH + r")")


def load_key(path):
    try:
        with open(path, "rb") as handle:
            value = handle.read(33)
        return value if len(value) == 32 else None
    except OSError:
        return None


def mac(key, expires, path):
    return hmac.new(key, f"{expires}\n{path}".encode("ascii"), hashlib.sha256).hexdigest()


def signed_url(key, origin, upload, expires):
    if not 0 < expires - time.time() <= MAX_AGE:
        raise ValueError("Secure media links support schedules up to 30 days ahead.")
    base, media = urlsplit(origin), urlsplit(upload)
    if (base.scheme != "https" or not base.hostname or base.username or base.password
            or base.path not in ("", "/") or base.query or base.fragment
            or (media.scheme, media.netloc) != (base.scheme, base.netloc)
            or media.query or media.fragment or not re.fullmatch(MEDIA_PATH, media.path)):
        raise ValueError("Postiz returned an unsupported media URL for secure delivery.")
    return f"{base.scheme}://{base.netloc}{PREFIX}{expires}/{mac(key, expires, media.path)}{media.path}"


def authorized(key, method, uri, now=None):
    match = LINK.fullmatch(uri)
    if not key or method not in ("GET", "HEAD") or not match:
        return False
    expires, supplied, path = match.groups()
    remaining = int(expires) - (time.time() if now is None else now)
    return 0 < remaining <= MAX_AGE and hmac.compare_digest(supplied, mac(key, expires, path))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def serves_media(url):
    try:
        with build_opener(NoRedirect()).open(Request(url, headers={"Range": "bytes=0-0"}), timeout=8) as response:
            return (response.status == 206
                    and bool(re.fullmatch(r"bytes 0-0/[1-9][0-9]*", response.headers.get("Content-Range", "")))
                    and response.headers.get_content_maintype() in ("video", "image")
                    and len(response.read(2)) == 1)
    except (OSError, HTTPException):
        return False


def serve(key_path):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Verifier(BaseHTTPRequestHandler):
        def do_GET(self):
            allowed = self.path == "/verify" and authorized(
                load_key(key_path), self.headers.get("X-Forwarded-Method", ""),
                self.headers.get("X-Forwarded-Uri", ""))
            self.send_response(204 if allowed else 403)
            self.end_headers()

        def log_message(self, *_args):
            pass

    ThreadingHTTPServer(("0.0.0.0", 8081), Verifier).serve_forever()


def init_key(path):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as handle:
        handle.write(secrets.token_bytes(32))


if __name__ == "__main__":
    action, key_path = sys.argv[1:]
    {"serve": serve, "init-key": init_key}[action](key_path)
