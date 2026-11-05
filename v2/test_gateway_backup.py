# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import sqlite3
import stat
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from gateway_backup import export_gateway, restore_gateway


class GatewayBackupTest(unittest.TestCase):
    def test_snapshot_includes_committed_wal_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "gateway"
            source.mkdir(mode=0o700)
            config = {"storage": {"encryption_key": "synthetic-encryption-key"}}
            users = {"users": {"owner@example.org": {"disabled": False}}}
            (source / "configuration.yml").write_text(json.dumps(config))
            (source / "users.json").write_text(json.dumps(users))
            (source / "enrollment.png").write_bytes(b"private temporary QR")
            backup = root / "gateway.enc"

            with closing(sqlite3.connect(source / "state.sqlite3")) as live:
                live.execute("PRAGMA journal_mode=WAL")
                live.execute("PRAGMA wal_autocheckpoint=0")
                live.execute("CREATE TABLE enrollment (value TEXT)")
                live.execute("INSERT INTO enrollment VALUES ('synthetic MFA record')")
                live.commit()
                self.assertTrue((source / "state.sqlite3-wal").exists())
                export_gateway(source, backup, "synthetic migration passphrase")

            restored = root / "restored"
            restore_gateway(backup, restored, "synthetic migration passphrase")
            self.assertEqual(stat.S_IMODE(restored.stat().st_mode), 0o700)
            self.assertEqual(
                {file.name: stat.S_IMODE(file.stat().st_mode) for file in restored.iterdir()},
                {"configuration.yml": 0o600, "users.json": 0o600, "state.sqlite3": 0o600},
            )
            self.assertEqual(json.loads((restored / "configuration.yml").read_text()), config)
            self.assertEqual(json.loads((restored / "users.json").read_text()), users)
            with closing(sqlite3.connect(restored / "state.sqlite3")) as db:
                self.assertEqual(db.execute("SELECT value FROM enrollment").fetchone(), ("synthetic MFA record",))

            invalid = root / "invalid"
            with self.assertRaisesRegex(ValueError, "Wrong passphrase"):
                restore_gateway(backup, invalid, "incorrect passphrase")
            with backup.open("ab") as stream:
                stream.write(b"tampered")
            with self.assertRaisesRegex(ValueError, "gateway backup is damaged"):
                restore_gateway(backup, invalid, "synthetic migration passphrase")
            self.assertFalse(invalid.exists())
