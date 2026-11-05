#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Move Postiz's own data between machines (DEPLOY-M1.md §8): account, channels, posts, media.

    export              exports/postiz-<date>.tar: Postiz's tables (pg_dump --schema=public),
                        data/postiz-uploads/ and a manifest with row counts. Contains channel
                        tokens: mode 600, never in the transfer bundle, carry it like .env.
    rehearse FILE       restore FILE into a throwaway database and folder, compare with the
                        manifest, then remove both. Changes nothing else.
    import FILE         restore FILE into this machine's Postiz, before Postiz first starts
                        (refuses if Postiz is running or already has tables; --replace to overwrite).

The WhatsApp session, Redis and Temporal's databases are never moved (see DEPLOY-M1.md §8).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

import pmlib
from pmlib import PMError, info

EXPORT_DIR = os.path.join(pmlib.ROOT, "exports")
UPLOADS = os.path.join(pmlib.ROOT, "data", "postiz-uploads")
REHEARSAL_DB = "pm_restore_rehearsal"


def pg(env, args, stdin=None, db=None):
    """Run a Postgres client tool inside pm-postgres; returns stdout bytes."""
    cmd = ["docker", "exec", "-i", "pm-postgres"] + args[:1] + ["-U", env.get("POSTGRES_USER", "postiz")]
    if db is not False:
        cmd += ["-d", db or env.get("POSTGRES_DB", "postiz")]
    cmd += args[1:]
    proc = subprocess.run(cmd, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise PMError("%s failed: %s" % (args[0], proc.stderr.decode("utf-8", "replace").strip()[-600:]))
    return proc.stdout


def sql(env, query, db=None):
    out = pg(env, ["psql", "-t", "-A", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-c", query], db=db)
    return [line.split("\t") for line in out.decode("utf-8").splitlines() if line]


def row_counts(env, db=None):
    tables = [r[0] for r in sql(env, "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1", db)]
    if not tables:
        return {}
    union = " UNION ALL ".join("SELECT '%s', count(*) FROM public.\"%s\"" % (t, t) for t in tables)
    return {name: int(n) for name, n in sql(env, union, db)}


def running(name):
    out = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", name],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout.strip()
    return out == "true"


def need_postgres():
    if not running("pm-postgres"):
        info("Starting Postgres only...")
        pmlib.run(["docker", "compose", "-f", os.path.join(pmlib.ROOT, "docker-compose.yml"), "up", "-d", "postgres"])
    for _ in range(30):
        if subprocess.run(["docker", "exec", "pm-postgres", "pg_isready", "-q"]).returncode == 0:
            return
        time.sleep(2)
    raise PMError("Postgres did not become ready")


def upload_stats(folder):
    files, size = 0, 0
    for base, _, names in os.walk(folder):
        for name in names:
            files += 1
            size += os.path.getsize(os.path.join(base, name))
    return files, size


def export(env):
    need_postgres()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    os.makedirs(EXPORT_DIR, exist_ok=True)
    os.chmod(EXPORT_DIR, 0o700)
    target = os.path.join(EXPORT_DIR, "postiz-%s.tar" % stamp)
    work = tempfile.mkdtemp(prefix="pm-export-")
    try:
        info("Dumping Postiz's tables...")
        with open(os.path.join(work, "postiz-public.dump"), "wb") as fh:
            fh.write(pg(env, ["pg_dump", "--schema=public", "--no-owner", "--no-privileges", "-Fc"]))
        info("Packing data/postiz-uploads/...")
        with tarfile.open(os.path.join(work, "uploads.tar"), "w") as tar:
            if os.path.isdir(UPLOADS):
                tar.add(UPLOADS, arcname="postiz-uploads")
        files, size = upload_stats(UPLOADS) if os.path.isdir(UPLOADS) else (0, 0)
        image = subprocess.run(["docker", "inspect", "-f", "{{.Config.Image}}", "pm-postiz"],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout.strip()
        manifest = {"created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "postiz_image": image or None,
                    "rows": row_counts(env), "upload_files": files, "upload_bytes": size}
        with open(os.path.join(work, "manifest.json"), "w") as fh:
            json.dump(manifest, fh, indent=1)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as out, tarfile.open(fileobj=out, mode="w") as tar:
            for name in ("manifest.json", "postiz-public.dump", "uploads.tar"):
                tar.add(os.path.join(work, name), arcname=name)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    rows = manifest["rows"]
    info("✔ Exported %s (%d tables; users %s, channels %s, posts %s; %d media files, %.1f MB)"
         % (target, len(rows), rows.get("User", 0), rows.get("Integration", 0), rows.get("Post", 0),
            files, size / 1e6))
    info("  It holds channel tokens: keep it private and carry it like .env.")
    return 0


def archive_members(tar, destination, members=None, required_prefix=None):
    """Restore regular files/directories only, within the selected destination."""
    selected = tar.getmembers() if members is None else [tar.getmember(name) for name in members]
    root = os.path.realpath(destination)
    for item in selected:
        target = os.path.realpath(os.path.join(root, item.name))
        if required_prefix and item.name.split("/")[0] != required_prefix:
            raise PMError("Backup media is outside its expected folder")
        if os.path.isabs(item.name) or os.path.commonpath([root, target]) != root:
            raise PMError("Backup contains a path outside its destination")
        if not (item.isfile() or item.isdir()):
            raise PMError("Backup contains a link or unsupported file type")
    return selected


def safe_extract(tar, destination, members=None, required_prefix=None):
    tar.extractall(destination, members=archive_members(tar, destination, members, required_prefix))


def unpack(path):
    work = tempfile.mkdtemp(prefix="pm-import-")
    try:
        with tarfile.open(path) as tar:
            safe_extract(tar, work, ("manifest.json", "postiz-public.dump", "uploads.tar"))
        with open(os.path.join(work, "manifest.json")) as fh:
            return work, json.load(fh)
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise


def compare(expected, actual):
    diff = {t: (n, actual.get(t)) for t, n in expected.items() if actual.get(t) != n}
    if diff:
        raise PMError("Row counts differ after restore (table: expected, got): %s" % diff)


def restore(env, work, db):
    # --clean: the dump creates schema "public", which every new database already has (empty).
    # do_import refuses to run over existing tables unless asked to replace them.
    args = ["pg_restore", "--no-owner", "--no-privileges", "--exit-on-error", "--clean", "--if-exists"]
    with open(os.path.join(work, "postiz-public.dump"), "rb") as fh:
        pg(env, args, stdin=fh.read(), db=db)


def rehearse(env, path):
    scratch_db = REHEARSAL_DB + "_" + str(os.getpid()) + "_" + os.urandom(3).hex()
    need_postgres()
    work, manifest = unpack(path)
    scratch = tempfile.mkdtemp(prefix="pm-uploads-")
    try:
        sql(env, "DROP DATABASE IF EXISTS %s" % scratch_db)
        sql(env, "CREATE DATABASE %s" % scratch_db)
        restore(env, work, scratch_db)
        compare(manifest["rows"], row_counts(env, scratch_db))
        with tarfile.open(os.path.join(work, "uploads.tar")) as tar:
            safe_extract(tar, scratch, required_prefix="postiz-uploads")
        files, size = upload_stats(scratch)
        if (files, size) != (manifest["upload_files"], manifest["upload_bytes"]):
            raise PMError("Media differs: expected %s files / %s bytes, got %s / %s"
                          % (manifest["upload_files"], manifest["upload_bytes"], files, size))
        info("✔ Rehearsal passed: %d tables with the same row counts, %d media files (%.1f MB)."
             % (len(manifest["rows"]), files, size / 1e6))
    finally:
        try:
            sql(env, "DROP DATABASE IF EXISTS %s" % scratch_db)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
            shutil.rmtree(work, ignore_errors=True)
    return 0


def do_import(env, path, replace):
    if running("pm-postiz"):
        raise PMError("Postiz is running. Import before its first start, or stop it: docker compose stop postiz")
    need_postgres()
    if row_counts(env) and not replace:
        raise PMError("This Postiz database already has tables. Use --replace to overwrite them.")
    if os.path.isdir(UPLOADS) and os.listdir(UPLOADS) and not replace:
        raise PMError("data/postiz-uploads/ is not empty. Use --replace to overwrite it.")
    work, manifest = unpack(path)
    try:
        # Validate media paths before changing the destination database.
        with tarfile.open(os.path.join(work, "uploads.tar")) as tar:
            archive_members(tar, os.path.dirname(UPLOADS), required_prefix="postiz-uploads")
        info("Restoring Postiz's tables...")
        restore(env, work, None)
        compare(manifest["rows"], row_counts(env))
        info("Restoring media into data/postiz-uploads/...")
        os.makedirs(os.path.dirname(UPLOADS), exist_ok=True)
        with tarfile.open(os.path.join(work, "uploads.tar")) as tar:
            safe_extract(tar, os.path.dirname(UPLOADS), required_prefix="postiz-uploads")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    info("✔ Imported. Now run ./publish-machine.sh start and log in with the existing account.")
    return 0


def main():
    parser = argparse.ArgumentParser(prog="postiz-transfer.sh", description=__doc__.split("\n")[0],
                                     epilog=__doc__.split("\n", 2)[2], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("export", "rehearse", "import"))
    parser.add_argument("file", nargs="?", help="an export made by `export` (rehearse, import)")
    parser.add_argument("--replace", action="store_true", help="import over existing Postiz data")
    args = parser.parse_args()
    env = pmlib.load_env()
    if args.action == "export":
        return export(env)
    if not args.file or not os.path.isfile(args.file):
        raise PMError("Give the export file, e.g. exports/postiz-YYYYMMDD-HHMM.tar")
    if args.action == "rehearse":
        return rehearse(env, args.file)
    return do_import(env, args.file, args.replace)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PMError as exc:
        print("✖ " + str(exc), file=sys.stderr)
        sys.exit(1)
