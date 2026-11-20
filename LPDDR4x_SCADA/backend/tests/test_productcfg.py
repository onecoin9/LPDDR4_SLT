"""Offline CFG editor round trips: reject losses before anything can be saved."""
import copy
import unittest

from app.cfg import BOARD_CONFIG_RANGES, _DEFAULTS, cfg_text
from app.productcfg import profile_from_cfg, read_editor_cfg
from app.profileplan import ProfileError, require_profile
from app.timing_catalog import CATALOG


def current_profile():
    return dict(name='ROUNDTRIP', customer='keep metadata', rankEnabled=False,
                pl1Enabled=False, pl2Enabled=False, channels={}, mr={},
                params=[dict(name='TRCD', value='-2', checked=True)],
                timingUnit=0, timingReviewRequired=True, timingContext={'old': 1},
                pl2={'screeningVersion': 1, 'testMode': '完整筛查'})


class ProductCfgImportTests(unittest.TestCase):
    def roundtrip(self, values=None, extra='', base=None):
        values = dict(_DEFAULTS, **(values or {}))
        text = cfg_text(values) + extra
        current = current_profile()
        baseline = dict(_DEFAULTS) if base is None else base
        original = copy.deepcopy((current, baseline))
        profile, preview = profile_from_cfg(text, current, baseline)
        self.assertEqual((current, baseline), original, 'Import is pure, including on success')
        self.assertTrue(preview['valid'], preview)
        self.assertFalse(preview.get('rejectedParameters'))
        # Recompiling the returned saved object must be the same preview.
        self.assertEqual(require_profile(profile, baseline)['cfgText'], preview['cfgText'])
        actual = read_editor_cfg(preview['cfgText'])
        for key, value in read_editor_cfg(text).items():
            if key in ('TREG', 'P2ORDER'):
                continue  # Their order/canonical syntax has dedicated assertions below.
            self.assertEqual(actual[key], value, key)
        self.assertEqual(profile['name'], current['name'])
        self.assertEqual(profile['customer'], 'keep metadata')
        for retired in ('timingUnit', 'timingReviewRequired', 'timingContext'):
            self.assertNotIn(retired, profile)
        return profile, preview, actual

    def rejected(self, text, field=None, current=None, base=None):
        current = current_profile() if current is None else current
        base = dict(_DEFAULTS) if base is None else base
        before = copy.deepcopy((current, base))
        with self.assertRaises(ProfileError) as caught:
            profile_from_cfg(text, current, base)
        self.assertFalse(caught.exception.preview['valid'])
        if field is not None:
            self.assertIn(field, [e['field'] for e in caught.exception.preview['errors']])
        self.assertEqual((current, base), before, 'Rejected import cannot alter the saved product')

    def test_complete_board_and_regular_parameters(self):
        values = dict(LOG_TO_UART1=0, PatternTest=0, Density=32, DieNum=2,
                      VideoTest=1, DvfsTest=0, EngineerMode=1, AgingTime=50,
                      Mode=3, VDD1=1800, VDD2=1125, VDD2L=0, VDDQ=600,
                      Freq=3733, LogLevel=2, BadBlockMgmt=1)
        profile, _, _ = self.roundtrip(values)
        self.assertEqual(profile['cfgOverrides'], {key: values[key] for key in BOARD_CONFIG_RANGES})
        self.assertEqual({r['name']: r['value'] for r in profile['params']}, {
            'VDD1(mV)': '1800', 'VDD2H(mV)': '1125', 'VDD2L(mV)': '0',
            'VDDQ(mV)': '600', '测试频率(M)': '3733', 'LogLevel': '2', 'BadBlockMgmt': '1'})

    def test_all_nine_board_parameter_boundaries(self):
        for key, (lo, hi) in BOARD_CONFIG_RANGES.items():
            for value in (lo, hi):
                with self.subTest(key=key, value=value):
                    self.roundtrip({key: value})
            for value in (lo-1, hi+1):
                with self.subTest(key=key, value=value):
                    self.rejected(cfg_text(dict(_DEFAULTS, **{key: value})), key)

    def test_rank_capacity_converts_gb_to_gigabytes_exactly(self):
        p, _, _ = self.roundtrip(dict(ChannelA_Rank0_Size=12, ChannelB_Rank0_Size=12,
                                      ChannelA_Rank1_Enable=1, ChannelA_Rank1_Size=4,
                                      ChannelB_Rank1_Enable=1, ChannelB_Rank1_Size=4))
        self.assertEqual(p['rankCapacityGb'], [1.5, 0.5])
        self.assertEqual(p['channels'], {'ch1': True, 'ch2': True})

    def test_single_channel_and_all_mr_expectations(self):
        extra = ''.join(f'ChannelA_MR{i}_2={i * 10}\n' for i in range(5, 9))
        p, _, _ = self.roundtrip(dict(ChannelB_Rank0_Enable=0, ChannelB_Rank0_Size=0), extra)
        self.assertEqual(p['channels'], {'ch1': True, 'ch2': False})
        self.assertEqual([r['value'] for r in p['mr']['ch1']], ['50', '60', '70', '80'])

    def test_asymmetric_rank_sizes_and_layout_are_rejected(self):
        for values in (dict(ChannelB_Rank0_Size=4),
                       dict(ChannelA_Rank1_Enable=1, ChannelA_Rank1_Size=8),
                       dict(ChannelA_Rank0_Enable=0), dict(ChannelA_Rank0_Size=-1),
                       dict(ChannelA_Rank0_Enable=2)):
            with self.subTest(values=values):
                self.rejected(cfg_text(dict(_DEFAULTS, **values)))

    def test_disabled_mr_value_is_not_silently_dropped(self):
        text = cfg_text(dict(_DEFAULTS, ChannelB_Rank0_Enable=0, ChannelB_Rank0_Size=0))
        self.rejected(text+'ChannelB_MR5_2=1\n', 'CHANNELB_MR5_2')
        self.rejected(cfg_text(_DEFAULTS)+'ChannelA_MR8_2=256\n')

    def test_high_bits_and_walking_group_keep_exact_execution_order(self):
        bits = [38, 13, 14, 0, 21]
        mask = sum(1 << bit for bit in bits)
        p, _, actual = self.roundtrip(extra=f'P2Mask=0x{mask:X}\nP2Order=38:13:14:0:21\n')
        self.assertEqual(actual['P2MASK'], mask)
        self.assertEqual(actual['P2ORDER'], '38:13:14:0:21')
        self.assertEqual(p['pl2']['executionOrder']['test_walking_ones_zeros'], '2')

    def test_implicit_all_mask_and_order_become_explicit_without_changing_base(self):
        _, preview, actual = self.roundtrip()
        self.assertEqual(actual['P2MASK'], (1 << 39)-1)
        self.assertEqual(actual['P2ORDER'], ':'.join(map(str, range(39))))
        self.assertEqual(preview['testCount'], 40)

    def test_order_integer_spelling_can_be_canonicalized(self):
        _, _, actual = self.roundtrip(extra='P2Mask=129\nP2Order=007:000\n')
        self.assertEqual(actual['P2ORDER'], '7:0')

    def test_unrepresentable_masks_and_walking_orders_are_rejected(self):
        for extra in ('P2Mask=0', 'P2Mask=-1', f'P2Mask={1 << 39}',
                      f'P2Mask={1 << 13}',
                      f'P2Mask={(1 << 13) | (1 << 14)}\nP2Order=14:13',
                      f'P2Mask={(1 << 13) | (1 << 14) | 1}\nP2Order=13:0:14'):
            with self.subTest(extra=extra):
                self.rejected(cfg_text(_DEFAULTS)+extra+'\n')

    def test_orders_must_match_mask_once_and_use_integer_tokens(self):
        for order in ('0', '0:7:7', '0:1', '0:39', '-0:7', '0:+7', '0:7.0', '0::7', '0: 7'):
            with self.subTest(order=order):
                self.rejected(cfg_text(_DEFAULTS)+f'P2Mask=129\nP2Order={order}\n', 'P2Order')

    def test_disabled_memtester_without_mask_roundtrips(self):
        p, preview, actual = self.roundtrip(dict(MemTester=0))
        self.assertFalse(p['pl2Enabled'])
        self.assertEqual(preview['algorithms'], [])
        self.assertNotIn('P2MASK', actual)
        self.rejected(cfg_text(dict(_DEFAULTS, MemTester=0))+'P2Mask=1\n', 'P2MASK')
        self.rejected(cfg_text(dict(_DEFAULTS, MemTester=2)), 'MemTester')

    def test_v1_raw_counts_half_flags_and_scaled_refresh_roundtrip(self):
        p, _, actual = self.roundtrip(extra='TimingRegV=1\nTReg=29:20000,1:1,26:40000,0:8,3:0\n')
        self.assertEqual(p['timingSchema'], 1)
        self.assertEqual(actual['TREG'], '0:8,1:1,3:0,26:40000,29:20000')
        rows = {r['name']: r['value'] for r in p['params']}
        self.assertEqual(rows['TRCD'], '8')
        self.assertEqual(rows['TRCD_05T'], '1')
        self.assertEqual(rows['TRFC'], '400')

    def test_v3_unsorted_absolute_ns_roundtrips_as_assignments(self):
        p, _, actual = self.roundtrip(extra='TimingRegV=3\nTReg=A;30:5000,0:2000,26:40000,29:20000\n')
        self.assertEqual(p['timingSchema'], 2)
        self.assertEqual(actual['TIMINGREGV'], 3)
        self.assertEqual(actual['TREG'], 'A;30:5000,0:2000,26:40000,29:20000')
        self.assertEqual({r['name']: r['value'] for r in p['params']}['TRCD'], '20')

    def test_raw_timing_leading_zeros_are_equivalent(self):
        _, _, actual = self.roundtrip(extra='TimingRegV=1\nTReg=00:008,01:01\n')
        self.assertEqual(actual['TREG'], '0:8,1:1')

    def test_all_fifty_published_raw_fields_roundtrip_at_both_bounds(self):
        for boundary in ('min', 'max'):
            values = {r['id']: int(r[boundary] * r['scale']) for r in CATALOG}
            encoded = ','.join(f'{ident}:{value}' for ident, value in reversed(list(values.items())))
            profile, preview, actual = self.roundtrip(extra=f'TimingRegV=1\nTReg={encoded}\n')
            self.assertEqual(len(profile['params'])-7, 50)
            self.assertEqual({int(k): int(v) for k, v in
                              (pair.split(':') for pair in actual['TREG'].split(','))}, values)
            self.assertLessEqual(preview['mcuMessage']['payloadBytes'], 1017)

    def test_ns_hundredth_precision_is_preserved_in_the_wire_request(self):
        profile, _, actual = self.roundtrip(extra='TimingRegV=3\nTReg=A;30:1234\n')
        self.assertEqual(actual['TREG'], 'A;30:1234')
        self.assertEqual({r['name']: r['value'] for r in profile['params']}['TZQCS'], '12.34')

    def test_ns_rejection_does_not_import_only_the_surviving_items(self):
        self.rejected(cfg_text(_DEFAULTS)+'TimingRegV=3\nTReg=A;0:100,30:5000\n', 'TReg')
        self.rejected(cfg_text(_DEFAULTS)+'TimingRegV=3\nTReg=A;26:40000,32:40000\n', 'TReg')

    def test_timing_pair_version_and_ids_are_strict(self):
        for extra in ('TimingRegV=1', 'TReg=0:8', 'TimingRegV=2\nTReg=0:8',
                      'TimingRegV=3\nTReg=0:2000', 'TimingRegV=3\nTReg=A;',
                      'TimingRegV=1\nTReg=0:8,0:9', 'TimingRegV=1\nTReg=50:1',
                      'TimingRegV=3\nTReg=A;1:100', 'TimingRegV=1\nTReg=0:16',
                      'TimingRegV=1\nTReg=1:2', 'TimingRegV=1\nTReg=0:-1',
                      'TimingRegV=1\nTReg=0:8,', 'TimingRegV=1\nTReg=0:8=9'):
            with self.subTest(extra=extra):
                self.rejected(cfg_text(_DEFAULTS)+extra+'\n')

    def test_aliases_comments_and_bom_preserve_integer_semantics(self):
        text = '\ufeff# header\n; another\n// third\nfrequency=03733 # requested\nVDD2L=0 // keep\n'
        p, preview = profile_from_cfg(text, current_profile(), dict(_DEFAULTS))
        self.assertEqual(read_editor_cfg(preview['cfgText'])['FREQ'], 3733)
        self.assertEqual(p['params'][2]['value'], '0')

    def test_unknown_retired_and_duplicate_alias_keys_are_rejected(self):
        for text in ('Freq=3200\nFrequency=3733', 'VDD1=1800\nvdd1=1900',
                     'TRCD=8', 'TIMING_UNIT=2', 'ChannelA_MR9_2=1', 'MemTestSize=100',
                     'VDD1=1800\nmisspelled=1'):
            with self.subTest(text=text):
                self.rejected(text)

    def test_malformed_values_size_and_input_types_are_validation_errors(self):
        for text in (None, [], {}, 123, '', '# comment only', 'VDD1', 'VDD1=',
                     'VDD1=1800.0', 'VDD1=nan', 'VDD1=1e3', 'VDD1=True',
                     'VDD1=1800; comment', '\ud800', 'x'*65537,
                     'VDD1='+'9'*5000, 'TimingRegV=1\nTReg=0:'+'9'*5000,
                     'TimingRegV=1\nTReg='+'9'*5000+':1'):
            with self.subTest(type=type(text).__name__, value=str(text)[:40]):
                self.rejected(text)
        self.rejected('VDD1=1800', current=['wrong'])
        for baseline in ([], 'wrong', {1: 2}, {'Freq': True}, {'Freq': '3733'}, {'unknown': 1}):
            self.rejected('VDD1=1800', base=baseline)

    def test_partial_baseline_is_filled_without_changing_it(self):
        baseline = {'Freq': 3733}
        p, preview = profile_from_cfg('VDD1=1800', current_profile(), baseline)
        self.assertEqual(baseline, {'Freq': 3733})
        effective = read_editor_cfg(preview['cfgText'])
        self.assertEqual(effective['FREQ'], 3733)
        self.assertEqual(effective['VDD1'], 1800)
        self.assertEqual(p['cfgOverrides']['AgingTime'], _DEFAULTS['AgingTime'])


if __name__ == '__main__':
    unittest.main()
