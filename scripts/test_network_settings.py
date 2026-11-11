# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import network_settings as net
from v2.gateway_setup import config

class NetworkTests(unittest.TestCase):
    def test_provider_specs_keep_gateway_and_private_token(self):
        for provider in net.PROVIDERS:
            spec=json.loads(net.provider_block(provider).split(': ',1)[1])
            self.assertIn('postforge-gateway',spec['depends_on'])
            self.assertNotIn('ports',spec)
            self.assertTrue(spec['read_only'])
            if provider!='ngrok':self.assertEqual(spec['environment']['NGROK_AUTHTOKEN'],'')
        self.assertIn('http://postforge-gateway:8080',net.provider_block('trycloudflare'))
        self.assertNotIn('secret-value',net.provider_block('cloudflare'))

    def test_render_preserves_other_services_and_is_idempotent(self):
        original='services:\n  postforge-auth:\n    image: auth\n  ngrok:\n    image: old\n  other:\n    image: kept\n'
        changed=net.render_override(original,'trycloudflare')
        self.assertIn('  other:\n    image: kept',changed)
        self.assertIn('    image: auth',changed)
        self.assertEqual(net.render_override(changed,'trycloudflare'),changed)

    def fixture(self,root):
        (root/'run').mkdir();(root/'data/gateway').mkdir(parents=True)
        env='NGROK_DOMAIN=old.example.org\nFRONTEND_URL=https://old.example.org\nNEXT_PUBLIC_BACKEND_URL=https://old.example.org/api\nMAIN_URL=https://old.example.org\nPM_CUSTOM_DOMAIN=https://saved.example.org\nCLOUDFLARE_TUNNEL_TOKEN=private-saved-token-value\n'
        (root/'.env').write_text(env)
        (root/'data/gateway/configuration.yml').write_text(json.dumps(config('old.example.org')))
        (root/'docker-compose.override.yml').write_text('services:\n  postforge-gateway:\n    image: gateway\n  ngrok:\n    command: [old]\n')
        return env

    def test_rotation_rebases_only_media_and_keeps_saved_domain_and_token(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.fixture(root)
            with patch.object(net,'ROOT',root),patch.object(net.pmlib,'load_env',return_value={}),patch.object(net,'guard_idle',return_value='org'),patch.object(net.tunnel,'probe',return_value=b'Postiz'),patch.object(net.tunnel,'compose') as compose,patch.object(net,'quick_url',return_value='https://new-test-url.trycloudflare.com'),patch.object(net.tunnel,'apply_services'),patch.object(net.tunnel,'wait_until_ready'),patch.object(net,'rebase_media') as media:
                result=net.apply({'provider':'trycloudflare','rotate':True,'confirm':True})
            self.assertEqual(result['url'],'https://new-test-url.trycloudflare.com')
            self.assertEqual(result['custom_domain'],'https://saved.example.org')
            self.assertNotIn('private-saved-token-value',json.dumps(result))
            self.assertIn('private-saved-token-value',(root/'.env').read_text())
            self.assertTrue(any('--force-recreate' in call.args for call in compose.call_args_list))
            media.assert_called_once_with({},'org','https://old.example.org',result['url'])
            self.assertEqual(json.loads((root/'data/gateway/configuration.yml').read_text())['access_control']['default_policy'],'deny')

    def test_verification_failure_restores_all_private_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);original=self.fixture(root);gateway=(root/'data/gateway/configuration.yml').read_text();override=(root/'docker-compose.override.yml').read_text()
            with patch.object(net,'ROOT',root),patch.object(net.pmlib,'load_env',return_value={}),patch.object(net,'guard_idle',return_value='org'),patch.object(net.tunnel,'probe',return_value=b'ok'),patch.object(net.tunnel,'compose'),patch.object(net,'quick_url',return_value='https://new-test.trycloudflare.com'),patch.object(net.tunnel,'apply_services'),patch.object(net.tunnel,'wait_until_ready',side_effect=RuntimeError('bad endpoint')),patch.object(net,'rebase_media') as media:
                with self.assertRaisesRegex(net.pmlib.PMError,'previous configuration was restored'):net.apply({'provider':'trycloudflare','confirm':True})
            self.assertEqual((root/'.env').read_text(),original)
            self.assertEqual((root/'data/gateway/configuration.yml').read_text(),gateway)
            self.assertEqual((root/'docker-compose.override.yml').read_text(),override);media.assert_not_called()

    def test_new_named_domain_requires_a_token_and_confirmation(self):
        with self.assertRaises(ValueError):net.apply({'provider':'trycloudflare'})
        with self.assertRaises(ValueError):net.merge('',{'KEY':'bad\nSETTING=value'})

    def test_restore_regenerates_named_profile_without_exposing_saved_token(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.fixture(root)
            path=root/'.env';path.write_text(net.merge(path.read_text(),{'PM_TUNNEL_PROVIDER':'cloudflare'}))
            net.restore_provider(path)
            override=(root/'docker-compose.override.yml').read_text()
            self.assertIn('"run"',override)
            self.assertIn('${CLOUDFLARE_TUNNEL_TOKEN:-}',override)
            self.assertNotIn('private-saved-token-value',override)
            self.assertEqual(net.values(path)['PM_CUSTOM_DOMAIN'],'https://saved.example.org')

    def test_media_rebase_includes_covers_but_never_caption_or_schedule(self):
        with patch.object(net.pmlib,'psql') as sql:
            net.rebase_media({},'org', 'https://old.example.org','https://new.example.org')
        query=sql.call_args.args[0]
        for field in ('image=','settings=','path=','thumbnail='):self.assertIn(field,query)
        for field in ('content=','state=','publishDate='):self.assertNotIn(field,query)

    def test_quick_hostname_parser_does_not_accept_lookalike_domains(self):
        self.assertIsNone(net.QUICK.search('https://safe.trycloudflare.com.attacker.example'))
        self.assertEqual(net.QUICK.search('URL https://some-test.trycloudflare.com |').group(),'https://some-test.trycloudflare.com')

if __name__=='__main__':unittest.main()
