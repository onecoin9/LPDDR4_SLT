import copy
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from app.cfg import _DEFAULTS, parse_cfg
from app.profileplan import compile_profile
from app import products


def valid_profile(**updates):
    p = {
        "name": "CONFIG-TEST", "rankEnabled": False,
        "pl1Enabled": True, "pl2Enabled": True, "channels": {}, "mr": {},
        "params": [],
        "pl2": {"selectedAlgorithms": ["test_solid_bit"], "patterns": {}},
    }
    p.update(updates)
    return p


class ProductPreflightTests(unittest.TestCase):
    def compile(self, p):
        return compile_profile(p, dict(_DEFAULTS))

    def test_canonical_empty_cannot_be_overridden_by_stale_category(self):
        p = valid_profile(pl2={"selectedAlgorithms": [], "patterns": {
            "Block测试": [{"name": "test_solid_bit", "checked": True}]}})
        result = self.compile(p)
        self.assertFalse(result["valid"])
        self.assertEqual(result["errors"][0]["code"], "empty_selection")

    def test_unknown_only_and_unknown_plus_known_are_blocked(self):
        for names in (["unknown"], ["unknown", "test_solid_bit"]):
            p = valid_profile(pl2={"selectedAlgorithms": names})
            self.assertIn("unknown_algorithm", [e["code"] for e in self.compile(p)["errors"]])

    def test_legacy_categories_preserve_previous_union(self):
        p = valid_profile(pl2={"patterns": {
            "Block测试": [{"name": "test_solid_bit", "checked": False}],
            "全空间测试": [{"name": "test_solid_bit", "checked": True}]}})
        plan = self.compile(p)
        self.assertTrue(plan["valid"])
        self.assertEqual(plan["mask"], "0x100")

    def test_high_bit_and_multi_bit_algorithm_not_truncated(self):
        p = valid_profile(pl2={"selectedAlgorithms": ["test_ac_colharass", "test_walking_ones_zeros"]})
        plan = self.compile(p)
        self.assertTrue(plan["valid"])
        self.assertEqual(int(plan["mask"], 16), (1 << 38) | (1 << 13) | (1 << 14))
        self.assertEqual(plan["testCount"], 4)  # Three mask bits + mandatory Stuck.

    def test_bad_voltage_fails_instead_of_using_a_different_value(self):
        p = valid_profile(params=[{"name": "VDD1(mV)", "checked": True, "value": "180"}])
        plan = self.compile(p)
        self.assertFalse(plan["valid"])
        self.assertEqual(plan["cfgText"], "")
        self.assertIn("range", [e["code"] for e in plan["errors"]])

    def test_blank_disabled_voltage_inherits_baseline(self):
        p = valid_profile(params=[{"name": "VDD1(mV)", "checked": False, "value": ""}])
        plan = self.compile(p)
        self.assertTrue(plan["valid"])
        self.assertEqual(parse_cfg(plan["cfgText"])["VDD1"], _DEFAULTS["VDD1"])
        row = next(r for r in plan["effectiveParameters"] if r["name"] == "VDD1")
        self.assertEqual(row["source"], "baseline")

    def test_nonfinite_and_fractional_integer_inputs_blocked(self):
        for value in ("nan", "inf", "1900.5"):
            p = valid_profile(params=[{"name": "VDD1(mV)", "checked": True, "value": value}])
            self.assertFalse(self.compile(p)["valid"], value)

    def test_reserved_unit_and_unsupported_parameter_blocked(self):
        self.assertFalse(self.compile(valid_profile(timingUnit=1))["valid"])
        plan=self.compile(valid_profile(params=[{"name":"TR2MRW","checked":True,"value":"1"}]))
        self.assertTrue(plan['valid'])
        self.assertEqual(plan['configurationStatus'],'partial')

    def test_legacy_bare_timings_are_not_transmitted_or_reported_as_effective(self):
        p = valid_profile(timingUnit=2, params=[
            {"name": "TRCD", "checked": True, "value": "30"},
            {"name": "TRFC", "checked": True, "value": "180"}])
        plan = self.compile(p)
        self.assertTrue(plan["valid"])
        wire = parse_cfg(plan["cfgText"])
        self.assertNotIn('TRCD',wire)
        self.assertNotIn('TRFC',wire)
        self.assertNotIn('TIMING_UNIT',wire)
        self.assertEqual(plan['configurationStatus'],'partial')
        units = {r["name"]: r["unit"] for r in plan["effectiveParameters"]}
        self.assertNotIn('TRCD',units)
        self.assertNotIn('TRFC',units)

    def test_disabled_memtester_does_not_claim_algorithms(self):
        plan = self.compile(valid_profile(pl2Enabled=False))
        self.assertTrue(plan["valid"])
        self.assertEqual(plan["algorithms"], [])
        self.assertEqual(plan["testCount"], 0)

    def test_inputs_not_mutated_and_hash_deterministic(self):
        p = valid_profile()
        original = copy.deepcopy(p)
        a, b = self.compile(p), self.compile(p)
        self.assertEqual(p, original)
        self.assertEqual(a["cfgSha256"], b["cfgSha256"])
        self.assertEqual(len(a["cfgSha256"]), 64)

    def test_inactive_override_values_do_not_change_or_block_baseline(self):
        p = valid_profile(pl1Enabled=False, timingUnit=1, params=[
            {"name": "VDD1(mV)", "checked": True, "value": "180"}])
        plan = self.compile(p)
        self.assertTrue(plan["valid"])
        self.assertEqual(parse_cfg(plan["cfgText"])["VDD1"], _DEFAULTS["VDD1"])

    def test_malformed_parameter_rows_and_null_selection_blocked(self):
        self.assertFalse(self.compile(valid_profile(params=[None]))["valid"])
        self.assertFalse(self.compile(valid_profile(pl2={"selectedAlgorithms": None}))["valid"])

    def test_invalid_json_write_does_not_damage_previous_product(self):
        with tempfile.TemporaryDirectory() as root, patch.object(products, "_DIR", root):
            old = {"name": "ATOMIC", "value": 1}
            self.assertIsNotNone(products.save(old))
            self.assertIsNone(products.save({"name": "ATOMIC", "value": float("nan")}))
            with open(os.path.join(root, "ATOMIC.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f), old)
            self.assertEqual(os.listdir(root), ["ATOMIC.json"])
