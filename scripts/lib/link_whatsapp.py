#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Link the bakery's WhatsApp to Evolution as a linked device (first setup, or after a logout).

It never touches a working link: if the instance is already connected it says so and stops.
Otherwise it creates the instance when missing, saves the QR to run/whatsapp-qr.png, opens it,
and waits while you scan it on the bakery phone (WhatsApp > Linked devices > Link a device).
The QR changes about every 45 s; the file is refreshed. Once linked, it turns on what status
receipts need (wa_settings.py).
"""
import argparse
import base64
import os
import subprocess
import sys
import time

import pmlib
from pmlib import PMError, info

EVO = "http://localhost:8080"
QR_FILE = os.path.join(pmlib.RUN_DIR, "whatsapp-qr.png")


def call(env, method, path, body=None):
    return pmlib.http(method, EVO + path, {"apikey": env.get("AUTHENTICATION_API_KEY", "")}, body=body, timeout=30)


def state(env, instance):
    status, data = call(env, "GET", "/instance/connectionState/" + instance)
    if status == 404:
        return None
    if status >= 400 or not isinstance(data, dict):
        raise PMError("Evolution answered HTTP %s to connectionState" % status)
    return (data.get("instance") or {}).get("state")


def save_qr(data):
    """Writes the QR from a connect/create answer; returns True if there was one."""
    qr = data.get("qrcode", data) if isinstance(data, dict) else {}
    b64 = qr.get("base64") if isinstance(qr, dict) else None
    if not b64:
        return False
    os.makedirs(pmlib.RUN_DIR, exist_ok=True)
    with open(QR_FILE, "wb") as fh:
        fh.write(base64.b64decode(b64.split(",", 1)[-1]))
    return True


def main():
    parser = argparse.ArgumentParser(prog="link-whatsapp.sh", description=__doc__.split("\n")[0])
    parser.add_argument("--instance", help="Evolution instance name (default: WA_INSTANCE from .env)")
    parser.add_argument("--wait", type=int, default=180, help="seconds to wait for the scan (default 180)")
    parser.add_argument("--no-open", action="store_true", help="save the QR but don't open it")
    args = parser.parse_args()

    env = pmlib.load_env()
    instance = args.instance or env.get("WA_INSTANCE", "status-engine")
    current = state(env, instance)
    if current == "open":
        info("WhatsApp is already linked (instance '%s' is connected). Nothing to do." % instance)
        return 0

    if current is None:
        info("Creating Evolution instance '%s'..." % instance)
        status, data = call(env, "POST", "/instance/create",
                            {"instanceName": instance, "integration": "WHATSAPP-BAILEYS", "qrcode": True})
        if status >= 400:
            raise PMError("Could not create the instance (HTTP %s): %s" % (status, data))
        have_qr = save_qr(data)
    else:
        info("Instance '%s' exists but is not connected (state: %s)." % (instance, current))
        have_qr = False

    info("On the bakery phone: WhatsApp > Settings > Linked devices > Link a device, then scan the QR.")
    deadline = time.time() + args.wait
    opened = False
    next_qr = 0
    while time.time() < deadline:
        if time.time() >= next_qr:
            if not have_qr:
                status, data = call(env, "GET", "/instance/connect/" + instance)
                have_qr = status < 400 and save_qr(data)
            if have_qr:
                if not opened and not args.no_open:
                    subprocess.run(["open", QR_FILE], check=False)
                    opened = True
                info("QR saved to %s (refreshes every ~45 s)." % QR_FILE)
            have_qr = False
            next_qr = time.time() + 40
        time.sleep(3)
        if state(env, instance) == "open":
            info("✔ Linked. Contacts sync from the phone over the next minutes.")
            try:
                os.remove(QR_FILE)
            except OSError:
                pass
            if instance == env.get("WA_INSTANCE", "status-engine"):
                code = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "wa_settings.py")]).returncode
                if code != 0:
                    info("Status receipts are not set up yet; run ./publish-machine.sh status for details.")
            return 0
    info("Not linked within %d s. Run it again for a fresh QR." % args.wait)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PMError as exc:
        print("✖ " + str(exc), file=sys.stderr)
        sys.exit(1)
