# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check that signed-out requests cannot reach Postiz through a public URL."""
import argparse
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request

from postforge_v2 import OPENER

PATHS = ("/", "/api/", "/_next/static/", "/uploads/postforge-gateway-probe")


def https_url(value):
    try:
        parsed = urlsplit(value)
        _ = parsed.port
        if parsed.scheme == "https" and parsed.hostname and not (
            parsed.username or parsed.password or parsed.query or parsed.fragment
        ):
            return parsed
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("Expected an HTTPS URL without credentials, query, or fragment.")


def origin(parsed):
    return parsed.scheme, parsed.hostname, parsed.port or 443


def gate_response(status, location, target, auth):
    if status in (401, 403):
        return True
    if status not in (302, 303, 307, 308) or not location:
        return False
    try:
        redirect = urlsplit(urljoin(target, location))
        if redirect.username or redirect.password or origin(redirect) != origin(auth):
            return False
        prefix = auth.path.rstrip("/")
        return not prefix or redirect.path == prefix or redirect.path.startswith(prefix + "/")
    except ValueError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", type=https_url)
    parser.add_argument("--login", required=True, type=https_url, help="expected outer login URL or path prefix")
    args = parser.parse_args()
    if args.url.path not in ("", "/"):
        parser.error("The Postiz URL must be an origin.")
    if origin(args.url) == origin(args.login) and args.login.path in ("", "/"):
        parser.error("For a same-origin login, specify its exact outer login path.")
    results = []
    for path in PATHS:
        target = urljoin(args.url.geturl(), path)
        request = Request(target, headers={"ngrok-skip-browser-warning": "true"})
        try:
            with OPENER.open(request, timeout=8) as response:
                status, location = response.status, response.headers.get("Location")
        except HTTPError as response:
            with response:
                status, location = response.code, response.headers.get("Location")
        except (URLError, TimeoutError, OSError):
            print(f"{path} · request failed")
            results.append(False)
            continue
        passed = gate_response(status, location, target, args.login)
        print(f"{path} · HTTP {status} · {'gate response' if passed else 'expected gate missing'}")
        results.append(passed)
    print("Complete a separate browser test for MFA, denied users, Postiz login, and OAuth callbacks.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
