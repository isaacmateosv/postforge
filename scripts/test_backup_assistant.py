# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import backup_assistant as backup

class BackupTests(unittest.TestCase):
    def test_authenticated_roundtrip_and_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=folder/'source';source.write_bytes(b'private configuration\n'*100)
            sealed=folder/'private.pfbackup';backup.seal(source,sealed,'long passphrase here')
            restored=folder/'restored';backup.unseal(sealed,restored,'long passphrase here')
            self.assertEqual(source.read_bytes(),restored.read_bytes())
            with self.assertRaises(ValueError):backup.unseal(sealed,folder/'wrong','wrong passphrase')
            data=bytearray(sealed.read_bytes());data[-34]^=1;sealed.write_bytes(data)
            with self.assertRaises(ValueError):backup.unseal(sealed,folder/'tampered','long passphrase here')
            self.assertFalse((folder/'tampered').exists())

    def test_rejects_archive_paths_and_links(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);archive=folder/'bad.tar'
            with tarfile.open(archive,'w') as tar:
                for name in ['manifest.json','credentials.env.enc','postiz.tar','../escape']:
                    info=tarfile.TarInfo(name);info.size=1;tar.addfile(info,io.BytesIO(b'x'))
            with self.assertRaises(ValueError):backup.extract(archive,folder/'out')
            self.assertFalse((folder/'escape').exists())

    def test_restore_requires_inspection_and_confirmation(self):
        with patch.object(backup.subprocess,'Popen') as spawn:
            for payload in [dict(action='restore',password='long passphrase here'),dict(action='restore',password='long passphrase here',confirmed=True,fingerprint='../x')]:
                with self.assertRaises(ValueError):backup.start(payload)
            spawn.assert_not_called()

    def test_missing_worker_is_reported(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(backup,'JOBS',Path(folder)):
            identifier='a'*32
            backup.write_status(identifier,state='running')
            path=Path(folder)/(identifier+'.json');value=json.loads(path.read_text());value['updated']=0;path.write_text(json.dumps(value))
            self.assertEqual(backup.status(identifier)['state'],'error')

    def test_worker_request_is_not_saved(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(backup,'JOBS',Path(folder)),patch.object(backup.subprocess,'Popen') as spawn:
            result=backup.start(dict(action='inspect',password='a private passphrase',file='/tmp/example.pfbackup'))
            record=(Path(folder)/(result['id']+'.json')).read_text()
            self.assertNotIn('passphrase',record)
            self.assertNotIn('example',record)
            self.assertIn(b'a private passphrase',spawn.return_value.stdin.write.call_args.args[0])

if __name__=='__main__':unittest.main()
