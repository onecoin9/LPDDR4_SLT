import asyncio
import json
import unittest
from urllib.request import urlopen
from app.timing_reports import fingerprint
from tests import test_profile_api as fixtures
from tests.test_profileplan import valid_profile


class NsApiTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.ProductApiTests.asyncSetUp
    asyncTearDown=fixtures.ProductApiTests.asyncTearDown

    async def test_preview_and_readback_have_distinct_provenance(self):
        p=valid_profile(timingSchema=2,params=[dict(name='测试频率(M)',checked=True,value='3200'),dict(name='TRCD',checked=True,value='18')])
        preview=await self.client.post('/api/timing/preview',json=p)
        self.assertEqual(preview.status_code,200)
        result=preview.json()
        row=next(r for r in result['rows'] if r['name']=='TRCD')
        self.assertEqual((row['minNs'],row['actualNs'],row['verified']),(18,18.75,False))
        plan=await self.client.post('/api/products/preview',json=p)
        self.assertEqual(result['tag'],fingerprint(plan.json()['cfgText']))
        self.assertEqual(self.main.hub.timing_reports.snapshot(result['tag']),[])
        self.main.hub.log(1,5,'INFO',f"[TNS] tag={result['tag']} id=0 CK=1600 DIV=8 ch=1 req=1800 actual=1875 reg=8 half=1 ok=1")
        def get():
            with urlopen(self.client.base+'/api/timing/readback?tag='+result['tag'],timeout=3) as response:
                return json.loads(response.read())
        actual=await asyncio.to_thread(get)
        self.assertTrue(actual['rows'][0]['verified'])
        self.assertEqual(actual['rows'][0]['slot'],5)

    async def test_retired_context_cannot_invent_device_limits(self):
        response=await self.client.post('/api/timing/preview',json=valid_profile(timingSchema=2,timingContext={'ioWidth':32}))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['contextSource'],'device_mr')
        row=next(r for r in response.json()['rows'] if r['name']=='TRFC')
        self.assertIsNone(row['minNs'])
        self.assertTrue(row['limitPending'])
