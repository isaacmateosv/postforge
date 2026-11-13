# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import runtime_install as runtime

class RuntimeTests(unittest.TestCase):
    def fixture(self,folder,version='2.0.0-rc.37'):
        source=folder/'source';source.mkdir()
        for name,text in {'VERSION':version,'scripts/desktop_bridge.py':'# public bridge','scripts/runtime_install.py':'# public installer','postforge.sh':'#!/bin/bash\ntrue\n','scripts/lib/file_lock.py':'# locking'}.items():
            p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
        (source/'.env').write_text('PRIVATE=secret')
        package=folder/'package';runtime.build(source,package,paths=[p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()])
        return package

    def test_fresh_install_and_update_preserve_private_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp).resolve();package=self.fixture(folder);target=folder/'fresh'
            runtime.apply(package,target)
            self.assertTrue((target/'scripts/desktop_bridge.py').is_file());self.assertFalse((target/'.env').exists())
            (target/'.env').write_text('PRIVATE=kept');(target/'data').mkdir();(target/'data/private').write_text('kept')
            (target/'scripts/desktop_bridge.py').write_text('# previous custom code')
            runtime.apply(package,target)
            self.assertEqual((target/'.env').read_text(),'PRIVATE=kept');self.assertEqual((target/'data/private').read_text(),'kept')
            saved=list((target/'run').glob('runtime-recovery-*/scripts/desktop_bridge.py'));self.assertEqual(saved[0].read_text(),'# previous custom code')

    def test_tampering_and_private_paths_are_rejected_before_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp).resolve();package=self.fixture(folder);target=folder/'fresh'
            (package/'VERSION').write_text('tampered')
            with self.assertRaises(ValueError):runtime.apply(package,target)
            self.assertFalse(target.exists())
        for name in ('../.env','/tmp/code','scripts/../../.env','scripts/data/private','config/whatsapp/vip-list.txt'):
            self.assertFalse(runtime.allowed(name))

    def test_failed_service_refresh_rolls_code_back_and_keeps_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp).resolve();package=self.fixture(folder);target=folder/'fresh';runtime.apply(package,target)
            (target/'.env').write_text('PRIVATE=kept');(target/'VERSION').write_text('old')
            with patch.object(runtime.subprocess,'run') as run:
                run.return_value.returncode=1;run.return_value.stdout=b'service unavailable'
                with self.assertRaisesRegex(ValueError,'Service refresh failed'):runtime.apply(package,target,refresh=True)
            self.assertEqual((target/'VERSION').read_text(),'old');self.assertEqual((target/'.env').read_text(),'PRIVATE=kept')

    def test_startup_never_downgrades_a_newer_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp).resolve();package=self.fixture(folder);target=folder/'fresh';runtime.apply(package,target)
            (target/'VERSION').write_text('9.0.0')
            result=runtime.apply(package,target,only_newer=True)
            self.assertTrue(result['unchanged']);self.assertEqual((target/'VERSION').read_text(),'9.0.0')

    def test_code_symlinks_cannot_overwrite_private_files(self):
        import os
        if os.name=='nt':self.skipTest('Windows symlink creation requires elevated privileges')
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp).resolve();package=self.fixture(folder);target=folder/'fresh';runtime.apply(package,target)
            private=folder/'private';private.write_text('keep');code=target/'scripts/desktop_bridge.py';code.unlink();code.symlink_to(private)
            with self.assertRaisesRegex(ValueError,'symbolic link'):runtime.apply(package,target)
            self.assertEqual(private.read_text(),'keep')

    def test_active_status_delivery_blocks_code_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp).resolve();package=self.fixture(folder);target=folder/'fresh';runtime.apply(package,target)
            (target/'run/whatsapp-pending.json').write_text(json.dumps([{'status':'sending'}]));(target/'VERSION').write_text('old')
            with self.assertRaisesRegex(ValueError,'Wait for WhatsApp'):runtime.apply(package,target,refresh=True)
            self.assertEqual((target/'VERSION').read_text(),'old')
