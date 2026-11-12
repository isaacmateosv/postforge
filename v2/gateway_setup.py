# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Provision a private gateway configuration. Never starts or switches the tunnel."""
import argparse
import getpass
import json
import os
import re
import secrets
import tempfile
from pathlib import Path

DEFAULT = Path("data/gateway")
EMAIL = re.compile(r"[a-z0-9][a-z0-9._%+-]*@[a-z0-9-]+(?:\.[a-z0-9-]+)+", re.ASCII)
HOST = re.compile(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z][a-z0-9-]+", re.ASCII)
HASH = re.compile(r"\$argon2id\$v=19\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+")


def private_write(path, value):
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def config(host):
    if not HOST.fullmatch(host) or ".." in host:
        raise ValueError("Use the exact HTTPS hostname, without a scheme, port, or path.")
    origin = "https://" + host
    return {
        "server": {"address": "tcp://:9091/authelia"},
        "authentication_backend": {"password_reset": {"disable": True},
                                   "file": {"path": "/config/users.json"}},
        "access_control": {"default_policy": "deny",
                           "rules": [{"domain": host, "subject": ["group:postforge"], "policy": "two_factor"}]},
        "session": {"name": "postforge_gateway", "secret": secrets.token_urlsafe(48),
                    "same_site": "lax", "inactivity": "30m", "expiration": "2h", "remember_me": -1,
                    "cookies": [{"domain": host, "authelia_url": origin + "/authelia",
                                 "default_redirection_url": origin + "/"}]},
        "storage": {"encryption_key": secrets.token_urlsafe(48), "local": {"path": "/config/state.sqlite3"}},
        "notifier": {"filesystem": {"filename": "/config/enrollment-notices.txt"}},
        "regulation": {"max_retries": 4, "find_time": "5m", "ban_time": "15m"},
        "log": {"level": "warn"},
    }


def update_hostname(current, host):
    generated = config(host)
    current["access_control"]["rules"][0]["domain"] = generated["access_control"]["rules"][0]["domain"]
    current["session"]["cookies"] = generated["session"]["cookies"]
    return current


def users(directory):
    return json.loads((directory / "users.json").read_text(encoding="utf-8"))["users"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init").add_argument("hostname")
    commands.add_parser("set-hostname").add_argument("hostname")
    add = commands.add_parser("add-user")
    add.add_argument("email")
    add.add_argument("--hash-file", type=Path)
    commands.add_parser("list-users")
    change = commands.add_parser("set-allowed")
    change.add_argument("email")
    change.add_argument("state", choices=("allow", "deny"))
    args = parser.parse_args()
    directory = args.directory
    try:
        if args.command == "init":
            initial = config(args.hostname.lower())
            directory.mkdir(mode=0o700, parents=True, exist_ok=False)
            private_write(directory / "configuration.yml", initial)
            private_write(directory / "users.json", {"users": {}})
            fd = os.open(directory / "media-signing.key", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(secrets.token_bytes(32))
            return 0
        if directory.stat().st_mode & 0o077:
            raise ValueError("The gateway directory must be private (0700 on macOS and Linux).")
        if args.command == "set-hostname":
            file = directory / "configuration.yml"
            current = json.loads(file.read_text(encoding="utf-8"))
            private_write(file, update_hostname(current, args.hostname.lower()))
            print("Hostname saved locally. Check TLS and the new gateway route before applying.")
            return 0
        records = users(directory)
        if args.command == "list-users":
            print(json.dumps([{"email": key, "allowed": not value.get("disabled", False)}
                              for key, value in sorted(records.items())]))
            return 0
        email = args.email.strip().lower()
        if len(email) > 254 or not EMAIL.fullmatch(email):
            raise ValueError("Use a valid email address.")
        if args.command == "add-user":
            if email in records:
                raise ValueError("That user already exists.")
            value = (args.hash_file.read_text() if args.hash_file else getpass.getpass("Argon2id password hash: ")).strip()
            if not HASH.fullmatch(value):
                raise ValueError("Expected an Authelia Argon2id password hash.")
            records[email] = {"displayname": email, "password": value, "email": email,
                              "groups": ["postforge"], "disabled": False}
        else:
            if email not in records:
                raise ValueError("That user has not been provisioned.")
            records[email]["disabled"] = args.state == "deny"
            if all(record.get("disabled", False) for record in records.values()):
                raise ValueError("At least one user must remain allowed.")
        private_write(directory / "users.json", {"users": records})
        print("Saved locally. Restart the gateway identity service to apply this change.")
        return 0
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
