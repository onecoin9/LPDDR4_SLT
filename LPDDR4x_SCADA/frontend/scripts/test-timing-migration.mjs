import assert from 'node:assert/strict'
import { buildSync } from 'esbuild'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const out = path.join(os.tmpdir(), 'slt-timing-' + process.pid + '.mjs')
buildSync({ entryPoints: [path.join(root, 'src/types/product.ts')], outfile: out,
  bundle: true, format: 'esm', platform: 'node', logLevel: 'silent' })
const m = await import(pathToFileURL(out).href)
fs.unlinkSync(out)
let passed = 0
const check = (value, message) => { assert.ok(value, message); passed++ }
const param = (name, value, checked=true) => ({ id: 1, name, value, checked, start: '1', step: '1', end: '8' })
const parse = p => m.parseProfileJson(JSON.stringify({ name: 'TIMING', ...p }))

check(m.TIMING_CATALOG.length === 50, '50 writable fields')
const fresh = parse({})
check(fresh.timingSchema === 2 && !('timingUnit' in fresh), 'new profile uses fixed units')
check(fresh.params.length === 42 && fresh.params.every(p => !('start' in p) && !('step' in p) && !('end' in p)), 'no scan ranges in new rows')
check(fresh.params.filter(r => m.TIMING_BY_KEY.has(r.name)).every(r => !r.checked && r.value === ''), 'blank timing inherits firmware')
for (const unit of [0, 1, 2]) {
  const old = parse({ timingUnit: unit, params: [param('TRCD', '5'), param('VDD1(mV)', '1800'), param('TMRW', '4')] })
  check(old.timingReviewRequired && old.timingMigration.unit === unit, `legacy mode ${unit} requires explicit review`)
  check(old.timingMigration.params.length === 2, 'legacy enabled timings archived')
  check(old.params.find(r => r.name === 'TRCD').value === '' && !old.params.find(r => r.name === 'TRCD').checked, 'legacy value never becomes a raw register')
  check(old.params.find(r => r.name === 'VDD1(mV)').value === '1800', 'voltage stays intact')
  check(!old.params.some(r => r.name === 'TMRW'), 'orphan legacy key removed from table')
  const second = parse(old)
  check(JSON.stringify(second) === JSON.stringify(old), 'migration is idempotent')
}
const zero = parse({ params: [param('TRCD', '0')] })
check(!zero.timingReviewRequired, 'legacy delta zero inherits')
const rawZero = parse({ timingUnit: 2, params: [param('TRCD', '0')] })
check(rawZero.timingReviewRequired, 'legacy raw zero is preserved for review')
const current = parse({ timingSchema: 1, params: [param('TRCD', '0'), param('TRFC', '380.01')] })
check(current.params.find(r => r.name === 'TRCD').value === '0' && current.params.find(r => r.name === 'TRCD').checked, 'explicit new zero survives save/reload')
check(!current.timingReviewRequired && current.params.find(r => r.name === 'TRFC').value === '380.01', 'new ns input survives save/reload')
const ns = parse({ timingSchema: 2, params: [param('TRCD','18')] })
check(ns.params.length === 42 && ns.params.find(r => r.name === 'TRCD').value === '18', 'ns input survives save/reload without reinterpretation')
check(!ns.params.some(r => r.name.endsWith('_05T')), 'half-cycle fields are derived automatically')
const obsolete = parse({ timingSchema: 2, timingContext: { ioWidth: 32, derated: true }, params: [param('VDD1(mV)','1800'),param('测试频率(M)','3200')] })
check(!('timingContext' in obsolete), 'retired JEDEC form fields are removed on import')
check(obsolete.params.find(r => r.name === 'VDD1(mV)').value === '1800', 'removing conditions preserves real voltage')
check(obsolete.params.find(r => r.name === '测试频率(M)').value === '3200', 'removing conditions preserves real frequency')
assert.throws(() => parse({ timingSchema: 3 }), /Unsupported timing schema/); passed++
assert.throws(() => parse({ timingSchema: 1, timingUnit: 2, params: [param('TRCD', '7')] }), /conflicts/); passed++
assert.throws(() => parse({ timingSchema: 1, params: [param('TRCD', '1'), param('TRCD', '2')] }), /Duplicate/); passed++
assert.throws(() => parse({ timingSchema: 1, params: [param('TMRW', '2')] }), /Legacy timing key/); passed++
console.log(`Timing migration: ${passed} checks passed`)
