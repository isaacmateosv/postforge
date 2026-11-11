# SPDX-License-Identifier: GPL-3.0-or-later
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import repair_media_links as repair

class RepairTests(unittest.TestCase):
    def test_only_failed_entries_are_selected_and_apply_never_reschedules(self):
        row={'id':'syntheticpost123','network':'youtube','image':json.dumps([{'path':'https://example.test/uploads/2026/11/10/'+'a'*24+'.mp4'}])}
        with tempfile.TemporaryDirectory() as folder,patch.object(repair.pmlib,'RUN_DIR',folder),patch.object(repair.pmlib,'Postiz') as client,patch.object(repair.media_links,'load_key',return_value=b'x'*32),patch.object(repair.pmlib,'psql',side_effect=[[[json.dumps(row)]],[]]) as sql:
            client.return_value.org_id='synthetic-org'
            result=repair.repair({'FRONTEND_URL':'https://example.test'},[row['id']],apply=True)
            self.assertTrue(result['applied'])
            self.assertEqual(Path(result['backup']).stat().st_mode&0o777,0o600)
            select=sql.call_args_list[0].args[0];update=sql.call_args_list[1].args[0]
            self.assertIn("p.state='ERROR'",select)
            self.assertIn('SET image=',update)
            self.assertNotIn('publishDate',update)
            self.assertNotIn('SET state',update)
            self.assertIn('END; $repair$',update)
    def test_invalid_identifiers_never_touch_database(self):
        with patch.object(repair.pmlib,'psql') as sql,self.assertRaises(ValueError):repair.repair({},['bad'])
        sql.assert_not_called()
if __name__=='__main__':unittest.main()
