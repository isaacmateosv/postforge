# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import composer
import pmlib


class ComposerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run_patch = patch.object(pmlib, "RUN_DIR", str(self.root))
        self.run_patch.start()
        jobs = patch.object(pmlib, "JOBS_DIR", str(self.root / "jobs"))
        jobs.start()
        self.addCleanup(jobs.stop)
        self.addCleanup(self.run_patch.stop)
        self.addCleanup(self.temp.cleanup)
        self.env = {"PM_TIMEZONE": "UTC", "CAPTION_LANGUAGE": "English"}
        self.fields = {"body": "Meet us Friday at 9am. ✨", "mode": "exact", "networks": ["facebook"],
                       "post_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                       "media": [], "text_confirmed": True, "language": "en"}
        self.plan = {"lang": "English", "caption": self.fields["body"], "caption_source": "your text",
                     "final_tag": "", "when_utc": self.fields["post_at"], "when_local": "Tomorrow",
                     "targets": [{"network": "facebook", "placement": "feed", "channel": "Synthetic", "integration_id": "synthetic-channel"}],
                     "warnings": ["original warning"], "notes": []}

    def preview(self):
        with patch.object(composer.plan_post, "run", return_value=self.plan):
            return composer.preview(self.env, self.fields)

    def test_structured_exact_words_do_not_change_schedule(self):
        plan = composer.build_plan(self.env, self.fields)
        self.assertEqual(plan["exact"], self.fields["body"])
        self.assertIsNone(plan["idea"])
        self.assertEqual(plan["when"].isoformat(), self.fields["post_at"])

    def test_revise_keeps_plan_and_all_versions_submit_once(self):
        original = self.preview()
        revised = composer.revise(self.env, original["review_id"], "Updated caption")
        self.assertEqual(revised["plan"]["targets"], self.plan["targets"])
        self.assertEqual(revised["plan"]["when_utc"], self.plan["when_utc"])
        self.assertEqual(revised["plan"]["warnings"], self.plan["warnings"])
        receipt = {"drafts": [{"post_id": "synthetic"}]}
        with patch.object(composer.plan_post, "run", return_value=receipt) as run:
            first = composer.submit(self.env, revised["review_id"], "draft")
            second = composer.submit(self.env, original["review_id"], "draft")
        self.assertEqual(first, receipt)
        self.assertTrue(second["already_submitted"])
        run.assert_called_once()

    def test_partial_failure_is_held_for_review(self):
        preview = self.preview()
        with patch.object(composer.plan_post, "run", side_effect=pmlib.PMError("provider error")) as run:
            with self.assertRaises(pmlib.PMError):
                composer.submit(self.env, preview["review_id"], "schedule")
            with self.assertRaisesRegex(pmlib.PMError, "needs review"):
                composer.submit(self.env, preview["review_id"], "schedule")
        run.assert_called_once()

    def test_changed_public_origin_requires_new_review(self):
        preview=self.preview()
        with patch.object(composer.plan_post,'run') as run:
            with self.assertRaisesRegex(pmlib.PMError,'public URL changed'):
                composer.submit(dict(self.env,FRONTEND_URL='https://new.example.org'),preview['review_id'],'draft')
        run.assert_not_called()

    def test_changed_media_requires_new_review(self):
        media = self.root / "synthetic.mp4"
        media.write_bytes(b"one")
        self.fields.update(media=[str(media)], text_confirmed=False)
        preview = self.preview()
        media.write_bytes(b"different bytes")
        with patch.object(composer.plan_post, "run") as run:
            with self.assertRaisesRegex(pmlib.PMError, "file changed"):
                composer.submit(self.env, preview["review_id"], "draft")
        run.assert_not_called()

    def test_concurrent_submit_returns_one_receipt(self):
        preview = self.preview()
        with patch.object(composer.plan_post, "run", return_value={"drafts": []}) as run:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: composer.submit(self.env, preview["review_id"], "draft"), range(2)))
        run.assert_called_once()
        self.assertEqual(sum(bool(result.get("already_submitted")) for result in results), 1)

    def test_older_unsubmitted_previews_require_review_after_media_policy_change(self):
        original = self.preview()
        path = composer.path_for(original["review_id"])
        ticket = json.loads(path.read_text())
        ticket.pop("pipeline_revision")
        composer.write_record(path, ticket)
        with self.assertRaisesRegex(pmlib.PMError, "planner changed"), patch.object(composer.plan_post, "run") as submit:
            composer.submit(self.env, original["review_id"], "draft")
        submit.assert_not_called()
        composer.write_record(composer.path_for(ticket["family"]), {"state":"completed", "receipt":{"drafts":[]}})
        self.assertTrue(composer.submit(self.env, original["review_id"], "draft")["already_submitted"])

    def test_title_only_edit_preserves_caption_and_delivery(self):
        original = self.preview()
        revised = composer.revise(self.env, original["review_id"], youtube_title="A complete short title")
        self.assertEqual(revised["plan"]["caption"], original["plan"]["caption"])
        self.assertEqual(revised["plan"]["targets"], original["plan"]["targets"])
        self.assertEqual(revised["plan"]["when_utc"], original["plan"]["when_utc"])
        self.assertEqual(revised["plan"]["youtube_title"], "A complete short title")
        with self.assertRaises(pmlib.PMError):
            composer.revise(self.env, original["review_id"], youtube_title="x" * 101)

    def test_time_edit_preserves_copy_and_updates_submission(self):
        original = self.preview()
        edited = composer.revise(self.env, original["review_id"], "Hand edited caption")
        when = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        moved = composer.revise(self.env, edited["review_id"], post_at=when)
        self.assertEqual(moved["plan"]["caption"], edited["plan"]["caption"])
        self.assertEqual(moved["plan"]["targets"], edited["plan"]["targets"])
        self.assertEqual(moved["plan"]["when_utc"], when)
        with patch.object(composer.plan_post, "run", return_value={"drafts":[]}) as run:
            composer.submit(self.env, moved["review_id"], "schedule")
        self.assertEqual(run.call_args.args[1]["when"].isoformat(), when)
        self.assertEqual(run.call_args.args[1]["reviewed_caption"], edited["plan"]["caption"])
        with self.assertRaises(pmlib.PMError):
            composer.revise(self.env, moved["review_id"], post_at="not-a-time")

    def test_caption_edit_keeps_independently_reviewed_title(self):
        self.plan.update(youtube_title="Reviewed title #Example", final_tag="#Example")
        original=self.preview()
        revised=composer.revise(self.env,original["review_id"],edited="Hand edited caption")
        self.assertEqual(revised["plan"]["youtube_title"],original["plan"]["youtube_title"])
        self.assertTrue(revised["plan"]["caption"].endswith("#Example"))

    def test_generated_title_changes_only_title_and_uses_current_caption(self):
        self.plan.update(youtube_title="Old title", final_tag="#Example")
        original = self.preview()
        with patch.object(composer.plan_post, "reviewed_youtube_title", return_value="New title #Example") as generate:
            revised = composer.revise(self.env, original["review_id"], regenerate_title=True)
        self.assertEqual(generate.call_args.args[1], original["plan"]["caption"])
        before = dict(original["plan"]); after = dict(revised["plan"])
        for key in ("youtube_title", "youtube_title_manual"):
            before.pop(key,None);after.pop(key,None)
        self.assertEqual(before,after)
        self.assertTrue(revised["plan"]["youtube_title"].endswith("#Example"))

    def test_new_install_has_no_business_hashtag_and_background_is_validated(self):
        with patch.object(pmlib, "Postiz") as api:
            api.return_value.integrations.return_value = []
            self.assertEqual(composer.options({})["final_tag"], "")
        self.fields["whatsapp_background"] = "#8244aa"
        self.assertEqual(composer.build_plan(self.env, composer.fields(self.fields))["whatsapp_background"], "#8244aa")
        self.fields["whatsapp_background"] = "not-a-color"
        with self.assertRaises(pmlib.PMError):
            composer.fields(self.fields)

    def test_host_stop_is_cooperative(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import host_agent
        stop = self.root / "stop"
        with patch.object(host_agent, "STOP", stop), \
             patch.object(host_agent, "running", side_effect=[123, None, None]), \
             patch.object(host_agent.os, "kill") as kill:
            host_agent.stop()
        self.assertTrue(stop.exists())
        kill.assert_not_called()

    def test_expired_and_invalid_tickets_are_rejected(self):
        with self.assertRaises(pmlib.PMError):
            composer.load_ticket("../.env")
        preview = self.preview()
        file = composer.path_for(preview["review_id"])
        ticket = json.loads(file.read_text())
        ticket["created_at"] = 0
        composer.write_record(file, ticket)
        with self.assertRaisesRegex(pmlib.PMError, "expired"):
            composer.submit(self.env, preview["review_id"], "draft")


if __name__ == "__main__":
    unittest.main()
