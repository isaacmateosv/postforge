#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""What the Publish Machine is doing right now, for the menu bar app and the lifecycle CLI.

  machine_state.py --json    one JSON object (the menu bar app polls this)
  machine_state.py           short report (publish-machine.sh pending)
  machine_state.py --guard   report, exit 3 if the stack is on and work is waiting (publish-machine.sh stop)
  machine_state.py --cache   refresh run/schedule-cache.json while the database is up

It never starts or stops anything and only writes under run/. While the stack is off, scheduled
posts and channel expiry dates come from run/schedule-cache.json, which every poll and every
`stop` refresh. Channels that need reconnecting (or will soon) come with the steps and a guide in
docs/reconnect/; scripts/lib/channels.py walks through the reconnect.

Scheduled posts survive a stop: each one is a Temporal workflow sleeping until its publish time
(Postiz post.workflow v1.1.2). If the machine is off at that time, the post goes out late, as soon
as the stack is back.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmlib  # noqa: E402

CONTAINERS = ("pm-postgres", "pm-redis", "pm-temporal",
              "pm-postiz", "pm-evolution-api", "pm-tunnel")
CACHE_FILE = os.path.join(pmlib.RUN_DIR, "schedule-cache.json")
IDLE_STOP_FILE = os.path.join(pmlib.RUN_DIR, "idle-stop")
LIFECYCLE_FILE = os.path.join(pmlib.RUN_DIR, "lifecycle.json")
GUARD_EXIT = 3
MAX_LISTED = 10
WHATSAPP_QUEUE = os.path.join(pmlib.RUN_DIR, "whatsapp-pending.json")
WHATSAPP_CONFIRMATIONS = os.path.join(pmlib.RUN_DIR, "wa-confirmations")
# A Temporal worker long-polls the "main" task queue; one seen this recently counts as alive.
POLLER_FRESH_SECONDS = 180

# Networks whose token this Postiz build can't renew (their refreshToken() returns nothing): at
# tokenExpiration they stop posting until someone reconnects them. The others renew themselves
# and flag trouble through refreshNeeded.
NO_RENEWAL = {"facebook", "instagram", "instagram-standalone"}
WARN_DAYS = 10  # default for PM_CHANNEL_WARN_DAYS
GUIDE_DIR = "docs/reconnect"
NETWORKS = {"facebook": "Facebook Page", "instagram": "Instagram", "instagram-standalone": "Instagram",
            "youtube": "YouTube", "tiktok": "TikTok", "tiktok-business": "TikTok", "threads": "Threads"}
GUIDES = {"facebook": "meta.md", "instagram": "meta.md", "instagram-standalone": "meta.md",
          "youtube": "youtube.md", "tiktok": "tiktok.md", "tiktok-business": "tiktok.md", "threads": "threads.md"}
# Keyed by the provider's first word (instagram-standalone -> instagram).
LOGINS = {
    "facebook": "Log in to Facebook with an account that manages the organization’s Page, keep every "
                "permission ticked, and pick the same Page.",
    "instagram": "Log in to Facebook with an account that manages the organization’s Page, keep every "
                 "permission ticked, and pick the same Page and its Instagram account.",
    "youtube": "Sign in with the Google account that owns the YouTube channel and allow access.",
    "tiktok": "Log in with the organization’s TikTok account and allow access.",
    "threads": "Log in to Threads with the organization’s Instagram account and allow access.",
}

STATUS_TEXT = ("left(coalesce(m.message->'extendedTextMessage'->>'text', m.message->>'conversation', "
               "m.message->'imageMessage'->>'caption', m.message->'videoMessage'->>'caption', ''), 60)")
RECEIPTS = ("(SELECT count(DISTINCT u.participant) FROM evolution.\"MessageUpdate\" u "
            "WHERE u.\"messageId\" = m.id AND u.participant IS DISTINCT FROM i.\"ownerJid\"%s)")
# Contact name, else the number; a LID nobody could match to a number stays anonymous.
VIEWER_NAMES = ("(SELECT coalesce(json_agg(v.name ORDER BY v.name), '[]'::json) FROM ("
                "SELECT DISTINCT CASE WHEN u.participant LIKE '%@lid' THEN 'someone (private WhatsApp id)' "
                "ELSE coalesce(nullif(c.\"pushName\", ''), '+' || split_part(u.participant, '@', 1)) END AS name "
                "FROM evolution.\"MessageUpdate\" u LEFT JOIN evolution.\"Contact\" c "
                "ON c.\"instanceId\" = m.\"instanceId\" AND c.\"remoteJid\" = u.participant "
                "WHERE u.\"messageId\" = m.id AND u.status = 'READ' AND u.participant IS DISTINCT FROM i.\"ownerJid\" "
                "LIMIT 15) v)")
# One round trip; ::jsonb::text keeps it on one line (json_agg adds newlines).
SNAPSHOT_SQL = (
    "SELECT json_build_object("
    "'scheduled', coalesce((SELECT json_agg(x ORDER BY x.at) FROM ("
    "  SELECT p.id, to_char(p.\"publishDate\", 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') AS at,"
    "    i.\"providerIdentifier\" AS provider, coalesce(i.\"customName\", i.name) AS channel,"
    "    left(btrim(regexp_replace(regexp_replace(regexp_replace(p.content, '</p>|<br[^>]*>', ' ', 'gi'),"
    "    '<[^>]*>', '', 'g'), '[[:space:]]+', ' ', 'g')), 70) AS text,"
    "    p.\"intervalInDays\" AS repeat_days"
    "  FROM public.\"Post\" p JOIN public.\"Integration\" i ON i.id = p.\"integrationId\""
    "  WHERE p.state = 'QUEUE' AND p.\"deletedAt\" IS NULL AND p.\"parentPostId\" IS NULL) x), '[]'::json),"
    "'channels', coalesce((SELECT json_agg(c ORDER BY c.provider, c.channel) FROM ("
    "  SELECT i.\"providerIdentifier\" AS provider, coalesce(i.\"customName\", i.name) AS channel,"
    "    i.disabled, i.\"refreshNeeded\" AS refresh_needed, i.\"inBetweenSteps\" AS unfinished,"
    "    to_char(i.\"tokenExpiration\", 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') AS expires,"
    "    to_char(i.\"updatedAt\", 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') AS updated"
    "  FROM public.\"Integration\" i WHERE i.\"deletedAt\" IS NULL) c), '[]'::json),"
    "'drafts', (SELECT count(*) FROM public.\"Post\" WHERE state = 'DRAFT' AND \"deletedAt\" IS NULL"
    "  AND \"parentPostId\" IS NULL),"
    "'failed_posts', (SELECT count(*) FROM public.\"Post\" WHERE state = 'ERROR' AND \"deletedAt\" IS NULL"
    "  AND \"parentPostId\" IS NULL AND \"updatedAt\" > (now() AT TIME ZONE 'UTC') - interval '24 hours'),"
    "'last_status', (SELECT row_to_json(s) FROM ("
    "  SELECT m.key->>'id' AS id, m.\"messageTimestamp\" AS ts, "
    + RECEIPTS % "" + " AS received, " + RECEIPTS % " AND u.status = 'READ'" + " AS viewed, "
    + VIEWER_NAMES + " AS viewer_names, "
    + STATUS_TEXT + " AS text"
    "  FROM evolution.\"Message\" m JOIN evolution.\"Instance\" i ON i.id = m.\"instanceId\""
    "  WHERE m.key->>'remoteJid' = 'status@broadcast' AND (m.key->>'fromMe')::boolean"
    "  ORDER BY m.\"messageTimestamp\" DESC LIMIT 1) s)"
    ")::jsonb::text;"
)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def whatsapp_state():
    pending = []
    needs_review = 0
    try:
        with open(WHATSAPP_QUEUE, encoding="utf-8") as fh:
            items = json.load(fh)
            pending = [item for item in items if item.get("status") == "pending"]
            needs_review = sum(item.get("status") == "needs_review" for item in items)
    except (OSError, ValueError, TypeError):
        pass
    confirmations = 0
    try:
        confirmations = sum(name.endswith(".json") for name in os.listdir(WHATSAPP_CONFIRMATIONS))
    except OSError:
        pass
    approved = [item for item in pending if item.get("approved")
                and item.get("approval_source") == "explicit-whatsapp-command"]
    pending_times = [item.get("when") for item in pending if item.get("when")]
    return {
        "pending": len(pending),
        "awaiting_approval": len(pending) - len(approved),
        "approved": len(approved),
        "needs_review": needs_review,
        "confirmations": confirmations,
        "next": min(pending_times) if pending_times else None,
    }


def parse_iso(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def containers():
    """{name: docker state} for the stack, or None when the Docker daemon can't be reached."""
    try:
        proc = subprocess.run(["docker", "ps", "-a", "--filter", "name=^pm-", "--format", "{{.Names}}\t{{.State}}"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    found = dict(line.split("\t", 1) for line in proc.stdout.splitlines() if "\t" in line)
    return {name: found.get(name, "missing") for name in CONTAINERS}


def lifecycle():
    """'starting' / 'stopping' while publish-machine.sh is doing that, else None."""
    try:
        with open(LIFECYCLE_FILE, encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError):
        return None
    return record.get("action") if pmlib.pid_alive(record.get("pid")) else None


def http_up(url, headers=None):
    try:
        status, data = pmlib.http("GET", url, headers, timeout=4)
    except pmlib.PMError:
        return None, None
    return status, data


def scheduler_alive():
    """True if a Postiz orchestrator worker polls Temporal's "main" task queue. Without one,
    scheduled posts never go out even though Postiz itself looks healthy. Only the running
    pm-postiz counts (worker identity "<pid>@<container hostname>"): after a Postiz-only restart,
    Temporal still lists the old container's worker for a few minutes."""
    try:
        host = pmlib.run(["docker", "inspect", "-f", "{{.Config.Hostname}}", "pm-postiz"])
        out = pmlib.run(["docker", "exec", "pm-temporal", "sh", "-c",
                         "temporal task-queue describe --task-queue main --namespace default "
                         "--address $(hostname -i):7233 -o json"])
        pollers = json.loads(out).get("pollers") or []
    except (pmlib.PMError, ValueError):
        return False
    now = datetime.now(timezone.utc)
    for poller in pollers:
        if not (poller.get("identity") or "").endswith("@" + host):
            continue
        seen = (poller.get("lastAccessTime") or "")[:19]
        try:
            age = (now - datetime.strptime(seen, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)).total_seconds()
        except ValueError:
            continue
        if age < POLLER_FRESH_SECONDS:
            return True
    return False


def services(env, running):
    out = {"postiz": False, "evolution": False, "whatsapp": None, "scheduler": False,
           "tunnel": running.get("pm-tunnel") == "running"}
    if out['tunnel'] and env.get('FRONTEND_URL','').startswith('https://'):
        try:
            sys.path.insert(0, os.path.join(pmlib.ROOT,'scripts'))
            import network_settings
            public=network_settings.status(check=True)
            out['tunnel']=bool(public.get('reachable') and not public.get('needs_sync'))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            out['tunnel']=False
    if running.get("pm-postiz") == "running":
        status, _ = http_up(env.get("POSTIZ_LOCAL_URL", "http://localhost:4200") + "/api/")
        out["postiz"] = bool(status) and status < 500
    if running.get("pm-temporal") == "running":
        out["scheduler"] = scheduler_alive()
    if running.get("pm-evolution-api") == "running":
        status, _ = http_up("http://localhost:8080/")
        out["evolution"] = status == 200
        if out["evolution"] and env.get("AUTHENTICATION_API_KEY"):
            _, data = http_up("http://localhost:8080/instance/connectionState/" + env.get("WA_INSTANCE", "status-engine"),
                              {"apikey": env["AUTHENTICATION_API_KEY"]})
            if isinstance(data, dict):
                out["whatsapp"] = (data.get("instance") or {}).get("state")
    return out


def snapshot(env):
    """Live numbers from Postgres, or None when it can't be queried."""
    try:
        out = pmlib.run(["docker", "exec", "-i", "pm-postgres", "psql",
                         "-U", env.get("POSTGRES_USER", "postiz"), "-d", env.get("POSTGRES_DB", "postiz"),
                         "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", SNAPSHOT_SQL])
        return json.loads(out)
    except (pmlib.PMError, ValueError):
        return None


def save_cache(scheduled, channels):
    os.makedirs(pmlib.RUN_DIR, exist_ok=True)
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"cached_at": now_iso(), "scheduled": scheduled, "channels": channels}, fh)
    os.replace(tmp, CACHE_FILE)


def load_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def warn_days(env):
    try:
        return max(1, int(env.get("PM_CHANNEL_WARN_DAYS") or WARN_DAYS))
    except ValueError:
        return WARN_DAYS


def reconnect_steps(provider):
    login = LOGINS.get(provider.split("-")[0], "Log in with the account that owns the channel and allow access.")
    return ["Turn Publish Machine on if it's off.",
            "Open Postiz. In the channel list on the left, open the channel's menu and choose Reconnect "
            "channel (a disconnected channel also says \"click to reconnect\").",
            login,
            "Done: the channel works again, and the warning clears within a minute."]


def channel_rows(channels):
    return [{"provider": c.get("provider") or "", "network": NETWORKS.get(c.get("provider"), c.get("provider") or ""),
             "channel": c.get("channel") or "", "renews": c.get("provider") not in NO_RENEWAL,
             "expires": c.get("expires") if c.get("provider") in NO_RENEWAL else None,
             "disabled": bool(c.get("disabled"))} for c in channels]


def channel_alerts(channels, days):
    """Channels to reconnect, the most urgent first: disconnected, unfinished, expired, or (networks
    Postiz can't renew) expiring within `days`."""
    now = datetime.now(timezone.utc)
    alerts = []
    for ch in channels:
        provider = ch.get("provider") or ""
        no_renewal = provider in NO_RENEWAL and bool(ch.get("expires"))
        expires = parse_iso(ch["expires"]) if no_renewal else None
        days_left = int((expires - now).total_seconds() // 86400) if expires else None
        if ch.get("refresh_needed"):
            reason = "disconnected"
        elif ch.get("unfinished"):
            reason = "setup not finished"
        elif expires and expires <= now:
            reason = "expired"
        elif expires and days_left < days:
            reason = "expires soon"
        else:
            continue
        alerts.append({
            "provider": provider,
            "network": NETWORKS.get(provider, provider),
            "channel": ch.get("channel") or "",
            "reason": reason,
            "urgent": reason != "expires soon",
            "expires": ch.get("expires") if no_renewal else None,
            "days_left": days_left,
            "guide": GUIDE_DIR + "/" + GUIDES.get(provider, "README.md"),
            "steps": reconnect_steps(provider),
        })
    alerts.sort(key=lambda a: (not a["urgent"], a["days_left"] if a["days_left"] is not None else -1))
    return alerts


def days_phrase(days):
    return "today" if days <= 0 else "tomorrow" if days == 1 else "in %d days" % days


def alert_line(alert):
    who = "%s (%s)" % (alert["network"], alert["channel"]) if alert["channel"] else alert["network"]
    if alert["reason"] == "expires soon":
        day = parse_iso(alert["expires"]).astimezone().strftime("%a %d %b")
        return "⚠ %s stops working %s (%s): reconnect it before then." % (who, day, days_phrase(alert["days_left"]))
    return "⚠ %s: %s. Reconnect it to keep posting." % (who, alert["reason"])


def collect(env):
    running = containers()
    docker_up = running is not None
    running = running or {}
    up = [name for name, state in running.items() if state == "running"]
    svc = services(env, running) if up else {"postiz": False, "evolution": False, "whatsapp": None,
                                             "scheduler": False, "tunnel": False}
    snap = snapshot(env) if "pm-postgres" in up else None

    if snap is not None:
        scheduled, channels, cached_at = snap.get("scheduled") or [], snap.get("channels") or [], None
        save_cache(scheduled, channels)
    else:
        cache = load_cache()
        scheduled, channels, cached_at = cache.get("scheduled") or [], cache.get("channels") or [], cache.get("cached_at")

    transition = lifecycle()
    if transition:
        state = transition
    elif not up:
        state = "off"
    elif len(up) == len(CONTAINERS) and svc["postiz"] and svc["evolution"] and svc["scheduler"]:
        state = "on"
    else:
        state = "partial"

    now = datetime.now(timezone.utc)
    overdue = [p for p in scheduled if parse_iso(p["at"]) <= now]
    upcoming = [p for p in scheduled if parse_iso(p["at"]) > now]
    jobs = pmlib.active_jobs()
    whatsapp = whatsapp_state()
    total = len(scheduled) + len(jobs) + whatsapp["pending"] + whatsapp["confirmations"]
    return {
        "checked_at": now_iso(),
        "state": state,
        "activity": ("active" if total else "idle") if state == "on" else None,
        "idle_stopped": state == "off" and os.path.isfile(IDLE_STOP_FILE),
        "docker": docker_up,
        "containers": running,
        "services": svc,
        "pending": {
            "total": total,
            "scheduled": len(scheduled),
            "overdue": len(overdue),
            "jobs": jobs,
            "next": upcoming[0] if upcoming else (overdue[0] if overdue else None),
            "from_cache": snap is None,
            "cached_at": cached_at,
            "whatsapp": whatsapp,
        },
        "scheduled": scheduled[:MAX_LISTED],
        "drafts": snap.get("drafts") if snap else None,
        "failed_posts": snap.get("failed_posts") if snap else None,
        "last_status": snap.get("last_status") if snap else None,
        "channels": channel_rows(channels),
        "channel_alerts": channel_alerts(channels, warn_days(env)),
        "channels_from_cache": snap is None,
        "postiz_url": "https://" + env["NGROK_DOMAIN"] if env.get("NGROK_DOMAIN") else "http://localhost:4200",
        "project": pmlib.ROOT,
    }


def local_time(iso):
    return parse_iso(iso).astimezone().strftime("%a %d %b %H:%M")


def report(st):
    pend = st["pending"]
    lines = ["Publish Machine: %s%s" % (st["state"], " (%s)" % st["activity"] if st["activity"] else "")]
    svc = st["services"]
    if st["state"] == "partial":
        down = [name for name in ("postiz", "evolution", "scheduler", "tunnel") if not svc[name]]
        lines.append("Not answering: %s." % (", ".join(down) or "some containers"))
    if pend["scheduled"]:
        source = " (as of %s, the stack is off)" % local_time(pend["cached_at"]) if pend["from_cache"] and pend["cached_at"] else ""
        lines.append("%d scheduled post%s waiting%s:" % (pend["scheduled"], "" if pend["scheduled"] == 1 else "s", source))
        for post in st["scheduled"]:
            late = "  (overdue)" if parse_iso(post["at"]) <= datetime.now(timezone.utc) else ""
            lines.append("  %s  %-10s %-18s %s%s" % (local_time(post["at"]), post["provider"], post["channel"][:18],
                                                   post["text"][:50], late))
        if pend["scheduled"] > len(st["scheduled"]):
            lines.append("  … and %d more" % (pend["scheduled"] - len(st["scheduled"])))
    else:
        lines.append("No scheduled posts waiting.")
    wa = pend.get("whatsapp") or {}
    if wa.get("confirmations"):
        lines.append("%d WhatsApp plan%s awaiting confirmation." %
                     (wa["confirmations"], "" if wa["confirmations"] == 1 else "s"))
    if wa.get("pending"):
        parts = []
        if wa.get("awaiting_approval"):
            parts.append("%d awaiting approval" % wa["awaiting_approval"])
        if wa.get("approved"):
            parts.append("%d approved" % wa["approved"])
        lines.append("WhatsApp Status: " + ", ".join(parts) + ".")
    for job in pend["jobs"]:
        lines.append("In progress: %s: %s (since %s)" % (job["kind"], job["label"],
                                                         time.strftime("%H:%M", time.localtime(job["since"]))))
    if st["drafts"]:
        lines.append("%d draft%s waiting for your review in Postiz." % (st["drafts"], "" if st["drafts"] == 1 else "s"))
    if st["failed_posts"]:
        lines.append("%d post%s failed in the last 24 h (see Postiz)." % (st["failed_posts"], "" if st["failed_posts"] == 1 else "s"))
    for alert in st["channel_alerts"]:
        lines.append(alert_line(alert))
        lines.append("  Guided: ./publish-machine.sh channels --reconnect   Guide: " + alert["guide"])
    return "\n".join(lines)


def idle_eligible(state):
    pending = state["pending"]
    return state["state"] == "on" and not pending["from_cache"] and pending["total"] == 0


def main():
    parser = argparse.ArgumentParser(description="Report what the Publish Machine is doing (read-only).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="print one JSON object")
    mode.add_argument("--guard", action="store_true", help="exit %d if the stack is on and work is waiting" % GUARD_EXIT)
    mode.add_argument("--guard-idle", action="store_true", help="require a live, empty queue before automatic stop")
    mode.add_argument("--cache", action="store_true", help="refresh the schedule cache (needs the database)")
    mode.add_argument("--check-scheduler", action="store_true",
                      help="exit 0 if a Postiz worker polls Temporal, else 1 (publish-machine.sh start)")
    args = parser.parse_args()
    env = pmlib.load_env()

    if args.check_scheduler:
        return 0 if scheduler_alive() else 1

    if args.cache:
        snap = snapshot(env)
        if snap is None:
            print("Database not reachable; cache unchanged.", file=sys.stderr)
            return 1
        save_cache(snap.get("scheduled") or [], snap.get("channels") or [])
        return 0

    st = collect(env)
    if args.guard_idle:
        if idle_eligible(st):
            return 0
        print("Automatic stop skipped: work is waiting or live idle status could not be verified.", file=sys.stderr)
        return GUARD_EXIT
    if args.json:
        print(json.dumps(st, ensure_ascii=False))
        return 0
    print(report(st))
    if args.guard and st["state"] in ("on", "partial", "starting") and st["pending"]["total"]:
        print("If you turn it off now, scheduled posts go out late: as soon as the machine is on again.\n"
              "A WhatsApp status that is still sending may reach only part of its audience.")
        return GUARD_EXIT
    return 0


if __name__ == "__main__":
    sys.exit(main())
