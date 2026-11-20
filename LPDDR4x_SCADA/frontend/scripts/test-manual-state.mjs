import fs from 'node:fs'
import assert from 'node:assert/strict'
import ts from 'typescript'

const src = fs.readFileSync(new URL('../src/lib/manualState.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText
const { manualStatus, RUN_STATE_META, runElapsed } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
let cases = 0
for (const phase of ['idle', 'offline', 'wait_ready', 'cfg_sent', 'running', 'pass', 'fail', 'timeout']) {
  for (const powerOn of [false, true]) {
    for (const connected of [false, true]) {
      for (const serverOnline of [false, true]) {
        const run = { dut: 1, channel: 5, state: phase, detail: 'test_detail', sinceSec: 63,
          enteredAt: 100, active: ['wait_ready', 'cfg_sent', 'running'].includes(phase), connected }
        const st = { slot: 5, state: 'PASS', connected: true, progress: 100, failItem: 'stale',
          durationSec: 1, countdownSec: 0, successCount: 4, totalCount: 5, step: '-', testInfo: '' }
        const v = manualStatus({ dut: 1, channel: 5, line: 4, powerOn }, run, st, serverOnline, 200)
        assert.equal(v.connected, serverOnline && powerOn && connected)
        const expected = phase === 'pass' ? 'PASS' : ['fail', 'timeout'].includes(phase) ? 'FAIL'
          : !serverOnline ? 'OFFLINE' : run.active ? 'TESTING' : v.connected ? 'IDLE' : 'OFFLINE'
        assert.equal(v.state, expected)
        assert.equal(v.durationSec, run.active ? 100 : 63)
        assert.equal(v.failItem, expected === 'FAIL' ? 'test_detail' : undefined)
        if (expected === 'TESTING') assert.ok(v.progress < 100)
        assert.ok(RUN_STATE_META[phase])
        cases++
      }
    }
  }
}
assert.equal(RUN_STATE_META.running.color, 'var(--st-testing)')
assert.equal(RUN_STATE_META.offline.color, 'var(--st-offline)')
assert.equal(runElapsed({ sinceSec: 61, active: false, enteredAt: 100 }, 400), 61)
assert.equal(runElapsed({ sinceSec: 0, active: true, enteredAt: 500 }, 400), 0)
// Field startup has no DUTs in the general snapshot. Manual telemetry must work
// without a matching site/slot row, and must win over a stale general row.
const power = { dut: 1, channel: 5, line: 4, powerOn: true }
const running = { dut: 1, channel: 5, state: 'running', detail: '', sinceSec: 95,
  enteredAt: 100, active: true, connected: true, progress: 3, step: '测试运行中' }
const stale = { slot: 5, state: 'TESTING', connected: true, progress: 0, step: '-',
  durationSec: 0, countdownSec: 0, successCount: 0, totalCount: 0, testInfo: '' }
let progressCases = 0
for (const general of [undefined, stale, { ...stale, progress: 98 }]) {
  const status = manualStatus(power, running, general, true, 200)
  assert.equal(status.progress, 3)
  assert.equal(status.step, '测试运行中')
  progressCases++
}
for (const [value, expected] of [[0, 0], [37, 37], [100, 99], [-1, 0], [NaN, 0]]) {
  assert.equal(manualStatus(power, { ...running, progress: value }, stale, true, 200).progress, expected)
  progressCases++
}
for (const state of ['wait_ready', 'cfg_sent', 'idle', 'offline']) {
  assert.equal(manualStatus(power, { ...running, state }, stale, true, 200).progress, 0)
  progressCases++
}
assert.equal(manualStatus(power, { ...running, state: 'pass' }, undefined, true, 200).progress, 100)
// A new run's explicit zero clears the old run's progress; old backends still
// use general status if the optional manual progress fields are absent.
assert.equal(manualStatus(power, { ...running, runId: 2, progress: 0 }, { ...stale, progress: 89 }, true, 200).progress, 0)
const { progress: _progress, step: _step, ...legacyProgress } = running
assert.equal(manualStatus(power, legacyProgress, { ...stale, progress: 24 }, true, 200).progress, 24)
assert.equal(manualStatus(power, { ...running, dut: 2, channel: 6, progress: 8 }, undefined, true, 200).progress, 8)
progressCases += 4
// 已在运行的旧后端推送 state/enteredAt/sinceSec，没有 active；页面秒表仍须递增。
let elapsedCases = 0
for (const state of ['wait_ready', 'cfg_sent', 'running']) {
  const legacyRun = { dut: 1, state, detail: '', sinceSec: 63, enteredAt: 100 }
  assert.equal(runElapsed(legacyRun, 200), 100)
  assert.equal(runElapsed(legacyRun, 205), 105)
  assert.equal(runElapsed({ ...legacyRun, active: false }, 205), 63)
  assert.equal(runElapsed({ ...legacyRun, enteredAt: null }, 205), 63)
  elapsedCases += 4
}
for (const state of ['idle', 'offline', 'pass', 'fail', 'timeout']) {
  const frozenRun = { dut: 1, state, detail: '', sinceSec: 63, enteredAt: 100 }
  assert.equal(runElapsed(frozenRun, 200), 63)
  assert.equal(runElapsed(frozenRun, 205), 63)
  elapsedCases += 2
}
const indicatorSrc = fs.readFileSync(new URL('../src/lib/stateIndicator.ts', import.meta.url), 'utf8')
const indicatorJs = ts.transpileModule(indicatorSrc, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText
const { siteIndicator, STATE_COLOR } = await import(`data:text/javascript;base64,${Buffer.from(indicatorJs).toString('base64')}`)
for (const [states, expected] of [
  [[], 'OFFLINE'], [['OFFLINE'], 'OFFLINE'], [['TESTING', 'OFFLINE'], 'TESTING'],
  [['FAIL', 'TESTING'], 'FAIL'], [['PASS', 'PASS'], 'PASS'], [['PASS', 'IDLE'], 'IDLE'],
  [['IDLE', 'OFFLINE'], 'IDLE'],
]) assert.equal(siteIndicator(states), expected)
assert.equal(STATE_COLOR.OFFLINE, 'var(--st-offline)')
console.log(`manual state matrix: ${cases} cases passed; running yellow / offline grey / elapsed frozen`)
console.log('site aggregation: 7 combinations passed')
console.log(`elapsed compatibility: ${elapsedCases} assertions passed; legacy active phases tick / terminal phases freeze`)
console.log(`manual progress: ${progressCases} cases passed; no general DUT row / stale row / new run / bounds / legacy backend`)
