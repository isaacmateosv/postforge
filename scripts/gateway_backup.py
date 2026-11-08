# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Snapshot and authenticate the private gateway files for Backup & Move."""
import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
from contextlib import closing
from pathlib import Path

from credentials import run_openssl

MAGIC = b"PostForge gateway backup v1\n"
FILES = ("configuration.yml", "users.json", "state.sqlite3")
OPTIONAL_FILES = ("media-signing.key",)
LIMIT = 64 * 1024 * 1024


def validate(directory):
    config = json.loads((directory / FILES[0]).read_text())
    users = json.loads((directory / FILES[1]).read_text())
    if not config["storage"]["encryption_key"] or not isinstance(users["users"], dict):
        raise ValueError("Invalid gateway configuration or users")
    with closing(sqlite3.connect((directory / FILES[2]).as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ValueError("Gateway database integrity check failed")


def keys(password, salt):
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000, dklen=64)
    return derived[:32].hex(), derived[32:]


def export_gateway(directory, output, password):
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        work = Path(temporary)
        for name in FILES:
            if (directory / name).is_symlink() or not (directory / name).is_file():
                raise ValueError("Gateway backup requires a private configuration and initialized database")
        for name in FILES[:2]:
            shutil.copyfile(directory / name, work / name)
        deadline = time.monotonic() + 15

        def check_deadline(status, remaining, total):
            if time.monotonic() > deadline:
                raise ValueError("Gateway database is busy. Try the backup again.")

        with closing(sqlite3.connect((directory / FILES[2]).as_uri() + "?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(work / FILES[2])) as destination:
                source.backup(destination, pages=128, progress=check_deadline)
                # Make the snapshot self-contained even when the live DB uses WAL.
                destination.execute("PRAGMA journal_mode=DELETE")
        if sum((work / name).stat().st_size for name in FILES) > LIMIT:
            raise ValueError("Gateway backup exceeds the supported size")
        validate(work)
        included = list(FILES)
        for name in OPTIONAL_FILES:
            source = directory / name
            if source.exists() or source.is_symlink():
                if source.is_symlink() or not source.is_file() or source.stat().st_size != 32:
                    raise ValueError("Invalid media signing key")
                shutil.copyfile(source, work / name)
                included.append(name)
        with zipfile.ZipFile(work / "snapshot", "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in included:
                archive.write(work / name, name)
        salt = os.urandom(16)
        encryption_password, auth_key = keys(password, salt)
        run_openssl("encrypt", encryption_password, work / "snapshot", work / "ciphertext")
        with (work / "ciphertext").open("rb") as stream:
            ciphertext = stream.read(LIMIT + 1)
        if len(ciphertext) > LIMIT:
            raise ValueError("Gateway backup exceeds the supported size")
        body = MAGIC + salt + ciphertext
        with (work / "sealed").open("wb") as stream:
            stream.write(body)
            stream.write(hmac.digest(auth_key, body, "sha256"))
        (work / "sealed").chmod(0o600)
        # Publish only after the same reader used by restore verifies the backup.
        restore_gateway(work / "sealed", work / "verified", password)
        os.replace(work / "sealed", output)


def restore_gateway(backup, directory, password):
    with backup.open("rb") as stream:
        envelope = stream.read(LIMIT + len(MAGIC) + 49)
    if not envelope.startswith(MAGIC) or not len(MAGIC) + 48 < len(envelope) <= LIMIT + len(MAGIC) + 48:
        raise ValueError("Invalid gateway backup")
    body, tag = envelope[:-32], envelope[-32:]
    offset = len(MAGIC) + 16
    encryption_password, auth_key = keys(password, body[len(MAGIC):offset])
    if not hmac.compare_digest(hmac.digest(auth_key, body, "sha256"), tag):
        raise ValueError("Wrong passphrase, or the gateway backup is damaged")
    with tempfile.TemporaryDirectory(dir=directory.parent) as temporary:
        work = Path(temporary)
        (work / "ciphertext").write_bytes(body[offset:])
        run_openssl("decrypt", encryption_password, work / "ciphertext", work / "snapshot")
        with zipfile.ZipFile(work / "snapshot") as archive:
            names = archive.namelist()
            if (len(names) != len(set(names)) or not set(FILES) <= set(names)
                    or not set(names) <= set(FILES + OPTIONAL_FILES)
                    or sum(entry.file_size for entry in archive.infolist()) > LIMIT):
                raise ValueError("Invalid gateway backup contents")
            staged = work / "gateway"
            staged.mkdir(mode=0o700)
            for name in names:
                if name in OPTIONAL_FILES and archive.getinfo(name).file_size != 32:
                    raise ValueError("Invalid media signing key")
                fd = os.open(staged / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as output, archive.open(name) as source:
                    shutil.copyfileobj(source, output)
        if not (staged / "media-signing.key").exists():
            fd = os.open(staged / "media-signing.key", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(os.urandom(32))
        validate(staged)
        staged.rename(directory)
