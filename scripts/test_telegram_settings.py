# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import telegram_settings as settings
import credentials
import host_agent

TOKEN = '12345:' + 'x' * 30


class TelegramSettingsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.env = self.root / '.env'
        self.env.write_text('KEEP_ME=synthetic-value\n', encoding='utf-8')
        self.payload = {'enabled': True, 'token': TOKEN, 'owner_id': '7', 'language': 'es', 'heartbeat': 15}
        for name in ('start', 'stop', 'running'):
            mock = patch.object(host_agent, name, return_value=False if name == 'running' else None)
            setattr(self, name, mock.start())
            self.addCleanup(mock.stop)

    def api(self, token, method, **payload):
        self.assertEqual(token, TOKEN)
        return {'getMe': {'id': 12345, 'username': 'synthetic_bot'}, 'getWebhookInfo': {},
                'getChat': {'id': 7, 'type': 'private'}, 'setMyCommands': True,
                'getUpdates': [{'update_id': 42}]}[method]

    def save(self):
        with patch.object(settings, 'telegram', side_effect=self.api):
            return settings.save(self.payload, self.root)

    def test_save_private_env_and_status_never_returns_token(self):
        result = self.save()
        self.assertTrue(result['enabled'])
        self.assertTrue(result['configured'])
        self.assertNotIn(TOKEN, json.dumps(result))
        config = settings.configuration(self.root)
        self.assertEqual(config['TELEGRAM_OWNER_ID'], '7')
        self.assertEqual(config['TELEGRAM_BOT_TOKEN'], TOKEN)
        self.assertEqual(config['TELEGRAM_LANGUAGE'], 'es')
        self.assertIn('KEEP_ME=synthetic-value', self.env.read_text())
        self.assertEqual(json.loads((self.root / 'run/host-agent/telegram.json').read_text())['offset'], 43)
        self.start.assert_called_once()
        if sys.platform != 'win32':
            self.assertEqual(self.env.stat().st_mode & 0o777, 0o600)

    def test_mobile_ping_changes_only_interval_and_preserves_migration_hold(self):
        self.env.write_text('KEEP_ME=synthetic-value\nTELEGRAM_BOT_TOKEN='+TOKEN+'\nTELEGRAM_OWNER_ID=7\nTELEGRAM_ENABLED=false\nTELEGRAM_MIGRATION_HOLD=true\nTELEGRAM_LANGUAGE=es\nTELEGRAM_HEARTBEAT_MINUTES=15\n')
        before=settings.configuration(self.root)
        result=settings.set_heartbeat(60,self.root)
        after=settings.configuration(self.root)
        self.assertEqual(result['minutes'],60)
        self.assertFalse(result['active'])
        before.pop('TELEGRAM_HEARTBEAT_MINUTES');after.pop('TELEGRAM_HEARTBEAT_MINUTES')
        self.assertEqual(before,after)
        self.start.assert_not_called();self.stop.assert_not_called()
        self.assertNotIn(TOKEN,json.dumps(result))
        for value in (-1,1,1441,True,'60'):
            with self.assertRaises(ValueError):settings.set_heartbeat(value,self.root)
        self.assertEqual(settings.heartbeat_preferences(self.root)['minutes'],60)

    def test_disable_works_offline_and_keeps_preferences(self):
        self.save()
        with patch.object(settings, 'telegram', side_effect=AssertionError('No network when disabling')):
            result = settings.save(dict(self.payload, enabled=False, token=''), self.root)
        self.assertFalse(result['enabled'])
        self.assertEqual(settings.configuration(self.root)['TELEGRAM_BOT_TOKEN'], TOKEN)
        self.assertFalse(settings.active(settings.configuration(self.root)))

    def test_invalid_webhook_or_group_does_not_mutate_env(self):
        original = self.env.read_text()
        for method, invalid in [('getWebhookInfo', {'url': 'https://example.org/hook'}), ('getChat', {'id': -7, 'type': 'group'})]:
            def api(token, action, **payload):
                return invalid if action == method else self.api(token, action, **payload)
            with patch.object(settings, 'telegram', side_effect=api), self.assertRaises(ValueError):
                settings.save(self.payload, self.root)
            self.assertEqual(self.env.read_text(), original)
        self.stop.assert_not_called()

    def test_restart_failure_restores_config_and_conversation(self):
        old = self.root / 'run/host-agent/conversation-old.json'
        old.parent.mkdir(parents=True)
        old.write_text('{"old":"review"}')
        self.running.return_value = True
        self.start.side_effect = [RuntimeError('Synthetic startup failure'), None]
        original = self.env.read_text()
        with self.assertRaisesRegex(RuntimeError, 'Synthetic'):
            self.save()
        self.assertEqual(self.env.read_text(), original)
        self.assertEqual(old.read_text(), '{"old":"review"}')
        self.assertFalse((old.parent / 'telegram.json').exists())

    def test_legacy_settings_are_encrypted_and_restored_paused(self):
        legacy = self.root / 'run/telegram'
        legacy.mkdir(parents=True)
        (legacy / 'token').write_text(TOKEN)
        (legacy / 'settings.env').write_text('TELEGRAM_OWNER_ID=7\nTELEGRAM_LANGUAGE=es\nTELEGRAM_HEARTBEAT_MINUTES=15\n')
        encrypted = self.root / 'credentials.env.enc'
        destination = self.root / 'restored.env'
        with patch.object(credentials, 'ROOT', str(self.root)), patch.object(credentials, 'ENV', str(self.env)), \
             patch.object(credentials, 'passphrase', return_value=('synthetic long migration passphrase',)*2):
            credentials.export_credentials(str(encrypted))
            self.assertNotIn(TOKEN.encode(), encrypted.read_bytes())
            credentials.import_credentials(str(encrypted), output=str(destination))
        restored = settings.read_values(destination)
        self.assertEqual(restored['TELEGRAM_BOT_TOKEN'], TOKEN)
        self.assertEqual(restored['TELEGRAM_OWNER_ID'], '7')
        self.assertEqual(restored['TELEGRAM_LANGUAGE'], 'es')
        self.assertEqual(restored['TELEGRAM_HEARTBEAT_MINUTES'], '15')
        self.assertEqual(restored['TELEGRAM_ENABLED'], 'true')
        self.assertEqual(restored['TELEGRAM_MIGRATION_HOLD'], 'true')
        self.assertFalse(settings.active(restored))
        self.assertNotIn('TELEGRAM_BOT_TOKEN', self.env.read_text())

    def test_restore_resume_ignores_old_commands_and_keeps_settings(self):
        self.save()
        self.env.write_text(settings.hold_restored(self.env.read_text()), encoding='utf-8')
        self.payload['token'] = ''
        result = self.save()
        self.assertFalse(result['migration_hold'])
        self.assertEqual(result['heartbeat'], 15)
        self.assertEqual(result['owner_id'], '7')
        self.assertTrue(settings.active(settings.configuration(self.root)))

    def test_restored_env_overrides_old_runtime_and_disabled_preference_survives(self):
        self.save()
        settings.save(dict(self.payload, enabled=False, token=''), self.root)
        restored = settings.hold_restored(settings.export_env(self.env.read_text(), self.root))
        destination = self.root / 'other-computer'
        (destination / 'run/telegram').mkdir(parents=True)
        (destination / '.env').write_text(restored)
        (destination / 'run/telegram/token').write_text('999:' + 'z' * 30)
        config = settings.configuration(destination)
        self.assertEqual(config['TELEGRAM_BOT_TOKEN'], TOKEN)
        self.assertEqual(config['TELEGRAM_OWNER_ID'], '7')
        self.assertEqual(config['TELEGRAM_ENABLED'], 'false')
        self.assertFalse(settings.active(config))

    def test_non_telegram_backup_does_not_inherit_destination_bot(self):
        self.save()
        restored = settings.hold_restored('KEEP_ME=incoming-snapshot\n', self.root)
        self.env.write_text(restored)
        old_token = self.root / 'run/telegram/token'
        old_token.parent.mkdir(parents=True, exist_ok=True)
        old_token.write_text(TOKEN)
        config = settings.configuration(self.root)
        self.assertEqual(config['TELEGRAM_BOT_TOKEN'], '')
        self.assertEqual(config['TELEGRAM_OWNER_ID'], '')
        self.assertFalse(settings.active(config))
        self.assertNotIn(TOKEN, restored)

    def test_detect_only_private_owner_starts(self):
        updates = [
            {'message': {'chat': {'id': 7, 'type': 'private'}, 'from': {'id': 7, 'first_name': 'Owner'}, 'text': '/start'}},
            {'message': {'chat': {'id': -1, 'type': 'group'}, 'from': {'id': 9}, 'text': '/start'}},
            {'message': {'chat': {'id': 8, 'type': 'private'}, 'from': {'id': 9}, 'text': '/start'}}]
        def api(token, method, **payload):
            return updates if method == 'getUpdates' else self.api(token, method, **payload)
        with patch.object(settings, 'telegram', side_effect=api):
            result = settings.detect({'token': TOKEN}, self.root)
        self.assertEqual([owner['id'] for owner in result['owners']], ['7'])


if __name__ == '__main__':
    unittest.main()
