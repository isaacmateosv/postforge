# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only, loopback-published dashboard for the v2 prototype."""
import concurrent.futures
import html
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROBES = {
    "Postiz API": "http://postiz:5000/api/",
    "Evolution API": "http://evolution-api:8080/",
    "Ollama": "http://host.docker.internal:11434/api/version",
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def reachable(url):
    try:
        with OPENER.open(url, timeout=2) as response:
            return response.status == 200
    except urllib.error.HTTPError as response:
        return response.code in (401, 403)
    except (OSError, ValueError):
        return False


# DNS resolution can outlive urllib's socket timeout. Bound the caller's wait
# and reuse one worker per probe so refreshes cannot accumulate blocked threads.
PROBE_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=len(PROBES))
PROBE_LOCK = threading.Lock()
PROBE_TASKS = {}
PROBE_DEADLINE = 2.25
PROBE_CACHE_SECONDS = 3


def services():
    with PROBE_LOCK:
        now = time.monotonic()
        for name, url in PROBES.items():
            previous = PROBE_TASKS.get(name)
            if (previous is None or previous[0] != url
                    or (previous[1].done() and now - previous[2] >= PROBE_CACHE_SECONDS)):
                PROBE_TASKS[name] = (url, PROBE_POOL.submit(reachable, url), now)
        tasks = {name: PROBE_TASKS[name][1] for name in PROBES}
    concurrent.futures.wait(tasks.values(), timeout=PROBE_DEADLINE)
    result = {}
    for name, task in tasks.items():
        try:
            result[name] = bool(task.result()) if task.done() else False
        except Exception:
            result[name] = False
    return result


def browser_url():
    value = os.environ.get("POSTIZ_BROWSER_URL", "http://localhost:4200")
    try:
        parsed = urllib.parse.urlsplit(value)
        if (not parsed.hostname or not re.fullmatch(r"[a-z0-9.-]+", parsed.hostname)
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("", "/") or parsed.scheme not in ("https", "http")):
            return None
        if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1"):
            return None
        return value
    except ValueError:
        return None


def dashboard(es):
    link = browser_url()
    labels = [
        ("Disponible" if up else "Sin respuesta") if es else ("Reachable" if up else "Unreachable")
        for up in services().values()
    ]
    cards = "".join(f"<li><strong>{name}</strong><span>{label}</span></li>" for name, label in zip(PROBES, labels))
    button = (f'<a class="button" href="{html.escape(link, quote=True)}">'
              f'{"Abrir Postiz" if es else "Open Postiz"}</a>') if link else ""
    note = ("Este panel comprueba si los servicios responden. La conexión de WhatsApp y el programador se revisan por separado."
            if es else "This checks whether services respond. WhatsApp pairing and the scheduler are checked separately.")
    return f"""<!doctype html><html lang="{'es-EC' if es else 'en'}"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>PostForge</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;font:16px system-ui;background:#111827;color:#f1f5f9}}
main{{max-width:640px;margin:8vh auto;padding:24px}} h1{{margin:16px 0 8px;font-size:42px}}
nav a{{color:#9dd9ff;margin-right:14px}} p{{color:#c1cedf;line-height:1.5}} ul{{padding:0;margin:24px 0}}
li{{display:flex;justify-content:space-between;padding:18px;border:1px solid #34465e;border-radius:12px;
background:#1d2b3d;margin:10px 0;gap:10px}} span{{color:#c4d8ee}} .button{{display:inline-block;color:#142134;
background:#9dd9ff;padding:11px 16px;margin-right:12px;border-radius:8px;text-decoration:none;font-weight:650}}
</style><main><nav><a href="/?lang=en">English</a><a href="/?lang=es">Español (Ecuador)</a></nav>
<h1>PostForge</h1><p>{'Panel local · Vista previa' if es else 'Local dashboard · Preview'}</p>
<ul>{cards}</ul>{button}<a class="button" href="/?lang={'es' if es else 'en'}">{'Actualizar estado' if es else 'Refresh status'}</a>
<p>{note}</p></main></html>""".encode()


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # The host publisher also binds loopback. Refuse arbitrary Host headers
        # so a hostile site cannot use DNS rebinding to reach this local UI.
        if self.headers.get("Host") not in ("localhost:8787", "127.0.0.1:8787"):
            self.send_error(403)
            return
        url = urllib.parse.urlsplit(self.path)
        if url.path != "/":
            self.send_error(404)
            return
        page = dashboard(urllib.parse.parse_qs(url.query).get("lang") == ["es"])
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, _format, *_args):
        pass


def main():
    if sys.argv[1:] == ["web"]:
        with ThreadingHTTPServer(("0.0.0.0", 8787), DashboardHandler) as server:
            server.serve_forever()
    elif sys.argv[1:] == ["telegram"]:
        import telegram_worker
        telegram_worker.run()
    else:
        raise SystemExit("Usage: python -m postforge_v2 {web|telegram}")


if __name__ == "__main__":
    main()
