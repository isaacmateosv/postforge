# SPDX-License-Identifier: GPL-3.0-or-later
import io
import json
import unittest
from unittest.mock import patch
import desktop_updates as updates

class UpdateTests(unittest.TestCase):
    def check_release(self,assets):
        reply=io.BytesIO(json.dumps({'tag_name':'v2.0.0','assets':[{'name':name} for name in assets]}).encode())
        with patch.object(updates.urllib.request,'urlopen',return_value=reply),patch.object(updates.platform,'machine',return_value='arm64'),patch.object(updates.sys,'platform','darwin'):
            return updates.check()
    def test_never_offers_legacy_packages(self):
        self.assertFalse(self.check_release(['PostForge-2.0.0.pkg'])['available'])
    def test_compatible_rust_release(self):
        self.assertTrue(self.check_release(['PostForge-Desktop-2.0.0-darwin-arm64.zip'])['available'])
    def test_network_failure_is_not_reported_current(self):
        with patch.object(updates.urllib.request,'urlopen',side_effect=OSError):
            self.assertFalse(updates.check()['checked'])

if __name__=='__main__':unittest.main()
