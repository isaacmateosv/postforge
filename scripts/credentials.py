#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Encrypt or restore the private PostForge .env file.

The encrypted export is safe to carry privately. The plaintext is written with
mode 600 and is never placed in the repository package.

The passphrase is asked for in the terminal. The PostForge app has no terminal, so it
passes it in the PM_PASSPHRASE environment variable (read once, then removed).
"""
import argparse
import getpass
import os
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = os.path.join(ROOT, ".env")


def run_openssl(args, password, input_path, output_path):
    command = ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "600000",
               "-salt", "-pass", "stdin", "-in", input_path, "-out", output_path]
    if args == "decrypt":
        command.insert(2, "-d")
    proc = subprocess.run(command, input=(password + "\n").encode(), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip() or "openssl failed")


def passphrase(prompt, confirm_prompt=None):
    """From PM_PASSPHRASE when the app supplies it, else asked in the terminal."""
    supplied = os.environ.pop("PM_PASSPHRASE", None)
    if supplied is not None:
        return supplied, supplied
    first = getpass.getpass(prompt)
    return first, (getpass.getpass(confirm_prompt) if confirm_prompt else first)


def export_credentials(path):
    if not os.path.isfile(ENV):
        raise RuntimeError("No .env found at " + ENV)
    password, confirmation = passphrase("Encryption passphrase: ", "Re-enter encryption passphrase: ")
    if password != confirmation:
        raise RuntimeError("Passphrases do not match")
    if len(password) < 12:
        raise RuntimeError("Use a passphrase of at least 12 characters")
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".credentials-", dir=os.path.dirname(path))
    os.close(fd)
    try:
        run_openssl("encrypt", password, ENV, temporary)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    print("Encrypted credentials written to %s" % path)


def import_credentials(path):
    if not os.path.isfile(path):
        raise RuntimeError("Encrypted credentials file not found: " + path)
    password, _ = passphrase("Decryption passphrase: ")
    fd, temporary = tempfile.mkstemp(prefix=".env-", dir=ROOT)
    os.close(fd)
    try:
        run_openssl("decrypt", password, path, temporary)
        os.chmod(temporary, 0o600)
        os.replace(temporary, ENV)
    except Exception as exc:
        if os.path.exists(temporary):
            os.remove(temporary)
        if "bad decrypt" in str(exc) or "bad magic" in str(exc):
            raise RuntimeError("Wrong passphrase, or the file is damaged") from exc
        raise
    print("Decrypted .env restored with permissions 600")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    exporting = subparsers.add_parser("export")
    exporting.add_argument("path", nargs="?", default=os.path.join(ROOT, "exports", "credentials.env.enc"))
    importing = subparsers.add_parser("import")
    importing.add_argument("path")
    args = parser.parse_args()
    if args.action == "export":
        export_credentials(os.path.abspath(args.path))
    else:
        import_credentials(os.path.abspath(args.path))


if __name__ == "__main__":
    main()
