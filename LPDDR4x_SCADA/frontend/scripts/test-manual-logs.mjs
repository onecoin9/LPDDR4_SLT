import fs from 'node:fs'
import assert from 'node:assert/strict'
import ts from 'typescript'

const pageText = fs.readFileSync(new URL('../src/pages/ManualDebug.tsx', import.meta.url), 'utf8')
const page = ts.createSourceFile('ManualDebug.tsx', pageText, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
let powerNode
function visit(node) {
  if (ts.isVariableDeclaration(node) && node.name.getText(page) === 'setPower') powerNode = node
  ts.forEachChild(node, visit)
}
visit(page)
assert.ok(powerNode, 'test must execute the actual manual power handler')
const powerCode = ts.transpileModule(`const ${powerNode.getText(page)};`, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText

const log = (id, slot, siteId = 1) => ({ id, slot, siteId, ts: '', level: 'INFO', cat: 'dut', msg: `line ${id}` })
const source = fs.readFileSync(new URL('../src/lib/manualLogs.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const helpers = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
const { clearManualLogs, visibleManualLogs, mergeManualLogs } = helpers
let cases = 0

async function powerCase({ on = true, powered = false, ok = true, responseOn = on,
  cfgDirty = false, cfgApplying = false, cfgReady = true, mode = 'full_run' } = {}) {
  let cursor = { all: 10, channels: {} }
  let sharedClears = 0
  let requests = 0
  let settingsOpened = false
  const sim = { logs: [log(11, 6), log(12, 7), log(13, 8), log(14, 5)],
    manualState: { duts: [{ dut: 1, channel: 5, powerOn: powered }] } }
  let info = { duts: sim.manualState.duts }
  const context = { sim, info, API_BASE: '', t: x => x, setNotice: () => {},
    runState: { mode }, cfgDirty, cfgApplying, cfgReady,
    setShowSettings: open => { settingsOpened = open },
    setInfo: fn => { info = fn(info) },
    setClearId: () => { sharedClears++ },
    setLogClear: fn => { cursor = fn(cursor) }, ...helpers,
    fetch: async () => {
      requests++
      // New DUT and peer logs can arrive before the HTTP response.
      sim.logs.push(log(15, 6), log(16, 5))
      return { ok, status: 400, json: async () => ({ powerOn: responseOn }) }
    } }
  const handler = new Function(...Object.keys(context), `${powerCode}; return setPower;`)(...Object.values(context))
  const success = await handler(1, on)
  const blocked = on && mode !== 'power_only' && (!cfgReady || cfgDirty || cfgApplying)
  assert.equal(success, blocked ? false : ok)
  assert.equal(requests, blocked ? 0 : 1)
  assert.equal(settingsOpened, blocked)
  assert.equal(sharedClears, 0, 'powering one DUT must never clear the shared cursor')
  return { cursor, sim, requests }
}

const started = await powerCase()
assert.equal(started.cursor.all, 10)
assert.equal(started.cursor.channels[5], 14)
assert.equal(started.cursor.channels[6], undefined)
assert.deepEqual(visibleManualLogs(started.sim.logs, started.cursor).map(e => e.id), [11, 12, 13, 15, 16])
cases++
for (const options of [{ on: false, powered: true }, { ok: false }, { powered: true }, { responseOn: false }]) {
  const { cursor, sim } = await powerCase(options)
  assert.deepEqual(cursor, { all: 10, channels: {} })
  assert.equal(visibleManualLogs(sim.logs, cursor).length, 6)
  cases++
}
for (const options of [{ cfgDirty: true }, { cfgApplying: true }, { cfgReady: false }]) {
  const { cursor } = await powerCase(options)
  assert.deepEqual(cursor, { all: 10, channels: {} }, 'unapplied CFG must not send power or clear logs')
  cases++
}
for (const options of [{ cfgDirty: true, on: false }, { cfgDirty: true, mode: 'power_only' },
  { cfgReady: false, mode: 'power_only' }]) {
  const { requests } = await powerCase(options)
  assert.equal(requests, 1, 'power off and power-only operation remain available with a CFG draft')
  cases++
}

const sample = [log(11, 5), log(12, 6), log(13, 7), log(14, null, null), log(15, 5), log(16, 6)]
const cursor = { all: 10, channels: {} }
const one = clearManualLogs(cursor, 5, 14)
assert.deepEqual(cursor, { all: 10, channels: {} }, 'state updates must not mutate the old cursor')
assert.deepEqual(visibleManualLogs(sample, one).map(e => e.id), [12, 13, 14, 15, 16])
cases++
const two = clearManualLogs(one, 6, 15)
assert.deepEqual(visibleManualLogs(sample, two).map(e => e.id), [13, 14, 15, 16])
assert.equal(visibleManualLogs([log(11, 5, 2)], two).length, 1, 'SITE 2 must not use SITE 1 cursors')
cases++
assert.deepEqual(visibleManualLogs(sample, clearManualLogs(two, null, 15)).map(e => e.id), [16])
assert.equal(clearManualLogs(one, 5, 2).channels[5], 14, 'late responses must not move the cursor backwards')
cases++

// A full shared ring of rebooting DUT05 logs must not evict DUT06/07/08 views.
const flood = Array.from({ length: 50000 }, (_, i) => log(20000 + i, 5))
const caches = { '1:5': flood.slice(-5000), '1:6': [log(19, 6)],
  '1:7': [log(17, 7)], '1:8': [log(18, 8)], '2:5': [log(16, 5, 2)] }
const merged = mergeManualLogs(flood, caches, [5, 6, 7, 8, 6])
assert.equal(merged.length, 50003)
assert.equal(new Set(merged.map(e => e.id)).size, merged.length)
assert.deepEqual(merged.slice(0, 3).map(e => e.id), [17, 18, 19])
for (const ch of [6, 7, 8]) assert.equal(visibleManualLogs(merged, one).filter(e => e.slot === ch).length, 1)
cases++
assert.deepEqual(mergeManualLogs([], caches, [6, 7, 8]).map(e => e.id), [17, 18, 19])
assert.strictEqual(mergeManualLogs(flood, {}, [5]), flood)
cases++

// Exercise the real clear-button expression, not a copy of its implementation.
let clearExpression
function findClear(node) {
  if (ts.isJsxAttribute(node) && node.name.getText(page) === 'onClick'
      && node.parent.parent.parent.getText(page).includes("t('mdClearLog')")) {
    clearExpression = node.initializer.expression.getText(page)
  }
  ts.forEachChild(node, findClear)
}
findClear(page)
assert.ok(clearExpression)
const clearCode = ts.transpileModule(`const clearView = ${clearExpression};`, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
for (const [tab, expected] of [['dut-5', [12, 13, 14, 16]], ['dut-6', [11, 13, 14, 15]], ['all', []]]) {
  let state = cursor
  const context = { tab, manualLogs: sample, clearManualLogs,
    setLogClear: fn => { state = fn(state) } }
  new Function(...Object.keys(context), `${clearCode}; return clearView;`)(...Object.values(context))()
  assert.deepEqual(visibleManualLogs(sample, state).map(e => e.id), expected)
  cases++
}

// Stage deduplication runs after visibility filtering, so a new PL milestone
// remains visible even if the preceding run already reached PL.
let eventNode
function findEvents(node) {
  if (ts.isVariableDeclaration(node) && node.name.getText(page) === 'events') eventNode = node
  ts.forEachChild(node, findEvents)
}
findEvents(page)
const eventCode = ts.transpileModule(`const ${eventNode.getText(page)};`, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const stages = [log(11, 5), log(12, 6), log(16, 5)].map(e => ({ ...e, msg: 'preloader ready' }))
const visible = visibleManualLogs(stages, one)
const eventContext = { useMemo: fn => fn(), visibleLogs: visible, runState: null,
  runningDut: null, stageOf: () => 'pl', isBenign: () => false }
const events = new Function(...Object.keys(eventContext), `${eventCode}; return events;`)(...Object.values(eventContext))
assert.deepEqual(events.map(e => e.id), [12, 16])
cases++

console.log(`manual log isolation: ${cases} scenarios passed; real power/clear handlers, peers survive 50k boot lines`)
