"""Pure product preflight. Legacy cfg parsing remains compatible; GUI plans fail closed."""
import copy
import hashlib
from collections import Counter
from decimal import Decimal, InvalidOperation

from .cfg import (
    _BADBLOCK_PARAM_NAMES, _FREQ_PARAM_NAMES, _FREQ_VALID, _LOGLEVEL_PARAM_NAMES,
    _MR_NAME_RE, _P2_BIT_BY_NAME, _TIMING_KEYS, _TIMING_RAW_MAX,
    _TIMING_UNSUPPORTED, _TRFC_FAMILY, _VDD_PARAM_KEYS, _VDD_RANGE,
    cfg_from_profile, cfg_text, parse_cfg, stages_from_map,
    BOARD_CONFIG_RANGES,
)
from .testplan import MODES, ALL_ALGORITHMS, BAD_AREA_ALGORITHMS, ordered_algorithms
from .protocol import HsgCodec, StartTest
from .timing_catalog import BY_KEY, LEGACY_KEYS, wire_value
from . import timing_ns


class ProfileError(ValueError):
    def __init__(self, preview):
        self.preview = preview
        super().__init__("Product configuration is invalid")


def issue(code, field, zh, en):
    return {"code": code, "field": field, "messageZh": zh, "messageEn": en}


def selected_algorithms(profile):
    """One canonical set; legacy category rows are unioned to preserve previous execution."""
    pl2 = profile.get("pl2") or {}
    explicit = pl2.get("selectedAlgorithms")
    if "selectedAlgorithms" in pl2:
        if not isinstance(explicit, list) or any(not isinstance(n, str) for n in explicit):
            raise ValueError("selectedAlgorithms must be a list of names")
        return sorted(set(n.strip() for n in explicit))
    patterns = pl2.get("patterns") or {}
    groups = [patterns] if isinstance(patterns, list) else patterns.values()
    names = set()
    for rows in groups:
        for row in rows or []:
            if isinstance(row, dict) and row.get("checked") is True:
                name = str(row.get("name", "")).strip()
                if name.startswith("test_ty_"):
                    name = "test_ac_" + name[len("test_ty_"):]
                names.add(name)
    return sorted(names)


def _number(value):
    try:
        n = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("not a number") from None
    if not n.is_finite():
        raise ValueError("not finite")
    return n


def compile_profile(profile, base, *, quick=False):
    """Return structured validation + exact effective cfg, without persistence or device IO."""
    errors, warnings = [], []
    preview = {"valid": False, "errors": errors, "warnings": warnings,
               "algorithms": [], "effectiveParameters": [], "stages": [],
               "cfgText": "", "cfgSha256": "", "mask": None, "testCount": 0}
    if not isinstance(profile, dict):
        errors.append(issue("structure", "profile", "产品档案必须是对象", "Product profile must be an object"))
        return preview
    p = copy.deepcopy(profile)
    board = p.get('cfgOverrides', {})
    if not isinstance(board, dict):
        errors.append(issue('structure', 'cfgOverrides', '测试板基础配置必须是对象', 'Board configuration must be an object'))
        return preview
    for key, value in board.items():
        bounds = BOARD_CONFIG_RANGES.get(key)
        if bounds is None or type(value) is not int or not bounds[0] <= value <= bounds[1]:
            errors.append(issue('board_parameter', key, '测试板参数不支持或超出合法范围', 'Unsupported board parameter or value outside the supported range'))
    p.pop("timingContext", None)
    ns_profile = p.get('timingSchema') == 2
    preview['timing'] = []
    preview['rejectedParameters'] = []
    screening = p.get("pl2", {}).get("screeningVersion") if isinstance(p.get("pl2"), dict) else None
    if screening is not None and (type(screening) is not int or screening != 1):
        errors.append(issue("screening_version", "pl2", "不支持的测试方案版本", "Unsupported screening version"))
    if screening == 1:
        p["pl1Enabled"] = p["pl2Enabled"] = True
        if p["pl2"].get("testMode") not in MODES:
            errors.append(issue("test_mode", "pl2.testMode", "请选择有效测试模式", "Select a valid screening mode"))
    if not isinstance(p.get("name"), str) or not p["name"].strip():
        errors.append(issue("name", "name", "请填写产品名称", "A product name is required"))
    for key in ("rankEnabled", "pl1Enabled", "pl2Enabled"):
        if type(p.get(key)) is not bool:
            errors.append(issue("structure", key, "启用字段必须是布尔值", "Enable fields must be booleans"))
    if not isinstance(p.get("pl2", {}), dict) or not isinstance(p.get("params", []), list):
        errors.append(issue("structure", "profile", "参数表或测试项结构错误", "Invalid parameter or algorithm structure"))
        return preview
    if not isinstance(p.get("channels", {}), dict) or not isinstance(p.get("mr", {}), dict):
        errors.append(issue("structure", "profile", "通道或MR配置结构错误", "Invalid channel or MR structure"))
        return preview
    if any(not isinstance(r, dict) or not isinstance(r.get("name"), str)
           for r in p.get("params", [])):
        errors.append(issue("structure", "params", "参数行必须有有效名称", "Every parameter row must have a valid name"))
        return preview
    if p.get("rankEnabled"):
        caps = p.get("rankCapacityGb")
        try:
            if not isinstance(caps, list) or len(caps) != 2:
                raise ValueError()
            for v in caps:
                n = _number(v)
                if n < 0 or n * 8 != (n * 8).to_integral_value():
                    raise ValueError()
            if not any(p.get("channels", {}).get(c) is True for c in ("ch1", "ch2")) or not any(_number(v) > 0 for v in caps):
                raise ValueError()
        except ValueError:
            errors.append(issue("topology", "rankCapacityGb", "请配置有效通道和容量（GB）", "Configure enabled channels and valid capacities in GB"))
    if ns_profile:
        if any(type(r.get('checked')) is not bool for r in p['params']):
            errors.append(issue('structure','params','参数勾选必须是布尔值','Parameter selection must be a boolean'))
            return preview
        c = timing_ns.context(p)
        rate = int(base.get('Freq',4266))
        for r in p.get('params',[]):
            if isinstance(r,dict) and r.get('checked') and str(r.get('name','')).upper() in _FREQ_PARAM_NAMES:
                try: rate=int(r.get('value'))
                except (ValueError,TypeError): pass
        preview['requiresDeviceValidation'] = True
        # Preview uses the requested CK/DIV8, never claims this is a device readback.
        accepted=[]
        counts=Counter(r['name'].strip() for r in p['params'] if r.get('checked'))
        for r in p.get('params',[]):
            if not isinstance(r,dict):
                accepted.append(r); continue
            name=str(r.get('name','')).strip()
            is_regular=name in _VDD_PARAM_KEYS or name.upper() in (_FREQ_PARAM_NAMES|_LOGLEVEL_PARAM_NAMES|_BADBLOCK_PARAM_NAMES)
            if r.get('checked') and not is_regular:
                try:
                    if name not in timing_ns.BY_NS_KEY: raise ValueError('unsupported')
                    if counts[name]>1: raise ValueError('duplicate')
                    result=timing_ns.quantize(name,r.get('value'),rate//2,True,c)
                    preview['timing'].append(result)
                except (ValueError,KeyError) as exc:
                    rejected=issue(str(exc),name,'该时序项未应用；其他合法项可生效','Timing item rejected; independent valid items may apply')
                    preview['rejectedParameters'].append(rejected)
                    warnings.append(rejected)
                    continue
            accepted.append(r)
        requested={r['name'].strip() for r in p['params'] if r.get('checked')}
        rejected_groups=timing_ns.group_rejections(preview['timing'],requested)
        for name in rejected_groups:
            rejected=issue('dependency',name,'关联时序组未满足约束，本组未应用','Dependent timing group rejected')
            preview['rejectedParameters'].append(rejected); warnings.append(rejected)
        p['params']=[r for r in accepted if r['name'].strip() not in rejected_groups]
        preview['timing']=[r for r in preview['timing'] if r['name'] not in rejected_groups]
        preview['configurationStatus']='partial' if preview['rejectedParameters'] else 'complete'
    register_profile = p.get("timingSchema") in (1,2)
    if "timingSchema" in p and (type(p["timingSchema"]) is not int or p["timingSchema"] not in (1,2)):
        errors.append(issue("timing_schema", "timingSchema", "不支持的时序配置版本", "Unsupported timing configuration version"))
    if p.get("timingReviewRequired"):
        errors.append(issue("timing_review", "params", "旧时序参数需重新填写并确认", "Re-enter and confirm the previous timing parameters"))
    if register_profile and "timingUnit" in p:
        errors.append(issue("unit", "timingUnit", "新版时序按各项固定单位填写，请移除旧单位设置", "Timing units are fixed per field; remove the legacy unit setting"))
    mode = p.get("timingUnit", 0) if p.get("pl1Enabled") and not register_profile else 0
    if not register_profile and (type(mode) is not int or mode not in (0, 2)):
        errors.append(issue("unit", "timingUnit", "时序单位仅支持增量ns或MCK半周期原始值", "Only delta ns and raw half-MCK timing units are supported"))
    if not register_profile and p.get('pl1Enabled'):
        kept=[]
        for r in p['params']:
            if r.get('checked') and (r['name'].strip() in _TIMING_KEYS or r['name'].strip() in _TIMING_UNSUPPORTED):
                rejected=issue('unsupported',r['name'],'旧裸时序键未应用，请按ns参数重新填写','Legacy timing key not applied; re-enter using ns parameters')
                preview['rejectedParameters'].append(rejected); warnings.append(rejected)
            else: kept.append(r)
        p['params']=kept
        if 'timingUnit' in p:
            warnings.append(issue('unsupported','timingUnit','旧单位字段未应用','Legacy unit field not applied'))
            p.pop('timingUnit')
        if preview['rejectedParameters']: preview['configurationStatus']='partial'
    seen = set()
    if p.get("pl1Enabled"):
        for row in p.get("params", []):
            if not isinstance(row, dict):
                errors.append(issue("structure", "params", "参数行结构错误", "Invalid parameter row"))
                continue
            if type(row.get("checked")) is not bool:
                errors.append(issue("structure", str(row.get("name", "")), "参数勾选必须是布尔值", "Parameter selection must be a boolean"))
                continue
            if row.get("checked") is not True:
                continue
            name, value = str(row.get("name", "")).strip(), str(row.get("value", "")).strip()
            if name in seen:
                errors.append(issue("duplicate", name, "参数重复", "Duplicate parameter"))
            seen.add(name)
            if register_profile and name in BY_KEY:
                try:
                    timing_ns.ns100(value) if ns_profile else wire_value(BY_KEY[name], value)
                except ValueError as exc:
                    errors.append(issue(str(exc), name, "请输入表中范围内的有效数值，并核对该项单位", "Enter a valid value within the displayed range and check the field unit"))
                continue
            if register_profile and name in LEGACY_KEYS:
                errors.append(issue("unsupported", name, "此旧时序键已替换，请使用当前参数表", "This legacy timing key was replaced; use the current parameter table"))
                continue
            if name in _TIMING_UNSUPPORTED or name == "锁定测试容量(MB)":
                errors.append(issue("unsupported", name, "当前平台未支持此参数", "This parameter is not supported by the current platform"))
                continue
            key = _VDD_PARAM_KEYS.get(name) or _TIMING_KEYS.get(name)
            up = name.upper()
            if not key and up not in (_FREQ_PARAM_NAMES | _LOGLEVEL_PARAM_NAMES | _BADBLOCK_PARAM_NAMES):
                errors.append(issue("unknown_parameter", name, "未知参数，不能保证生效", "Unknown parameter; effective application cannot be verified"))
                continue
            try:
                n = _number(value)
                integer = key in _VDD_RANGE or up in (_FREQ_PARAM_NAMES | _LOGLEVEL_PARAM_NAMES | _BADBLOCK_PARAM_NAMES) or (name in _TIMING_KEYS and key not in _TRFC_FAMILY and mode == 2)
                if integer and n != n.to_integral_value():
                    raise ValueError()
            except ValueError:
                errors.append(issue("number", name, "请输入有效数值；整数参数不接受小数", "Enter a finite number; integer parameters do not accept fractions"))
                continue
            good = True
            if key in _VDD_RANGE:
                lo, hi = _VDD_RANGE[key]
                good = lo <= n <= hi or key == 'VDD2L' and n == 0
            elif up in _FREQ_PARAM_NAMES:
                good = int(n) in _FREQ_VALID
            elif up in _LOGLEVEL_PARAM_NAMES:
                good = 0 <= n <= 2
            elif up in _BADBLOCK_PARAM_NAMES:
                good = 0 <= n <= 1
            elif key in _TRFC_FAMILY:
                good = 60 <= n <= 400
            elif mode == 2:
                good = key in _TIMING_RAW_MAX and 1 <= n <= _TIMING_RAW_MAX[key] * 2
            else:
                good = -10 <= n <= 10
            if not good:
                errors.append(issue("range", name, "数值超出支持范围，请核对单位", "Value is outside the supported range; check the unit"))
    names = []
    try:
        names = selected_algorithms(p)
    except (ValueError, TypeError, AttributeError):
        errors.append(issue("structure", "pl2", "测试项结构错误", "Invalid algorithm selection"))
    if screening == 1 and p["pl2"].get("testMode") == "完整筛查":
        if any(n not in _P2_BIT_BY_NAME for n in names):
            errors.append(issue("unknown_algorithm", "pl2", "测试项未登记", "Unregistered algorithm"))
        names = list(ALL_ALGORITHMS)
    if screening == 1 and p["pl2"].get("testMode") == "坏区管理":
        if any(n not in BAD_AREA_ALGORITHMS for n in names):
            errors.append(issue("address_algorithm", "pl2", "坏区管理仅支持可继续扫描并记录期望值地址的测试项", "Bad-area mode requires address-recording expected-value scans"))
    if p.get("pl2Enabled") and not quick:
        for name in names:
            if name not in _P2_BIT_BY_NAME:
                errors.append(issue("unknown_algorithm", name, "测试项未在当前固件目录中登记", "Algorithm is not in the current firmware catalogue"))
        if not names:
            errors.append(issue("empty_selection", "pl2", "请选择至少一个测试项", "Select at least one algorithm"))
    if p.get("pl2Enabled") and not quick and not errors:
        try:
            names = ordered_algorithms(p["pl2"], names)
        except ValueError:
            errors.append(issue("execution_order", "pl2.executionOrder", "执行顺序须为1至9999的整数，已选项不能重复", "Order must be an integer from 1 to 9999, unique among selected items"))
    for channel, rows in p.get("mr", {}).items():
        if not isinstance(rows, list):
            errors.append(issue("structure", channel, "MR参数必须是列表", "MR parameters must be a list"))
            continue
        for row in rows:
            if not isinstance(row, dict):
                errors.append(issue("structure", channel, "MR行结构错误", "Invalid MR row"))
                continue
            value = str(row.get("value", "")).strip()
            if not value:
                continue
            try:
                if not _MR_NAME_RE.match(str(row.get("name", ""))) or not 0 <= int(value, 0) <= 255:
                    raise ValueError()
            except ValueError:
                errors.append(issue("mr", str(row.get("name", "")), "MR名称或8位期望值非法", "Invalid MR name or 8-bit expected value"))
    if errors:
        return preview
    # Canonical list is authoritative, including an explicit empty list.
    p.setdefault("pl2", {})["patterns"] = {"selected": [{"name": n, "checked": True} for n in names]}
    if quick:
        p["pl2Enabled"] = False
    d, compiler_warnings = cfg_from_profile(p, dict(base))
    d["MemTester"] = 1 if p.get("pl2Enabled") else 0
    if d["MemTester"] and not quick:
        d["P2Order"] = ":".join(str(b) for n in names for b in _P2_BIT_BY_NAME[n])
    if screening == 1:
        d["BadBlockMgmt"] = int(p["pl2"].get("testMode") == "坏区管理")
    if quick:
        d.update(AgingTime=0, MemTester=0, DvfsTest=0, PatternTest=1)
    for message in compiler_warnings:
        warnings.append(issue("compiler", "", message, message))
    text = cfg_text(d)
    payload = text.encode("utf-8")
    if len(payload) > 1017:
        errors.append(issue("frame_size", "profile", "配置超过设备1017字节载荷限制，请减少参数", "Configuration exceeds the device's 1017-byte payload limit"))
        return preview
    frame = HsgCodec().encode(StartTest(text))
    mask = sum(1 << bit for bit in set(b for n in names if n in _P2_BIT_BY_NAME for b in _P2_BIT_BY_NAME[n])) if d.get("MemTester") else None
    preview.update(valid=True, cfgText=text, cfgSha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                   mask=f"0x{mask:X}" if mask is not None else None,
                   algorithms=names if d.get("MemTester") else [],
                   mcuMessage={"command": "0x15", "payloadBytes": len(payload), "frameHex": frame.hex(" ").upper()},
                   testCount=mask.bit_count() + 1 if mask else 0,
                   stages=stages_from_map(parse_cfg(text)))
    for label, key, unit in (("VDD1", "VDD1", "mV"), ("VDD2H", "VDD2", "mV"),
                             ("VDD2L", "VDD2L", "mV"), ("VDDQ", "VDDQ", "mV"),
                             ("Frequency", "Freq", "MT/s"), ("AgingTime", "AgingTime", "min")):
        overridden = any(r.get("checked") is True and (_VDD_PARAM_KEYS.get(r.get("name")) == key or (key == "Freq" and str(r.get("name", "")).upper() in _FREQ_PARAM_NAMES)) for r in p.get("params", [])) and p.get("pl1Enabled")
        preview["effectiveParameters"].append({"name": label, "value": d.get(key), "unit": unit, "source": "override" if overridden else "baseline"})
    for row in p.get("params", []):
        if ns_profile and row.get('checked') and row.get('name','').strip() in timing_ns.BY_NS_KEY:
            preview['effectiveParameters'].append({'name':row['name'].strip(),'value':float(row['value']),'unit':'ns','source':'request'})
            continue
        if register_profile and row.get("checked") and row.get("name", "").strip() in BY_KEY:
            field = BY_KEY[row["name"].strip()]
            preview["effectiveParameters"].append({"name": field["key"], "value": wire_value(field, row.get("value", "")) / field["scale"],
                                                  "unit": field["unit"], "source": "override"})
            continue
        key = _TIMING_KEYS.get(row.get("name"))
        if key and key in d:
            raw = mode == 2 and key not in _TRFC_FAMILY
            preview["effectiveParameters"].append({"name": key, "value": d[key] if raw else d[key] / 100,
                                                  "unit": "half-MCK" if raw else ("ns" if key in _TRFC_FAMILY else "delta ns"),
                                                  "source": "override"})
    return preview


def require_profile(profile, base, *, quick=False):
    preview = compile_profile(profile, base, quick=quick)
    if not preview["valid"]:
        raise ProfileError(preview)
    return preview
