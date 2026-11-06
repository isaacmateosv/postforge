# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import unittest
from urllib.parse import urlsplit
from unittest.mock import Mock, patch

import check_gateway
import ngrok_policy
import postforge_v2 as web
import telegram_worker as bot


class PreviewTests(unittest.TestCase):
    def test_google_policy_is_fail_closed_and_uses_exact_addresses(self):
        for values in ([], ["*@example.org"], ['x@example.org" || true']):
            with self.subTest(values=values), self.assertRaises(ValueError):
                ngrok_policy.make_policy(values)
        policy = ngrok_policy.make_policy(["Owner@example.org", "owner@example.org"])
        authenticate, deny = policy["on_http_request"]
        self.assertEqual(authenticate["actions"][0]["config"]["provider"], "google")
        self.assertEqual(deny["expressions"],
                         ['!(actions.ngrok.oauth.identity.email in ["owner@example.org"])'])
        self.assertEqual(deny["actions"][0]["config"]["status_code"], 403)

    def test_postiz_redirect_is_not_an_outer_login(self):
        postiz = "https://postiz.example.org/"
        gate = urlsplit("https://login.example.org/sso")
        self.assertFalse(check_gateway.gate_response(307, "/auth/login", postiz, gate))
        self.assertFalse(check_gateway.gate_response(200, "", postiz, gate))
        self.assertFalse(check_gateway.gate_response(302, "https://login.example.org/sso-evil", postiz, gate))
        self.assertTrue(check_gateway.gate_response(302, "https://login.example.org/sso/start", postiz, gate))
        self.assertTrue(check_gateway.gate_response(401, "", postiz, gate))

    def test_postiz_link_rejects_unsafe_urls(self):
        for url in ("javascript:alert(1)", "http://example.org", "https://a:b@example.org",
                    "https://example.org/path", "https://example.org/?redirect=1"):
            with self.subTest(url=url), patch.dict(os.environ, {"POSTIZ_BROWSER_URL": url}):
                self.assertIsNone(web.browser_url())

    def test_dashboard_has_language_and_distinguishes_reachability(self):
        with patch.object(web, "services", return_value=dict(zip(web.PROBES, [True, False, True]))):
            page = web.dashboard(True).decode()
        self.assertIn('lang="es-EC"', page)
        self.assertIn("Sin respuesta", page)
        self.assertIn("se revisan por separado", page)

    def test_telegram_rejects_unauthorized_chat_and_callback(self):
        call = Mock()
        for update in (
            {"message": {"from": {"id": 8}, "chat": {"type": "private", "id": 8}, "text": "/status"}},
            {"message": {"from": {"id": 7}, "chat": {"type": "group", "id": 7}, "text": "/status"}},
            {"callback_query": {"id": "q", "from": {"id": 8},
                                "message": {"chat": {"type": "private", "id": 7}}, "data": "status"}},
        ):
            bot.handle(call, update, 7, False)
        call.assert_not_called()

    def test_owner_can_refresh_and_heartbeat_contains_health(self):
        call = Mock()
        update = {"callback_query": {"id": "q", "from": {"id": 7},
                                     "message": {"chat": {"type": "private", "id": 7}}, "data": "status"}}
        with patch.object(bot, "services", return_value={"Postiz API": False}):
            bot.handle(call, update, 7, False)
            bot.send_status(call, 7, True, heartbeat=True)
        self.assertEqual([entry.args[0] for entry in call.call_args_list],
                         ["answerCallbackQuery", "sendMessage", "sendMessage"])
        self.assertIn("Postiz API: sin respuesta", call.call_args.kwargs["text"])
        self.assertEqual(call.call_args.kwargs["chat_id"], 7)





class TelegramSetupTest(unittest.TestCase):
    def test_discovery_requires_private_start_from_the_owner(self):
        from telegram_setup import pending_owners

        def update(owner, chat, message, kind="private"):
            return {"message": {"from": {"id": owner}, "chat": {"id": chat, "type": kind}, "text": message}}

        self.assertEqual(pending_owners([update(10, 10, "/start"), update(11, 10, "/start"),
                                         update(12, 12, "/status"), update(13, 13, "/start", "group")]), {10})

    def test_saves_bot_and_owner_separately_from_token(self):
        import os
        import tempfile
        from pathlib import Path
        from telegram_setup import save

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "telegram"
            token = "42:" + "synthetic" * 4
            save(directory, token, 17, "es", 15)
            self.assertEqual((directory / "token").read_text().strip(), token)
            settings = (directory / "settings.env").read_text()
            self.assertNotIn(token, settings)
            self.assertIn("TELEGRAM_BOT_ID=42", settings)
            self.assertIn("TELEGRAM_OWNER_ID=17", settings)
            if os.name != "nt":
                self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
                self.assertEqual((directory / "settings.env").stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
