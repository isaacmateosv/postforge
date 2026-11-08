# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
import base64
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import desktop_status
import pmlib
import plan_post
from datetime import datetime, timezone, timedelta

class DesktopStatusTests(unittest.TestCase):
    def test_linked_whatsapp_never_creates_or_replaces_session(self):
        with patch.object(pmlib, 'http', return_value=(200, {'instance': {'state': 'open'}})) as api:
            result = desktop_status.whatsapp({'AUTHENTICATION_API_KEY': 'synthetic'}, connect=True)
        self.assertTrue(result['connected'])
        self.assertNotIn('qr', result)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(api.call_args.args[0], 'GET')

    def test_qr_is_embedded_and_non_image_response_is_rejected(self):
        png = b'\x89PNG\r\n\x1a\n' + b'synthetic'
        replies = [(200, {'instance': {'state': 'close'}}), (200, {'base64': base64.b64encode(png).decode()})]
        with patch.object(pmlib, 'http', side_effect=replies):
            self.assertTrue(desktop_status.whatsapp({}, True)['qr'].startswith('data:image/png;base64,'))
        replies[1] = (200, {'base64': base64.b64encode(b'<script>bad</script>').decode()})
        with patch.object(pmlib, 'http', side_effect=replies), self.assertRaises(pmlib.PMError):
            desktop_status.whatsapp({}, True)

    def test_long_short_preview_counts_stories_and_announces_separate_trim(self):
        now = datetime.now(timezone.utc)
        plan = plan_post.plan({}, 'Post everywhere tomorrow at 9am; caption: Exact test', ['sample.mp4'], 'English', now)
        plan['youtube_trim'] = True
        with patch.object(pmlib, 'Postiz') as api, patch.object(pmlib, 'normalize_media', return_value=('video','sample.mp4')), \
             patch.object(pmlib, 'is_short', return_value=False), patch.object(pmlib, 'ffprobe', return_value=(205,'h264','aac',720,1280)):
            api.return_value.integrations.return_value = [{'id': n, 'identifier': n, 'name': n} for n in ('youtube','facebook','instagram')]
            result = plan_post.run({}, plan, True)
            self.assertEqual(result['youtube_trim_seconds'],179)
            self.assertTrue(result['short'])
            self.assertTrue(any('2:59' in note for note in result['warnings']))
            self.assertEqual([t['parts'] for t in result['targets'] if t['placement']=='story'],[4,4])
            api.return_value.upload.assert_not_called()

    def test_youtube_upload_is_trimmed_without_changing_facebook_media(self):
        now = datetime.now(timezone.utc)
        plan = plan_post.plan({}, 'YouTube and Facebook tomorrow at 9am, posts only; caption: Exact test', ['original.mp4'], 'English', now)
        plan['youtube_trim'] = True
        with patch.object(pmlib, 'Postiz') as api, patch.object(pmlib, 'normalize_media', return_value=('video','original.mp4')), \
             patch.object(pmlib, 'is_short', return_value=False), \
             patch.object(pmlib, 'ffprobe', side_effect=lambda path: (179 if path.endswith('trimmed.mp4') else 205,'h264','aac',720,1280)), \
             patch.object(pmlib, 'to_mp4', return_value='trimmed.mp4') as trim, patch.object(pmlib, 'append_log'):
            api.return_value.integrations.return_value = [{'id': n, 'identifier': n, 'name': n} for n in ('youtube','facebook')]
            api.return_value.upload.side_effect = lambda path: {'id':path,'path':'/uploads/'+path}
            api.return_value.create_draft.return_value = [{'postId':'synthetic'}]
            plan_post.run({}, plan, False)
            trim.assert_called_once()
            self.assertEqual(trim.call_args.kwargs['max_seconds'],179)
            calls = {c.args[0]['identifier']:c.args[2][0]['path'] for c in api.return_value.create_draft.call_args_list}
            self.assertEqual(calls['youtube'],'/uploads/trimmed.mp4')
            self.assertEqual(calls['facebook'],'/uploads/original.mp4')

    def test_text_status_color_survives_queue_and_is_used_at_delivery(self):
        import tempfile
        import whatsapp_pending
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(whatsapp_pending, "QUEUE_FILE", str(Path(folder)/"queue.json")), \
             patch.object(pmlib, "whatsapp_scratch", return_value=folder), \
             patch.object(pmlib, "load_env", return_value={"WA_STATUS_AUDIENCE":"test"}), \
             patch.object(whatsapp_pending.subprocess, "run") as send:
            item_id = whatsapp_pending.enqueue("Synthetic text", [], [], datetime.now(timezone.utc), background="#8244aa")
            item = whatsapp_pending._read()[0]
            self.assertEqual(item["id"], item_id)
            self.assertEqual(item["background"], "#8244aa")
            whatsapp_pending._send_item(item)
            args = send.call_args.args[0]
            self.assertEqual(args[args.index("--bg")+1], "#8244aa")

    def test_approval_requires_connected_whatsapp_before_queue_change(self):
        import desktop_bridge
        with patch.object(pmlib, "load_env", return_value={}), \
             patch.object(desktop_status, "whatsapp", return_value={"connected":False}), \
             patch("whatsapp_pending.approve") as approve, \
             self.assertRaisesRegex(pmlib.PMError, "Connect WhatsApp"):
            desktop_bridge.dispatch("approve_status", {"id":"synthetic"})
        approve.assert_not_called()

if __name__ == '__main__':unittest.main()
