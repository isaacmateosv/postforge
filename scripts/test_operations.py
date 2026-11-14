#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Regression checks for retention, optional liveness, and read-only update detection."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import tarfile
from datetime import datetime, timezone, timedelta
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'lib'))


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / filename))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


retention = module('retention', 'retention.py')
updates = module('updates', 'component_updates.py')
rollback = module('rollback', 'image_rollback.py')
import wa_inbox
import create_draft
import plan_post
import postiz_transfer
import pmlib
import machine_state
credentials = module("credentials", "credentials.py")
tunnel = module("tunnel_url", "tunnel_url.py")
manage_posts = module("manage_posts", "manage_posts.py")


class Operations(unittest.TestCase):
    def setUp(self):
        # Synthetic planner fixtures have no real video to probe. Real-file
        # orientation is exercised separately by test_media_preview.py.
        orientation=patch.object(pmlib,'display_dimensions',side_effect=lambda path,width,height:(width,height))
        orientation.start();self.addCleanup(orientation.stop)

    def test_quoted_idea_is_exact_and_schedule_ignores_caption_dates(self):
        words = 'WhatsApp today at 8:36 pm; idea: "Open on Saturday at 9am. See you! 🎉"'
        command, exact, idea = plan_post.split_instruction(words)
        self.assertEqual(exact, "Open on Saturday at 9am. See you! 🎉")
        self.assertIsNone(idea)
        now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
        when, notes = plan_post.parse_when(command, now)
        self.assertEqual((when.day, when.hour, when.minute), (7, 20, 36))
        command, exact, idea = plan_post.split_instruction("idea: a project update; post everywhere tomorrow at 7pm")
        self.assertEqual(idea, "a project update")
        self.assertEqual(plan_post.parse_when(command, now)[0].hour, 19)
        self.assertEqual(plan_post.parse_when("2026-11-09 at 18:30", now)[0].day, 9)
        self.assertIsNone(plan_post.parse_when("2026-02-31 at 18:30", now)[0])
        self.assertEqual(plan_post.parse_when("mañana a las 8:36 p. m.", now)[0].hour, 20)
        self.assertIsNone(plan_post.parse_when("tomorrow at 25:00", now)[0])
        self.assertIsNone(plan_post.parse_when("tomorrow at 13 pm", now)[0])
        command, exact, idea = plan_post.split_instruction('caption: "Offers tomorrow at 9am"; post everywhere today at 7pm')
        self.assertEqual(exact, "Offers tomorrow at 9am")
        self.assertEqual(plan_post.parse_when(command, now)[0].hour, 19)

    def test_cleanup_skips_changed_posts_and_inflight_whatsapp(self):
        from unittest.mock import Mock
        client = Mock(org_id="synthetic-org")
        group = {"group": "g", "posts": [{"id": "a", "state": "DRAFT"}]}
        reviewed = {"organization": "synthetic-org", "scope": "all", "groups": [group],
                    "whatsapp": [{"id": "w", "status": "pending"}]}
        changed = {"groups": [], "whatsapp": []}
        with patch.object(manage_posts, "snapshot", return_value=changed), \
             patch.object(manage_posts.whatsapp_pending, "_queue_lock"), \
             patch.object(manage_posts.whatsapp_pending, "_read", return_value=[{"id": "w", "status": "sending"}]), \
             patch.object(manage_posts.whatsapp_pending, "_write") as write:
            result = manage_posts.clear({}, reviewed, client)
        client._call.assert_not_called()
        write.assert_not_called()
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["cancelled_whatsapp"], 0)

    def test_cleanup_calls_cancellation_api_and_checks_removal(self):
        from unittest.mock import Mock
        client = Mock(org_id="synthetic-org")
        group = {"group": "g", "posts": [{"id": "a", "state": "DRAFT"}]}
        reviewed = {"organization": "synthetic-org", "scope": "drafts", "groups": [group], "whatsapp": []}
        with patch.object(manage_posts, "snapshot", side_effect=[{"groups": [group]}, {"groups": []}]):
            result = manage_posts.clear({}, reviewed, client)
        client._call.assert_called_once_with("DELETE", "/posts/a")
        self.assertEqual(result["deleted"], 1)

    def test_media_links_are_scoped_expire_and_reject_writes(self):
        import media_links
        from urllib.parse import urlsplit
        key = b"k" * 32
        origin = "https://media.example.test"
        path = "/uploads/2026/11/06/synthetic_media_only_123456.mp4"
        now = 1794013200
        expiry = now + 86400
        with patch.object(media_links.time, "time", return_value=now):
            link = media_links.signed_url(key, origin, origin + path, expiry)
        uri = urlsplit(link).path
        self.assertTrue(media_links.authorized(key, "GET", uri, now))
        self.assertTrue(media_links.authorized(key, "HEAD", uri, now))
        for method in ("POST", "PUT", "DELETE"):
            self.assertFalse(media_links.authorized(key, method, uri, now))
        self.assertFalse(media_links.authorized(key, "GET", uri, expiry))
        self.assertFalse(media_links.authorized(b"x" * 32, "GET", uri, now))
        self.assertFalse(media_links.authorized(key, "GET", uri.replace("123456", "123457"), now))
        self.assertFalse(media_links.authorized(key, "GET", uri + "?override=1", now))
        self.assertFalse(media_links.authorized(key, "GET", uri.replace("/uploads/", "/uploads/../"), now))
        self.assertFalse(media_links.authorized(key, "GET", uri, now - media_links.MAX_AGE))
        with patch.object(media_links.time, "time", return_value=now):
            with self.assertRaises(ValueError):
                media_links.signed_url(key, origin, "https://other.example" + path, expiry)
            with self.assertRaises(ValueError):
                media_links.signed_url(key, origin, origin + path, now + media_links.MAX_AGE + 1)

    def test_secure_media_failure_stops_before_creating_any_posts(self):
        import media_links
        now = datetime.now(timezone.utc)
        env = {"FRONTEND_URL": "https://media.example.test"}
        p = plan_post.plan(env, "Facebook tomorrow at 9am; caption: Delivery check",
                           ["clip.mp4"], "English", now, placement_override="feed")
        p["reviewed_caption"] = "Delivery check"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gateway = root / "data/gateway"
            gateway.mkdir(parents=True)
            (gateway / "configuration.yml").write_text("{}")
            (gateway / "media-signing.key").write_bytes(b"k" * 32)
            with patch.object(pmlib, "ROOT", directory), \
                 patch.object(pmlib, "Postiz") as client, \
                 patch.object(pmlib, "normalize_media", return_value=("video", "clip.mp4")), \
                 patch.object(pmlib, "is_short", return_value=False), \
                 patch.object(media_links, "serves_media", return_value=False), \
                 patch.object(plan_post, "verify_public_media_origin") as preflight:
                client.return_value.integrations.return_value = [
                    {"id": "facebook-test", "identifier": "facebook", "name": "Synthetic account"}]
                client.return_value.upload.return_value = {
                    "id": "synthetic-media",
                    "path": env["FRONTEND_URL"] + "/uploads/2026/11/06/synthetic_media_only_123456.mp4"}
                with self.assertRaisesRegex(pmlib.PMError, "No posts were created"):
                    plan_post.run(env, p, False, schedule=True)
                client.return_value.create_draft.assert_not_called()
                client.return_value.upload.reset_mock()
                preflight.side_effect = pmlib.PMError("Public media access is not ready. No posts were created.")
                with self.assertRaisesRegex(pmlib.PMError, "No posts were created"):
                    plan_post.run(env, p, False, schedule=True)
                client.return_value.upload.assert_not_called()
                client.return_value.create_draft.assert_not_called()

    def test_long_story_uses_separate_clips_and_keeps_full_feed_video(self):
        now = datetime.now(timezone.utc)
        p = plan_post.plan({}, "Facebook tomorrow at 9am; caption: Delivery check",
                           ["clip.mp4"], "English", now, placement_override="both")
        p["reviewed_caption"] = "Delivery check"
        with patch.object(pmlib, "Postiz") as client, \
             patch.object(pmlib, "normalize_media", return_value=("video", "clip.mp4")), \
             patch.object(pmlib, "is_short", return_value=False), \
             patch.object(pmlib, "ffprobe", return_value=(93, "h264", "aac", 1080, 1920)), \
             patch.object(pmlib, "split_story_video", return_value=["part1.mp4", "part2.mp4"]), \
             patch.object(pmlib, "append_log"):
            api = client.return_value
            api.integrations.return_value = [{"id": "test", "identifier": "facebook", "name": "Test"}]
            api.upload.side_effect = lambda path: {"id": path, "path": path}
            api.create_draft.return_value = [{"postId": "synthetic-draft"}]
            result = plan_post.run({}, p, False)
            self.assertEqual(len(result["drafts"]), 3)
            calls = api.create_draft.call_args_list
            self.assertEqual(calls[0].args[2][0]["path"], "clip.mp4")
            self.assertEqual(calls[1].args[2][0]["path"], "part1.mp4")
            self.assertEqual(calls[2].args[2][0]["path"], "part2.mp4")
            self.assertEqual(calls[1].kwargs["settings"]["post_type"], "story")
            self.assertEqual(calls[2].kwargs["when"] - calls[1].kwargs["when"], timedelta(minutes=1))
            self.assertTrue(any("2 Story drafts" in warning for warning in result["warnings"]))

    def test_text_announcement_overrides_require_explicit_supported_destinations(self):
        now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
        selected = plan_post.plan({}, 'Instagram tomorrow at 7pm; caption: "Opening at 10 tomorrow"',
                                  [], "English", now, text_networks=["facebook", "threads", "whatsapp"])
        self.assertEqual(selected["networks"], ["facebook", "threads", "whatsapp"])
        self.assertEqual(selected["placement"], "both")
        self.assertTrue(selected["text_approved"])
        self.assertEqual(selected["exact"], "Opening at 10 tomorrow")
        with patch.object(pmlib, "Postiz") as client:
            client.return_value.integrations.return_value = [
                {"id": "facebook", "identifier": "facebook", "name": "Example"},
                {"id": "threads", "identifier": "threads", "name": "Example"}]
            output = plan_post.run({}, selected, True)
            self.assertEqual([(item["network"], item["placement"]) for item in output["targets"]],
                             [("facebook", "feed"), ("threads", "feed"), ("whatsapp", "status")])
            client.return_value.create_draft.assert_not_called()
        with self.assertRaises(pmlib.PMError):
            plan_post.plan({}, "Instagram tomorrow at 7pm; idea: an announcement", [], "English", now,
                           text_networks=["instagram"])

    def test_reviewed_accounts_exclude_new_connections(self):
        now = datetime.now(timezone.utc)
        p = plan_post.plan({}, "Facebook tomorrow at 9am; caption: Delivery check",
                           ["clip.mp4"], "English", now, placement_override="feed")
        p["reviewed_integrations"] = ["original"]
        with patch.object(pmlib, "Postiz") as client, \
             patch.object(pmlib, "normalize_media", return_value=("video", "clip.mp4")), \
             patch.object(pmlib, "is_short", return_value=False):
            client.return_value.integrations.return_value = [
                {"id": "original", "identifier": "facebook", "name": "Original"},
                {"id": "new", "identifier": "facebook", "name": "New connection"}]
            result = plan_post.run({}, p, True)
            self.assertEqual([target["integration_id"] for target in result["targets"]], ["original"])
            p["reviewed_integrations"] = ["missing"]
            with self.assertRaisesRegex(pmlib.PMError, "no longer connected"):
                plan_post.run({}, p, True)

    def test_video_warnings_respect_platform_thresholds(self):
        networks = {"instagram", "youtube", "whatsapp"}
        self.assertEqual(plan_post.video_warnings(networks, [60], "English"), [])
        self.assertEqual(len(plan_post.video_warnings(networks, [180], "English")), 1)
        warnings = plan_post.video_warnings(networks, [181], "Spanish")
        self.assertEqual(len(warnings), 3)
        self.assertIn("nuevas audiencias", warnings[0])
        self.assertIn("4 partes", warnings[-1])
        self.assertEqual(plan_post.video_warnings({"facebook"}, [181], "English"), [])

    def test_drafts_use_reviewed_caption_and_threads_variant(self):
        now = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
        text = "Threads and Facebook tomorrow at 9am; idea: share a project update"
        plan = plan_post.plan({}, text, ["clip.mp4"], "English", now)
        with patch.object(pmlib, "Postiz") as mock_postiz, \
             patch.object(pmlib, "normalize_media", return_value=("video", "clip.mp4")), \
             patch.object(pmlib, "is_short", return_value=False), \
             patch.object(pmlib, "ffprobe", return_value=(30, None, None, 1920, 1080)), \
             patch.object(pmlib, "append_log"), \
             patch.object(plan_post, "ollama_caption", return_value=("Reviewed caption", "test", 0)) as generate, \
             patch.object(plan_post, "threads_caption", return_value="Reviewed Threads text") as shorten:
            postiz = mock_postiz.return_value
            postiz.integrations.return_value = [{"id": name, "name": name, "identifier": name}
                                                for name in ("threads", "facebook")]
            postiz.upload.return_value = {"id": "clip", "path": "https://example.test/clip.mp4"}
            postiz.create_draft.return_value = [{"postId": "draft"}]
            preview = plan_post.run({}, plan, True)
            self.assertEqual(preview["threads_caption"], "Reviewed Threads text")
            plan.update(reviewed_caption=preview["caption"], reviewed_threads_caption=preview["threads_caption"])
            plan_post.run({}, plan, False)
            generate.assert_called_once()
            shorten.assert_called_once()
            self.assertEqual([call.args[1] for call in postiz.create_draft.call_args_list],
                             ["Reviewed Threads text", "Reviewed caption", "Reviewed caption"])

    def test_final_tag_moves_to_footer_and_whatsapp_can_change_it(self):
        tag = pmlib.final_tag("MiNegocio")
        caption = pmlib.apply_final_tag("Mi texto\n\n#minegocio #OtraEtiqueta", tag)
        self.assertEqual(caption, "Mi texto\n\n#OtraEtiqueta #MiNegocio")
        self.assertEqual(pmlib.apply_final_tag(caption, tag), caption)
        self.assertEqual(pmlib.apply_final_tag(caption, ""), caption)
        with self.assertRaises(pmlib.PMError):
            pmlib.final_tag("dos etiquetas")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "plan.json"
            confirmation = {"lang": "Spanish", "result": {
                "caption": caption, "final_tag": tag, "networks": ["threads"],
                "threads_caption": "Texto corto\n\n#MiNegocio",
            }}
            path.write_text(json.dumps(confirmation))
            mtime = path.stat().st_mtime_ns
            result = wa_inbox.change_plan_tag(str(path), confirmation, "#OtroNegocio", {})
            self.assertEqual(result["caption"], "Mi texto\n\n#OtraEtiqueta #OtroNegocio")
            self.assertEqual(result["threads_caption"], "Texto corto\n\n#OtroNegocio")
            self.assertEqual(json.loads(path.read_text())["result"]["final_tag"], "#OtroNegocio")
            self.assertEqual(path.stat().st_mtime_ns, mtime)

    def test_youtube_title_respects_limit_without_trimming_description(self):
        caption = "#Opening\nA title " + "🍓" * 80 + "\n\nThe full description."
        for short in (False, True):
            title = pmlib.youtube_title(caption, short)
            self.assertLessEqual(len(title.encode("utf-16-le")) // 2, 100)
            self.assertFalse(title.endswith(" #Shorts"))
            self.assertEqual(pmlib.draft_settings("youtube", caption, short=short)["title"], title)
            self.assertNotIn("The full description", title)
        self.assertEqual(pmlib.youtube_title("A <good> title"), "A good title")

    def test_youtube_long_title_uses_reviewable_ai_summary(self):
        caption = ("¿Te gustaría unirte a nosotros con una rica torta de frutillas con chantilly "
                   "para celebrar los partidos de Liga Deportiva Universitaria?")
        with patch.object(pmlib, "http", return_value=(200, {
            "response": "Torta de frutillas con chantilly para la hinchada de Liga"
        })) as generate:
            title = plan_post.reviewed_youtube_title({}, caption, "Torta para hinchas de Liga", "Spanish", True)
        generate.assert_called_once()
        self.assertEqual(title, "Torta de frutillas con chantilly para la hinchada de Liga")
        with patch.object(pmlib, "http", side_effect=pmlib.PMError("offline")):
            fallback = plan_post.reviewed_youtube_title({}, caption, None, "Spanish", True)
        prefix = fallback.removesuffix("…")
        self.assertTrue(caption.startswith(prefix + " "))
        self.assertLessEqual(len(fallback), 100)

    def test_generated_caption_retries_when_hashtags_are_missing(self):
        with patch.object(pmlib, "http", side_effect=[
            (200, {"response": "Galletas para compartir."}),
            (200, {"response": "Galletas para compartir.\n\n#Galletas #Antojo"}),
        ]) as generate:
            caption, _, _ = create_draft.ollama_caption({}, "galletas", "Spanish")
        self.assertEqual(generate.call_count, 2)
        self.assertTrue(pmlib.apply_final_tag(caption, "#MiNegocio").endswith("#Galletas #Antojo #MiNegocio"))

    def test_caption_intent_distinguishes_brief_from_exact_text(self):
        instruction = 'post everywhere today at 6:40 pm; escribe sobre una torta para “Liga Deportiva Universitaria”'
        command, exact, idea = plan_post.split_instruction(instruction)
        self.assertEqual(command.strip(" ;"), "post everywhere today at 6:40 pm")
        self.assertIsNone(exact)
        self.assertEqual(idea, 'una torta para “Liga Deportiva Universitaria”')
        _, exact, idea = plan_post.split_instruction('Instagram hoy 6pm; texto: “Frutillas y chantilly 🍓”')
        self.assertEqual(exact, "Frutillas y chantilly 🍓")
        self.assertIsNone(idea)
        self.assertEqual(create_draft.fitting_emojis("Una torta 🎂", "torta de frutillas"), "Una torta 🍓")
        self.assertEqual(create_draft.finish("Torta de frutillas 🍓.", "Spanish", topic="torta de frutillas"),
                         "Torta de frutillas. 🍓")

    def test_copy_revision_keeps_plan_and_skips_media_processing(self):
        snapshot = {"lang": "Spanish", "when_utc": "2026-11-07T01:00:00+00:00",
                    "targets": [{"network": "instagram", "placement": "feed", "cover_second": 8}],
                    "warnings": ["Original warning"], "caption": "Texto anterior", "final_tag": "#Negocio"}
        with patch.object(pmlib, "Postiz") as postiz, patch.object(pmlib, "normalize_media") as normalize, \
             patch.object(plan_post, "ollama_caption", return_value=("Otro texto 🍓", "test", 0)) as model:
            revised = plan_post.revise_copy({}, snapshot, "Instagram mañana 7pm; idea: torta de frutillas")
            edited = plan_post.revise_copy({}, snapshot, "Instagram mañana 7pm; idea: torta", "Texto editado")
        for result in (revised, edited):
            for key in ("when_utc", "targets", "warnings"):
                self.assertEqual(result[key], snapshot[key])
            self.assertTrue(result["caption"].endswith("#Negocio"))
        postiz.assert_not_called()
        normalize.assert_not_called()
        model.assert_called_once()

    def test_postiz_schedules_only_when_explicitly_requested(self):
        client = pmlib.Postiz.__new__(pmlib.Postiz)
        client.env = {}
        with patch.object(client, "_call") as call:
            channel = {"id": "test", "identifier": "threads"}
            client.create_draft(channel, "Caption")
            self.assertEqual(call.call_args.args[2]["type"], "draft")
            client.create_draft(channel, "Caption", schedule=True)
            self.assertEqual(call.call_args.args[2]["type"], "schedule")

    def test_whatsapp_only_direct_schedule_approves_reviewed_item(self):
        now = datetime.now(timezone.utc)
        p = plan_post.plan({}, 'whatsapp tomorrow at 9am; caption: "A synthetic notice"', [], None, now,
                           text_networks=["whatsapp"])
        with patch.object(pmlib, "Postiz"), patch.object(plan_post.whatsapp_pending, "enqueue", return_value="new-status") as enqueue, patch.object(plan_post.whatsapp_pending, "approve", return_value="new-status") as approve:
            preview = plan_post.run({}, p, True)
            self.assertTrue(preview["direct_schedule_available"])
            approve.assert_not_called()
            receipt = plan_post.run({}, p, False, schedule=True)
            approve.assert_called_once_with("new-status", source="reviewed-direct-schedule")
            self.assertTrue(receipt["whatsapp_scheduled"])
            self.assertEqual(enqueue.call_args.args[3], p["when"].astimezone(timezone.utc))

    def test_short_frame_cover_is_uploaded_and_passed_to_youtube(self):
        now = datetime.now(timezone.utc)
        p = plan_post.plan({}, 'youtube tomorrow at 9am; caption: "Synthetic video"', ["clip.mp4"], None, now, cover_second=1)
        def extract(command, **kwargs):
            if command[0] == "ffmpeg": Path(command[-1]).write_bytes(b"synthetic jpeg")
        with patch.object(pmlib,"Postiz") as api, patch.object(pmlib,"normalize_media",return_value=("video","clip.mp4")), patch.object(pmlib,"ffprobe",return_value=(30,"h264","aac",1080,1920)), patch.object(pmlib,"is_short",return_value=True), patch.object(pmlib,"run",side_effect=extract), patch.object(pmlib,"append_log"):
            client=api.return_value
            client.integrations.return_value=[{"id":"yt","identifier":"youtube","name":"Synthetic"}]
            client.upload.side_effect=[{"id":"video","path":"https://synthetic.example/video.mp4"},{"id":"cover","path":"https://synthetic.example/cover.jpg"}]
            client.create_draft.return_value=[{"postId":"synthetic"}]
            plan_post.run({},p,False)
            self.assertEqual(client.create_draft.call_args.kwargs["settings"]["thumbnail"]["id"],"cover")

    def test_short_cover_and_business_title_are_supported(self):
        self.assertEqual(plan_post.cover_mode({}, "youtube", "feed", None, 12, True), "frame-image")
        self.assertEqual(plan_post.cover_mode({}, "youtube", "feed", "cover.jpg", None, True), "image")
        title = plan_post.tagged_youtube_title("A complete title " * 15, "#Example")
        self.assertTrue(title.endswith(" #Example"))
        self.assertLessEqual(len(title.encode("utf-16-le")) // 2,100)
        with self.assertRaises(pmlib.PMError):
            plan_post.tagged_youtube_title("🍓" * 48, "#Example", strict=True)

    def test_whatsapp_settings_require_an_explicit_standalone_command(self):
        import telegram_settings
        with patch.object(telegram_settings,'set_heartbeat') as save, patch.object(telegram_settings,'heartbeat_preferences',return_value={'minutes':60,'configured':True,'active':True}):
            for text in ('post everywhere; idea: explain settings and ping', 'caption: postforge ping 60', 'I want postforge settings in this caption', '60', 'settings'):
                self.assertIsNone(wa_inbox.settings_request(text,False))
            self.assertIn('Every 60 minutes',wa_inbox.settings_request('postforge settings',False))
            wa_inbox.settings_request('postforge ping off',False,dry_run=True)
            save.assert_not_called()
            save.return_value={'minutes':0,'configured':True,'active':True}
            self.assertIn('guardado',wa_inbox.settings_request('postforge ping apagado',True))
            save.assert_called_once_with(0)

    def test_ollama_reasoning_is_excluded_from_caption(self):
        self.assertEqual(pmlib.ollama_final_text({"response": "<think>analysis</think>Texto"}), "Texto")
        self.assertEqual(pmlib.ollama_final_text({"response": "<think>unfinished"}), "")
        self.assertFalse(pmlib.ollama_text_prompt("qwen3:4b", "Caption")["think"])

    def test_topic_first_colloquial_post_everywhere(self):
        now = datetime(2026, 11, 5, 12, tzinfo=plan_post.ZoneInfo("America/Guayaquil"))
        text = "galletas y cupcakes; postea en todo lado a las 7:15 pm, posts e historias"
        p = plan_post.plan({}, text, [], None, now)
        self.assertEqual(p["idea"], "galletas y cupcakes")
        self.assertEqual((p["when"].hour, p["when"].minute), (19, 15))
        self.assertEqual(p["placement"], "both")
        self.assertEqual(p["networks"], list(plan_post.NETWORKS))
        with self.assertRaisesRegex(pmlib.PMError, "hora indicada ya pasó"):
            plan_post.plan({}, text, [], None, now.replace(hour=20), ui_lang="Spanish")
        explicit = 'Instagram mañana a las 7pm; texto: "galletas y cupcakes; publica en todo lado"'
        self.assertEqual(plan_post.split_instruction(explicit)[1], "galletas y cupcakes; publica en todo lado")

    def test_everywhere_and_story_only_make_only_supported_drafts(self):
        now = datetime(2026, 11, 5, 8, tzinfo=timezone.utc)
        channels = [{"id": name, "name": name, "identifier": name}
                    for name in ("facebook", "instagram-standalone", "threads", "youtube")]
        with patch.object(pmlib, "Postiz") as mock_postiz, \
             patch.object(pmlib, "normalize_media", return_value=("video", "clip.mp4")), \
             patch.object(pmlib, "is_short", return_value=False), \
             patch.object(pmlib, "ffprobe", return_value=(30, None, None, 1920, 1080)):
            postiz = mock_postiz.return_value
            postiz.integrations.return_value = channels
            for text, expected in (
                ('Post everywhere tomorrow at 9am; text: "A demo"', {
                    ("facebook", "feed"), ("facebook", "story"), ("instagram", "feed"),
                    ("instagram", "story"), ("threads", "feed"), ("youtube", "feed"),
                    ("whatsapp", "status")}),
                ('En todas las redes mañana 9am, solo historias; texto: "Un ejemplo"', {
                    ("facebook", "story"), ("instagram", "story"), ("whatsapp", "status")}),
            ):
                plan = plan_post.plan({}, text, ["clip.mp4"], None, now)
                result = plan_post.run({}, plan, True)
                self.assertEqual({(t["network"], t["placement"]) for t in result["targets"]}, expected)
                self.assertEqual(result["video_without_cover"], any(
                    network == "instagram" and placement == "feed" for network, placement in expected))
            postiz.create_draft.assert_not_called()
            postiz.upload.assert_not_called()

    def test_cover_timestamp_only_reaches_supported_video_drafts(self):
        now = datetime(2026, 11, 5, 8, tzinfo=timezone.utc)
        env = {"TIKTOK_POSTING_METHOD": "DIRECT_POST"}
        channels = [{"id": name, "name": name, "identifier": name} for name in ("instagram", "tiktok")]
        p = plan_post.plan(env, 'Instagram y TikTok mañana 9am; portada en el segundo 12,5; texto: "Un ejemplo"',
                           ["clip.mp4"], None, now)
        with patch.object(pmlib, "Postiz") as mock_postiz, \
             patch.object(pmlib, "normalize_media", return_value=("video", "clip.mp4")), \
             patch.object(pmlib, "is_short", return_value=False), \
             patch.object(pmlib, "ffprobe", return_value=(30, None, None, 1920, 1080)), \
             patch.object(pmlib, "append_log"):
            postiz = mock_postiz.return_value
            postiz.integrations.return_value = channels
            postiz.upload.return_value = {"id": "clip", "path": "https://example.test/clip.mp4"}
            postiz.create_draft.return_value = [{"postId": "draft"}]
            result = plan_post.run(env, p, False)
            calls = postiz.create_draft.call_args_list
            self.assertEqual([call.args[2][0].get("thumbnailTimestamp") for call in calls], [12500, None, 12500])
            self.assertEqual(calls[1].kwargs["settings"], {"post_type": "story"})
            with patch.object(wa_inbox, "ui_language", return_value="Spanish"):
                message = wa_inbox.summary(result, "Spanish", confirmation_id="2")
            self.assertIn("portada en el segundo 12,5", message)
            self.assertIn("Instagram · historia", message)
            self.assertIn("rechazar plan 2", message)
            with patch.object(wa_inbox, "ui_language", return_value="English"):
                message = wa_inbox.summary(result, "Spanish", confirmation_id="2")
            self.assertIn("cover at 12.5 s", message)
            self.assertIn("Instagram · story", message)

    def test_whatsapp_cover_image_is_separate_from_video_attachment(self):
        now = datetime(2026, 11, 5, 8, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            video, cover = (Path(directory) / name for name in ("clip.mp4", "cover.png"))
            video.touch()
            cover.touch()
            plan = plan_post.plan({}, 'Instagram tomorrow at 9am; cover image; text: "A demo"',
                                  [str(cover), str(video)], None, now)
            with patch.object(pmlib, "Postiz") as mock_postiz, \
                 patch.object(pmlib, "normalize_media", side_effect=[("video", str(video)), ("image", str(cover))]) as normalize, \
                 patch.object(pmlib, "is_short", return_value=False), \
                 patch.object(pmlib, "ffprobe", return_value=(30, None, None, 1920, 1080)):
                mock_postiz.return_value.integrations.return_value = [
                    {"id": "ig", "name": "Instagram", "identifier": "instagram"}]
                result = plan_post.run({}, plan, True)
                self.assertEqual(normalize.call_args_list[0].args[0], str(video))
                self.assertEqual([t["cover"] for t in result["targets"]], ["image", None])
                mock_postiz.return_value.upload.assert_not_called()

    def test_whatsapp_cleanup_keeps_future_confirmation_and_other_uploads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            uploads = root / "postiz-uploads"
            plans = root / "wa-confirmations"
            scratch = root / "wa-cache"
            (uploads / "whatsapp-pending").mkdir(parents=True)
            plans.mkdir()
            scratch.mkdir()
            for name, when in (("expired", "2020-01-01T00:00:00Z"), ("future", "2099-01-01T00:00:00Z")):
                (plans / (name + ".json")).write_text(json.dumps({"result": {"when_utc": when}}))
            old = [scratch / "stale.mp4", uploads / "whatsapp-pending" / "delivered.mp4", uploads / "other.mp4"]
            for file in old:
                file.touch()
            for file in old + list(plans.iterdir()):
                os.utime(file, (1, 1))
            with patch.object(retention, "ROOTS", tuple(map(str, (uploads, plans, scratch)))), \
                 patch.object(retention, "referenced_media", return_value=""):
                self.assertEqual({Path(p).name for p in retention.candidates(time.time(), whatsapp_only=True)},
                                 {"expired.json", "stale.mp4", "delivered.mp4"})

    def test_idle_stop_requires_live_empty_queue(self):
        for state, cached, total, expected in (
            ("on", False, 0, True), ("on", True, 0, False),
            ("on", False, 1, False), ("partial", False, 0, False),
            ("off", False, 0, False),
        ):
            with self.subTest(state=state, cached=cached, total=total):
                self.assertEqual(machine_state.idle_eligible({
                    "state": state, "pending": {"from_cache": cached, "total": total}
                }), expected)

    def test_evolution_manager_reports_new_stable_release(self):
        with patch.object(updates, 'run', return_value=json.dumps({'tag_name': 'v2.3.8', 'prerelease': False})):
            self.assertEqual(updates.evolution_status([updates.EVOLUTION_PIN]),
                             {'installed': '2.3.7', 'latest': '2.3.8', 'update_available': True})
        with patch.object(updates, 'run', return_value=json.dumps({'tag_name': 'v2.4.0-rc1', 'prerelease': True})):
            self.assertIsNone(updates.evolution_status([updates.EVOLUTION_PIN]))

    def test_tunnel_validation_and_rollback(self):
        for url in ("http://example.org", "https://user@example.org", "example.org:443",
                    "example.org/path", "example.org?", "-bad.example.org", "127.0.0.1"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                tunnel.normalize(url)
        with tempfile.TemporaryDirectory() as folder:
            env = Path(folder) / ".env"
            previous = b"NGROK_DOMAIN=old.example.org\nFRONTEND_URL=https://old.example.org\n"
            previous += b"NEXT_PUBLIC_BACKEND_URL=https://old.example.org/api\nMAIN_URL=https://old.example.org\n"
            previous += b"UNCHANGED=synthetic\n"
            env.write_bytes(previous)
            with patch.object(tunnel, "probe", return_value=b"Postiz"), patch.object(tunnel, "compose") as compose, \
                 patch.object(tunnel, "wait_until_ready", side_effect=[RuntimeError("bad endpoint"), None]) as ready:
                with self.assertRaisesRegex(RuntimeError, "previous settings and services were restored"):
                    tunnel.switch(env, "new.example.org")
                self.assertEqual(env.read_bytes(), previous)
                self.assertEqual(compose.call_count, 5)
                self.assertEqual(ready.call_args.args[1], "https://old.example.org")
            with patch.object(tunnel, "probe", return_value=b"Postiz"), patch.object(tunnel, "compose"), \
                 patch.object(tunnel, "wait_until_ready"):
                self.assertEqual(tunnel.switch(env, "https://New.Example.org/"), "https://new.example.org")
                self.assertEqual(env.read_bytes(), previous.replace(b"old.example.org", b"new.example.org"))
                self.assertEqual(env.stat().st_mode & 0o777, 0o600)
            self.assertFalse((env.parent / "run/tunnel-url.previous").exists())

    def test_gateway_tunnel_rollback_preserves_enrollment_keys(self):
        from v2.gateway_setup import config

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            env = root / ".env"
            original = b"NGROK_DOMAIN=old.example.org\nFRONTEND_URL=https://old.example.org\n"
            original += b"NEXT_PUBLIC_BACKEND_URL=https://old.example.org/api\nMAIN_URL=https://old.example.org\n"
            env.write_bytes(original)
            gateway = root / "data/gateway/configuration.yml"
            gateway.parent.mkdir(parents=True)
            original_gateway = json.dumps(config("old.example.org")).encode()
            gateway.write_bytes(original_gateway)

            def verify(local, public, expected, *, gated):
                self.assertTrue(gated)
                current = json.loads(gateway.read_text())
                self.assertEqual(current["storage"], json.loads(original_gateway)["storage"])
                self.assertEqual(current["session"]["cookies"][0]["domain"], tunnel.normalize(public)[0])
                if public == "https://new.example.org":
                    raise RuntimeError("simulated public verification failure")

            with patch.object(tunnel, "probe", return_value=b"Postiz") as probe, \
                 patch.object(tunnel, "gateway_ready", return_value=True), \
                 patch.object(tunnel, "check_gateway_config"), patch.object(tunnel, "compose") as compose, \
                 patch.object(tunnel, "wait_until_ready", side_effect=verify):
                with self.assertRaisesRegex(RuntimeError, "previous settings and services were restored"):
                    tunnel.switch(env, "new.example.org")
                self.assertEqual(env.read_bytes(), original)
                self.assertEqual(gateway.read_bytes(), original_gateway)
                self.assertEqual([call.args[1:] for call in compose.call_args_list].count(("stop", "ngrok")), 2)
                probe.assert_called_once_with("http://localhost:4200")
            self.assertFalse((root / "run/tunnel-gateway.previous").exists())

    def test_uninstall_preserves_data_and_aborts_on_failed_docker_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            project = root / 'project'
            home = root / 'home'
            app = home / 'Applications' / 'PostForge.app'
            app.mkdir(parents=True)
            tools = root / 'bin'
            tools.mkdir()
            docker = tools / 'docker'
            docker.write_text('#!/bin/bash\n[[ "$1" == info || "$TEST_COMPOSE_OK" == yes ]]\n')
            docker.chmod(0o755)
            scripts = project / 'scripts'
            scripts.mkdir(parents=True)
            uninstall = scripts / 'uninstall.sh'
            shutil.copyfile(ROOT / 'uninstall.sh', uninstall)
            (project / 'docker-compose.yml').touch()
            private_files = [project / '.env', project / 'data' / 'db', project / 'exports' / 'backup']
            for file in private_files:
                file.parent.mkdir(exist_ok=True)
                file.write_text('synthetic private data')
            env = dict(os.environ, HOME=str(home), PATH=str(tools) + os.pathsep + os.environ['PATH'])
            args = ['/bin/bash', str(uninstall), '--yes', '--keep-app-running']
            failed = subprocess.run(args + ['--purge-data'], env=dict(env, TEST_COMPOSE_OK='no'),
                                    capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertTrue(app.exists())
            subprocess.run(args, env=dict(env, TEST_COMPOSE_OK='yes'), check=True, capture_output=True)
            self.assertFalse(app.exists())
            for file in private_files:
                self.assertEqual(file.read_text(), 'synthetic private data')

    def test_backup_rejects_traversal_and_links_before_writing(self):
        for name, kind in [("../outside.txt", tarfile.REGTYPE), ("link", tarfile.SYMTYPE)]:
            with tempfile.TemporaryDirectory() as folder:
                archive = Path(folder) / 'bad.tar'
                with tarfile.open(archive, 'w') as target:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = '../outside.txt' if kind == tarfile.SYMTYPE else ''
                    target.addfile(member, io.BytesIO(b''))
                destination = Path(folder) / 'restore'
                destination.mkdir()
                with tarfile.open(archive) as source:
                    with self.assertRaises(pmlib.PMError):
                        postiz_transfer.safe_extract(source, str(destination))
                self.assertEqual(list(destination.iterdir()), [])
                self.assertFalse((Path(folder) / 'outside.txt').exists())

    def test_credentials_round_trip_and_wrong_password_preserves_env(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(credentials, 'ROOT', folder), patch.object(credentials, 'ENV', str(Path(folder) / '.env')), contextlib.redirect_stdout(io.StringIO()):
            env = Path(folder) / '.env'
            original = b'TEST_SECRET=synthetic-only\n'
            env.write_bytes(original)
            archive = str(Path(folder) / 'credentials.env.enc')
            with patch.object(credentials, 'passphrase', return_value=('correct-test-passphrase', 'correct-test-passphrase')):
                credentials.export_credentials(archive)
                env.write_bytes(b'CURRENT=preserve-me\n')
            with patch.object(credentials, 'passphrase', return_value=('wrong-test-passphrase', 'wrong-test-passphrase')):
                with self.assertRaises(RuntimeError):
                    credentials.import_credentials(archive)
            self.assertEqual(env.read_bytes(), b'CURRENT=preserve-me\n')
            with patch.object(credentials, 'passphrase', return_value=('correct-test-passphrase', 'correct-test-passphrase')):
                credentials.import_credentials(archive)
            self.assertEqual(env.read_bytes(), original)
            self.assertEqual(env.stat().st_mode & 0o777, 0o600)

    def test_direct_schedule_worker_sends_approved_due_status_once(self):
        import whatsapp_pending
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(whatsapp_pending, "QUEUE_FILE", str(Path(folder) / "queue.json")), \
             patch.object(whatsapp_pending, "_send_item") as send:
            base = {"status":"pending", "when":"2026-01-01T00:00:00Z"}
            whatsapp_pending._write([
                dict(base,id="scheduled",approved=True,approval_source="reviewed-direct-schedule"),
                dict(base,id="unapproved",approved=False,approval_source="reviewed-direct-schedule"),
                dict(base,id="unknown",approved=True,approval_source="unknown"),
                dict(base,id="future",approved=True,approval_source="reviewed-direct-schedule",when="2999-01-01T00:00:00Z")])
            whatsapp_pending.process({})
            whatsapp_pending.process({})
            self.assertEqual(send.call_count,1)
            self.assertEqual(send.call_args.args[0]["id"],"scheduled")
            items=whatsapp_pending._read()
            self.assertEqual(items[0]["status"],"sent")
            self.assertTrue(all(item["status"]=="pending" for item in items[1:]))

    def test_whatsapp_uncertain_delivery_is_not_retried(self):
        import whatsapp_pending

        item = {"id": "aabbcc112233", "status": "pending", "approved": True,
                "approval_source": "explicit-whatsapp-command", "when": "2026-01-01T00:00:00Z"}
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(whatsapp_pending, "QUEUE_FILE", str(Path(folder) / "queue.json")), \
             patch.object(whatsapp_pending, "_send_item", side_effect=TimeoutError) as send:
            whatsapp_pending._write([item])
            whatsapp_pending.process({})
            whatsapp_pending.process({})
            send.assert_called_once()
            self.assertEqual(whatsapp_pending._read()[0]["status"], "needs_review")
            self.assertIsNone(whatsapp_pending.approve(item["id"]))
            whatsapp_pending._write([dict(item, status="sending")])
            self.assertEqual(whatsapp_pending.recover_interrupted(), 1)
            whatsapp_pending.process({})
            send.assert_called_once()
            self.assertEqual(whatsapp_pending._read()[0]["review_reason"], "send_interrupted")

    def test_status_approval_sends_exact_reference_to_own_chat(self):
        reference = "aabbcc112233"
        env = {}
        with patch.object(sys, "argv", ["wa-inbox", "--send-status-approval", reference]), \
             patch.object(pmlib, "load_env", return_value=env), \
             patch.object(wa_inbox, "own_identity", return_value=("instance", "id", "555", [])), \
             patch.object(wa_inbox, "ui_language", return_value="Spanish"), \
             patch.object(wa_inbox, "reply") as reply:
            self.assertEqual(wa_inbox.main(), 0)
        reply.assert_called_once_with(env, "instance", "555", "555",
                                      "aprobar whatsapp " + reference, {}, False)

    def test_generated_caption_repairs_split_tag_and_drops_unrelated_emoji(self):
        text = "¿Galletas o cupcakes ? 🍪🎂\n\n#GalletasY CupcakesEcuador\n\n#ComidaCasera #comidacasera"
        self.assertEqual(
            create_draft.finish(text, "Spanish", topic="galletas y cupcakes"),
            "¿Galletas o cupcakes? 🍪\n\n#GalletasYCupcakesEcuador #ComidaCasera",
        )
        inline = "Start with #Weekend Hikes are more fun outside."
        self.assertEqual(create_draft.split_hashtags(inline), (inline, []))

    def test_caption_removes_prompt_echo_and_duplicate_cta(self):
        text = 'Pan de yuca recién horneado. Pan de yuca recién horneado. 🍎\nEscribe frases cortas sobre el tema.\nHaz tu pedido por WhatsApp.\n#PanDeYuca #PanDeYuca'
        result = create_draft.finish(text, 'Spanish', topic='pan de yuca')
        self.assertNotIn('frases cortas', result)
        self.assertNotIn('🍎', result)
        self.assertEqual(result.count('Pan de yuca recién horneado.'), 1)
        self.assertNotIn('WhatsApp', result)
        self.assertEqual(result.count('#PanDeYuca'), 1)
        configured = create_draft.finish(text, 'Spanish', env={'CAPTION_CTA_ES': 'Escríbenos para más información.'})
        self.assertIn('Escríbenos para más información.', configured)
        self.assertNotIn('WhatsApp', configured)

    def test_draft_contract_cannot_schedule_a_live_post(self):
        api = object.__new__(pmlib.Postiz)
        api.env = {}
        with patch.object(api, '_call', return_value=[{'postId': 'test'}]) as call:
            api.create_draft({'id': 'test', 'identifier': 'facebook'}, 'Texto aprobado', when=datetime(2026, 11, 6, 23, tzinfo=timezone.utc))
        payload = call.call_args.args[2]
        self.assertEqual(payload['type'], 'draft')
        self.assertEqual(payload['date'], '2026-11-06T23:00:00.000Z')
        self.assertEqual(payload['posts'][0]['value'][0]['content'], 'Texto aprobado')

    def test_ecuador_schedule_does_not_take_dates_from_caption(self):
        now = datetime(2026, 11, 4, 12, tzinfo=timezone(timedelta(hours=-5)))
        result = plan_post.plan({}, 'Facebook mañana a las 6 de la tarde, texto: Pedidos hasta el sábado', [], 'Spanish', now)
        self.assertEqual(result['when'], datetime(2026, 11, 5, 18, tzinfo=now.tzinfo))
        self.assertEqual(result['exact'], 'Pedidos hasta el sábado')

    def test_oversized_protobuf_media_never_reaches_evolution(self):
        row = {'type': 'videoMessage', 'key': {'id': 'test'}, 'message': {'videoMessage': {'fileLength': {'low': 180887424, 'high': 0, 'unsigned': True}}}}
        with patch.object(wa_inbox, 'evo_call') as api:
            with self.assertRaises(wa_inbox.PMError):
                wa_inbox.download({}, 'test', row, '/tmp')
            api.assert_not_called()
        self.assertEqual(wa_inbox.media_size({'type': 'videoMessage', 'message': {'videoMessage': {'fileLength': {'low': -1, 'high': 1}}}}), (1 << 33) - 1)
        self.assertEqual(wa_inbox.media_size({'type': 'audioMessage', 'message': {'audioMessage': {'fileLength': '1024'}}}), 1024)
        self.assertIsNone(wa_inbox.media_size({'type': 'imageMessage', 'message': {}}))

    def test_large_video_uses_disk_stream_and_checks_length(self):
        size = 180887424
        row = {'type': 'videoMessage', 'message': {'videoMessage': {
            'fileLength': size, 'directPath': '/video', 'mediaKey': 'synthetic',
            'fileSha256': 'synthetic', 'mimetype': 'video/mp4',
        }}}
        with tempfile.TemporaryDirectory() as folder, patch.object(wa_inbox, 'evo_call') as api:
            with patch.object(wa_inbox, 'stream_video', return_value='video.mp4') as stream:
                self.assertEqual(wa_inbox.download({}, 'test', row, folder), 'video.mp4')
                stream.assert_called_once_with(row, folder, size)
            with patch.object(wa_inbox.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
                with self.assertRaisesRegex(pmlib.PMError, 'verify'):
                    wa_inbox.download({}, 'test', row, folder)
                self.assertEqual(list(Path(folder).iterdir()), [])
            api.assert_not_called()

    def test_explicit_short_rejects_ineligible_video(self):
        now = datetime(2026, 11, 5, 6, tzinfo=timezone(timedelta(hours=-5)))
        plan = plan_post.plan({}, 'YouTube Shorts today at 8am, caption: Test', ['sample.mp4'], 'English', now)
        with patch.object(pmlib, 'Postiz') as api, patch.object(pmlib, 'normalize_media', return_value=('video', 'sample.mp4')), \
             patch.object(pmlib, 'is_short', return_value=False), \
             patch.object(pmlib, 'ffprobe', return_value=(200, 'h264', 'aac', 1920, 1080)):
            api.return_value.integrations.return_value = [{'identifier': 'youtube'}]
            with self.assertRaisesRegex(pmlib.PMError, 'at most 3 minutes'):
                plan_post.run({}, plan, True)
            api.return_value.upload.assert_not_called()

    def test_retention_preserves_referenced_media_and_pending_plans(self):
        with tempfile.TemporaryDirectory() as folder:
            roots = [Path(folder) / name for name in ('postiz-uploads', 'logs', 'wa-confirmations')]
            for root in roots:
                root.mkdir()
            for root, name in [(roots[0], 'scheduled.jpg'), (roots[0], 'unused.jpg'), (roots[1], 'old.log'), (roots[2], 'pending.json')]:
                target = root / name
                target.write_text('test')
                os.utime(target, (1, 1))
            with patch.object(retention, 'ROOTS', tuple(map(str, roots))), patch.object(retention, 'referenced_media', return_value='[{"path":"/uploads/scheduled.jpg"}]'):
                self.assertEqual({Path(p).name for p in retention.candidates(time.time())}, {'unused.jpg', 'old.log'})
            with patch.object(retention, 'ROOTS', tuple(map(str, roots))), patch.object(retention, 'referenced_media', return_value=None):
                self.assertEqual({Path(p).name for p in retention.candidates(time.time())}, {'old.log'})

    def test_registry_timeout_also_stops_a_child_holding_the_pipe(self):
        code = "import subprocess,sys,time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); time.sleep(60)"
        started = time.monotonic()
        with patch.object(updates, 'COMMAND_TIMEOUT_SECONDS', 0.3):
            self.assertIsNone(updates.run([sys.executable, '-c', code]))
        self.assertLess(time.monotonic() - started, 3)

    def test_pinned_digest_needs_no_registry_request(self):
        image = 'repo@sha256:fixed'
        with patch.object(updates, 'run', return_value='["repo@sha256:fixed"]') as command:
            self.assertEqual(updates.image_status(image), (image, 'current'))
        self.assertEqual(command.call_count, 1)

    def test_unavailable_docker_is_not_reported_as_up_to_date(self):
        with patch.object(updates, 'run', return_value=None):
            result = updates.check()
        self.assertFalse(result['check_complete'])
        self.assertFalse(result['updates_available'])

    def test_component_updates_distinguish_changed_and_unknown(self):
        def fake(args):
            if args[1] == 'compose':
                return 'same:1\nchanged:1\nunknown:1'
            image = args[3] if args[1] == 'image' else args[4]
            if image == 'unknown:1':
                return None
            return json.dumps(['repo@sha256:old']) if args[1] == 'image' else json.dumps({'digest': 'sha256:old' if image == 'same:1' else 'sha256:new'})
        with patch.object(updates, 'run', side_effect=fake):
            result = updates.check()
            self.assertEqual(result['components'], [{'name': 'changed:1', 'kind': 'docker'}])
            self.assertTrue(result['updates_available'])
            self.assertFalse(result['check_complete'])
            self.assertEqual(result['unchecked_images'], ['unknown:1'])

    def test_rollback_keeps_immutable_digest_references(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'images.json'
            path.write_text(json.dumps({'image@sha256:pinned': 'sha256:pinned', 'mutable:1': 'sha256:old'}))
            with patch.object(rollback, 'command', return_value='ok') as command, patch.object(sys, 'argv', ['rollback', 'restore', str(path)]):
                rollback.main()
            tags = [call.args for call in command.call_args_list if 'tag' in call.args]
            self.assertEqual(tags, [('docker', 'image', 'tag', 'sha256:old', 'mutable:1')])

    def test_rollback_checks_all_images_before_changing_tags(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'images.json'
            path.write_text(json.dumps({'first:1': 'sha256:first', 'second:1': 'sha256:missing'}))
            calls = []
            def fake(*args):
                calls.append(args)
                if 'sha256:missing' in args:
                    raise RuntimeError('missing image')
                return 'ok'
            with patch.object(rollback, 'command', side_effect=fake), patch.object(sys, 'argv', ['rollback', 'restore', str(path)]):
                with self.assertRaises(RuntimeError):
                    rollback.main()
            self.assertFalse(any('tag' in call for call in calls))


if __name__ == '__main__':
    unittest.main()
