import { TIMING_CATALOG, TIMING_BY_KEY, TIMING_SCHEMA, LEGACY_TIMING_KEYS } from './timingCatalog'
import { TIMING_NS_CATALOG } from './timingCatalog'
export { TIMING_CATALOG, TIMING_BY_KEY } from './timingCatalog'

// 产品配置文件契约（JSON 格式 —— 比 YAML 好实现：浏览器/Node 原生支持，无需解析库）
// 后端就绪后按 <产品名>.json 落盘，字段与本类型一一对应

// 参数行：勾选 = 启用该测试项
export interface ProductParam {
  id: number
  name: string
  value: string           // 统一字符串存储（数值/枚举由后端解析）
  checked: boolean
  options?: string[]      // 枚举型参数（如测试频率）；有值时界面渲染为下拉
  start?: string          // 仅供旧档案迁移归档
  step?: string           // 仅供旧档案迁移归档
  end?: string            // 仅供旧档案迁移归档
  unsupported?: boolean   // [AC-TIM] 本平台固件无对应寄存器位域 → 灰化不可勾选
}

// MR 配置行（MR配置弹窗）：无勾选项 —— 用户填了值才校验，留空 = 不校验
export interface MrRow {
  name: string            // MR 名称（MR5_2..MR8_2，"_2"为固件协议键的固定后缀）
  value: string           // 期望值（客户按颗粒规格书配置；整寄存器低 8 位比对）
}

// MR 配置按通道分组（CH1/CH2 = 颗粒的通道配置；固件按通道比对，无 Rank 维度）
export interface MrConfig {
  ch1: MrRow[]
  ch2: MrRow[]
}

// 默认 MR 行（MR5=Vendor ID、MR8=密度位宽，均只读身份寄存器；默认空值 = 不校验）
function mrRows(): MrRow[] {
  return ['MR5_2', 'MR6_2', 'MR7_2', 'MR8_2'].map(m => ({ name: m, value: '' }))
}
function defaultMr(): MrConfig {
  return { ch1: mrRows(), ch2: mrRows() }
}

// PL2 Pattern 行（Pattern及关联参数表）：勾选 = 启用该 Pattern
export interface Pl2Pattern {
  id: number
  name: string            // Pattern 名（如 test_random_value）
  checked: boolean
  order: string           // 执行顺序
  param: string           // 参数（可空）
}

// PL2 配置（Pattern及关联参数页）
export interface Pl2Config {
  screeningVersion?: 1
  executionOrder?: Record<string, string>
  selectedAlgorithms?: string[] // 唯一执行选择；分类行只是视图，旧档案按原执行集合迁移
  testMode: string        // 当前选中的测试模式（PL2_TEST_MODES 之一）
  ascEnabled: boolean     // 升降序开关
  ascOrder: string        // 升序 / 降序
  patterns: Record<string, Pl2Pattern[]>  // 按测试模式分组的 Pattern 表（key = 测试模式名）
}

// 测试模式枚举：全映射读写测试 / Block测试 / 全空间测试（2026-08-31 用户提供的组合清单）
export const PL2_TEST_MODES = ['快速筛查', '完整筛查', '坏区管理']
export const PL2_ASC_ORDERS = ['升序', '降序']

// 一份产品配置 = 一个 JSON 文件
export interface ProductProfile {
  name: string
  cfgOverrides?: Record<string, number> // Product-owned board defaults, shared with the CFG editor.
  rankEnabled: boolean                   // Rank 启用（取消后锁定 Rank 容量）
  pl1Enabled: boolean                    // PL1 启用（取消后锁定阶段全局参数等子选项卡）
  pl2Enabled: boolean                    // PL2 启用（取消后锁定 PL2 子选项卡）
  rankCapacityGb: [number, number]     // Rank0 / Rank1 容量(GB)
  channels: { ch1: boolean; ch2: boolean }  // CHn 使能（通道个数）
  mr: MrConfig                            // MR 读回校验（按通道 CH1/CH2 分组，填值才校验）
  // [AC-TIM 2026-10-13] 时序单位模式（缺省 = 0，旧档案迁移兜底同）：
  // 0=增量ns；2=MCK 原始半周期值(reg<<1|05T 网格)；1=绝对ns 固件预留（后端按 0 处理并告警）。
  // 仅作用于直接时序项；TRFC/TRFCPB/TXRefCnt 恒为绝对 ns。
  timingUnit?: 0 | 1 | 2
  timingSchema?: 1 | 2
  timingReviewRequired?: boolean
  timingMigration?: { unit: number; params: ProductParam[] }
  params: ProductParam[]               // 测试项配置（checked=启用）
  pl2: Pl2Config                       // PL2 Pattern 配置
}

// mock 默认参数表（参照用户提供的 SLT 产品配置截图）
// 枚举选项 = 固件 Freq 白名单（三层同步：固件 platform.c 校验 ↔ cfg.py _FREQ_VALID ↔ 此处）。
// 2026-09-03 扩档 +1600/2400/3200；移除 4800（固件枚举从未支持，旧固件会静默跑 4266，
// 新固件直接 FAIL 0x04）
const PARAM_OPTIONS: Record<string, string[]> = {
  '测试频率(M)': ['1600', '2400', '3200', '3733', '4266'],
}

function defaultParams(ns = true): ProductParam[] {
  // [AC-TIM 2026-09-20] 时序行默认值一律 '0'(0=标称不动);
  // 旧默认值(TRCD=10 等)是占位符,与 ns 语义不符,归零防误发
  const rows: Array<[string, string, boolean]> = [
    ['VDD1(mV)', '', false],
    ['VDD2H(mV)', '', false],
    ['VDD2L(mV)', '', false],
    ['VDDQ(mV)', '', false],
    ['测试频率(M)', '4266', true],
    ['LogLevel', '', false],
    ['BadBlockMgmt', '', false],
    ...(ns ? TIMING_NS_CATALOG : TIMING_CATALOG).map(r => [r.key, '', false] as [string, string, boolean]),
  ]
  return rows.map(([name, value, checked], i) => ({
    id: i + 1, name, value, checked,
    options: PARAM_OPTIONS[name],
    unsupported: false,
  }))
}

// Stable catalogue order matches firmware mask bits; Walking combines bits13/14.
export const ALL_ALGORITHMS = [
  'test_random_value',
  'test_xor_comparison',
  'test_sub_comparison',
  'test_mul_comparison',
  'test_div_comparison',
  'test_or_comparison',
  'test_and_comparison',
  'test_seqinc_comparison',
  'test_solid_bit',
  'test_block_sequential',
  'test_checkerboard',
  'test_bit_spread',
  'test_bit_flip',
  'test_walking_ones_zeros',
  'test_march_c_comparison',
  'test_eigenvalue_comparison',
  'test_pattern_array',
  'test_hammer_comparison',
  'test_bitadd_comparison',
  'test_gseed_comparison',
  'test_run_moving_inv',
  'test_neon_random_value',
  'test_neon_solid_bit',
  'test_neon_block_sequential',
  'test_neon_checkerboard',
  'test_neon_bit_spread',
  'test_neon_walking_ones_zeros',
  'test_neon_run_moving_inv',
  'test_neon_bitadd_comparison',
  'test_neon_gseed_comparison',
  'test_ac_march_c',
  'test_ac_march_la',
  'test_ac_complement',
  'test_ac_step_len_parity_interleav_128',
  'test_ac_address_step_len_parity_interleav',
  'test_ac_rc_frame_march_raw',
  'test_ac_graycode',
  'test_ac_colharass',
]
export const QUICK_ALGORITHMS = [
  'test_seqinc_comparison', 'test_random_value', 'test_march_c_comparison',
  'test_run_moving_inv', 'test_ac_graycode',
]
export const BAD_AREA_ALGORITHMS = [
  'test_march_c_comparison', 'test_run_moving_inv', 'test_ac_march_c',
  'test_ac_march_la', 'test_ac_graycode', 'test_ac_rc_frame_march_raw',
]
// New views contain one selection and one order map. Quick mode can be customized;
// complete mode always selects the entire catalogue; bad-area mode is restricted.
const PL2_PATTERNS_BY_MODE: Record<string, string[]> = {
  '快速筛查': ALL_ALGORITHMS,
  '完整筛查': ALL_ALGORITHMS,
  '坏区管理': BAD_AREA_ALGORITHMS,
}

// PL2 默认 Pattern 表（按模式分组；参照 SLT 产品配置 PL2 页截图 + 2026-08-31 组合清单）
function defaultPl2(): Pl2Config {
  const mkRows = (names: string[]): Pl2Pattern[] =>
    names.map((name, i) => ({ id: i + 1, name, checked: true, order: String(i + 1), param: '' }))
  const patterns: Record<string, Pl2Pattern[]> = {}
  PL2_TEST_MODES.forEach(m => { patterns[m] = mkRows(PL2_PATTERNS_BY_MODE[m] ?? []) })
  return {
    screeningVersion: 1,
    executionOrder: Object.fromEntries(ALL_ALGORITHMS.map((n, i) => [n, String(i + 1)])),
    testMode: '完整筛查',
    ascEnabled: true,
    ascOrder: PL2_ASC_ORDERS[0],
    patterns,
    selectedAlgorithms: [...new Set(Object.values(patterns).flat().map(r => r.name))],
  }
}

export function defaultProfiles(): Record<string, ProductProfile> {
  const mk = (name: string, r0: number, r1: number, ch2 = true): ProductProfile => ({
    name,
    rankEnabled: true,
    pl1Enabled: true,
    pl2Enabled: true,
    rankCapacityGb: [r0, r1],
    channels: { ch1: true, ch2 },
    mr: defaultMr(),
    timingSchema: 2,
    params: defaultParams(),
    pl2: defaultPl2(),
  })
  return {
    'LPDDR4x-16Gb': mk('LPDDR4x-16Gb', 1, 1),
    'LPDDR4x-8Gb': mk('LPDDR4x-8Gb', 0.5, 0.5, false),
    'LPDDR4x-32Gb': mk('LPDDR4x-32Gb', 2, 2),
  }
}

// mock 持久化（localStorage）；后端就绪后替换为读写 JSON 文件
const STORAGE_KEY = 'slt-products'

// 空白产品档案（仅名字确定的导入文件以此兜底缺字段）
export function blankProfile(name: string): ProductProfile {
  return {
    name,
    rankEnabled: true,
    pl1Enabled: true,
    pl2Enabled: true,
    rankCapacityGb: [0, 0],
    channels: { ch1: true, ch2: true },
    mr: defaultMr(),
    timingSchema: 2,
    params: defaultParams(),
    pl2: defaultPl2(),
  }
}

// 单份档案规范化：补齐缺失字段 + 旧格式迁移（loadProfiles 与 JSON 导入共用，保证两条入口行为一致）
export function normalizeProfile(prof: ProductProfile): ProductProfile {
  // Retired form-only conditions never override the real cfg or device MR reads.
  delete (prof as unknown as Record<string, unknown>).timingContext
  if (prof.timingSchema !== undefined && prof.timingSchema !== TIMING_SCHEMA && prof.timingSchema !== 2) throw new Error('Unsupported timing schema')
  // 兼容旧存档：单一 enabled 字段拆分为 rankEnabled / pl1Enabled
  const legacyEnabled = (prof as unknown as { enabled?: boolean }).enabled
  if (typeof prof.rankEnabled !== 'boolean') prof.rankEnabled = legacyEnabled ?? true
  if (typeof prof.pl1Enabled !== 'boolean') prof.pl1Enabled = legacyEnabled ?? true
  if (typeof prof.pl2Enabled !== 'boolean') prof.pl2Enabled = true
  // 结构兜底：rank 容量 / 通道使能
  if (!Array.isArray(prof.rankCapacityGb) || prof.rankCapacityGb.length !== 2) prof.rankCapacityGb = [0, 0]
  if (!prof.channels || typeof prof.channels !== 'object') prof.channels = { ch1: true, ch2: true }
  else {
    if (typeof prof.channels.ch1 !== 'boolean') prof.channels.ch1 = true
    if (typeof prof.channels.ch2 !== 'boolean') prof.channels.ch2 = true
  }
  // PL2 配置
  if (!prof.pl2 || typeof prof.pl2 !== 'object') {
    prof.pl2 = defaultPl2()
  } else {
    // 兼容旧存档：patterns 从单一数组（全映射读写测试）迁移为按模式分组
    const legacyPatterns = prof.pl2.patterns as unknown
    if (Array.isArray(legacyPatterns)) {
      prof.pl2.patterns = { [PL2_TEST_MODES[0]]: legacyPatterns as Pl2Pattern[] }
    }
    if (!prof.pl2.patterns || typeof prof.pl2.patterns !== 'object') prof.pl2.patterns = {}
    const oldMode = !PL2_TEST_MODES.includes(prof.pl2.testMode)
    if (!PL2_ASC_ORDERS.includes(prof.pl2.ascOrder)) prof.pl2.ascOrder = PL2_ASC_ORDERS[0]
    if (typeof prof.pl2.ascEnabled !== 'boolean') prof.pl2.ascEnabled = true
    // 迁移：ty 系更名 ac 系（2026-09-11）——旧存档的 test_ty_* 行改写为新名，
    // 保留用户勾选/顺序/参数，避免合并时产生重复幽灵行
    Object.keys(prof.pl2.patterns).forEach(m => {
      const cur = prof.pl2.patterns[m]
      if (Array.isArray(cur)) {
        cur.forEach(r => {
          if (typeof r.name === 'string' && r.name.startsWith('test_ty_')) {
            r.name = 'test_ac_' + r.name.slice('test_ty_'.length)
          }
        })
      }
    })
    // 保存旧执行集合，再补分类行；新算法不自动启用。
    if ('selectedAlgorithms' in prof.pl2 && (!Array.isArray(prof.pl2.selectedAlgorithms) ||
      prof.pl2.selectedAlgorithms.some(name => typeof name !== 'string'))) {
      throw new Error('selectedAlgorithms must be a list of algorithm names')
    }
    const selected = new Set(Array.isArray(prof.pl2.selectedAlgorithms)
      ? prof.pl2.selectedAlgorithms.map(name => name.trim().replace(/^test_ty_/, 'test_ac_'))
      : Object.values(prof.pl2.patterns).flat().filter(r => r.checked).map(r => r.name))
    prof.pl2.selectedAlgorithms = [...selected]
    if (oldMode) prof.pl2.testMode = selected.size === ALL_ALGORITHMS.length && ALL_ALGORITHMS.every(n => selected.has(n)) ? '完整筛查' : '快速筛查'
    // Legacy row numbers never affected firmware execution. Do not accidentally
    // activate conflicting numbers from different old categories on migration.
    if ('executionOrder' in prof.pl2 && (!prof.pl2.executionOrder || typeof prof.pl2.executionOrder !== 'object' || Array.isArray(prof.pl2.executionOrder))) throw new Error('executionOrder must be an object')
    if (!prof.pl2.executionOrder) {
      prof.pl2.executionOrder = Object.fromEntries(ALL_ALGORITHMS.map((n, i) => [n, String(i + 1)]))
      prof.pl2.ascOrder = '升序'
    }
    // Inactive rows have no execution position, including old 100+ placeholders.
    Object.keys(prof.pl2.executionOrder).forEach(name => {
      if (!selected.has(name)) prof.pl2.executionOrder![name] = ''
    })
    // 每个模式：按名字补齐新增 Pattern 行（保留用户顺序/参数）
    const def = defaultPl2().patterns
    PL2_TEST_MODES.forEach(m => {
      const cur = prof.pl2.patterns[m] ?? (prof.pl2.patterns[m] = [])
      def[m].forEach(d => {
        if (!cur.some(r => r.name === d.name)) {
          cur.push(structuredClone(d))
        }
      })
      cur.sort((a, b) => a.id - b.id)
      cur.forEach(r => { r.checked = selected.has(r.name); r.order = prof.pl2.executionOrder![r.name] ?? '' })
    })
    Object.values(prof.pl2.patterns).flat().forEach(r => {
      r.checked = selected.has(r.name)
      r.order = r.checked ? prof.pl2.executionOrder![r.name] ?? '' : ''
    })
  }
  // Timing units changed per field. Archive active legacy values; never reinterpret them.
  if (!Array.isArray(prof.params)) prof.params = []
  const previous = prof.params
  // No selected timing value can change meaning. Empty timing profiles can
  // adopt ns without changing any effective setting; active raw profiles need
  // the explicit clear-and-re-enter action in the settings window.
  if (prof.timingSchema !== 1 && prof.timingSchema !== 2 && !prof.timingReviewRequired && !previous.some(r => r.checked &&
      (TIMING_BY_KEY.has(r.name) || LEGACY_TIMING_KEYS.has(r.name)) &&
      (prof.timingSchema === 1 || prof.timingUnit === 2 || Number(r.value) !== 0))) {
    prof.timingSchema = 2
  }
  const currentTiming = prof.timingSchema === TIMING_SCHEMA || prof.timingSchema === 2
  if (currentTiming) {
    if (prof.timingUnit !== undefined) throw new Error('Legacy timingUnit conflicts with fixed units')
    const names = previous.map(r => r.name.trim())
    if (new Set(names).size !== names.length) throw new Error('Duplicate parameter names')
    if (prof.timingSchema !== 2 && previous.some(r => r.checked && LEGACY_TIMING_KEYS.has(r.name) && !TIMING_BY_KEY.has(r.name))) {
      throw new Error('Legacy timing key in a new profile')
    }
  }
  if (!currentTiming) {
    const active = previous.filter(r => r.checked && (LEGACY_TIMING_KEYS.has(r.name) || TIMING_BY_KEY.has(r.name)) &&
      (prof.timingUnit === 2 || Number(r.value) !== 0))
    if (active.length) {
      prof.timingMigration = { unit: prof.timingUnit ?? 0, params: structuredClone(active) }
      prof.timingReviewRequired = true
    }
  }
  const defaults = defaultParams(prof.timingSchema === 2)
  prof.params = defaults.map(def => {
    const old = previous.find(r => r.name === def.name)
    if (!old || (!currentTiming && TIMING_BY_KEY.has(def.name))) return def
    return { ...def, value: old.value, checked: old.checked }
  })
  const known = new Set(defaults.map(r => r.name))
  previous.filter(r => !known.has(r.name) && (prof.timingSchema === 2 || !LEGACY_TIMING_KEYS.has(r.name)) && r.name !== '锁定测试容量(MB)')
    .forEach(r => prof.params.push({ id: prof.params.length + 1, name: r.name, value: r.value, checked: r.checked,
      unsupported: !['LogLevel', 'BadBlockMgmt'].includes(r.name) }))
  prof.timingSchema = prof.timingSchema === 2 ? 2 : TIMING_SCHEMA
  delete prof.timingUnit
  // MR 配置：按通道分组（填值才校验，无勾选项）。
  // 迁移：①最旧 {ch1,ch2:[{name,value,checked}]} → 按名保留 value；②按 Rank 分组
  // {rank1,rank2:{enabled,rows:[MR5_1..MR8_2]}} → 双通道同值（优先 rank2 的 _2 行，
  // 空则回退 rank1 的 _1 行）；③缺/非法 → 默认空值四行。
  const mrAny = prof.mr as unknown as {
    ch1?: MrRow[]; ch2?: MrRow[]
    rank1?: { rows?: { name: string; value: string }[] }
    rank2?: { rows?: { name: string; value: string }[] }
  } | undefined
  const isNewMr = !!mrAny && Array.isArray(mrAny.ch1) && Array.isArray(mrAny.ch2)
  if (isNewMr) {
    (['ch1', 'ch2'] as const).forEach(ck => {
      const rows = mrAny![ck]!
      mrRows().forEach(d => {
        if (!rows.some(r => r.name === d.name)) rows.push(structuredClone(d))
      })
    })
  } else {
    const def = defaultMr()
    const r1 = mrAny?.rank1?.rows ?? []
    const r2 = mrAny?.rank2?.rows ?? []
    if (r1.length > 0 || r2.length > 0) {
      // 按 Rank 旧档：同名（_2）优先，否则取 _1 行的值；双通道同值
      def.ch1.forEach((row, i) => {
        const base = row.name.slice(0, 3)          // MR5_2 → MR5
        const hit = r2.find(l => l.name === row.name)
          ?? r1.find(l => l.name === `${base}_1`)
        const v = hit?.value ?? ''
        def.ch1[i].value = v
        def.ch2[i].value = v
      })
    }
    prof.mr = def
  }
  return prof
}

export function setAlgorithmChecked(profile: ProductProfile, name: string, checked: boolean): ProductProfile {
  const selected = new Set(profile.pl2.selectedAlgorithms ??
    Object.values(profile.pl2.patterns).flat().filter(r => r.checked).map(r => r.name))
  const executionOrder = { ...profile.pl2.executionOrder }
  if (checked && !selected.has(name)) {
    const existing = [...selected].map(n => [n, Number(executionOrder[n])] as const)
    const valid = existing.filter(([, value]) => Number.isInteger(value) && value >= 1 && value <= 9999)
    const descending = profile.pl2.ascOrder === '降序'
    const next = !valid.length ? 1 : descending ? Math.min(...valid.map(([, v]) => v)) - 1 : Math.max(...valid.map(([, v]) => v)) + 1
    if (next >= 1 && next <= 9999) executionOrder[name] = String(next)
    else if (valid.length === existing.length && new Set(valid.map(([, v]) => v)).size === valid.length) {
      // At the numeric boundary, keep the existing execution order while
      // compacting its positions to make room for the appended algorithm.
      valid.sort((a, b) => descending ? b[1] - a[1] : a[1] - b[1])
      valid.forEach(([n], i) => { executionOrder[n] = String(descending ? valid.length + 1 - i : i + 1) })
      executionOrder[name] = String(descending ? 1 : valid.length + 1)
    } else executionOrder[name] = '' // Keep invalid edits visible to preflight.
  }
  if (checked) selected.add(name)
  else selected.delete(name)
  Object.keys(executionOrder).forEach(n => { if (!selected.has(n)) executionOrder[n] = '' })
  if (!checked) executionOrder[name] = ''
  const patterns = Object.fromEntries(Object.entries(profile.pl2.patterns).map(([category, rows]) =>
    [category, rows.map(r => ({ ...r, checked: selected.has(r.name), order: selected.has(r.name) ? executionOrder[r.name] ?? '' : '' }))]))
  return { ...profile, pl2: { ...profile.pl2, patterns, executionOrder, selectedAlgorithms: [...selected] } }
}

export function setAlgorithmOrder(profile: ProductProfile, name: string, order: string): ProductProfile {
  if (!profile.pl2.selectedAlgorithms?.includes(name)) return profile
  const patterns = Object.fromEntries(Object.entries(profile.pl2.patterns).map(([mode, rows]) =>
    [mode, rows.map(r => r.name === name ? { ...r, order } : r)]))
  return { ...profile, pl2: { ...profile.pl2, patterns, executionOrder: { ...profile.pl2.executionOrder, [name]: order } } }
}

export function selectScreeningMode(profile: ProductProfile, mode: string): ProductProfile {
  const chosen = mode === '完整筛查' ? ALL_ALGORITHMS : mode === '坏区管理' ? BAD_AREA_ALGORITHMS : QUICK_ALGORITHMS
  const selected = new Set(chosen)
  const executionOrder = Object.fromEntries(ALL_ALGORITHMS.map(n => [n, selected.has(n) ? String(chosen.indexOf(n) + 1) : '']))
  const patterns = Object.fromEntries(Object.entries(profile.pl2.patterns).map(([category, rows]) =>
    [category, rows.map(r => ({ ...r, checked: selected.has(r.name), order: executionOrder[r.name] }))]))
  return { ...profile, pl1Enabled: true, pl2Enabled: true, pl2: { ...profile.pl2, screeningVersion: 1, testMode: mode, ascOrder: '升序', patterns, selectedAlgorithms: [...chosen], executionOrder } }
}

export function activeScreeningProfile(profile: ProductProfile): ProductProfile {
  return { ...profile, pl1Enabled: true, pl2Enabled: true, pl2: { ...profile.pl2, screeningVersion: 1 } }
}

// 解析并校验产品档案 JSON 文本（前面板「选择」按钮导入用）
// 非法 JSON / 非对象 / 缺 name → 抛错（调用方弹 spBadProfileJson）；合法档案经 normalize 补全后返回
export function parseProfileJson(text: string): ProductProfile {
  const obj = JSON.parse(text) as unknown   // 语法错误直接抛
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) throw new Error('profile is not an object')
  const name = (obj as { name?: unknown }).name
  if (typeof name !== 'string' || !name.trim()) throw new Error('profile.name missing')
  // 旧版单一 enabled 字段：合并模板前先映射，否则模板的 true 会抢占迁移（normalize 只看 boolean 已就位）
  const raw = obj as Record<string, unknown>
  const legacyPatch: Partial<ProductProfile> = {}
  if (typeof raw.enabled === 'boolean') {
    if (raw.rankEnabled === undefined) legacyPatch.rankEnabled = raw.enabled
    if (raw.pl1Enabled === undefined) legacyPatch.pl1Enabled = raw.enabled
  }
  // JSON 无 undefined，obj 中出现的键必有值，可安全覆盖空白模板
  // Do not let the new blank template mark a legacy file as migrated.
  return normalizeProfile({ ...blankProfile(name), ...(raw as unknown as ProductProfile),
    timingSchema: raw.timingSchema as ProductProfile['timingSchema'], ...legacyPatch, name })
}

export function loadProfiles(): Record<string, ProductProfile> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const p = JSON.parse(raw) as Record<string, ProductProfile>
      if (p && typeof p === 'object' && Object.keys(p).length > 0) {
        // 兼容旧存档：统一走 normalizeProfile（补齐字段 + 旧格式迁移）
        Object.values(p).forEach(normalizeProfile)
        return p
      }
    }
  } catch { /* 忽略损坏数据，回退默认 */ }
  return defaultProfiles()
}

export function saveProfiles(p: Record<string, ProductProfile>) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(p)) } catch { /* 忽略 */ }
}
