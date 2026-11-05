#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Regression checks for retention, optional liveness, and read-only update detection."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import tarfile
from datetime import datetime, timezone, timedelta
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'lib'))


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / filename))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


retention = module('retention', 'retention.py')
updates = module('updates', 'component_updates.py')
rollback = module('rollback', 'image_rollback.py')
import wa_inbox
import create_draft
import plan_post
import postiz_transfer
import pmlib
credentials = module("credentials", "credentials.py")


class Operations(unittest.TestCase):
    def test_uninstall_preserves_data_and_aborts_on_failed_docker_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            project = root / 'project'
            home = root / 'home'
            app = home / 'Applications' / 'PostForge.app'
            app.mkdir(parents=True)
            tools = root / 'bin'
            tools.mkdir()
            docker = tools / 'docker'
            docker.write_text('#!/bin/bash\n[[ "$1" == info || "$TEST_COMPOSE_OK" == yes ]]\n')
            docker.chmod(0o755)
            scripts = project / 'scripts'
            scripts.mkdir(parents=True)
            uninstall = scripts / 'uninstall.sh'
            shutil.copyfile(ROOT / 'uninstall.sh', uninstall)
            (project / 'docker-compose.yml').touch()
            private_files = [project / '.env', project / 'data' / 'db', project / 'exports' / 'backup']
            for file in private_files:
                file.parent.mkdir(exist_ok=True)
                file.write_text('synthetic private data')
            env = dict(os.environ, HOME=str(home), PATH=str(tools) + os.pathsep + os.environ['PATH'])
            args = ['/bin/bash', str(uninstall), '--yes', '--keep-app-running']
            failed = subprocess.run(args + ['--purge-data'], env=dict(env, TEST_COMPOSE_OK='no'),
                                    capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertTrue(app.exists())
            subprocess.run(args, env=dict(env, TEST_COMPOSE_OK='yes'), check=True, capture_output=True)
            self.assertFalse(app.exists())
            for file in private_files:
                self.assertEqual(file.read_text(), 'synthetic private data')

    def test_backup_rejects_traversal_and_links_before_writing(self):
        for name, kind in [("../outside.txt", tarfile.REGTYPE), ("link", tarfile.SYMTYPE)]:
            with tempfile.TemporaryDirectory() as folder:
                archive = Path(folder) / 'bad.tar'
                with tarfile.open(archive, 'w') as target:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = '../outside.txt' if kind == tarfile.SYMTYPE else ''
                    target.addfile(member, io.BytesIO(b''))
                destination = Path(folder) / 'restore'
                destination.mkdir()
                with tarfile.open(archive) as source:
                    with self.assertRaises(pmlib.PMError):
                        postiz_transfer.safe_extract(source, str(destination))
                self.assertEqual(list(destination.iterdir()), [])
                self.assertFalse((Path(folder) / 'outside.txt').exists())

    def test_credentials_round_trip_and_wrong_password_preserves_env(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(credentials, 'ROOT', folder), patch.object(credentials, 'ENV', str(Path(folder) / '.env')), contextlib.redirect_stdout(io.StringIO()):
            env = Path(folder) / '.env'
            original = b'TEST_SECRET=synthetic-only\n'
            env.write_bytes(original)
            archive = str(Path(folder) / 'credentials.env.enc')
            with patch.object(credentials, 'passphrase', return_value=('correct-test-passphrase', 'correct-test-passphrase')):
                credentials.export_credentials(archive)
                env.write_bytes(b'CURRENT=preserve-me\n')
            with patch.object(credentials, 'passphrase', return_value=('wrong-test-passphrase', 'wrong-test-passphrase')):
                with self.assertRaises(RuntimeError):
                    credentials.import_credentials(archive)
            self.assertEqual(env.read_bytes(), b'CURRENT=preserve-me\n')
            with patch.object(credentials, 'passphrase', return_value=('correct-test-passphrase', 'correct-test-passphrase')):
                credentials.import_credentials(archive)
            self.assertEqual(env.read_bytes(), original)
            self.assertEqual(env.stat().st_mode & 0o777, 0o600)

    def test_caption_removes_prompt_echo_and_duplicate_cta(self):
        text = 'Pan de yuca recién horneado. Pan de yuca recién horneado. 🍎\nEscribe frases cortas sobre el tema.\nHaz tu pedido por WhatsApp.\n#PanDeYuca #PanDeYuca'
        result = create_draft.finish(text, 'Spanish', topic='pan de yuca')
        self.assertNotIn('frases cortas', result)
        self.assertNotIn('🍎', result)
        self.assertEqual(result.count('Pan de yuca recién horneado.'), 1)
        self.assertEqual(result.count('WhatsApp'), 1)
        self.assertEqual(result.count('#PanDeYuca'), 1)
        self.assertIn('retíralo', result)

    def test_draft_contract_cannot_schedule_a_live_post(self):
        api = object.__new__(pmlib.Postiz)
        api.env = {}
        with patch.object(api, '_call', return_value=[{'postId': 'test'}]) as call:
            api.create_draft({'id': 'test', 'identifier': 'facebook'}, 'Texto aprobado', when=datetime(2026, 11, 6, 23, tzinfo=timezone.utc))
        payload = call.call_args.args[2]
        self.assertEqual(payload['type'], 'draft')
        self.assertEqual(payload['date'], '2026-11-06T23:00:00.000Z')
        self.assertEqual(payload['posts'][0]['value'][0]['content'], 'Texto aprobado')

    def test_ecuador_schedule_does_not_take_dates_from_caption(self):
        now = datetime(2026, 11, 4, 12, tzinfo=timezone(timedelta(hours=-5)))
        result = plan_post.plan({}, 'Facebook mañana a las 6 de la tarde, texto: Pedidos hasta el sábado', [], 'Spanish', now)
        self.assertEqual(result['when'], datetime(2026, 11, 5, 18, tzinfo=now.tzinfo))
        self.assertEqual(result['exact'], 'Pedidos hasta el sábado')

    def test_oversized_protobuf_media_never_reaches_evolution(self):
        row = {'type': 'videoMessage', 'key': {'id': 'test'}, 'message': {'videoMessage': {'fileLength': {'low': 180887424, 'high': 0, 'unsigned': True}}}}
        with patch.object(wa_inbox, 'evo_call') as api:
            with self.assertRaises(wa_inbox.PMError):
                wa_inbox.download({}, 'test', row, '/tmp')
            api.assert_not_called()
        self.assertEqual(wa_inbox.media_size({'type': 'videoMessage', 'message': {'videoMessage': {'fileLength': {'low': -1, 'high': 1}}}}), (1 << 33) - 1)
        self.assertEqual(wa_inbox.media_size({'type': 'audioMessage', 'message': {'audioMessage': {'fileLength': '1024'}}}), 1024)
        self.assertIsNone(wa_inbox.media_size({'type': 'imageMessage', 'message': {}}))

    def test_retention_preserves_referenced_media_and_pending_plans(self):
        with tempfile.TemporaryDirectory() as folder:
            roots = [Path(folder) / name for name in ('postiz-uploads', 'logs', 'wa-confirmations')]
            for root in roots:
                root.mkdir()
            for root, name in [(roots[0], 'scheduled.jpg'), (roots[0], 'unused.jpg'), (roots[1], 'old.log'), (roots[2], 'pending.json')]:
                target = root / name
                target.write_text('test')
                os.utime(target, (1, 1))
            with patch.object(retention, 'ROOTS', tuple(map(str, roots))), patch.object(retention, 'referenced_media', return_value='[{"path":"/uploads/scheduled.jpg"}]'):
                self.assertEqual({Path(p).name for p in retention.candidates(time.time())}, {'unused.jpg', 'old.log'})
            with patch.object(retention, 'ROOTS', tuple(map(str, roots))), patch.object(retention, 'referenced_media', return_value=None):
                self.assertEqual({Path(p).name for p in retention.candidates(time.time())}, {'old.log'})

    def test_registry_timeout_also_stops_a_child_holding_the_pipe(self):
        code = "import subprocess,sys,time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); time.sleep(60)"
        started = time.monotonic()
        with patch.object(updates, 'COMMAND_TIMEOUT_SECONDS', 0.3):
            self.assertIsNone(updates.run([sys.executable, '-c', code]))
        self.assertLess(time.monotonic() - started, 3)

    def test_pinned_digest_needs_no_registry_request(self):
        image = 'repo@sha256:fixed'
        with patch.object(updates, 'run', return_value='["repo@sha256:fixed"]') as command:
            self.assertEqual(updates.image_status(image), (image, 'current'))
        self.assertEqual(command.call_count, 1)

    def test_unavailable_docker_is_not_reported_as_up_to_date(self):
        with patch.object(updates, 'run', return_value=None):
            result = updates.check()
        self.assertFalse(result['check_complete'])
        self.assertFalse(result['updates_available'])

    def test_component_updates_distinguish_changed_and_unknown(self):
        def fake(args):
            if args[1] == 'compose':
                return 'same:1\nchanged:1\nunknown:1'
            image = args[3] if args[1] == 'image' else args[4]
            if image == 'unknown:1':
                return None
            return json.dumps(['repo@sha256:old']) if args[1] == 'image' else json.dumps({'digest': 'sha256:old' if image == 'same:1' else 'sha256:new'})
        with patch.object(updates, 'run', side_effect=fake):
            result = updates.check()
            self.assertEqual(result['components'], [{'name': 'changed:1', 'kind': 'docker'}])
            self.assertTrue(result['updates_available'])
            self.assertFalse(result['check_complete'])
            self.assertEqual(result['unchecked_images'], ['unknown:1'])

    def test_rollback_keeps_immutable_digest_references(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'images.json'
            path.write_text(json.dumps({'image@sha256:pinned': 'sha256:pinned', 'mutable:1': 'sha256:old'}))
            with patch.object(rollback, 'command', return_value='ok') as command, patch.object(sys, 'argv', ['rollback', 'restore', str(path)]):
                rollback.main()
            tags = [call.args for call in command.call_args_list if 'tag' in call.args]
            self.assertEqual(tags, [('docker', 'image', 'tag', 'sha256:old', 'mutable:1')])

    def test_rollback_checks_all_images_before_changing_tags(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'images.json'
            path.write_text(json.dumps({'first:1': 'sha256:first', 'second:1': 'sha256:missing'}))
            calls = []
            def fake(*args):
                calls.append(args)
                if 'sha256:missing' in args:
                    raise RuntimeError('missing image')
                return 'ok'
            with patch.object(rollback, 'command', side_effect=fake), patch.object(sys, 'argv', ['rollback', 'restore', str(path)]):
                with self.assertRaises(RuntimeError):
                    rollback.main()
            self.assertFalse(any('tag' in call for call in calls))


if __name__ == '__main__':
    unittest.main()
