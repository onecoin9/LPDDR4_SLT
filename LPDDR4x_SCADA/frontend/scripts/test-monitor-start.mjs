import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { buildSync } from 'esbuild'
import ts from 'typescript'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const file = path.join(os.tmpdir(), `slt-monitor-start-${process.pid}.mjs`)
globalThis.location = { protocol: 'http:', host: '127.0.0.1' }
globalThis.localStorage = { getItem: () => null }
buildSync({ stdin: { resolveDir: root, contents: `
  export * from './src/lib/testStart';
  export {waitForPendingSettings} from './src/hooks/useAppSettings';
  export * from './src/lib/settingsPending';
  export {default as SidePanel} from './src/sections/SidePanel';
  export {default as SiteDetail} from './src/sections/SiteDetail';
  export {createElement} from 'react';
  export {renderToStaticMarkup} from 'react-dom/server';
` }, outfile: file, bundle: true, platform: 'node', format: 'esm', jsx: 'automatic',
  define: { 'import.meta.env.DEV': 'false' },
  banner: { js: "import {createRequire} from 'node:module';const require=createRequire(import.meta.url);" }, logLevel: 'silent' })
const m = await import(pathToFileURL(file).href)
fs.unlinkSync(file)
let count = 0
function check(actual, expected, message) { assert.deepEqual(actual, expected, message); count++ }
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
const response = body => ({ json: async () => body })

const availability = { ready: true, saving: false, error: '', submitting: false, hasProduct: true }
check(m.startBlockedReason(availability), null, 'Ready controls accept a start')
for (const [change, reason] of [[{ ready: false }, 'loading'], [{ saving: true }, 'saving'],
  [{ error: 'disk failure' }, 'settings_error'], [{ submitting: true }, 'submitting'], [{ hasProduct: false }, 'product']]) {
  check(m.startBlockedReason({ ...availability, ...change }), reason, 'Every blocked start has an explicit reason')
}

function starterFixture(post) {
  const calls = [], busy = [], errors = [], logs = []
  let revision = 'saved-r1', starts = 0
  const starter = m.createTestStarter({ config: () => ({ product: 'Chosen', workOrder: 'WO', lotNo: 'LOT', operator: 'op' }),
    ioControl: () => ({ boardInit: 'poweron' }), revision: () => revision,
    updateRevision: value => { revision = value },
    post: async (url, body) => { calls.push({ url, body }); return post(url, body) },
    busy: value => busy.push(value), error: value => errors.push(value), log: value => logs.push(value),
    started: () => { starts++ }, messages: () => ({ noProduct: 'choose product', noTarget: 'no eligible channel', failed: 'start failed' }),
  })
  return { starter, calls, busy, errors, logs, revision: () => revision, starts: () => starts }
}
const profile = { name: 'Chosen', params: [{ name: 'VDD1(mV)', value: '1800', checked: true }] }
const ok = starterFixture(async url => response(url === '/api/config' ? { settingsRevision: 'compiled-r2' } : { started: [5, 6] }))
check(await ok.starter(profile), true, 'A valid config is followed by a test-start request')
check(ok.calls.map(x => x.url), ['/api/config', '/api/test/start'], 'Configuration must precede the start command')
check(ok.calls[0].body.profile, profile, 'The submitted profile is the caller-selected saved profile')
check(ok.calls[0].body.settingsRevision, 'saved-r1', 'Configuration uses the saved settings revision')
check(ok.revision(), 'compiled-r2', 'A successful config response advances the revision immediately')
check(ok.starts(), 1, 'Only a nonempty accepted target list starts the session clock')
check(ok.busy, [true, false], 'Submission controls always leave busy state')
await ok.starter(profile, 2)
check(ok.calls[3].body, { site: 2 }, 'Single-site entry uses the same submission path')
check(ok.calls[2].body.settingsRevision, 'compiled-r2', 'A later start does not reuse the pre-config revision')

const rejected = starterFixture(async () => { throw new Error('VDD1: invalid value') })
check(await rejected.starter(profile), false, 'Config failures refuse test-start')
check(rejected.calls.length, 1, 'No start packet follows a config error')
check(rejected.errors.at(-1), 'VDD1: invalid value', 'The API failure remains visible outside the log filter')
check(rejected.logs.at(-1), 'VDD1: invalid value', 'The same failure is retained in the log')
const empty = starterFixture(async () => response({ started: [] }))
check(await empty.starter(profile), false, 'An empty target list does not look like a successful start')
check(empty.errors.at(-1), 'no eligible channel', 'No-target starts explain why no configuration is transmitted to a DUT')
check(empty.starts(), 0, 'No-target starts do not reset elapsed time')
const waitConfig = deferred()
const pending = starterFixture(async url => url === '/api/config' ? waitConfig.promise : response({ started: [5] }))
const first = pending.starter(profile)
check(await pending.starter(profile, 1), false, 'Repeated all-site/site clicks share a submission lock')
check(pending.calls.length, 1, 'Duplicate clicks do not double-submit config')
waitConfig.resolve(response({ settingsRevision: 'r2' })); await first
check(pending.calls.length, 2, 'Exactly one start follows the one config request')

const a = deferred(), b = deferred()
const queue = { current: a.promise }, settings = { current: { version: 'old' } }
let flushed = false
const flushing = m.waitForPendingSettings(queue, settings).then(value => { flushed = true; return value })
queue.current = a.promise.then(() => b.promise.then(() => { settings.current = { version: 'latest' } }))
a.resolve(); await Promise.resolve(); await Promise.resolve()
check(flushed, false, 'Flush waits for saves appended while an earlier request was in flight')
b.resolve()
check(await flushing, { version: 'latest' }, 'Flush returns the latest acknowledged settings object')
await assert.rejects(m.waitForPendingSettings({ current: Promise.reject(new Error('save rejected')) }, settings), /save rejected/); count++

// The product editor serializes draft A/B locally before B reaches the HTTP
// settings queue. Both queues must be drained, including across route changes.
{
  const first = deferred(), second = deferred()
  const queue = { current: first.promise }
  const current = { current: 'before' }
  const localB = m.trackSettingsSave(first.promise.then(async () => {
    queue.current = second.promise.then(() => { current.current = 'draft B' })
    await queue.current
  }))
  let done = false
  const flush = m.waitForPendingSettings(queue, current).then(value => { done = true; return value })
  first.resolve()
  for (let i = 0; i < 8; i++) await Promise.resolve()
  check(done, false, 'Flush cannot finish between local draft A and draft B HTTP saves')
  second.resolve()
  check(await flush, 'draft B', 'The cross-queue barrier returns only the final acknowledged draft')
  await localB
  check(m.pendingSettingsSaves().length, 0, 'Completed drafts leave no stale route-change barrier')
  const errors = [], failed = deferred()
  const unsubscribe = m.onSettingsSaveError(message => errors.push(message))
  const request = m.trackSettingsSave(failed.promise)
  const flushed = m.waitForPendingSettings({ current: Promise.resolve() }, current)
  const reject = assert.rejects(flushed, /draft conflict/)
  failed.reject(new Error('draft conflict')); await reject
  await assert.rejects(request, /draft conflict/)
  check(errors, ['draft conflict'], 'Draft-only failures remain visible after the product page closes')
  unsubscribe()
}

// Execute the real Home callback with deferred settings saves. This checks the
// integration: no stale profile can be captured before the final save resolves.
const source = fs.readFileSync(path.join(root, 'src/pages/Home.tsx'), 'utf8')
const ast = ts.createSourceFile('Home.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
let declaration
function visit(node) { if (ts.isVariableDeclaration(node) && node.name.getText(ast) === 'handleStart') declaration = node.initializer; ts.forEachChild(node, visit) }
visit(ast); assert.ok(declaration)
const callback = ts.transpileModule(`const handleStart = ${declaration.getText(ast)}; return handleStart;`,
  { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText
const prep = [], prepErrors = [], submitted = [], refreshed = []
const saved = deferred()
const lock = { current: false }
const sim = { config: { product: 'Chosen' }, setSettingsRevision: value => submitted.push({ revision: value }),
  startAll: async value => submitted.push({ profile: value }), startSite: async (site, value) => submitted.push({ site, profile: value }) }
sim.getConfig = () => sim.config
const appSettings = { flush: () => saved.promise, refresh: async () => refreshed.push(true) }
const handleStart = new Function('startLock', 'setPreparingStart', 'setPreparationError', 'appSettings', 'sim', 't', callback)(
  lock, v => prep.push(v), v => prepErrors.push(v), appSettings, sim, k => k)
const homeStart = handleStart()
await handleStart(3)
check(submitted, [], 'Home sends nothing before settings persistence is acknowledged')
const latest = { ...profile, params: [{ name: 'VDD1(mV)', value: '1900', checked: true }] }
saved.resolve({ valid: true, revision: 'latest-r3', settings: { products: { Chosen: latest } } })
await homeStart
check(submitted, [{ revision: 'latest-r3' }, { profile: latest }], 'Home chooses the persisted product returned by flush')
check(refreshed.length, 1, 'Home refreshes settings after config may advance its revision')
check(lock.current, false, 'Home releases its lock after settings refresh')

// Product selection is a persisted operation, without a configuration/start
// command. A route change must wait for this before choosing a manual product.
function homeCallback(name, args) {
  let callback
  function find(node) { if (ts.isVariableDeclaration(node) && node.name.getText(ast) === name) callback = node.initializer; ts.forEachChild(node, find) }
  find(ast); assert.ok(callback)
  const js = ts.transpileModule(`return ${callback.getText(ast)};`, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText
  return new Function(...Object.keys(args), js)(...Object.values(args))
}
{
  const reply = deferred(), choices = [], errors = [], selectionPending = { current: 0 }
  const sim = { value: { product: 'Old', lotNo: 'old lot' }, revision: '', getConfig() { return this.value },
    setConfig(value) { this.value = value }, setSettingsRevision(value) { this.revision = value } }
  const select = homeCallback('handleSelectProduct', { selectionPending, setPreparationError: value => errors.push(value),
    appSettings: { selectProduct: name => { choices.push(name); return m.trackSettingsSave(reply.promise) } }, sim, t: key => key })
  const selecting = select('New')
  check(sim.value.product, 'Old', 'Home does not claim a product selection until the server accepts it')
  sim.value.lotNo = 'edited meanwhile'
  let readyForManual = false
  const navigating = m.waitForPendingSettings({ current: Promise.resolve() }, { current: {} }).then(() => { readyForManual = true })
  await Promise.resolve()
  check(readyForManual, false, 'Switching to manual waits for the pending product selection')
  reply.resolve({ product: 'New', settingsRevision: 'new-r4' })
  await selecting; await navigating
  check(sim.value, { product: 'New', lotNo: 'edited meanwhile' }, 'Selection preserves other fields edited while waiting')
  check(sim.revision, 'new-r4', 'The accepted selection revision replaces the previous one')
  check(selectionPending.current, 0, 'The selection lock always clears')
  const failure = homeCallback('handleSelectProduct', { selectionPending, setPreparationError: value => errors.push(value),
    appSettings: { selectProduct: async () => { throw new Error('Product removed') } }, sim, t: key => key })
  await failure('Deleted')
  check(errors.at(-1), 'Product removed', 'A rejected selection is visibly explained')
  check(sim.value.product, 'New', 'A rejected selection cannot change the last confirmed product')
}
{
  // Execute useServer's real setter without mounting a UI. React effects may no
  // longer run after leaving Home, so persistence must happen in the setter.
  const code = fs.readFileSync(path.join(root, 'src/hooks/useServer.ts'), 'utf8')
  const ast = ts.createSourceFile('useServer.ts', code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  let setter
  function find(node) { if (ts.isVariableDeclaration(node) && node.name.getText(ast) === 'setConfig') setter = node.initializer; ts.forEachChild(node, find) }
  find(ast); assert.ok(setter)
  const js = ts.transpileModule(`return ${setter.getText(ast)};`, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText
  const writes = [], configRef = { current: {} }
  const setConfig = new Function('configRef', 'localStorage', 'setConfigState', js)(configRef,
    { setItem: (key, value) => writes.push({ key, value }) }, () => {})
  setConfig({ product: 'New', lotNo: 'L' })
  check(JSON.parse(writes[0].value).product, 'New', 'Accepted product selection is durable even after Home unmounts')
  check(configRef.current.product, 'New', 'Subsequent start reads the same confirmed selection immediately')
}
{
  // A selection ACK cannot bless a stale library with a newer revision. Execute
  // the real hook callback and simulate an external product update before POST.
  const code = fs.readFileSync(path.join(root, 'src/hooks/useAppSettings.ts'), 'utf8')
  const ast = ts.createSourceFile('useAppSettings.ts', code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  let selecting
  function find(node) { if (ts.isVariableDeclaration(node) && node.name.getText(ast) === 'selectProduct') selecting = node.initializer; ts.forEachChild(node, find) }
  find(ast); assert.ok(selecting)
  const js = ts.transpileModule(`return ${selecting.getText(ast)};`, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText
  const current = { current: { revision: 'r1', settings: { products: { New: { value: 'old' } } } } }
  const posts = [], applied = []
  const select = new Function('enqueue', 'current', 'fetch', 'API_BASE', 'apiErrorText', 'setState', 'apply', js)(
    action => action(), current, async (url, options) => {
      const body = JSON.parse(options.body); posts.push({ url, body })
      return body.settingsRevision === 'r2'
        ? { ok: true, json: async () => ({ product: 'New', settingsRevision: 'r3' }) }
        : { ok: false, json: async () => ({ error: 'Settings changed externally' }) }
    }, '', value => value.error, () => {}, { current: value => applied.push(value) })
  await assert.rejects(select('New'), /changed externally/); count++
  check(posts[0].body, { product: 'New', settingsRevision: 'r1' }, 'Selection carries the revision of the products currently loaded')
  check(current.current.revision, 'r1', 'A selection conflict cannot bless an old library with a new revision')
  check(applied.length, 0, 'Conflict responses never replace the acknowledged settings')
  current.current = { revision: 'r2', settings: { products: { New: { value: 'external update' } } } }
  await select('New')
  check(current.current.revision, 'r3', 'After refreshing products the same selection can succeed')
  check(current.current.settings.products.New.value, 'external update', 'The refreshed library remains authoritative')
}

const side = m.renderToStaticMarkup(m.createElement(m.SidePanel, { duts: [], logs: [], products: ['Chosen'],
  config: sim.config, onConfigChange() {}, onImportProfile() {}, sessionElapsed: 0, totalSuccess: 0,
  totalRuns: 0, siteFilter: null, slotFilter: null, onStart() {}, onStop() {},
  startDisabled: true, startHint: 'Saving configuration', startError: 'VDD1 invalid' }))
check(/<button[^>]*disabled=""[^>]*aria-describedby="monitor-start-status"/.test(side), true, 'The displayed confirm button is disabled while settings are pending')
check(side.includes('role="status"') && side.includes('Saving configuration'), true, 'The reason is visible without hovering or changing log filters')
check(side.includes('role="alert"') && side.includes('VDD1 invalid'), true, 'Start failures have their own visible alert')
const site = m.renderToStaticMarkup(m.createElement(m.SiteDetail, { site: { id: 1, duts: [] }, engineer: true,
  selectedSlot: null, onSelectSlot() {}, onStartSite() {}, onStopSite() {}, dutLogs: {}, startDisabled: true, startHint: 'Saving configuration' }))
check(/<button[^>]*disabled=""[^>]*title="Saving configuration"/.test(site), true, 'The site entry is guarded by the same settings state')
console.log(`Monitor start: ${count} checks passed; queue/profile/revision/order/errors/duplicate clicks/visible controls`)
