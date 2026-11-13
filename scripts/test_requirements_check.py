# SPDX-License-Identifier: GPL-3.0-or-later
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import requirements_check as requirements

class RequirementsTests(unittest.TestCase):
    def test_stopped_docker_is_distinguished_from_missing(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(requirements,'ROOT',Path(tmp)),patch.object(requirements.shutil,'which',return_value='/installed/tool'),patch.object(requirements,'command',side_effect=lambda args:args[:2]!=['docker','info']):
            result=requirements.check()
        self.assertTrue(result['ready_for_inspection']);self.assertFalse(result['ready_for_restore'])
        docker=next(row for row in result['items'] if row['key']=='docker');self.assertTrue(docker['installed']);self.assertTrue(docker['stopped'])
    def test_optional_ollama_does_not_block_restore(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(requirements,'ROOT',Path(tmp)),patch.object(requirements.shutil,'which',side_effect=lambda key:None if key=='ollama' else '/installed/tool'),patch.object(requirements,'command',return_value=True):
            self.assertTrue(requirements.check()['ready_for_restore'])
