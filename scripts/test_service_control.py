# SPDX-License-Identifier: GPL-3.0-or-later
import contextlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import service_control as services

class ServiceTests(unittest.TestCase):
    def run_fixture(self,folder):
        root=Path(folder);(root/'.env').write_text('POSTGRES_DB=synthetic\n')
        return root
    def test_only_explicit_fixed_actions_are_allowed(self):
        with patch.object(services,'command') as command:
            for payload in ({'action':'start'},{'action':'delete','confirmed':True}):
                with self.assertRaises(ValueError):services.apply(payload)
            command.assert_not_called()
    def test_start_preserves_connector_and_does_not_activate_legacy_or_disabled_profiles(self):
        calls=[]
        def command(args,timeout=15):
            calls.append(args)
            if args[-3:]==['config','--format','json']:
                return SimpleNamespace(returncode=0,stdout=json.dumps({'services':{'postgres':{},'postiz':{},'ngrok':{},'postforge-telegram':{'profiles':['telegram']},'postforge-web':{'profiles':['web']}}}),stderr='')
            return SimpleNamespace(returncode=0,stdout='',stderr='')
        with tempfile.TemporaryDirectory() as folder,patch.object(services,'ROOT',self.run_fixture(folder)),patch.object(services.pmlib,'load_env',return_value={}),patch.object(services,'command',side_effect=command),patch.object(services,'wait_ready'),patch.object(services,'start_receiver'),patch.object(services,'ensure_ollama'),patch.object(services,'status',return_value={'running':True}),patch.object(services.pmlib,'Job',return_value=contextlib.nullcontext()),patch('host_agent.start'):
            services.apply({'action':'start','confirmed':True})
        up=[args for args in calls if args[:3]==['docker','compose','up']]
        self.assertEqual(len(up),2);self.assertNotIn('ngrok',up[0]);self.assertNotIn('postforge-telegram',up[0]);self.assertNotIn('postforge-web',up[0]);self.assertIn('--no-recreate',up[1]);self.assertNotIn('pull',[word for args in calls for word in args])
    def test_stop_refuses_waiting_approved_work_before_stopping_receivers(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(services,'ROOT',self.run_fixture(folder)),patch.object(services.pmlib,'load_env',return_value={}),patch.object(services,'command',return_value=SimpleNamespace(returncode=0)),patch.object(services,'queue_counts',return_value=(1,0)),patch.object(services,'stop_receiver') as stop:
            with self.assertRaisesRegex(ValueError,'Finish or cancel'):services.apply({'action':'stop','confirmed':True})
            stop.assert_not_called()
    def test_empty_stop_preserves_tools_and_data_and_marks_publishing_paused(self):
        calls=[]
        def command(args,timeout=15):calls.append(args);return SimpleNamespace(returncode=0,stdout='',stderr='')
        with tempfile.TemporaryDirectory() as folder,patch.object(services,'ROOT',self.run_fixture(folder)),patch.object(services.pmlib,'load_env',return_value={}),patch.object(services,'command',side_effect=command),patch.object(services,'queue_counts',return_value=(0,0)),patch.object(services,'stop_receiver'),patch.object(services,'status',return_value={'running':False}),patch.object(services.pmlib,'Job',return_value=contextlib.nullcontext()):
            services.apply({'action':'stop','confirmed':True});self.assertTrue((Path(folder)/'run/publishing-paused').exists());self.assertTrue((Path(folder)/'.env').exists())
        self.assertIn(['docker','compose','stop'],calls);self.assertNotIn('down',[word for args in calls for word in args]);self.assertNotIn('ollama',[word for args in calls for word in args])

    def test_desktop_bridge_routes_all_three_service_actions(self):
        import desktop_bridge
        with patch.object(services,'status',return_value={'running':True}) as status,patch.object(services,'task',return_value={'running':False}) as task,patch.object(services,'apply',return_value={'ok':True}) as apply:
            self.assertTrue(desktop_bridge.dispatch('services_status',{})['running'])
            self.assertFalse(desktop_bridge.dispatch('services_progress',{})['running'])
            self.assertTrue(desktop_bridge.dispatch('services_action',{'action':'stop','confirmed':True})['ok'])
            apply.assert_called_once_with({'action':'stop','confirmed':True})
