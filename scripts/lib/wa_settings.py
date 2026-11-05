#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Keep the WhatsApp instance setting that status receipts depend on (README Gotcha #14).

Baileys drops all status@broadcast traffic, including the receipts that say who received or
viewed a status, unless the Evolution instance setting readStatus is on. It is turned on only
while the boot patch that skips other people's statuses is applied; without that patch it is
turned off, so Evolution never stores contacts' statuses (and a newer image never views them).

It also swaps phone numbers into receipts stored under a LID (WhatsApp's private id for a
person) once Baileys has learned the number. The boot patch stores numbers already; this covers
receipts that arrived before Baileys knew one.

    wa_settings.py           make it so; print what changed
    wa_settings.py --check   print the state only
Exit status: 0 when receipts are being recorded, 1 otherwise. publish-machine.sh start runs it.
"""
import json
import re
import subprocess
import sys

import pmlib

SKIP_PATCH_MARK = "/*pm-skip-contact-statuses*/"
RECEIPTS_PATCH_MARK = "/*pm-status-receipts*/"
# Evolution's settings endpoint replaces the whole record, so every field is sent back.
FIELDS = ("rejectCall", "msgCall", "groupsIgnore", "alwaysOnline", "readMessages", "readStatus",
          "syncFullHistory", "wavoipToken")


def redis_text(raw):
    """Baileys keys are JSON, which Evolution JSON-encodes once more: decode down to the string."""
    value = raw
    for _ in range(3):
        try:
            decoded = json.loads(value)
        except ValueError:
            break
        if not isinstance(decoded, str):
            break
        value = decoded
    return value


def resolve_stored_lids(env):
    """Replace LIDs in stored status receipts with phone numbers Baileys has learned since.

    Baileys keeps LID -> number pairs in Redis db 1, hash evolution:instance:<id>, field
    lid-mapping-<lid>_reverse. Returns how many LIDs were replaced.
    """
    rows = pmlib.psql("SELECT DISTINCT participant, \"instanceId\" FROM evolution.\"MessageUpdate\" "
                      "WHERE \"remoteJid\" = 'status@broadcast' AND participant LIKE '%@lid'", env)
    fixed = 0
    for jid, instance_id in rows:
        if not re.match(r"^\d+(:\d+)?@lid$", jid) or not re.match(r"^[0-9a-f-]{36}$", instance_id):
            continue
        raw = pmlib.run(["docker", "exec", "pm-redis", "redis-cli", "-n", "1", "--raw", "HGET",
                         "evolution:instance:" + instance_id, "lid-mapping-%s_reverse" % jid.split("@")[0].split(":")[0]],
                        check=False)
        number = redis_text(raw) if raw else None
        if not number or not number.isdigit():
            continue
        pmlib.psql("UPDATE evolution.\"MessageUpdate\" SET participant = '%s@s.whatsapp.net' "
                   "WHERE participant = '%s' AND \"remoteJid\" = 'status@broadcast'" % (number, jid), env)
        fixed += 1
    return fixed


def patched(mark):
    return subprocess.run(["docker", "exec", "pm-evolution-api", "grep", "-qF", mark, "/evolution/dist/main.js"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def main():
    check_only = "--check" in sys.argv[1:]
    env = pmlib.load_env()
    instance = env.get("WA_INSTANCE", "status-engine")
    base = "http://localhost:8080/settings/"
    headers = {"apikey": env.get("AUTHENTICATION_API_KEY", "")}
    status, current = pmlib.http("GET", base + "find/" + instance, headers, timeout=15)
    if status != 200 or not isinstance(current, dict):
        print("Status receipts: unknown (Evolution settings unreachable, HTTP %s)" % status)
        return 1

    patch_ok = patched(SKIP_PATCH_MARK) and patched(RECEIPTS_PATCH_MARK)
    wanted = patch_ok
    if bool(current.get("readStatus")) != wanted and not check_only:
        body = {k: current.get(k) for k in FIELDS if current.get(k) is not None}
        body["readStatus"] = wanted
        status, _ = pmlib.http("POST", base + "set/" + instance, headers, body=body, timeout=15)
        if status >= 400:
            print("Status receipts: could not change readStatus (HTTP %s)" % status)
            return 1
        current["readStatus"] = wanted
        print("Status receipts: readStatus turned %s" % ("on" if wanted else "off"))

    if not check_only:
        fixed = resolve_stored_lids(env)
        if fixed:
            print("Status receipts: matched %d private WhatsApp id%s to phone numbers" % (fixed, "" if fixed == 1 else "s"))

    if current.get("readStatus") and patch_ok:
        print("Status receipts: recorded (patch applied, readStatus on)")
        return 0
    if not patch_ok:
        print("Status receipts: NOT recorded (Evolution boot patch missing; see docker logs pm-evolution-api | grep pm-patch)")
    else:
        print("Status receipts: NOT recorded (readStatus off; run scripts/lib/wa_settings.py)")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except pmlib.PMError as exc:
        print("Status receipts: unknown (%s)" % exc)
        sys.exit(1)
