"""Always-on Handler settings, unified persistence, and transactional rebinding."""
import json
import socket
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException
from tests import test_profile_api as profile_api_fixture


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class HandlerSettingsApi(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = profile_api_fixture.ProductApiTests.asyncSetUp

    async def asyncTearDown(self):
        await self.main.handler.close()
        await profile_api_fixture.ProductApiTests.asyncTearDown(self)

    async def test_get_is_always_enabled(self):
        snapshot = await self.main.get_handler_settings()
        self.assertTrue(snapshot["enabled"])
        self.assertFalse(snapshot["running"])  # Fixture deliberately skips lifespan.

    async def test_save_listens_and_uses_single_settings_file(self):
        out = await self.main.post_handler_settings({"rx_port": free_port(), "tx_host": "192.0.2.9"})
        self.assertTrue(out["running"])
        self.assertEqual(self.main.seq.on_result, self.main.handler.notify_result)
        data = json.loads(Path(self.tmp.name, "settings.json").read_text())
        self.assertEqual(data["handler"]["tx_host"], "192.0.2.9")
        self.assertNotIn("enabled", data["handler"])
        self.assertFalse(Path(self.tmp.name, "handler_settings.json").exists())

    async def test_invalid_or_disable_rejected_without_changes(self):
        before = self.main.settings_store.status()
        for body in ({"enabled": False}, {"enabled": "yes"}, {"rx_port": -1},
                     {"rx_port": 70000}, {"rx_port": "x"}, {"tx_port": True},
                     {"tx_host": "bad ip!"}, {"junk": 1}, {}):
            with self.subTest(body=body), self.assertRaises(HTTPException) as caught:
                await self.main.post_handler_settings(body)
            self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.main.settings_store.status(), before)

    async def test_bind_failure_preserves_listener_and_file(self):
        await self.main.post_handler_settings({"rx_port": free_port()})
        old, before = self.main.handler, self.main.settings_store.path.read_bytes()
        with socket.socket() as occupied:
            occupied.bind(("0.0.0.0", 0)); occupied.listen()
            with self.assertRaises(HTTPException) as caught:
                await self.main.post_handler_settings({"rx_port": occupied.getsockname()[1]})
        self.assertEqual(caught.exception.status_code, 409)
        self.assertIs(self.main.handler, old)
        self.assertTrue(old.snapshot()["running"])
        self.assertEqual(self.main.settings_store.path.read_bytes(), before)

    async def test_write_failure_preserves_listener_and_closes_candidate(self):
        await self.main.post_handler_settings({"rx_port": free_port()})
        old, before = self.main.handler, self.main.settings_store.path.read_bytes()
        new_port = free_port()
        with patch("app.settingsstore.atomic_json", side_effect=OSError("read only")):
            with self.assertRaises(OSError):
                await self.main.post_handler_settings({"rx_port": new_port})
        self.assertIs(self.main.handler, old)
        self.assertTrue(old.snapshot()["running"])
        self.assertEqual(self.main.settings_store.path.read_bytes(), before)
        with socket.socket() as probe:
            probe.bind(("0.0.0.0", new_port))

    async def test_tx_change_keeps_server_and_pending_results(self):
        await self.main.post_handler_settings({"rx_port": free_port()})
        old = self.main.handler
        await self.main.post_handler_settings({"tx_host": "192.0.2.8"})
        self.assertIs(self.main.handler, old)
        self.assertEqual(old.tx_host, "192.0.2.8")
