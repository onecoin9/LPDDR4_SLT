"""Bounded readback cache. A calculated preview never enters this cache."""
import re
import time
from collections import OrderedDict
from .timing_ns import CATALOG_NS

FIELDS={r['id']:r['key'] for r in CATALOG_NS}
REPORT=re.compile(r'\[TNS\] tag=([0-9a-fA-F]{8}) id=(\d+) CK=(\d+) DIV=(4|8) ch=(\d+) req=(\d+) actual=(\d+) reg=(\d+) half=([01]) ok=([01])(?:\s|$)')
REJECT=re.compile(r'\[TNS-REJECT\] tag=([0-9a-fA-F]{8}) id=(\d+)(?: CK=(\d+))? reason=(\w+)')

LIMIT=re.compile(r'\[TNS-LIMIT\] tag=([0-9a-fA-F]{8}) id=(\d+) CK=(\d+) min=(\d+) max=(\d+)(?:\s|$)')


def fingerprint(text):
    tag=2166136261
    for byte in text.encode('utf-8'):
        tag=((tag^byte)*16777619)&0xffffffff
    return f'{tag:08x}'


def for_run(hub,cfg,site,slot,started):
    cache=getattr(hub,'timing_reports',None)
    if cache is None: return []
    return [r for r in cache.snapshot(fingerprint(cfg)) if r['site']==site and r['slot']==slot and r['receivedAt']>=started]


class TimingReports:
    def __init__(self):
        self.rows=OrderedDict()
        self.pending={}
        self.limits=OrderedDict()

    def ingest(self,site,slot,line):
        if site is None or slot is None: return
        bound=LIMIT.search(line)
        if bound:
            tag,field,ck,lo,hi=bound.groups()
            field,ck,lo,hi=map(int,(field,ck,lo,hi))
            if field not in FIELDS or not 1<=ck<=10000 or max(lo,hi)>100000000: return
            key=(tag.lower(),site,slot,field,ck)
            bound=dict(minNs=lo/100 if lo else None,maxNs=hi/100 if hi else None,limitsKnown=True)
            self.limits[key]=bound
            keys=[(tag.lower(),site,slot,ch,ck,field) for ch in range(4)]
            keys.append((tag.lower(),site,slot,'rejected',field))
            for row_key in keys:
                record=self.rows.get(row_key)
                if record is not None and record['ckMHz']==ck: record.update(bound)
            while len(self.limits)>8192: self.limits.popitem(last=False)
            return
        rejection=REJECT.search(line)
        if rejection:
            tag,field,ck,reason=rejection.groups(); field=int(field)
            if field in FIELDS:
                key=(tag.lower(),site,slot,'rejected',field)
                # Retain ordering: a later rejection must supersede older success.
                self.rows.pop(key,None)
                self.rows[key]=dict(tag=tag.lower(),site=site,slot=slot,name=FIELDS[field],
                    channel=None,ckMHz=int(ck or 0),div=None,requestNs=None,actualNs=None,
                    verified=False,reason=reason,receivedAt=time.time())
                while len(self.rows)>8192: self.rows.popitem(last=False)
            return
        address=(site,slot)
        if '[TNS]' in line:
            text=line[line.index('[TNS]'):]
        elif address in self.pending:
            text=self.pending.pop(address)+re.sub(r'^CH\d+\s*','',line)
        else: return
        match=REPORT.search(text)
        if not match:
            if len(text)<1024:
                if len(self.pending)>=1200: self.pending.pop(next(iter(self.pending)))
                self.pending[address]=text
            return
        self.pending.pop(address,None)
        tag=match[1].lower()
        field,ck,div,ch,request,actual,reg,half,ok=map(int,match.groups()[1:])
        if field not in FIELDS or not 1<=ck<=10000 or ch>3: return
        key=(tag,site,slot,ch,ck,div,field)
        self.rows.pop(key,None)
        self.rows[key]=dict(tag=tag,site=site,slot=slot,channel=ch,name=FIELDS[field],
                           ckMHz=ck,div=div,requestNs=request/100,actualNs=actual/100 if ok else None,
                           register=reg,half=half,verified=bool(ok),receivedAt=time.time())
        self.rows[key].update(self.limits.get((tag,site,slot,field,ck),{}))
        while len(self.rows)>8192: self.rows.popitem(last=False)

    def snapshot(self,tag):
        return [r for r in self.rows.values() if r['tag']==tag and time.time()-r['receivedAt']<=3600]
