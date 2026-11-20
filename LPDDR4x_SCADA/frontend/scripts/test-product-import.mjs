// 产品档案 JSON 导入机制单元测试（node 直跑，无测试框架依赖）
// 覆盖：parseProfileJson（合法/旧格式/非法输入）、normalizeProfile 迁移、loadProfiles/saveProfiles 闭环
// 用法：npm test  或  node scripts/test-product-import.mjs
import { buildSync } from 'esbuild'
import { fileURLToPath, pathToFileURL } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'

const here = path.dirname(fileURLToPath(import.meta.url))
const bundleOut = path.join(here, '.tmp-product-test-bundle.mjs')

// localStorage 桩（loadProfiles/saveProfiles 依赖；须在 import 被测模块前挂好）
const store = new Map()
globalThis.localStorage = {
  getItem: k => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: k => store.delete(k),
  clear: () => store.clear(),
}

buildSync({
  entryPoints: [path.join(here, '../src/types/product.ts')],
  bundle: true, format: 'esm', platform: 'node', outfile: bundleOut, logLevel: 'silent',
})
const { parseProfileJson, loadProfiles, saveProfiles, defaultProfiles, PL2_TEST_MODES } =
  await import(pathToFileURL(bundleOut).href)
fs.rmSync(bundleOut, { force: true })

// ---- 迷你断言框架 ----
let passed = 0
const failures = []
function ok(cond, name) {
  if (cond) { passed++; console.log(`  ✓ ${name}`) }
  else { failures.push(name); console.log(`  ✗ ${name}`) }
}
function throws(fn, name) {
  try { fn(); failures.push(name); console.log(`  ✗ ${name}（未抛错）`) }
  catch { passed++; console.log(`  ✓ ${name}`) }
}
function section(s) { console.log(`\n[${s}]`) }

// ---- A. parseProfileJson 合法输入 ----
section('A. parseProfileJson 合法输入')

const full = defaultProfiles()['LPDDR4x-16Gb']
const p1 = parseProfileJson(JSON.stringify(full))
ok(p1.name === 'LPDDR4x-16Gb', 'A1 完整档案 round-trip：name 保留')
ok(p1.params.length === 42, `A1 ns参数表42行：35主时序+7工作参数（实际 ${p1.params.length}）`)
ok(PL2_TEST_MODES.every(m => p1.pl2.patterns[m]), 'A1 PL2 三模式齐全')
ok(
  p1.pl2.patterns['快速筛查'].length === 38 &&
  p1.pl2.patterns['完整筛查'].length === 38 &&
  p1.pl2.patterns['坏区管理'].length === 6,
  'A1 三模式 Pattern 数 38/38/6'
)
ok(p1.mr.ch1.length === 4 && p1.mr.ch2.length === 4, 'A1 MR 配置双通道各 4 行')
ok(p1.rankEnabled === true && p1.pl1Enabled === true && p1.pl2Enabled === true, 'A1 三个启用位齐全')

const p2 = parseProfileJson('{"name":"X"}')
ok(p2.name === 'X', 'A2 最小档案 {name} 导入成功')
ok(p2.rankEnabled === true && p2.pl1Enabled === true && p2.pl2Enabled === true, 'A2 缺省启用位补 true')
ok(Array.isArray(p2.rankCapacityGb) && p2.rankCapacityGb.length === 2, 'A2 rankCapacityGb 兜底 [0,0]')
ok(p2.channels.ch1 === true && p2.channels.ch2 === true, 'A2 channels 兜底双通道使能')
ok(p2.params.length === 42, 'A2 参数表补齐42行ns模板')
ok(
  p2.pl2.patterns['快速筛查'].length === 38 &&
  p2.pl2.patterns['完整筛查'].length === 38 &&
  p2.pl2.patterns['坏区管理'].length === 6,
  'A2 PL2 三模式默认表补齐'
)
ok(p2.pl2.testMode === '完整筛查' && p2.pl2.ascOrder === '升序', 'A2 新档案默认完整筛查/升序')

const legacy = parseProfileJson(JSON.stringify({
  name: 'OLD',
  enabled: false,                     // 旧版单一启用字段
  rankCapacityGb: [2, 2],
  pl2: {
    testMode: 'Block测试',
    ascEnabled: true,
    ascOrder: '降序',
    patterns: [{ id: 1, name: 'test_solid_bit', checked: false, order: '5', param: 'abc' }],  // 旧扁平数组
  },
}))
ok(legacy.rankEnabled === false && legacy.pl1Enabled === false, 'A3 旧 enabled=false → rank/pl1 双 false')
ok(legacy.pl2Enabled === true, 'A3 旧档无 pl2Enabled → 补 true')
ok(legacy.pl2.testMode === '快速筛查' && legacy.pl2.ascOrder === '升序', 'A3 旧无效排序开关不意外激活为降序执行')
ok(legacy.pl2.patterns['快速筛查'].some(r => r.name === 'test_solid_bit' && !r.checked && r.param === 'abc'),
  'A3 旧扁平行勾选和参数保留；旧无效行号不激活为新执行顺序')
ok(legacy.pl2.patterns['快速筛查'].length === 38, 'A3 快速筛查补齐全目录，供追加算法')
ok(legacy.pl2.patterns['完整筛查'].length === 38, 'A3 完整筛查包含38个界面项')

const p4 = parseProfileJson(JSON.stringify({ name: 'X', pl2: { testMode: '不存在的模式' } }))
ok(p4.pl2.testMode === '快速筛查', 'A4 非法 testMode 回退第一个模式')

const p5 = parseProfileJson(JSON.stringify({ name: 'X', mr: {} }))
ok(p5.mr.ch1.length === 4 && p5.mr.ch2.length === 4, 'A5 残缺 mr={} → 双通道各补 4 行')
ok(p5.mr.ch1.every(r => r.value === ''), 'A5b 默认 MR 行空值（填值才校验）')
ok(!('checked' in p5.mr.ch1[0]), 'A5c MR 行无 checked 字段')

// 按 Rank 分组的旧档 → 按通道迁移：_2 同名优先，空则回退 _1 行；双通道同值
const p5r = parseProfileJson(JSON.stringify({
  name: 'X',
  mr: {
    rank1: { enabled: true, rows: [{ name: 'MR5_1', value: '0x11', checked: true }] },
    rank2: { enabled: true, rows: [{ name: 'MR5_2', value: '0x1A', checked: true },
                                    { name: 'MR8_2', value: '0x3C', checked: false }] },
  },
}))
ok(Array.isArray(p5r.mr.ch1) && p5r.mr.ch1.length === 4, 'A5d Rank 旧档迁移为按通道 4 行')
ok(p5r.mr.ch1.find(r => r.name === 'MR5_2').value === '0x1A', 'A5e _2 同名行优先迁移')
ok(p5r.mr.ch1.find(r => r.name === 'MR8_2').value === '0x3C', 'A5f 值保留（旧 checked 忽略）')
ok(p5r.mr.ch2.find(r => r.name === 'MR5_2').value === '0x1A', 'A5g 双通道同值')
ok(p5r.mr.ch1.find(r => r.name === 'MR6_2').value === '', 'A5h 无值行留空')
const p5r2 = parseProfileJson(JSON.stringify({
  name: 'X',
  mr: { rank1: { enabled: true, rows: [{ name: 'MR6_1', value: '0x22', checked: true }] } },
}))
ok(p5r2.mr.ch1.find(r => r.name === 'MR6_2').value === '0x22', 'A5i 只有 _1 行时回退迁移')

const p6 = parseProfileJson(JSON.stringify({ name: 'X', params: [{ id: 200, name: 'CUSTOM_X', value: '7', checked: true }] }))
ok(p6.params.some(r => r.name === 'CUSTOM_X' && r.value === '7'), 'A6 自定义参数行保留')
ok(p6.params.length === 43, `A6 默认行补齐（42+1=43，实际 ${p6.params.length}）`)

const p7 = parseProfileJson(JSON.stringify({ name: '  带空格产品  ' }))
ok(p7.name === '  带空格产品  ', 'A7 name 原样保留（不擅自 trim）')

// ---- B. parseProfileJson 非法输入：必须全部抛错 ----
section('B. parseProfileJson 非法输入')
throws(() => parseProfileJson('not json {'), 'B1 语法错误 JSON 抛错')
throws(() => parseProfileJson(''), 'B2 空串抛错')
throws(() => parseProfileJson('{"x":1}'), 'B3 缺 name 抛错')
throws(() => parseProfileJson('{"name":""}'), 'B4 空 name 抛错')
throws(() => parseProfileJson('{"name":"   "}'), 'B5 纯空白 name 抛错')
throws(() => parseProfileJson('{"name":123}'), 'B6 非字符串 name 抛错')
throws(() => parseProfileJson('[1,2,3]'), 'B7 数组抛错')
throws(() => parseProfileJson('123'), 'B8 数字抛错')
throws(() => parseProfileJson('"hello"'), 'B9 字符串抛错')
throws(() => parseProfileJson('null'), 'B10 null 抛错')

// ---- C. loadProfiles / saveProfiles 持久化与迁移 ----
section('C. loadProfiles / saveProfiles')

store.clear()
const d1 = loadProfiles()
ok(Object.keys(d1).length === 3 && d1['LPDDR4x-16Gb'], 'C1 空 localStorage → 3 个默认产品')

store.set('slt-products', 'xxx{损坏')
const d2 = loadProfiles()
ok(Object.keys(d2).length === 3, 'C2 损坏 JSON → 回退默认')

store.set('slt-products', '{}')
const d3 = loadProfiles()
ok(Object.keys(d3).length === 3, 'C3 空对象 {} → 回退默认')

store.set('slt-products', 'null')
const d4 = loadProfiles()
ok(Object.keys(d4).length === 3, 'C4 null → 回退默认')

store.set('slt-products', JSON.stringify({
  老产品: { name: '老产品', enabled: false, rankCapacityGb: [4, 4] },
}))
const d5 = loadProfiles()
ok(d5['老产品'].rankEnabled === false && d5['老产品'].pl1Enabled === false, 'C5 旧存档 enabled 迁移')
ok(d5['老产品'].pl2.patterns['坏区管理'].length === 6, 'C5 旧存档 PL2 补齐')
ok(d5['老产品'].mr.ch1.length === 4, 'C5 旧存档 MR 补齐')
ok(d5['老产品'].rankCapacityGb[0] === 4, 'C5 用户 rank 容量不被覆盖')

store.clear()
const d6 = loadProfiles()
d6['新导入'] = parseProfileJson('{"name":"新导入"}')
saveProfiles(d6)
const d7 = loadProfiles()
ok(d7['新导入'] && d7['新导入'].params.length === 42, 'C6 导入→保存→重载 闭环字段完整')

// ---- D. 导入闭环（等价 Home.handleImportProfile：并入 profiles + 持久化 + 可选中）----
section('D. 导入闭环')
store.clear()
const profiles = loadProfiles()
const imported = parseProfileJson(JSON.stringify({ name: '导入A', rankCapacityGb: [8, 8] }))
profiles[imported.name] = imported
saveProfiles(profiles)
const reloaded = loadProfiles()
ok(reloaded['导入A']?.rankCapacityGb[0] === 8, 'D1 导入产品重载后用户值保留')
ok(Object.keys(reloaded).length === 4, 'D2 默认 3 + 导入 1 = 4 个产品')
ok(reloaded['导入A'].pl2.patterns['完整筛查'].length === 38, 'D3 导入产品经 normalize 字段齐全')

// ---- 汇总 ----
console.log(`\n========================================`)
console.log(`通过 ${passed} 项${failures.length ? `，失败 ${failures.length} 项：` : '，全部通过 ✓'}`)
failures.forEach(f => console.log(`  ✗ ${f}`))
process.exit(failures.length ? 1 : 0)
