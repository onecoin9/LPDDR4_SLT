import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from tests.test_profileplan import valid_profile
from app.profileplan import ProfileError
from app.sequencer import SequencerBusyError
from app.settingsstore import SettingsStore, SettingsDocument, read_document, revision, SettingsPolicyStore
from app.runtimepolicy import PolicyConflict, PolicyUnavailable, atomic_json
from tests import test_profile_api as profile_api_fixture


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.store = SettingsStore(self.directory, {})

    def test_legacy_migration_and_restart_preserve_all_fields(self):
        legacy = self.directory / "old"
        legacy.mkdir(); (legacy / "products").mkdir()
        atomic_json(legacy / "handler_settings.json", {"enabled": False, "rx_port": 7101, "tx_host": "192.0.2.3"})
        atomic_json(legacy / "machine_settings.json", {"ioControl": {"action": "download", "batch": 3}})
        atomic_json(legacy / "runtime_policy.json", {"cfgAckTimeoutSec": 30})
        atomic_json(legacy / "products/p.json", {"name": "p", "rankEnabled": False})
        store = SettingsStore(legacy, {})
        self.assertIsNone(store.error)
        self.assertEqual(store.document.handler.rx_port, 7101)
        self.assertEqual(store.document.ioControl.batch, 3)
        self.assertEqual(store.document.runtimePolicy.cfgAckTimeoutSec, 30)
        self.assertIn("p", store.document.products)
        self.assertEqual(store.document.browserMigrationPending, ["basic", "ioControl", "products"])
        self.assertEqual(SettingsStore(legacy, {}).status(), store.status())
        self.assertTrue((legacy / "handler_settings.json").exists())

    def test_save_roundtrip_partial_merge_and_frozen_policy(self):
        frozen = SettingsPolicyStore(self.store).snapshot()
        document = self.store.candidate({"basic": {"theme": "light"}, "runtimePolicy": {"cfgAckTimeoutSec": 12}}, revision(self.store.document))
        self.store.save(document)
        reopened = SettingsStore(self.directory, {})
        self.assertEqual(reopened.document.basic.language, "zh")
        self.assertEqual(reopened.document.basic.theme, "light")
        self.assertEqual(frozen.cfgAckTimeoutSec, 0)
        self.assertEqual(SettingsPolicyStore(reopened).snapshot().cfgAckTimeoutSec, 12)

    def test_stale_revision_and_external_changes_rejected(self):
        with self.assertRaises(PolicyConflict):
            self.store.candidate({"basic": {"theme": "light"}}, "stale")
        self.store.path.write_text(self.store.path.read_text() + "\n")
        with self.assertRaises(PolicyConflict):
            self.store.candidate({"basic": {"theme": "light"}}, revision(self.store.document))

    def test_failed_save_leaves_file_and_state_unchanged(self):
        before, state = self.store.path.read_bytes(), self.store.status()
        document = self.store.candidate({"basic": {"language": "en"}}, state["revision"])
        with patch("app.settingsstore.atomic_json", side_effect=OSError("disk full")), self.assertRaises(OSError):
            self.store.save(document)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual(self.store.status(), state)

    def test_file_selection_persists_path_and_saves_to_selected_file(self):
        path = self.directory / "other.json"
        document = SettingsDocument(basic={"theme": "nord"})
        atomic_json(path, document.model_dump())
        self.store.select(path, read_document(path))
        reopened = SettingsStore(self.directory, {})
        self.assertEqual(reopened.path, path)
        reopened.save(reopened.candidate({"basic": {"language": "en"}}, revision(reopened.document)))
        self.assertEqual(read_document(path).basic.language, "en")
        self.assertEqual(read_document(self.directory / "settings.json").basic.theme, "dark")

    def test_invalid_file_never_activates(self):
        path = self.directory / "bad.json"
        for text in ('{"name":"product"}', '{"schemaVersion":1,"basic":{"theme":"wrong"}}',
                     '{"schemaVersion":true,"basic":{}}', '{"schemaVersion":1,"basic":{},"basic":{}}'):
            path.write_text(text)
            with self.subTest(text=text), self.assertRaises(ValueError):
                read_document(path)
        self.assertFalse((self.directory / ".settings.active").exists())

    def test_corrupt_active_file_blocks_new_runs_without_overwrite(self):
        self.store.path.write_text("broken")
        reopened = SettingsStore(self.directory, {})
        self.assertFalse(reopened.status()["valid"])
        with self.assertRaises(PolicyUnavailable):
            SettingsPolicyStore(reopened).snapshot()
        self.assertEqual(reopened.path.read_text(), "broken")

    def test_unknown_fields_and_disabled_handler_rejected(self):
        for update in ({"handler": {"enabled": False}}, {"foo": 1}, {"ioControl": {"batch": True}},
                       {"products": {"p": {"name": "q"}}}, {"basic": {"language": "xx"}}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.store.candidate(update, revision(self.store.document))


class SettingsApiTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = profile_api_fixture.ProductApiTests.asyncSetUp

    async def asyncTearDown(self):
        await self.main.handler.close()
        await profile_api_fixture.ProductApiTests.asyncTearDown(self)

    async def test_patch_requires_revision_and_rejects_stale(self):
        update = {"basic": {"theme": "light"}}
        response = await self.client.post("/api/settings", update)
        self.assertEqual(response.status_code, 428)
        token = self.main.settings_store.status()["revision"]
        response = await self.client.post("/api/settings", update, {"If-Match": token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["settings"]["basic"]["theme"], "light")
        response = await self.client.post("/api/settings", update, {"If-Match": token})
        self.assertEqual(response.status_code, 409)

    async def test_selection_refreshes_runtime_library_and_policy(self):
        path = Path(self.tmp.name, "chosen.json")
        document = SettingsDocument(basic={"language": "en", "theme": "solarized"},
                                    ioControl={"action": "power_key", "batch": 2},
                                    runtimePolicy={"cfgAckTimeoutSec": 18}, products={"q": {"name": "q"}})
        atomic_json(path, document.model_dump())
        response = await self.client.post("/api/settings/select", {"path": str(path)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.main.machine.ioControl.batch, 2)
        self.assertEqual(self.main.machine.product, "q")
        self.assertEqual(self.main.recorder.root, str(Path(self.tmp.name) / "records"))
        self.assertEqual(self.main.run_policy_store.snapshot().cfgAckTimeoutSec, 18)
        self.assertEqual(await self.main.get_products(), {"q": {"name": "q"}})
        self.assertEqual(response.json()["settings"]["basic"]["theme"], "solarized")

    async def test_active_job_blocks_selection_io_and_handler_but_allows_theme(self):
        owner = object(); self.main.seq.reserve(owner)
        try:
            token = self.main.settings_store.status()["revision"]
            response = await self.client.post("/api/settings", {"ioControl": {"batch": 2}}, {"If-Match": token})
            self.assertEqual(response.status_code, 409)
            response = await self.client.post("/api/settings/select", {"path": str(self.main.settings_store.path)})
            self.assertEqual(response.status_code, 409)
            response = await self.client.post("/api/settings", {"handler": {"tx_host": "192.0.2.1"}}, {"If-Match": token})
            self.assertEqual(response.status_code, 409)
            response = await self.client.post("/api/settings", {"basic": {"theme": "nord"}}, {"If-Match": token})
            self.assertEqual(response.status_code, 200)
        finally:
            self.main.seq.release(owner)

    async def test_invalid_selection_and_write_failure_not_acknowledged(self):
        state = self.main.settings_store.status()
        path = Path(self.tmp.name, "bad.json"); path.write_text('{"name":"wrong"}')
        response = await self.client.post("/api/settings/select", {"path": str(path)})
        self.assertEqual(response.status_code, 422)
        with patch("app.settingsstore.atomic_json", side_effect=OSError("disk full")):
            response = await self.client.post("/api/settings", {"basic": {"theme": "light"}}, {"If-Match": state["revision"]})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.main.settings_store.status(), state)

    async def test_log_path_is_applied_and_cannot_change_during_run(self):
        token = self.main.settings_store.status()["revision"]
        response = await self.client.post("/api/settings", {"basic": {"logPath": "new_records"}}, {"If-Match": token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.main.recorder.root, str(Path(self.tmp.name) / "new_records"))
        self.assertEqual(self.main.sweep.records_root, self.main.recorder.root)
        self.main.handler._tx_queue.put_nowait(("testend", {}))
        token = response.json()["revision"]
        response = await self.client.post("/api/settings", {"basic": {"logPath": "other"}}, {"If-Match": token})
        self.assertEqual(response.status_code, 409)

    async def test_handler_start_compiles_current_selected_product(self):
        profile = valid_profile()
        await self.main.post_product(profile)
        with patch.object(self.main.seq, "start", new_callable=AsyncMock, return_value=[(1, 1)]) as start:
            result = await self.main._start_handler_test([(1, 1)], "batch")
        self.assertEqual(result, [(1, 1)])
        start.assert_awaited_once_with([(1, 1)], "batch")
        self.assertIn("P2Mask=0x100", self.main.seq.cfg_text)

    async def test_handler_rejects_invalid_saved_draft_before_start(self):
        profile = valid_profile(pl2={"selectedAlgorithms": []})
        token = self.main.settings_store.status()["revision"]
        reply = await self.client.post("/api/settings", {"products": {profile["name"]: profile}}, {"If-Match": token})
        self.assertEqual(reply.status_code, 200)
        with patch.object(self.main.seq, "start", new_callable=AsyncMock) as start:
            with self.assertRaises(ProfileError):
                await self.main._start_handler_test([(1, 1)], "batch")
        start.assert_not_awaited()

    async def test_stale_browser_cannot_restore_old_product_on_start(self):
        before = self.main.settings_store.status()
        reply = await self.client.post("/api/config", {"product": "stale", "profile": valid_profile(),
                                                      "settingsRevision": "stale"})
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(self.main.settings_store.status(), before)

    async def test_reserved_scan_rejects_handler_before_changing_cfg(self):
        await self.main.post_product(valid_profile())
        owner = object(); self.main.seq.reserve(owner)
        previous = self.main.seq.cfg_text
        try:
            with self.assertRaises(SequencerBusyError):
                await self.main._start_handler_test([(1, 1)], "batch")
            self.assertEqual(self.main.seq.cfg_text, previous)
        finally:
            self.main.seq.release(owner)

    async def test_uncommitted_handler_cannot_admit_test(self):
        from fastapi import HTTPException
        candidate = self.main._make_handler({"handler": {"enabled": True}})
        with patch.object(self.main.seq, "start", new_callable=AsyncMock) as start:
            with self.assertRaises(HTTPException) as caught:
                await candidate.start_test([(1, 1)], "batch")
        self.assertEqual(caught.exception.status_code, 409)
        start.assert_not_awaited()

    async def test_reloading_external_edit_updates_runtime_and_unblocks_save(self):
        path = self.main.settings_store.path
        data = json.loads(path.read_text())
        data["basic"]["theme"] = "meadow"
        atomic_json(path, data)
        token = self.main.settings_store.status()["revision"]
        response = await self.client.post("/api/settings", {"basic": {"language": "en"}}, {"If-Match": token})
        self.assertEqual(response.status_code, 409)
        response = await self.client.post("/api/settings/select", {"path": str(path)})
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.json()["settings"]["basic"]["theme"], "meadow")
        response = await self.client.post("/api/settings", {"basic": {"language": "en"}}, {"If-Match": response.json()["revision"]})
        self.assertEqual(response.status_code, 200)

    async def test_record_directory_picker_preserves_relative_path_and_writes_results(self):
        path = Path(self.tmp.name, "selected_records"); path.mkdir()
        listing = await self.main.browse_settings(str(path))
        self.assertEqual(listing["selectionPath"], "selected_records")
        token = self.main.settings_store.status()["revision"]
        reply = await self.client.post("/api/settings", {"basic": {"logPath": listing["selectionPath"]}}, {"If-Match": token})
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()["settings"]["basic"]["logPath"], "selected_records")
        file = self.main.recorder.append_result("picker-test", 1, 1, "PASS", "", 1.0)
        self.assertTrue(Path(file).is_relative_to(path))
        self.assertIn("PASS", Path(file).read_text())
        self.assertEqual(self.main.sweep.records_root, str(path))
        document = json.loads(self.main.settings_store.path.read_text())
        self.assertEqual(document["basic"]["logPath"], "selected_records")

    async def test_external_directory_picker_returns_absolute_path(self):
        with tempfile.TemporaryDirectory() as directory:
            listing = await self.main.browse_settings(directory)
            self.assertEqual(listing["selectionPath"], str(Path(directory)))

    async def test_directory_picker_drive_list_has_no_selection(self):
        listing = await self.main.browse_settings("")
        self.assertEqual(listing["path"], "")
        self.assertNotIn("selectionPath", listing)
