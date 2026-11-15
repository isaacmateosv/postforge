# SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import preferences
import operation_guard

class PreferencesTests(unittest.TestCase):
    def fixture(self,folder):
        path=Path(folder)/'.env';path.write_text('PRIVATE_SECRET=keep-private\nPM_RETENTION_DAYS=30\nCAPTION_FINAL_TAG=\nLOCAL_LLM_MODEL=example:model\n')
        return path
    def test_save_changes_only_public_defaults_and_never_deletes_files(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(preferences,'ROOT',Path(folder)),patch.object(preferences.pmlib,'http',return_value=(200,{'models':[{'name':'example:model'}]})):
            path=self.fixture(folder);media=Path(folder)/'old-video';media.write_bytes(b'kept')
            result=preferences.save({'retention_days':90,'final_tag':'Example','model':'example:model','PRIVATE_SECRET':'overwrite'})
            self.assertEqual(result['final_tag'],'#Example');self.assertTrue(result['model_ready'])
            self.assertIn('PRIVATE_SECRET=keep-private',path.read_text());self.assertNotIn('PRIVATE_SECRET',result)
            self.assertEqual(media.read_bytes(),b'kept');self.assertEqual(path.stat().st_mode&0o777,0o600)
    def test_invalid_defaults_never_change_configuration(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(preferences,'ROOT',Path(folder)):
            path=self.fixture(folder);before=path.read_bytes()
            for change in ({'retention_days':True},{'retention_days':0},{'retention_days':3651},{'model':'name\nPRIVATE=bad'},{'final_tag':'two tags'}):
                with self.subTest(change=change),self.assertRaises((ValueError,preferences.pmlib.PMError)):
                    preferences.save(dict({'retention_days':30,'final_tag':'','model':'example:model'},**change))
                self.assertEqual(path.read_bytes(),before)
    def test_missing_setup_is_explicit_and_does_not_create_an_env(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(preferences,'ROOT',Path(folder)),patch.object(preferences.pmlib,'http',side_effect=preferences.pmlib.PMError('offline')):
            self.assertFalse(preferences.status()['configured'])
            with self.assertRaisesRegex(ValueError,'Configure or restore'):preferences.save({'retention_days':30,'final_tag':'','model':'example:model'})
            self.assertFalse((Path(folder)/'.env').exists())
    def test_saved_model_changes_do_not_change_telegram_owner_identity(self):
        from telegram_actions import Actions
        action=Actions({'TELEGRAM_OWNER_ID':'7','LOCAL_LLM_MODEL':'old'},None,None,None)
        with patch.object(preferences.pmlib,'load_env',return_value={'TELEGRAM_OWNER_ID':'999','LOCAL_LLM_MODEL':'new','CAPTION_FINAL_TAG':'#Example'}):
            result=action.current_env()
        self.assertEqual(result['TELEGRAM_OWNER_ID'],'7');self.assertEqual(result['LOCAL_LLM_MODEL'],'new')
