# SPDX-License-Identifier: GPL-3.0-or-later
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import whatsapp_audience as audience
import whatsapp_pending
import pmlib

class AudienceTests(unittest.TestCase):
    def test_new_default_does_not_retarget_existing_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);envfile=root/'.env';envfile.write_text('WA_STATUS_AUDIENCE=all\nOTHER=keep\n')
            queue=[{'id':'synthetic','status':'pending'},{'id':'explicit','status':'needs_review','audience':'test','recipients':'593991234567'}]
            with patch.object(audience,'ROOT',root),patch.object(pmlib,'RUN_DIR',folder),patch.object(pmlib,'load_env',return_value={'WA_STATUS_AUDIENCE':'all'}),patch.object(whatsapp_pending,'_read',return_value=queue),patch.object(whatsapp_pending,'_write') as write:
                result=audience.save({'audience':'test','recipients':'+593991234568, +593991234568'})
            self.assertEqual(result['recipients'],'593991234568')
            self.assertEqual(write.call_args.args[0][0]['audience'],'all')
            self.assertEqual(write.call_args.args[0][1]['recipients'],'593991234567')
            self.assertIn('OTHER=keep',envfile.read_text())
            if os.name != 'nt':self.assertEqual(envfile.stat().st_mode&0o777,0o600)
    def test_sending_blocks_default_change(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(pmlib,'RUN_DIR',folder),patch.object(pmlib,'load_env',return_value={}),patch.object(whatsapp_pending,'_read',return_value=[{'status':'sending'}]),patch.object(whatsapp_pending,'_write') as write:
            with self.assertRaisesRegex(pmlib.PMError,'being sent'):audience.save({'audience':'all','recipients':''})
            write.assert_not_called()
    def test_empty_selected_contacts_rejected(self):
        with self.assertRaises(pmlib.PMError):audience.save({'audience':'test','recipients':''})
if __name__=='__main__':unittest.main()
