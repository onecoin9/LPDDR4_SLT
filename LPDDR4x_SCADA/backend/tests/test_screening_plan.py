import unittest
from app.cfg import _DEFAULTS, _P2_BIT_BY_NAME, parse_cfg
from app.profileplan import compile_profile
from app.protocol import HsgCodec, StartTest
from app.testplan import ALL_ALGORITHMS, QUICK_ALGORITHMS, BAD_AREA_ALGORITHMS
from tests.test_profileplan import valid_profile


class ScreeningPlanTests(unittest.TestCase):
    def plan(self, mode="快速筛查", names=QUICK_ALGORITHMS, orders=None, **updates):
        p = valid_profile(pl2={"screeningVersion": 1, "testMode": mode,
                               "selectedAlgorithms": list(names), "executionOrder": orders or {n: str(i + 1) for i, n in enumerate(names)}})
        p.update(updates)
        return compile_profile(p, dict(_DEFAULTS))

    def test_quick_preset_is_ordered_and_mcu_frame_is_exact(self):
        plan = self.plan()
        self.assertTrue(plan["valid"], plan["errors"])
        self.assertEqual(plan["algorithms"], list(QUICK_ALGORITHMS))
        self.assertIn("P2Order=7:0:15:21:37\n", plan["cfgText"])
        self.assertEqual(bytes.fromhex(plan["mcuMessage"]["frameHex"]), HsgCodec().encode(StartTest(plan["cfgText"])))
        self.assertEqual(plan["mcuMessage"]["payloadBytes"], len(plan["cfgText"].encode()))

    def test_complete_mode_always_includes_all_39_bits(self):
        plan = self.plan("完整筛查", [], {n: str(i + 1) for i, n in enumerate(ALL_ALGORITHMS)})
        self.assertTrue(plan["valid"], plan["errors"])
        self.assertEqual(int(plan["mask"], 16), (1 << 39) - 1)
        self.assertEqual(plan["testCount"], 40)
        self.assertEqual(len(plan["cfgText"].split("P2Order=")[1].splitlines()[0].split(":")), 39)

    def test_walk_alias_expands_adjacent_stable_bits(self):
        names = ["test_walking_ones_zeros", "test_random_value"]
        plan = self.plan(names=names)
        self.assertTrue(plan["valid"])
        self.assertIn("P2Order=13:14:0\n", plan["cfgText"])

    def test_bad_area_mode_enables_transport_and_restricts_scans(self):
        plan = self.plan("坏区管理", BAD_AREA_ALGORITHMS)
        self.assertTrue(plan["valid"], plan["errors"])
        self.assertEqual(parse_cfg(plan["cfgText"])["BADBLOCKMGMT"], 1)
        bad = self.plan("坏区管理", ["test_xor_comparison"])
        self.assertIn("address_algorithm", [e["code"] for e in bad["errors"]])

    def test_order_invalid_duplicate_and_missing_value_fail_closed(self):
        for value in ("", "1.5", "0", "-1", "10000", True, None):
            plan = self.plan(names=["test_random_value"], orders={"test_random_value": value})
            self.assertFalse(plan["valid"], value)
            self.assertEqual(plan["cfgText"], "")
        plan = self.plan(names=["test_random_value", "test_seqinc_comparison"], orders={"test_random_value": "1", "test_seqinc_comparison": "1"})
        self.assertFalse(plan["valid"])

    def test_new_modes_remove_global_parameter_and_memtester_gates(self):
        plan = self.plan(pl1Enabled=False, pl2Enabled=False, params=[{"name": "VDD1(mV)", "checked": True, "value": "1800"}])
        self.assertTrue(plan["valid"])
        self.assertEqual(parse_cfg(plan["cfgText"])["VDD1"], 1800)
        self.assertEqual(parse_cfg(plan["cfgText"])["MEMTESTER"], 1)

    def test_invalid_mode_and_version_block(self):
        self.assertFalse(self.plan("future")["valid"])
        p = valid_profile(pl2={"screeningVersion": True})
        self.assertFalse(compile_profile(p, dict(_DEFAULTS))["valid"])

    def test_payload_limit_blocks_preloader_receive_overflow(self):
        base = dict(_DEFAULTS, PADDING="x" * 1024)
        self.assertIn("frame_size", [e["code"] for e in compile_profile(valid_profile(), base)["errors"]])

    def test_order_descending_is_used_in_payload(self):
        p = valid_profile(pl2={"selectedAlgorithms": ["test_random_value", "test_seqinc_comparison"],
                               "ascOrder": "降序", "executionOrder": {"test_random_value": "1", "test_seqinc_comparison": "2"}})
        self.assertIn("P2Order=7:0\n", compile_profile(p, dict(_DEFAULTS))["cfgText"])
