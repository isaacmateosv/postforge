#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Connected channels: when each one stops working, and a guided reconnect (publish-machine.sh channels).

  channels.py                        list the channels and what needs attention
  channels.py --reconnect            walk through every channel that needs reconnecting
  channels.py --reconnect instagram  reconnect that network now, warning or not (restarts its 60 days);
                                     also facebook, meta (both), youtube, tiktok, threads
  channels.py --json                 the list as JSON

The reconnect itself happens in Postiz (Reconnect channel, log in, pick the same Page or account).
This opens Postiz, watches the database until the channel works again (up to 15 minutes), says so,
and refreshes the menu bar's cache. Guides: docs/reconnect/.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmlib  # noqa: E402
import machine_state as ms  # noqa: E402

WAIT_SECONDS = 15 * 60
POLL_SECONDS = 5
ALIASES = {"ig": "instagram", "fb": "facebook", "yt": "youtube", "tt": "tiktok", "th": "threads"}


def day(iso):
    return ms.parse_iso(iso).astimezone().strftime("%a %d %b %Y")


def matches(provider, network):
    network = ALIASES.get(network, network)
    if network == "meta":
        return provider.split("-")[0] in ("facebook", "instagram")
    return provider.split("-")[0] == network


def postiz_url(env):
    """The public address: OAuth logins come back to it, so a reconnect can't run on localhost."""
    if env.get("FRONTEND_URL"):
        return env["FRONTEND_URL"].rstrip("/")
    return "https://" + env["NGROK_DOMAIN"] if env.get("NGROK_DOMAIN") else "http://localhost:4200"


def state_of(channel, alert):
    if alert:
        if alert["reason"] == "expires soon":
            return "reconnect by %s (%s)" % (day(alert["expires"]), ms.days_phrase(alert["days_left"]))
        return alert["reason"].upper()
    if channel["provider"] in ms.NO_RENEWAL and channel.get("expires"):
        return "works until %s" % day(channel["expires"])
    return "works, renews itself"


def listing(env):
    snap = ms.snapshot(env)
    if snap is not None:
        channels, source = snap.get("channels") or [], "live"
    else:
        cache = ms.load_cache()
        channels = cache.get("channels") or []
        source = ("as of %s, the stack is off" % ms.local_time(cache["cached_at"])) if cache.get("cached_at") else "the stack is off"
    alerts = {(a["provider"], a["channel"]): a for a in ms.channel_alerts(channels, ms.warn_days(env))}
    return channels, alerts, source


def show(env):
    channels, alerts, source = listing(env)
    if not channels:
        print("No channels connected (%s). Add them in Postiz: Add Channel." % source)
        return 0
    print("Connected channels (%s):" % source)
    for c in channels:
        print("  %-14s %-22s %s" % (ms.NETWORKS.get(c["provider"], c["provider"]), c["channel"][:22],
                                     state_of(c, alerts.get((c["provider"], c["channel"])))))
    if any(c["provider"] in ms.NO_RENEWAL for c in channels):
        print("\nFacebook and Instagram connections last 60 days and can't renew themselves. Reconnecting\n"
              "early restarts the 60 days: ./publish-machine.sh channels --reconnect meta")
    for alert in alerts.values():
        print("\n" + ms.alert_line(alert))
        for n, step in enumerate(alert["steps"], 1):
            print("  %d. %s" % (n, step))
        print("  Guide: %s" % alert["guide"])
    if alerts:
        print("\nGuided (opens Postiz and confirms when it's done): ./publish-machine.sh channels --reconnect")
    return 0


def guided(env, network):
    snap = ms.snapshot(env)
    if snap is None:
        print("Publish Machine is off. Turn it on first (menu bar → Turn On, or ./publish-machine.sh start),\n"
              "then run this again.")
        return 1
    channels = snap.get("channels") or []
    alerts = ms.channel_alerts(channels, ms.warn_days(env))
    if network:
        targets = [c for c in channels if matches(c["provider"], network)]
        if not targets:
            print("No %s channel is connected. Add it in Postiz: Add Channel." % network)
            return 1
    else:
        wanted = {(a["provider"], a["channel"]) for a in alerts}
        targets = [c for c in channels if (c["provider"], c["channel"]) in wanted]
        if not targets:
            print("Nothing needs reconnecting.")
            return 0

    url = postiz_url(env) + "/launches"
    for c in targets:
        print("Reconnect %s (%s):" % (ms.NETWORKS.get(c["provider"], c["provider"]), c["channel"]))
        for n, step in enumerate(ms.reconnect_steps(c["provider"])[1:3], 1):
            print("  %d. %s" % (n, step))
    subprocess.run(["open", url], check=False)
    print("\nOpened %s. Waiting until it's done (up to 15 minutes; Ctrl-C stops waiting)…" % url)

    baseline = {(c["provider"], c["channel"]): c.get("updated") or "" for c in targets}
    pending = set(baseline)
    deadline = time.time() + WAIT_SECONDS
    try:
        while pending and time.time() < deadline:
            time.sleep(POLL_SECONDS)
            snap = ms.snapshot(env)
            if snap is None:
                continue
            now_channels = snap.get("channels") or []
            ms.save_cache(snap.get("scheduled") or [], now_channels)
            still = {(a["provider"], a["channel"]) for a in ms.channel_alerts(now_channels, ms.warn_days(env))}
            for c in now_channels:
                key = (c["provider"], c["channel"])
                if key in pending and (c.get("updated") or "") > baseline[key] and key not in still:
                    pending.discard(key)
                    until = (" until %s" % day(c["expires"])) if c["provider"] in ms.NO_RENEWAL and c.get("expires") else ""
                    print("✔ %s (%s) works again%s." % (ms.NETWORKS.get(c["provider"], c["provider"]), c["channel"], until))
    except KeyboardInterrupt:
        print("\nStopped waiting. Run this again whenever you're ready.")
        return 130
    if pending:
        names = ", ".join("%s (%s)" % (ms.NETWORKS.get(p, p), ch) for p, ch in sorted(pending))
        print("Still waiting for: %s. Run this again when you're ready. Guides: docs/reconnect/" % names)
        return 1
    print("All done. The menu bar shows it within a minute.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Connected channels: expiry, warnings and a guided reconnect.")
    parser.add_argument("--reconnect", nargs="?", const="", metavar="NETWORK",
                        help="guide through reconnecting (all that need it, or one network: instagram, "
                             "facebook, meta, youtube, tiktok, threads)")
    parser.add_argument("--json", action="store_true", help="print the channels and warnings as JSON")
    args = parser.parse_args()
    env = pmlib.load_env()
    if args.json:
        channels, alerts, source = listing(env)
        print(json.dumps({"source": source, "channels": ms.channel_rows(channels),
                          "alerts": list(alerts.values())}, ensure_ascii=False))
        return 0
    if args.reconnect is not None:
        return guided(env, args.reconnect.strip().lower())
    return show(env)


if __name__ == "__main__":
    sys.exit(main())
