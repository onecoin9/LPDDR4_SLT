import copy
import unittest
from app import timing_ns as ns
from app.cfg import _DEFAULTS
from app.profileplan import compile_profile
from app.timing_catalog import firmware_error
from app.timing_reports import TimingReports, fingerprint
from tests.test_profileplan import valid_profile


class NsTimingTests(unittest.TestCase):
    def test_standard_limits_are_conditional_and_missing_upper_is_not_invented(self):
        c=dict(densityPerChannelGb=16,ioWidth=16,ratedRate=4266,refreshPercent=100,derated=False)
        self.assertEqual(ns.limits('TRCD',1600,c)[:3],(1800,4,None))
        self.assertEqual(ns.limits('TRAS',1600,c)[2],3513600)
        self.assertEqual(ns.limits('TRFC',1600,c)[0],38000)
        c['densityPerChannelGb']=2
        self.assertEqual(ns.limits('TRFC',1600,c)[0],13000)
        self.assertEqual(ns.limits('TPBR2PBR',1600,c)[0],6000)
        c.update(ioWidth=8,derated=True)
        self.assertEqual(ns.limits('TWR',1600,c)[0],2000)
        self.assertEqual(ns.limits('TRRD',1600,c)[0],938)
        self.assertIsNone(ns.limits('REFCNT',1600,c)[0])

    def test_nearest_rounding_stays_inside_minimum_and_ties_go_longer(self):
        c=dict(densityPerChannelGb=16,ioWidth=16,ratedRate=4266,refreshPercent=100,derated=False)
        r=ns.quantize('TRCD','18',1600,True,c)
        self.assertEqual((r['register'],r['half'],r['actualNs']),(8,1,18.75))
        self.assertEqual(ns.quantize('TRCD','19',1000,True,c)['actualNs'],20)
        self.assertRaises(ValueError,ns.quantize,'TRCD','17.99',1600,True,c)
        self.assertRaises(ValueError,ns.quantize,'TRAS','42',1600,True,c)
        self.assertEqual(ns.quantize('TRFC','380',1600,True,c)['actualNs'],380)
        for key in ns.BY_NS_KEY:
            for div8 in (False,True):
                for ck in (800,1200,1600,2133):
                    lo,nck,hi,_=ns.limits(key,ck,c)
                    value=max((lo or 0)/100,nck*1000/ck)
                    value=str(round(value+0.01,2))
                    try: r=ns.quantize(key,value,ck,div8,c)
                    except ValueError: continue
                    # Actual fixed-point report may differ by <0.005ns from the exact rational.
                    self.assertGreaterEqual(r['actualNs']+0.005,r['minNs'] or 0)
                    if r['maxNs'] is not None: self.assertLessEqual(r['actualNs']-0.005,r['maxNs'])

    def test_partial_application_keeps_valid_rows_and_reports_rejections(self):
        rows=[dict(name=k,value=v,checked=True) for k,v in
              [('TRCD','18'),('TRAS','42'),('Unknown','10')]]
        p=valid_profile(timingSchema=2,params=rows)
        before=copy.deepcopy(p)
        result=compile_profile(p,dict(_DEFAULTS))
        self.assertTrue(result['valid'],result['errors'])
        self.assertEqual(result['configurationStatus'],'partial')
        self.assertEqual(len(result['rejectedParameters']),2)
        self.assertIn('TimingRegV=3\n',result['cfgText'])
        self.assertIn('TReg=A;0:1800\n',result['cfgText'])
        self.assertEqual(p,before)
        self.assertIsNotNone(firmware_error(result['cfgText'],'T1:abcdef0 1234'))
        self.assertIsNotNone(firmware_error(result['cfgText'],'T2:abcdef0 1234'))
        self.assertIsNone(firmware_error(result['cfgText'],'T3:abcdef0 1234'))

    def test_retired_context_is_ignored_but_malformed_values_still_fail(self):
        for c in (dict(ioWidth=32),dict(refreshPercent=0),dict(densityPerChannelGb=0)):
            result=compile_profile(valid_profile(timingSchema=2,timingContext=c),dict(_DEFAULTS))
            self.assertTrue(result['valid'],result['errors'])
            self.assertNotIn('timing_context',[e['code'] for e in result['errors']])
        result=compile_profile(valid_profile(timingSchema=2,params=None),dict(_DEFAULTS))
        self.assertFalse(result['valid'])
        for value in ('NaN','Infinity','-1','1e999999','18.001'):
            self.assertRaises(ValueError,ns.ns100,value)

    def test_baseline_frequency_and_dependency_groups_match_preview(self):
        p=valid_profile(timingSchema=2,params=[dict(name='TRCD',value='18',checked=True)])
        self.assertEqual(ns.table(p,3200)['ckMHz'],1600)
        p['params'] += [dict(name=k,value=v,checked=True) for k,v in [('TRFC','400'),('TXREFCNT','387.5')]]
        result=compile_profile(p,dict(_DEFAULTS))
        self.assertTrue(result['valid'])
        self.assertEqual({r['field'] for r in result['rejectedParameters']},{'TRFC','TXREFCNT'})
        self.assertNotIn('26:40000',result['cfgText'])
        self.assertIn('0:1800',result['cfgText'])

    def test_real_cfg_fields_survive_and_old_conditions_do_not_control_wire(self):
        p=valid_profile(timingSchema=2,rankEnabled=True,rankCapacityGb=[1,0],
            channels={'ch1':True,'ch2':False},
            timingContext={'ratedRate':1600,'densityPerChannelGb':16,'ioWidth':8,'refreshPercent':0,'derated':True},
            params=[dict(name=k,value=v,checked=True) for k,v in
                [('测试频率(M)','3200'),('VDD1(mV)','1800'),('VDD2H(mV)','1125'),('VDDQ(mV)','600'),('TRCD','18')]])
        result=compile_profile(p,dict(_DEFAULTS))
        self.assertTrue(result['valid'],result['errors'])
        text=result['cfgText']
        for line in ('Freq=3200','VDD1=1800','VDD2=1125','VDDQ=600',
                     'ChannelA_Rank0_Size=8','ChannelA_Rank1_Enable=0','ChannelB_Rank0_Enable=0','TReg=A;0:1800'):
            self.assertIn(line+'\n',text)
        for key in ('densityPerChannelGb','ioWidth','ratedRate','refreshPercent','derated'):
            self.assertNotIn(key,text)
        preview=ns.table(p,3200)
        self.assertEqual(preview['contextSource'],'device_mr')
        self.assertTrue(preview['requiresDeviceValidation'])
        rfc=next(r for r in preview['rows'] if r['name']=='TRFC')
        self.assertIsNone(rfc['minNs'])
        self.assertTrue(rfc['limitPending'])

    def test_device_limits_are_scoped_to_dut_request_and_clock(self):
        reports=TimingReports(); tag='12345678'
        reports.ingest(1,5,f'[TNS-LIMIT] tag={tag} id=0 CK=1600 min=1988 max=0')
        reports.ingest(1,6,f'[TNS] tag={tag} id=0 CK=1600 DIV=8 ch=0 req=2000 actual=2000 reg=8 half=0 ok=1')
        self.assertNotIn('limitsKnown',reports.snapshot(tag)[0])
        reports.ingest(1,5,f'[TNS] tag={tag} id=0 CK=1600 DIV=8 ch=0 req=2000 actual=2000 reg=8 half=0 ok=1')
        actual=reports.snapshot(tag)[-1]
        self.assertTrue(actual['limitsKnown'])
        self.assertEqual(actual['minNs'],19.88)
        self.assertIsNone(actual['maxNs'])

    def test_ready_t3_is_ascii_and_old_settings_drop_only_retired_conditions(self):
        from app.protocol import HsgCodec, build_frame, ROLE_SLAVE, CMD_READY
        from app.settingsstore import SettingsDocument
        frame=build_frame(ROLE_SLAVE,CMD_READY,b'T3:abcdef0 1234\0')
        self.assertEqual(HsgCodec().decode(frame).version,'T3:abcdef0 1234')
        p=valid_profile(timingSchema=2,timingContext={'ioWidth':8},rankCapacityGb=[1,0])
        before=copy.deepcopy(p)
        document=SettingsDocument(products={p['name']:p})
        saved=document.model_dump()['products'][p['name']]
        self.assertNotIn('timingContext',saved)
        self.assertEqual(saved['rankCapacityGb'],[1,0])
        self.assertEqual(p,before)

    def test_rejection_then_limit_still_shows_real_device_range(self):
        reports=TimingReports();tag='12345678'
        reports.ingest(1,5,f'[TNS-REJECT] tag={tag} id=0 CK=1600 reason=range_or_no_tick')
        reports.ingest(1,5,f'[TNS-LIMIT] tag={tag} id=0 CK=1600 min=1988 max=0')
        rejected=reports.snapshot(tag)[0]
        self.assertEqual(rejected['reason'],'range_or_no_tick')
        self.assertTrue(rejected['limitsKnown'])
        self.assertEqual(rejected['minNs'],19.88)

    def test_readback_is_separate_from_calculation_and_scoped_by_request(self):
        reports=TimingReports()
        tag=fingerprint('TimingRegV=2\n')
        self.assertEqual(reports.snapshot(tag),[])
        reports.ingest(1,5,f'CH05 [TNS] tag={tag} id=0 CK=1600 DIV=8 ch=1 req=1800 actual=1875 reg=8 half=1 ok=1')
        record=reports.snapshot(tag)[0]
        self.assertEqual((record['slot'],record['actualNs'],record['verified']),(5,18.75,True))
        self.assertEqual(reports.snapshot('12345678'),[])
        reports.ingest(1,5,f'[TNS] tag={tag} id=0 CK=1600 DIV=8 ch=0 req=1800 actual=1875 ')
        reports.ingest(1,5,'reg=8 half=1 ok=0')
        self.assertFalse(reports.snapshot(tag)[-1]['verified'])
