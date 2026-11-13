# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

@unittest.skipUnless(shutil.which('bash') and os.name!='nt','POSIX service shell')
class RefreshTests(unittest.TestCase):
    def test_refresh_recreates_services_but_preserves_connector(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'calls';script=Path(__file__).parent/'refresh-services.sh'
            program='''docker() {
              if [ "$*" = "compose config --services" ]; then printf '%s\\n' postgres redis postiz ngrok evolution-api postforge-gateway; else printf '%s\\n' "$*" >> "$TEST_LOG"; fi
            }
            . "$TEST_SCRIPT"
            refresh_container_stack
            '''
            subprocess.run(['bash','-c',program],env=dict(os.environ,TEST_LOG=str(log),TEST_SCRIPT=str(script)),check=True)
            calls=log.read_text();self.assertIn('--force-recreate',calls);self.assertIn('postiz',calls);self.assertIn('evolution-api',calls);self.assertNotIn('ngrok',calls);self.assertNotIn('down',calls)
