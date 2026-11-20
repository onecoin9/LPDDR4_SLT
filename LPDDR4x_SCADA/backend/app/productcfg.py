"""Strict, reversible CFG import into the shared product configuration.

Unlike the firmware-compatible log parser, this editor parser must never ignore
an unknown key, duplicate assignment, or a value the product model cannot express.
"""
import copy
import re
from decimal import Decimal

from .cfg import BOARD_CONFIG_RANGES, _DEFAULTS, _P2_BIT_BY_NAME, canonical_key
from .profileplan import ProfileError, issue, require_profile
from .timing_catalog import CATALOG
from .timing_ns import CATALOG_NS, WIRE_VERSION


def _fail(field, message, code='cfg_import'):
    raise ProfileError(dict(valid=False, errors=[issue(code, field, message, message)], warnings=[]))


def read_editor_cfg(text):
    if not isinstance(text, str) or not text.strip():
        _fail('cfgText', 'CFG 不能为空 / CFG must not be empty')
    try:
        size = len(text.encode('utf-8'))
    except UnicodeEncodeError:
        _fail('cfgText', 'CFG 包含无效字符 / CFG contains invalid Unicode')
    if size > 65536:
        _fail('cfgText', 'CFG 文件过大 / CFG file is too large')
    values = {}
    known = {canonical_key(k) for k in _DEFAULTS} | {'P2MASK', 'P2ORDER', 'TIMINGREGV', 'TREG'}
    for number, line in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith(('#', ';', '//')):
            continue
        if '=' not in line:
            _fail(str(number), f'第 {number} 行缺少 = / Missing assignment')
        name, value = line.split('=', 1)
        key = canonical_key(name)
        if key in values:
            _fail(name, f'第 {number} 行重复键 {name.strip()} / Duplicate key')
        if key not in known and not re.fullmatch(r'CHANNEL[AB]_MR[5-8]_2', key):
            _fail(name, f'不支持的 CFG 键 {name.strip()}，未保存 / Unsupported CFG key; nothing saved')
        # A semicolon is part of the versioned TReg grammar, not a comment.
        value = value.split('#', 1)[0].split('//', 1)[0].strip()
        if key in ('TREG', 'P2ORDER'):
            if not value:
                _fail(name, '列表不能为空 / List must not be empty')
            values[key] = value
        else:
            try:
                if not re.fullmatch(r'(?:0[xX][0-9a-fA-F]+|[+-]?[0-9]+)', value):
                    raise ValueError()
                values[key] = int(value, 16 if value.lower().startswith('0x') else 10)
            except ValueError:
                _fail(name, f'{name.strip()} 必须是整数 / An integer is required')
    if not values:
        _fail('cfgText', 'CFG 没有可用参数 / CFG has no parameters')
    return values


def _timing_values(version, encoded):
    """Parse assignments as integers; textual order and leading zeros are immaterial."""
    if version not in (1, WIRE_VERSION):
        _fail('TimingRegV', '不支持的时序协议版本 / Unsupported timing protocol version')
    catalog = CATALOG if version == 1 else CATALOG_NS
    by_id = {row['id']: row for row in catalog}
    if version == WIRE_VERSION:
        if not encoded.startswith('A;'):
            _fail('TReg', 'ns 时序列表必须以 A; 开头 / ns timing must start with A;')
        encoded = encoded[2:]
    values = {}
    for pair in encoded.split(','):
        if not re.fullmatch(r'[0-9]+:[0-9]+', pair):
            _fail('TReg', '时序列表格式无效 / Invalid timing list')
        try:
            ident, value = map(int, pair.split(':'))
        except ValueError:
            _fail('TReg', '时序整数过大 / Timing integer is too large')
        if ident not in by_id or ident in values:
            _fail('TReg', f'未知或重复的时序 ID {ident} / Unknown or duplicate timing ID')
        values[ident] = value
    return values, by_id


def profile_from_cfg(text, current, base):
    supplied = read_editor_cfg(text)
    if not isinstance(current, dict):
        _fail('profile', '产品档案必须是对象 / Product profile must be an object')
    if not isinstance(base, dict):
        _fail('baseCfg', '基础配置必须是对象 / Baseline configuration must be an object')
    # The shared baseline is a base_cfg() result: default keys with integer
    # values. Validate it before constructing rows or doing arithmetic, and
    # fill omitted factory defaults for isolated callers as base_cfg() does.
    canonical_defaults = {canonical_key(k): k for k in _DEFAULTS}
    baseline = dict(_DEFAULTS)
    for key, value in base.items():
        canonical = canonical_key(key)
        if not isinstance(key, str) or canonical not in canonical_defaults or type(value) is not int:
            _fail('baseCfg', '基础配置含不支持的键或非整数 / Invalid baseline key or value')
        baseline[canonical_defaults[canonical]] = value
    effective = {canonical_key(k): v for k, v in baseline.items()}
    effective.update(supplied)
    p = copy.deepcopy(current)
    p.update(pl1Enabled=True, rankEnabled=True,
             cfgOverrides={k: effective[canonical_key(k)] for k in BOARD_CONFIG_RANGES})
    for old in ('timingUnit', 'timingReviewRequired', 'timingMigration', 'timingContext'):
        p.pop(old, None)
    p['params'] = []

    def parameter(name, value):
        p['params'].append(dict(id=len(p['params']) + 1, name=name, value=str(value), checked=True))

    for name, key in (('VDD1(mV)', 'VDD1'), ('VDD2H(mV)', 'VDD2'),
                      ('VDD2L(mV)', 'VDD2L'), ('VDDQ(mV)', 'VDDQ'),
                      ('测试频率(M)', 'FREQ'), ('LogLevel', 'LOGLEVEL'), ('BadBlockMgmt', 'BADBLOCKMGMT')):
        parameter(name, effective[key])
    caps, channels = [None, None], {}
    for ci, letter in enumerate('AB', 1):
        enabled = []
        for rank in (0, 1):
            prefix = f'CHANNEL{letter}_RANK{rank}_'
            on, size = effective[prefix+'ENABLE'], effective[prefix+'SIZE']
            if on not in (0, 1) or size < 0 or bool(on) != (size > 0):
                _fail(prefix, 'Rank 的启用与容量不一致 / Rank enable and size disagree')
            enabled.append(bool(on))
            if on:
                if caps[rank] is not None and caps[rank] != size:
                    _fail(prefix, '产品设置目前要求两通道同一 Rank 容量一致；未保存 / Asymmetric rank sizes are not supported')
                caps[rank] = size
        channels[f'ch{ci}'] = any(enabled)
    p['rankCapacityGb'] = [float(Decimal(v or 0) / 8) for v in caps]
    p['channels'] = channels
    # A missing rank in one enabled channel cannot be represented by the shared
    # two-rank editor. Refuse instead of changing topology during the round trip.
    for ci, letter in enumerate('AB', 1):
        for rank in (0, 1):
            if effective[f'CHANNEL{letter}_RANK{rank}_ENABLE'] != int(channels[f'ch{ci}'] and bool(caps[rank])):
                _fail('channels', '产品设置暂不支持此不对称 Rank 布局，未保存 / Asymmetric rank layout is not supported')
    p['mr'] = {f'ch{i}': [dict(name=f'MR{r}_2', value=str(supplied.get(f'CHANNEL{letter}_MR{r}_2', '')))
                          for r in range(5, 9)] for i, letter in enumerate('AB', 1)}
    p['pl2Enabled'] = bool(effective['MEMTESTER'])
    if effective['MEMTESTER'] not in (0, 1):
        _fail('MemTester', 'MemTester 只能是 0 或 1 / MemTester must be 0 or 1')
    mask = supplied.get('P2MASK', (1 << 39) - 1)
    if type(mask) is not int or not 0 < mask < (1 << 39):
        _fail('P2Mask', 'P2Mask 必须包含已登记的测试位 / P2Mask must contain registered test bits')
    selected = []
    for name, bits in _P2_BIT_BY_NAME.items():
        chosen = [bool(mask & (1 << b)) for b in bits]
        if any(chosen) and not all(chosen):
            _fail('P2Mask', 'Walking Ones/Zeros 在产品设置中是组合项，必须同时选择 / Both Walking bits are required')
        if all(chosen):
            selected.append(name)
    expected = [b for b in range(39) if mask & (1 << b)]
    try:
        if 'P2ORDER' in supplied and not re.fullmatch(r'[0-9]+(?::[0-9]+)*', supplied['P2ORDER']):
            raise ValueError()
        order = [int(v) for v in supplied['P2ORDER'].split(':')] if 'P2ORDER' in supplied else expected
    except ValueError:
        _fail('P2Order', '测试顺序格式无效 / Invalid execution order')
    if sorted(order) != expected or len(set(order)) != len(order):
        _fail('P2Order', '执行顺序必须恰好覆盖 P2Mask，不能重复 / Order must match P2Mask exactly')
    execution = {}
    for name in selected:
        bits = _P2_BIT_BY_NAME[name]
        positions = [order.index(bit) for bit in bits]
        if positions != list(range(positions[0], positions[0]+len(bits))):
            _fail('P2Order', '组合算法位必须相邻且正序 / Grouped algorithm bits must be adjacent and ordered')
        execution[name] = str(positions[0] + 1)
    p['pl2'] = dict(testMode='坏区管理' if effective['BADBLOCKMGMT'] else '快速筛查',
                    ascEnabled=True, ascOrder='升序', selectedAlgorithms=selected,
                    executionOrder=execution, patterns={})
    if ('TIMINGREGV' in supplied) != ('TREG' in supplied):
        _fail('TimingRegV', 'TimingRegV 与 TReg 必须成对 / Version and TReg must occur together')
    p['timingSchema'] = 2
    if 'TREG' in supplied:
        version = supplied['TIMINGREGV']
        timings, by_id = _timing_values(version, supplied['TREG'])
        p['timingSchema'] = 1 if version == 1 else 2
        for ident, value in timings.items():
            row = by_id[ident]
            parameter(row['key'], Decimal(value) / row['scale'])
    preview = require_profile(p, baseline)
    if preview.get('rejectedParameters'):
        _fail('TReg', '部分时序被拒绝，CFG 尚未保存 / Timing items were rejected; nothing saved')
    # Compare every supplied setting, not just values shown in the main table.
    # Successful import guarantees no silent omission or reinterpretation.
    generated = read_editor_cfg(preview['cfgText'])
    for key, value in supplied.items():
        same = generated.get(key) == value
        if key == 'TREG':
            same = ('TREG' in generated and
                    _timing_values(supplied['TIMINGREGV'], generated['TREG'])[0] == timings)
        elif key == 'P2ORDER':
            same = generated.get(key) is not None and [int(v) for v in generated[key].split(':')] == order
        if not same:
            _fail(key, f'{key} 无法无损转换为产品设置，未保存 / Value cannot be imported without a change')
    return p, preview
