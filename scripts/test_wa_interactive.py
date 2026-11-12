# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent/'lib'))
import wa_interactive as buttons
import wa_inbox

class InteractiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.registry=buttons.Registry(Path(self.temp.name)/'buttons.json')
        self.record={'id':'aabbccddeeff','result':{'caption':'Synthetic caption','when_local':'Tomorrow 19:00','targets':[{'network':'whatsapp'}]}}

    def test_owner_expiry_replay_and_sibling_buttons(self):
        rows=self.registry.issue('owner',[('Review','review_approval'),('Options','options')],now=100)
        self.assertEqual(self.registry.consume(rows[0]['id'],'someone-else',now=101)[0],'invalid')
        self.assertEqual(self.registry.consume(rows[0]['id'],'owner',now=101,dry_run=True)[0],'ok')
        self.assertEqual(self.registry.consume(rows[0]['id'],'owner',now=101)[0],'ok')
        self.assertEqual(self.registry.consume(rows[0]['id'],'owner',now=102)[0],'used')
        self.assertEqual(self.registry.consume(rows[1]['id'],'owner',now=102)[0],'used')
        fresh=self.registry.issue('owner',[('Settings','settings')],now=100)
        self.assertEqual(self.registry.consume(fresh[0]['id'],'owner',now=2000)[0],'expired')
        self.assertTrue(all(record['owner']!='owner' for record in self.registry.read().values()))
        if sys.platform!='win32':self.assertEqual(self.registry.path.stat().st_mode&0o777,0o600)

    def test_only_native_response_ids_are_decoded(self):
        identifier='pf1:'+'a'*32
        for message in (
            {'interactiveResponseMessage':{'nativeFlowResponseMessage':{'paramsJson':json.dumps({'id':identifier})}}},
            {'buttonsResponseMessage':{'selectedButtonId':identifier,'selectedDisplayText':'ignored'}},
            {'templateButtonReplyMessage':{'selectedId':identifier}},
            {'listResponseMessage':{'singleSelectReply':{'selectedRowId':identifier}}}):
            self.assertEqual(buttons.response(message),identifier)
            self.assertEqual(buttons.response({'viewOnceMessage':{'message':message}}),identifier)
            self.assertEqual(buttons.response({'deviceSentMessage':{'message':message}}),identifier)
        for message in ({'conversation':identifier},{'buttonsResponseMessage':{'selectedButtonId':'approve plan 1'}},
                        {'interactiveResponseMessage':{'nativeFlowResponseMessage':'invalid'}},
                        {'interactiveResponseMessage':{'nativeFlowResponseMessage':{'paramsJson':'[]'}}},
                        {'listResponseMessage':{'singleSelectReply':'invalid'}}, {'viewOnceMessage':{'message':'bad'}}):
            self.assertIsNone(buttons.response(message))

    def token(self,action):
        return self.registry.issue('owner',[(action,action)],reference=self.record['id'],plan_hash=buttons.fingerprint(self.record))[0]['id']

    def test_review_does_not_publish_and_confirmation_is_single_use(self):
        ident=('synthetic','instance','owner',set())
        with patch.object(buttons,'Registry',return_value=self.registry),patch.object(wa_inbox,'resolve_confirmation_ref',return_value=('file',self.record)),patch.object(wa_inbox,'ui_language',return_value='English'),patch.object(wa_inbox,'reply'),patch.object(wa_inbox,'button_menu'),patch.object(wa_inbox,'act') as act:
            wa_inbox.button_action({},ident,{},self.token('review_approval'),'/tmp',{})
            act.assert_not_called()
            token=self.token('confirm_plan')
            wa_inbox.button_action({},ident,{},token,'/tmp',{})
            self.assertEqual(act.call_args.args[3],'approve plan aabbccddeeff')
            wa_inbox.button_action({},ident,{},token,'/tmp',{})
            act.assert_called_once()

    def test_stale_caption_cannot_be_approved(self):
        token=self.token('confirm_plan');self.record['result']['caption']='Changed after review'
        with patch.object(buttons,'Registry',return_value=self.registry),patch.object(wa_inbox,'resolve_confirmation_ref',return_value=('file',self.record)),patch.object(wa_inbox,'ui_language',return_value='English'),patch.object(wa_inbox,'reply'),patch.object(wa_inbox,'act') as act:
            wa_inbox.button_action({},('synthetic','instance','owner',set()),{},token,'/tmp',{})
        act.assert_not_called()

    def test_taps_do_not_consume_media_waiting_for_a_post(self):
        import time
        now=time.time();identifier='pf1:'+'a'*32
        rows=[{'id':'video','key':{'id':'video'},'type':'videoMessage','ts':now-20,'message':{'videoMessage':{}}},
              {'id':'tap','key':{'id':'tap'},'type':'interactiveResponseMessage','ts':now-10,
               'message':{'interactiveResponseMessage':{'nativeFlowResponseMessage':{'paramsJson':json.dumps({'id':identifier})}}}}]
        state={'since':now-100,'done':[],'sent':[]}
        with patch.object(wa_inbox,'own_identity',return_value=('synthetic','instance','owner',set())),patch.object(wa_inbox,'messages_since',return_value=rows),patch.object(wa_inbox.whatsapp_pending,'process'),patch.object(wa_inbox.pmlib,'whatsapp_scratch',return_value=self.temp.name),patch.object(wa_inbox,'button_action') as action,patch.object(wa_inbox,'save_state'),patch.object(wa_inbox,'act') as act:
            wa_inbox.one_pass({},state,False)
        action.assert_called_once();act.assert_not_called()
        self.assertIn('tap',state['done']);self.assertNotIn('video',state['done'])

    def test_unsupported_controls_do_not_retry_or_break_text_workflow(self):
        with patch.object(buttons,'Registry',return_value=self.registry),patch.object(wa_inbox,'evo_call',return_value=(400,{})) as call:
            wa_inbox.button_menu({},'synthetic','owner',{},[('Settings','settings')],'Test','Test')
            call.assert_called_once()
        with self.assertRaises(ValueError):self.registry.issue('owner',[('bad','arbitrary-action')])

if __name__=='__main__':unittest.main()
