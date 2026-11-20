"""Real ASGI endpoints in hardware-disabled temporary data; no lifespan/device startup."""
import importlib
import asyncio
import json as jsonlib
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from types import SimpleNamespace
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desktop"))
from init_local_data import init_mock_data
from app import products
from tests.test_profileplan import valid_profile


class LoopbackClient:
    def __init__(self, port):
        self.base = f"http://127.0.0.1:{port}"

    async def post(self, path, json, headers=None):
        def request():
            req = Request(self.base + path, data=jsonlib.dumps(json).encode(),
                          headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
            try:
                response = urlopen(req, timeout=4)
            except HTTPError as exc:
                response = exc
            with response:
                body = jsonlib.loads(response.read())
                return SimpleNamespace(status_code=response.code, json=lambda: body)
        return await asyncio.to_thread(request)


class ProductApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        init_mock_data(self.tmp.name)
        self.env = patch.dict(os.environ, {"SLT_DATA_DIR": self.tmp.name})
        self.env.start()
        self.product_dir = patch.object(products, "_DIR", os.path.join(self.tmp.name, "products"))
        self.product_dir.start()
        self.main = importlib.import_module("app.main")
        self.main = importlib.reload(self.main)
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        self.server = uvicorn.Server(uvicorn.Config(self.main.app, lifespan="off",
                                                  log_level="critical", access_log=False))
        self.server_task = asyncio.create_task(self.server.serve(sockets=[listener]))
        async with asyncio.timeout(4):
            while not self.server.started:
                await asyncio.sleep(.01)
        self.client = LoopbackClient(listener.getsockname()[1])

    async def asyncTearDown(self):
        self.server.should_exit = True
        await self.server_task
        self.product_dir.stop()
        self.env.stop()
        self.tmp.cleanup()

    async def test_invalid_config_keeps_previous_machine_and_cfg(self):
        previous_machine = self.main.machine
        previous_cfg = self.main.seq.cfg_text
        p = valid_profile(pl2={"selectedAlgorithms": []})
        r = await self.client.post("/api/config", json={"product": "WRONG", "profile": p})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["errors"][0]["code"], "empty_selection")
        self.assertIs(self.main.machine, previous_machine)
        self.assertEqual(self.main.seq.cfg_text, previous_cfg)

    async def test_preview_has_no_file_or_runtime_side_effect(self):
        text = self.main.seq.cfg_text
        before = list(Path(self.tmp.name).rglob("*"))
        r = await self.client.post("/api/products/preview", json=valid_profile())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["valid"])
        self.assertEqual(r.json()["mask"], "0x100")
        self.assertEqual(list(Path(self.tmp.name).rglob("*")), before)
        self.assertEqual(self.main.seq.cfg_text, text)

    async def test_valid_save_ack_matches_persisted_product(self):
        p = valid_profile()
        r = await self.client.post("/api/products", json=p)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["plan"]["valid"])
        self.assertEqual(self.main.settings_store.document.products[p["name"]], p)
        self.assertFalse(Path(self.tmp.name, "products", p["name"] + ".json").exists())

    async def test_config_and_power_on_blocked_during_scan_reservation(self):
        owner = object()
        self.main.seq.reserve(owner)
        r = await self.client.post("/api/config", json={"product": "OTHER", "profile": valid_profile()})
        self.assertEqual(r.status_code, 409)
        r = await self.client.post("/api/manual/power", json={"dut": 1, "on": True})
        self.assertEqual(r.status_code, 409)
        self.main.seq.release(owner)
