"""JESD209-4E constraints and bounded quantization, in 0.01 ns fixed point.

MTK-private counters use an explicitly labelled MCK-equivalent estimate. Such
an estimate is not evidence of a physical command interval or JEDEC compliance.
The published v1 field IDs and raw units are never reinterpreted as ns.
"""
from decimal import Decimal, InvalidOperation
from .timing_catalog import CATALOG

SCHEMA = 2
CONTEXT = dict(densityPerChannelGb=None, ioWidth=None, ratedRate=None,
               refreshPercent=None, derated=None)
WIRE_VERSION = 3
SOURCE = "JESD209-4E: Tables 88/89, 118/119, 174, 219"
# kind: generic estimate, refresh with vendor compensation, self-refresh exit.
CATALOG_NS = [dict(r, unit="ns", scale=100,
                   halfId=(r['id']+1 if r['id']+1 < len(CATALOG) and
                           CATALOG[r['id']+1]['key'] == r['key']+'_05T' else -1),
                   model='vendor' if r['key'] in ('TRFC','TRFCPB','TXREFCNT') else 'estimate')
              for r in CATALOG if r['unit'] != 'flag']
BY_NS_KEY = {r['key']: r for r in CATALOG_NS}
BY_NS_KEY['TXREFCNT'].update(purposeZh='退出自刷新等待时间；按平台补偿公式转换',
    purposeEn='Self-refresh exit wait time, encoded with platform compensation')


def context(profile):
    """No customer-entered DRAM identity: actual constraints arrive from device MRR.

    Rank capacity is intentionally not substituted for per-die/channel density.
    A requested operating rate does not establish the device speed grade.
    Retired timingContext data is ignored, including on imported old profiles.
    """
    return dict(CONTEXT)


def ns100(value):
    try:
        if len(str(value))>128: raise ValueError('number')
        n = Decimal(str(value).strip())
        if not n.is_finite() or n < 0 or n > 1000000:
            raise ValueError('number')
        if 0<n<Decimal('0.01'): raise ValueError('precision')
        if n * 100 != (n * 100).to_integral_value():
            raise ValueError('precision')
        return int(n * 100)
    except (InvalidOperation, TypeError):
        raise ValueError('number') from None


def limits(key, mhz, c):
    """Return min ns100, min CK count, max ns100, and source.

    None denotes an unspecified or device-dependent bound; never a guessed register limit.
    Density is per channel (Tables 118/119), not package capacity.
    """
    d = c['densityPerChannelGb']
    rfc = None if d is None else 130 if d <= 2 else 180 if d <= 4 else 280 if d <= 8 else 380
    pb = None if d is None else 60 if d <= 2 else 90 if d <= 4 else 140 if d <= 8 else 190
    fast = c['ratedRate'] == 4266  # Table 88 note 2: device speed grade, not current CK.
    core = {'TRCD': (1800,4), 'TRP': (1800,4), 'TRPAB': (2100,4),
            'TRAS': (4200,3), 'TWR': (2000 if c['ioWidth']==8 else 1800,6),
            'TWTR': (1200 if c['ioWidth']==8 else 1000,8),
            'TRRD': (750 if fast else 1000,4), 'TFAW': (3000 if fast else 4000,0),
            'TRTP': (750,8), 'TXP': (750,5), 'TRFC': (None if rfc is None else rfc*100,0),
            'TRFCPB': (None if pb is None else pb*100,0), 'TPBR2PBR': (None if d is None else 6000 if d<=2 else 9000,0),
            'TXREFCNT': (None if rfc is None else rfc*100+750,2),
            'CKEPRD': (750,4), 'CMDCKE': (175,3), 'CKELCKCNT': (500,5)}
    # Other register names are not JEDEC symbols (e.g. TZQCS != tZQCAL).
    lo, ck = core.get(key, (None,0))
    if c['derated'] and key in ('TRCD','TRP','TRPAB','TRAS','TRRD'):
        lo += 188  # 1.875ns rounded outward to fixed-point 0.01ns.
    if key == 'TRC':
        # Conservative all-bank path; use requested group values when selected below.
        lo = 6300 + (375 if c['derated'] else 0)
        ck = 7
    hi = min(9*390400*c['refreshPercent']//100, 7020000) if key=='TRAS' and c['refreshPercent'] is not None else None
    return lo, ck, hi, SOURCE if key in core or key=='TRC' else 'MTK internal counter; no direct JEDEC bound'


def quantize(key, value, mhz, div8, c):
    """Nearest representable time inside both JEDEC and hardware bounds.

    Enumerate the bounded register space. Ties choose the longer time; compare
    exact integer rational times before rounding the reporting value.
    """
    r = BY_NS_KEY[key]
    target = ns100(value)
    if not isinstance(mhz,int) or not 1 <= mhz <= 10000:
        raise ValueError('clock')
    lo, nck, hi, source = limits(key,mhz,c)
    lower = max((lo or 0)*mhz, nck*100000)
    upper = hi*mhz if hi is not None else None
    if target*mhz < lower or (upper is not None and target*mhz > upper):
        raise ValueError('jedec_range')
    factor = 4 if div8 else 2
    refresh = key in ('TRFC','TRFCPB')
    max_ticks2=((1 << r['width'])-1 + (11 if refresh else -4 if key=='TXREFCNT' else 0))*2
    if target*mhz > max_ticks2*factor*50000 or (refresh and target*mhz<22*factor*50000):
        raise ValueError('hardware_range')
    half_allowed = (r['halfId'] >= 0 or refresh) and div8
    best = None
    for reg in range(1 << r['width']):
        for half in range(2 if half_allowed else 1):
            ticks2 = ((reg+11)*2+half if refresh else
                      (reg-4)*2 if key=='TXREFCNT' else reg*2-half)
            if ticks2 < 0: continue
            num = ticks2*factor*50000
            if num < lower or (upper is not None and num > upper): continue
            candidate = (abs(num-target*mhz),-num,reg,half,num)
            if best is None or candidate < best: best=candidate
    if best is None: raise ValueError('no_legal_tick')
    _,_,reg,half,num = best
    return dict(name=key, id=r['id'], requestNs=target/100,
                minNs=max((lo or 0)/100,nck*1000/mhz) if lo is not None else None,
                maxNs=hi/100 if hi is not None else None,
                actualNs=(num+mhz//2)//mhz/100,
                register=reg, half=half, ckMHz=mhz, div=8 if div8 else 4,
                model=r['model'], source=source, verified=False)


def encode(profile):
    selected=[f"{BY_NS_KEY[r['name'].strip()]['id']}:{ns100(r['value'])}"
              for r in profile.get('params',[]) if r.get('checked') and r['name'].strip() in BY_NS_KEY]
    return 'A;'+','.join(selected) if selected else ''


def group_rejections(results, requested):
    by={r['name']:r for r in results}
    rejected=set()
    if 'TRFC' in requested and 'TXREFCNT' in requested:
        if 'TRFC' not in by or 'TXREFCNT' not in by or by['TXREFCNT']['actualNs'] < by['TRFC']['actualNs']+7.5:
            rejected.update(('TRFC','TXREFCNT'))
    if 'TRC' in requested:
        group={'TRC','TRAS','TRP','TRPAB'} & requested
        if any(key not in by for key in group): rejected.update(group)
        elif 'TRAS' in group and group & {'TRP','TRPAB'}:
            rp=max(by[k]['actualNs'] for k in group & {'TRP','TRPAB'})
            if by['TRC']['actualNs'] < by['TRAS']['actualNs']+rp: rejected.update(group)
    return rejected


def table(profile, default_rate=4266):
    from .cfg import _FREQ_PARAM_NAMES
    c=context(profile)
    rate=default_rate
    for r in profile.get('params',[]):
        if r.get('checked') and str(r.get('name','')).strip().upper() in _FREQ_PARAM_NAMES:
            rate=int(r['value'])
    if rate not in (1600,2400,3200,3733,4266): raise ValueError('clock')
    mhz=rate//2
    rows=[]
    inputs={r['name']:r for r in profile.get('params',[]) if isinstance(r,dict)}
    for field in CATALOG_NS:
        key=field['key']
        lo,ck,hi,source=limits(key,mhz,c)
        pending=key in ('TRFC','TRFCPB','TXREFCNT','TPBR2PBR','TRAS','TWR','TWTR','TRCD','TRP','TRPAB','TRRD','TRC')
        row=dict(name=key,limitPending=pending,minPending=pending,maxPending=key=='TRAS',minNs=max((lo or 0)/100,ck*1000/mhz) if lo is not None else None,
                 maxNs=hi/100 if hi is not None else None, source=source,model=field['model'],
                 actualNs=None, verified=False, status='inherit')
        r=inputs.get(key)
        if r and r.get('checked'):
            try: row.update(quantize(key,r['value'],mhz,True,c),status='accepted')
            except ValueError as exc: row.update(status='rejected',reason=str(exc))
        rows.append(row)
    rejected=group_rejections([r for r in rows if r['status']=='accepted'],
                              {k for k,r in inputs.items() if r.get('checked')})
    for row in rows:
        if row['name'] in rejected: row.update(status='rejected',actualNs=None,reason='dependency')
    return dict(rows=rows,contextSource='device_mr',requiresDeviceValidation=True,ckMHz=mhz,div=8)
