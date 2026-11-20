import assert from 'node:assert/strict'
import { buildSync } from 'esbuild'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { execFileSync } from 'node:child_process'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const out = path.join(os.tmpdir(), 'slt-product-trust-' + process.pid + '.mjs')
const store = new Map()
globalThis.localStorage = { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) }
globalThis.window = { dispatchEvent() {} }
buildSync({
  stdin: {
    contents: "export * from './src/types/product'; export * from './src/lib/productPlan'; export * from './src/lib/runtimePolicy'; export {setLang} from './src/lib/i18n';",
    resolveDir: root,
  },
  outfile: out, bundle: true, format: 'esm', platform: 'node', logLevel: 'silent',
})
const m = await import(pathToFileURL(out).href)
fs.unlinkSync(out)
let count = 0
const check = (value, message) => { assert.ok(value, message); count++ }
check(m.validRuntimePolicy(m.defaultRuntimePolicy()), 'Default runtime policy preserves existing run behavior')
check(!m.validRuntimePolicy({ ...m.defaultRuntimePolicy(), cfgAckTimeoutSec: 3601 }), 'Invalid ACK budgets cannot be submitted')
check(!m.validRuntimePolicy({ ...m.defaultRuntimePolicy(), cfgRetryIntervalSec: NaN }), 'Non-finite limits cannot become JSON null')
check(!m.validRuntimePolicy({ ...m.defaultRuntimePolicy(), checkReadyVersion: true }), 'Enabled version checks require an identifier')
check(m.validRuntimePolicy({ ...m.defaultRuntimePolicy(), checkReadyVersion: true, expectedReadyVersion: 'M80-_6785' }), 'Actual READY format is accepted')
check(!m.validRuntimePolicy({ ...m.defaultRuntimePolicy(), expectedReadyVersion: 'M80-\u0000_6785' }), 'Non-printable version strings are rejected')
const profile = m.defaultProfiles()['LPDDR4x-16Gb']
check(profile.pl2.testMode === '完整筛查', 'New products default to the complete catalogue')
const fast = m.selectScreeningMode(profile, '快速筛查')
check(fast.pl2.selectedAlgorithms.join(',') === m.QUICK_ALGORITHMS.join(','), 'Quick screen presets target common fault patterns')
check(Object.values(fast.pl2.patterns).flat().filter(r => r.checked).every(r => m.QUICK_ALGORITHMS.includes(r.name)), 'Switching presets replaces the actual shared selection')
const reordered = m.setAlgorithmOrder(fast, 'test_random_value', '90')
check(Object.values(reordered.pl2.patterns).flat().filter(r => r.name === 'test_random_value').every(r => r.order === '90'), 'Order changes propagate to every view')
check(fast.pl2.executionOrder.test_random_value === '2', 'Order editing does not mutate the original')
const badArea = m.selectScreeningMode(profile, '坏区管理')
check(badArea.pl2.selectedAlgorithms.length === 6 && badArea.pl2.patterns['坏区管理'].length === 6, 'Bad-area mode contains six address-recording scans')
check(Object.values(fast.pl2.patterns).flat().filter(r => !r.checked).every(r => r.order === ''), 'Unselected preset rows have no position')
const appended = m.setAlgorithmChecked(fast, 'test_solid_bit', true)
check(appended.pl2.executionOrder.test_solid_bit === '6', 'New selection appends after the five quick-screen tests')
const cancelled = m.setAlgorithmChecked(appended, 'test_solid_bit', false)
check(cancelled.pl2.executionOrder.test_solid_bit === '' && Object.values(cancelled.pl2.patterns).flat().filter(r => r.name === 'test_solid_bit').every(r => r.order === ''), 'Cancellation clears the map and every row')
const customOrder = m.setAlgorithmOrder(appended, 'test_solid_bit', '60')
check(m.setAlgorithmChecked(customOrder, 'test_solid_bit', true).pl2.executionOrder.test_solid_bit === '60', 'Already checked rows retain manual order')
check(m.setAlgorithmOrder(cancelled, 'test_solid_bit', '101') === cancelled, 'Inactive order cannot be edited')
const migratedOrder = m.parseProfileJson(JSON.stringify({ ...fast, pl2: { ...fast.pl2, executionOrder: { ...fast.pl2.executionOrder, test_solid_bit: '108' } } }))
check(migratedOrder.pl2.executionOrder.test_solid_bit === '' && migratedOrder.pl2.executionOrder.test_random_value === '2', 'Old inactive placeholders clear while selected orders remain')
const descending = { ...fast, pl2: { ...fast.pl2, ascOrder: '降序' } }
const descendingAppend = m.setAlgorithmChecked(descending, 'test_solid_bit', true)
check(descendingAppend.pl2.executionOrder.test_solid_bit === '1' && descendingAppend.pl2.executionOrder.test_seqinc_comparison === '2', 'Descending append preserves the previous execution order')
const emptyFast = fast.pl2.selectedAlgorithms.reduce((p, n) => m.setAlgorithmChecked(p, n, false), fast)
check(m.setAlgorithmChecked(emptyFast, 'test_solid_bit', true).pl2.executionOrder.test_solid_bit === '1', 'First selected test starts at one')
check(profile.params.filter(r => r.name.startsWith('VDD')).every(r => !r.checked && r.value === ''),
  'New voltage entries inherit the machine baseline with no guessed conversion')
const legacy = m.parseProfileJson(JSON.stringify({
  name: 'LEGACY', rankEnabled: false, pl1Enabled: true, pl2Enabled: true,
  pl2: { patterns: {
    'Block测试': [{ id: 1, name: 'test_solid_bit', checked: false }],
    '全空间测试': [{ id: 1, name: 'test_solid_bit', checked: true }],
  }},
}))
check(legacy.pl2.selectedAlgorithms.length === 1, 'Legacy execution union preserved, without enabling newly added algorithms')
const off = m.setAlgorithmChecked(legacy, 'test_solid_bit', false)
check(off.pl2.selectedAlgorithms.length === 0, 'Shared selection can be explicitly empty')
check(Object.values(off.pl2.patterns).flat().filter(r => r.name === 'test_solid_bit').every(r => !r.checked),
  'Every category reflects the same cancellation')
check(legacy.pl2.selectedAlgorithms.length === 1, 'Original profile is immutable')
const on = m.setAlgorithmChecked(off, 'test_solid_bit', true)
check(Object.values(on.pl2.patterns).flat().filter(r => r.name === 'test_solid_bit').every(r => r.checked),
  'Every category reflects the same enabling')
const stale = m.parseProfileJson(JSON.stringify({
  name: 'EXPLICIT-NONE', pl2: { selectedAlgorithms: [], patterns: {
    'Block测试': [{ id: 1, name: 'test_solid_bit', checked: true }],
  }},
}))
check(stale.pl2.selectedAlgorithms.length === 0 &&
  Object.values(stale.pl2.patterns).flat().every(r => !r.checked), 'Explicit selection wins over stale legacy views')
assert.throws(() => m.parseProfileJson(JSON.stringify({ name: 'BAD-SET', pl2: { selectedAlgorithms: null } })),
  /selectedAlgorithms/)
count++
assert.throws(() => m.parseProfileJson(JSON.stringify({ name: 'BAD-ORDER', pl2: { executionOrder: null } })), /executionOrder/)
count++
check(m.parseProfileJson(JSON.stringify({ name: 'ALIAS', pl2: { selectedAlgorithms: [' test_ty_step128 '] } }))
  .pl2.selectedAlgorithms[0] === 'test_ac_step128', 'Canonical legacy names are migrated without changing selection')
const invalidFreq = m.parseProfileJson(JSON.stringify({
  name: 'BAD-FREQ', params: [{ id: 5, name: '测试频率(M)', value: '4800', checked: true }],
}))
check(invalidFreq.params.find(r => r.name === '测试频率(M)').value === '4800',
  'Unsupported imported frequency is not silently changed')
const py = "import sys,json;sys.path.insert(0,sys.argv[1]);from app.profileplan import compile_profile;from app.cfg import _DEFAULTS;print(json.dumps(compile_profile(json.load(sys.stdin),dict(_DEFAULTS))))"
const backend = path.join(root, '../backend')
const ascendingPlan = JSON.parse(execFileSync('python', ['-B', '-X', 'utf8', '-c', py, backend], { input: JSON.stringify(appended), encoding: 'utf8' }))
check(ascendingPlan.valid && ascendingPlan.cfgText.includes('P2Order=7:0:15:21:37:8\n'), 'Appended frontend selection becomes the exact firmware sequence')
const descendingPlan = JSON.parse(execFileSync('python', ['-B', '-X', 'utf8', '-c', py, backend], { input: JSON.stringify(descendingAppend), encoding: 'utf8' }))
check(descendingPlan.valid && descendingPlan.cfgText.includes('P2Order=37:21:15:0:7:8\n'), 'Descending append executes last rather than first')
for (const p of [fast, badArea, profile]) {
  const result = JSON.parse(execFileSync('python', ['-B', '-X', 'utf8', '-c', py, backend], { input: JSON.stringify(p), encoding: 'utf8' }))
  check(result.valid, 'Frontend preset passes backend validation: ' + p.pl2.testMode)
  check(result.testCount === (p === profile ? 40 : p === fast ? 6 : 7), 'Expanded bits and mandatory Stuck agree across layers')
}
const planOn = JSON.parse(execFileSync('python', ['-B', '-X', 'utf8', '-c', py, backend], { input: JSON.stringify(on), encoding: 'utf8' }))
const planOff = JSON.parse(execFileSync('python', ['-B', '-X', 'utf8', '-c', py, backend], { input: JSON.stringify(off), encoding: 'utf8' }))
check(planOn.valid && planOn.mask === '0x100' && planOn.testCount === 2, 'Frontend selection compiles into the expected firmware mask')
check(!planOff.valid && planOff.errors.some(e => e.code === 'empty_selection'), 'Cancelled selection never becomes a full-test plan')
const unknown = m.parseProfileJson(JSON.stringify({ name: 'UNKNOWN', pl2: { selectedAlgorithms: ['test_future'] } }))
const planUnknown = JSON.parse(execFileSync('python', ['-B', '-X', 'utf8', '-c', py, backend], { input: JSON.stringify(unknown), encoding: 'utf8' }))
check(!planUnknown.valid && planUnknown.errors.some(e => e.code === 'unknown_algorithm'),
  'Unknown imported algorithms are rejected instead of changing to full testing')

globalThis.fetch = async () => ({ ok: false, json: async () => ({ detail: { errors: [
  { field: 'VDD1', messageZh: '无效电压', messageEn: 'Invalid voltage' },
] } }) })
await assert.rejects(m.saveProduct(profile, ''), /VDD1.*无效电压/)
count++
m.setLang('en')
await assert.rejects(m.saveProduct(profile, ''), /VDD1.*Invalid voltage/)
count++
globalThis.fetch = async () => ({ ok: true, json: async () => ({ ok: true }) })
await assert.rejects(m.saveProduct(profile, ''), /Request failed/)
count++
let reply
globalThis.fetch = () => new Promise(resolve => { reply = resolve })
let finished = false
const pending = m.saveProduct(profile, '').then(result => { finished = true; return result })
await Promise.resolve()
check(!finished, 'Save remains pending before the backend acknowledgement')
reply({ ok: true, json: async () => ({ ok: true, plan: planOn }) })
check((await pending).valid, 'Save resolves only with a validated backend acknowledgement')
console.log('Product trust: ' + count + ' checks passed')
