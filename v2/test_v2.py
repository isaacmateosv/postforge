# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import unittest
from unittest.mock import Mock, patch

import postforge_v2 as web
import telegram_worker as bot


class PreviewTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
