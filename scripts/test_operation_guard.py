# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/"lib"))
import operation_guard as guard

class GuardTests(unittest.TestCase):
    def test_backup_blocks_updates_but_completed_and_dead_jobs_do_not(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);jobs=root/'run/backup-jobs';jobs.mkdir(parents=True);job=jobs/'synthetic.json'
            job.write_text(json.dumps({'state':'running','pid':os.getpid()}))
            with self.assertRaisesRegex(ValueError,'backup or migration'):guard.assert_idle(root)
            job.write_text(json.dumps({'state':'done','pid':os.getpid()}));guard.assert_idle(root)
            job.write_text(json.dumps({'state':'running','pid':987654321}))
            with patch.object(guard.pmlib,'pid_alive',return_value=False):guard.assert_idle(root)
    def test_disruptive_operations_cannot_overlap(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as folder:
            def competing():
                with guard.maintenance(folder):return True
            with guard.maintenance(folder):
                with guard.maintenance(folder):pass  # Nested helpers in one operation share its lease.
                with ThreadPoolExecutor(max_workers=1) as pool:
                    with self.assertRaisesRegex(ValueError,'Another backup'):pool.submit(competing).result()
            with guard.maintenance(folder):pass
    def test_unreadable_active_state_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'run/whatsapp-pending.json';path.parent.mkdir();path.write_text('broken')
            with self.assertRaisesRegex(ValueError,'Could not verify'):guard.assert_idle(folder)
