# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import json

from telegram_flow import Conversation


def save(path, value):
    path.write_text(json.dumps(value))


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.actions = Mock()
        self.send = Mock()
        self.actions.options.return_value = {"final_tag": "", "networks": [
            {"id": "facebook", "name": "Facebook", "text": True},
            {"id": "instagram", "name": "Instagram", "text": False}]}
        self.flow = Conversation(Path(self.folder.name) / "conversation.json", 7, True,
                                 self.actions, self.send, save)
        self.sequence = 0

    def message(self, text, owner=7):
        self.sequence += 1
        self.flow.handle({"update_id": self.sequence, "message": {
            "from": {"id": owner}, "chat": {"id": owner, "type": "private"}, "text": text}})

    def callback(self, action, raw=None):
        self.sequence += 1
        prefix = self.flow.state.get("id", "home") + ":" + str(self.flow.state.get("version", 0)) + ":"
        update = {"update_id": self.sequence, "callback_query": {
            "id": "synthetic", "from": {"id": 7}, "message": {"chat": {"id": 7, "type": "private"}},
            "data": raw if raw is not None else prefix + action}}
        self.flow.handle(update)
        return update

    def ready(self):
        self.message("/new")
        self.callback("mode_exact")
        self.message("New hours on Friday at 9am. ✨")
        self.callback("text_only")
        self.callback("dest_all")
        self.callback("dest_next")
        self.actions.time_value.return_value = "2026-12-01T09:00:00-05:00"
        self.callback("time_tomorrow")
        self.actions.preview.return_value = {"review_id": "synthetic-review", "plan": {
            "caption": "New hours on Friday at 9am. ✨", "when_local": "Dec 1, 09:00",
            "targets": [{"network": "facebook", "placement": "feed"}], "warnings": [], "notes": [],
            "direct_schedule_available": True}}

    def test_saved_old_schedule_confirmation_cannot_approve_new_scope(self):
        self.ready()
        self.flow.state.update(stage="confirm",submit_mode="schedule",history=[self.actions.preview.return_value],selected=0)
        self.callback("confirm_submit")
        self.actions.submit.assert_not_called()
        self.assertEqual(self.flow.state["stage"],"review")

    def test_ping_settings_preserve_the_reviewed_plan_and_do_not_publish(self):
        self.ready();self.callback("bake")
        reviewed=self.flow.current()
        self.actions.heartbeat_preferences.return_value={"minutes":60,"configured":True,"active":True}
        self.message("/settings")
        self.assertEqual(self.flow.state["stage"],"review")
        self.callback("heartbeat_360")
        self.actions.set_heartbeat.assert_called_once_with(360)
        self.assertEqual(self.flow.current(),reviewed)
        self.callback("settings_back")
        self.assertEqual(self.flow.state["stage"],"review")
        self.actions.submit.assert_not_called()
        self.actions.preview.assert_called_once()
        self.actions.status.assert_not_called()

    def test_ready_does_not_expose_private_cover_paths_and_supports_frame_zero(self):
        self.ready()
        self.flow.state['data']['cover_image']='/private/synthetic-cover.jpg'
        self.flow.ready()
        message=self.send.call_args.args[0] if self.send.call_args.args else ''
        self.assertNotIn('/private/',self.send.call_args.kwargs['text'])
        self.flow.state['data'].update(cover_image=None,cover_second=0)
        self.flow.ready()
        self.assertIn('0 s',self.send.call_args.kwargs['text'])

    def test_ping_settings_work_after_an_old_posting_plan_expires(self):
        self.ready();self.callback("bake")
        self.flow.state['created_at']=1
        self.actions.heartbeat_preferences.return_value={"minutes":0,"configured":True,"active":True}
        self.message('/settings');self.callback('heartbeat_60')
        self.actions.set_heartbeat.assert_called_once_with(60)
        self.actions.submit.assert_not_called()

    def test_unauthorized_sender_does_not_touch_planner(self):
        self.message("/new", owner=8)
        self.actions.options.assert_not_called()
        self.send.assert_not_called()

    def test_text_only_choices_exclude_instagram_and_no_publish_before_confirmation(self):
        self.ready()
        self.assertEqual(self.flow.state["data"]["networks"], ["facebook"])
        self.callback("bake")
        self.assertEqual(self.flow.state["stage"], "review")
        self.actions.submit.assert_not_called()
        self.callback("create")
        self.actions.submit.assert_not_called()

    def test_replayed_and_stale_buttons_do_not_resubmit(self):
        self.ready()
        self.callback("bake")
        self.callback("create")
        self.actions.submit.return_value = {"drafts": [{"post_id": "synthetic"}]}
        previous = self.callback("confirm_submit")
        self.flow.handle(previous)
        self.callback("", raw=previous["callback_query"]["data"])
        self.actions.submit.assert_called_once()
        self.assertEqual(self.flow.state["stage"], "done")

    def test_failed_submission_is_held_across_restart(self):
        self.ready()
        self.callback("bake")
        self.callback("create")
        self.actions.submit.side_effect = RuntimeError("failure")
        self.callback("confirm_submit")
        self.assertEqual(self.flow.state["stage"], "needs_review")
        restored = Conversation(self.flow.path, 7, True, self.actions, self.send, save)
        self.assertEqual(restored.state["stage"], "needs_review")
        self.callback("confirm_submit")
        self.actions.submit.assert_called_once()

    def test_callback_size_and_private_chat_rules(self):
        self.ready()
        for call in self.send.call_args_list:
            for row in call.kwargs.get("reply_markup", {}).get("inline_keyboard", []):
                for button in row:
                    self.assertLessEqual(len(button["callback_data"].encode()), 64)
        self.send.reset_mock()
        self.flow.handle({"update_id": 900, "callback_query": {
            "id": "q", "from": {"id": 7}, "message": {"chat": {"id": 7, "type": "group"}},
            "data": "status"}})
        self.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class DownloadSafetyTests(unittest.TestCase):
    def test_large_or_traversing_file_is_rejected_before_download(self):
        from unittest.mock import patch
        from telegram_actions import Actions, MAX_FILE
        from pmlib import PMError
        call = Mock()
        actions = Actions({}, call, "synthetic-token", Mock())
        with self.assertRaises(PMError):
            actions.download({"document": {"file_id": "synthetic", "file_size": MAX_FILE + 1}})
        call.assert_not_called()
        call.return_value = {"file_size": 10, "file_path": "../private.mp4"}
        with patch("telegram_actions.OPENER.open") as download:
            with self.assertRaises(PMError):
                actions.download({"document": {"file_id": "synthetic", "file_size": 10}})
        download.assert_not_called()
