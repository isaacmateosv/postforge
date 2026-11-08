# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare an allowlisted Google OAuth policy. Does not start or modify ngrok."""
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

EMAIL = re.compile(r"[a-z0-9][a-z0-9._%+-]*@[a-z0-9-]+(?:\.[a-z0-9-]+)+", re.ASCII)


def make_policy(lines):
    addresses = sorted({line.strip().lower() for line in lines if line.strip()})
    if not addresses or any(len(address) > 254 or not EMAIL.fullmatch(address) for address in addresses):
        raise ValueError("Enter at least one valid Google sign-in email, one address per line.")
    return {
        "on_http_request": [
            {"actions": [{"type": "oauth", "config": {"provider": "google"}}]},
            {
                "expressions": [f"!(actions.ngrok.oauth.identity.email in {json.dumps(addresses)})"],
                "actions": [{"type": "deny", "config": {"status_code": 403}}],
            },
        ],
    }


def write_policy(path, policy):
    path.parent.mkdir(mode=0o700, exist_ok=True)
    if path.parent.stat().st_mode & 0o077:
        raise ValueError("Use a private policy directory with permissions 0700.")
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".policy-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(policy, output, indent=2)
            output.write("\n")
        # The non-root agent can read the mounted file. The parent directory
        # prevents other host users from traversing to it.
        os.chmod(temporary, 0o444)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("run/ngrok-access/policy.json"))
    args = parser.parse_args()
    if sys.stdin.isatty():
        print("Enter the allowed Google email addresses, one per line. Press Ctrl-D when finished.", file=sys.stderr)
    try:
        write_policy(args.output, make_policy(sys.stdin))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")
    print("Policy prepared. The running tunnel has not changed.")


if __name__ == "__main__":
    main()
