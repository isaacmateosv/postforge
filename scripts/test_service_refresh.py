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

    def test_health_gate_retries_transient_startup_and_rejects_persistent_failure(self):
        script=Path(__file__).parent/'refresh-services.sh'
        program=''' . "$TEST_SCRIPT"
          POSTIZ_URL=http://localhost:4200; EVO_URL=http://localhost:8080
          container_running() { return 0; }
          http_code() { echo 200; }
          counter=0
          wait_for_scheduler() { counter=$((counter + 1)); [ "$counter" -ge 2 ]; }
          sleep() { :; }
          wait_refreshed_stack 3 || exit 10
          [ "$counter" = 2 ] || exit 11
          http_code() { echo 503; }
          if wait_refreshed_stack 2; then exit 12; fi
        '''
        result=subprocess.run(['bash','-c',program],env=dict(os.environ,TEST_SCRIPT=str(script)),capture_output=True,text=True,check=True)
        self.assertIn('scheduler=false',result.stdout);self.assertIn('Postiz=503',result.stdout)
