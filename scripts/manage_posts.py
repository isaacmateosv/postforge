#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Preview and clear unpublished Postiz work through its normal cancellation API."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import pmlib
import whatsapp_pending

STATES = {"drafts": ("DRAFT", "ERROR"), "queue": ("QUEUE",), "all": ("DRAFT", "ERROR", "QUEUE")}


def quote(value):
    return "'" + value.replace("'", "''") + "'"


def snapshot(env, scope, client):
    states = ",".join(quote(state) for state in STATES[scope])
    rows = pmlib.psql(
        """SELECT json_build_object('group', "group", 'posts',
           json_agg(json_build_object('id', id, 'state', state)
                    ORDER BY ("parentPostId" IS NOT NULL), id))
           FROM "Post" WHERE "organizationId" = """ + quote(client.org_id) +
        """ AND "deletedAt" IS NULL GROUP BY "group"
           HAVING bool_and(state IN (""" + states + ")) ORDER BY \"group\";", env)
    groups = [json.loads(row[0]) for row in rows]
    local = []
    if scope in ("all", "queue"):
        with whatsapp_pending._queue_lock():
            local = [{"id": item["id"], "status": item["status"]}
                     for item in whatsapp_pending._read()
                     if item.get("status") in ("pending", "needs_review")]
    return {"organization": client.org_id, "scope": scope, "groups": groups, "whatsapp": local,
            "post_count": sum(len(group["posts"]) for group in groups), "whatsapp_count": len(local)}


def clear(env, reviewed, client):
    if reviewed.get("organization") != client.org_id or reviewed.get("scope") not in STATES:
        raise pmlib.PMError("The cleanup preview does not belong to this organization.")
    deleted = skipped = 0
    errors = []
    for group in reviewed["groups"]:
        current = snapshot(env, reviewed["scope"], client)
        match = next((item for item in current["groups"] if item == group), None)
        if not match:
            skipped += len(group["posts"])
            continue
        try:
            client._call("DELETE", "/posts/" + match["posts"][0]["id"])
            remaining = snapshot(env, reviewed["scope"], client)
            if any(item["group"] == group["group"] for item in remaining["groups"]):
                raise pmlib.PMError("Postiz did not confirm cancellation.")
            deleted += len(group["posts"])
        except pmlib.PMError:
            errors.append(group["group"])
    cancelled = 0
    if reviewed["scope"] in ("all", "queue"):
        wanted = {item["id"]: item["status"] for item in reviewed.get("whatsapp", [])}
        with whatsapp_pending._queue_lock():
            items = whatsapp_pending._read()
            for item in items:
                if item["id"] in wanted and item.get("status") == wanted[item["id"]]:
                    if item["status"] in ("pending", "needs_review"):
                        item.update(status="cancelled", approved=False, cancelled_at=int(time.time()),
                                    cancel_reason="Explicit cleanup in PostForge")
                        cancelled += 1
            if cancelled:
                whatsapp_pending._write(items)
    return {"deleted": deleted, "cancelled_whatsapp": cancelled, "skipped": skipped, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=STATES, default="all")
    parser.add_argument("--apply-snapshot", type=Path)
    args = parser.parse_args()
    try:
        env = pmlib.load_env()
        client = pmlib.Postiz(env)
        if args.apply_snapshot:
            reviewed = json.loads(args.apply_snapshot.read_text())
            result = clear(env, reviewed, client)
        else:
            result = snapshot(env, args.scope, client)
        print(json.dumps(result))
        return 1 if result.get("errors") else 0
    except (pmlib.PMError, OSError, ValueError, KeyError) as error:
        print(json.dumps({"error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
