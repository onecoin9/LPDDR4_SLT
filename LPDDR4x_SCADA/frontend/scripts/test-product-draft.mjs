import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { buildSync } from 'esbuild'
import ts from 'typescript'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const file = path.join(os.tmpdir(), `slt-product-draft-${process.pid}.mjs`)
globalThis.location = { protocol: 'http:', host: '127.0.0.1' }
globalThis.localStorage = { getItem: () => null }
buildSync({ stdin: { resolveDir: root, contents: `
  export {default as ProductSettings, ProductDraftSession} from './src/sections/ProductSettings';
  export {default as ProductConfigEditor} from './src/sections/ProductConfigEditor';
  export {defaultProfiles, normalizeProfile, activeScreeningProfile} from './src/types/product';
  export {waitForPendingSettings} from './src/hooks/useAppSettings';
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
const tick = async () => { for (let i = 0; i < 5; i++) await Promise.resolve() }
const profile = (name, value) => ({ name, value })
function fixture(profiles = { Product: profile('Product', 0) }, name = 'Product') {
  const calls = []
  const persist = value => { const wait = deferred(); calls.push({ value: structuredClone(value), ...wait }); return wait.promise }
  const session = new m.ProductDraftSession(profiles, name, persist)
  return { session, calls, persist }
}

// Reproduce the real lost-edit sequence: save A, edit B, receive A, then leave.
{
  const { session, calls, persist } = fixture()
  session.edit(profile('Product', 'A'))
  const a = session.save()
  await tick()
  session.edit(profile('Product', 'B'))
  session.setSource({ Product: m.normalizeProfile(structuredClone(calls[0].value.Product)) }, persist)
  check(session.receive('Product').value, 'B', 'An older autosave response cannot replace a newer local draft')
  check(session.conflicted, false, 'A known autosave response is not treated as an external conflict')
  const b = session.save()
  check(session.save(), b, 'Manual save and unmount share the same pending revision')
  await tick()
  check(calls.length, 1, 'A newer revision waits for the older save to finish')
  calls[0].resolve()
  await a
  await tick()
  check(calls[1].value.Product.value, 'B', 'Leaving the page persists the latest draft after the old response')
  check(session.draft.value, 'B', 'An acknowledgement only marks its submitted revision saved')
  calls[1].resolve()
  await b
  await session.save()
  check(calls.length, 2, 'A clean draft does not cause duplicate saves')
}

// A save failure leaves the draft retryable, and does not poison the queue.
{
  const { session, calls } = fixture()
  session.edit(profile('Product', 1))
  const failed = session.save()
  const rejected = assert.rejects(failed, /disk failure/)
  await tick()
  calls[0].reject(new Error('disk failure'))
  await rejected
  const retry = session.save()
  await tick()
  check(calls[1].value.Product.value, 1, 'Failed revisions remain available for retry')
  calls[1].resolve()
  await retry
  session.edit(profile('Product', 2))
  const newer = session.save()
  await tick()
  calls[2].resolve()
  await newer
  check(session.draft.value, 2, 'Later edits can be saved after a failure')
}

// Switching products flushes the old draft without transplanting it into the new one.
{
  const { session, calls, persist } = fixture({ A: profile('A', 0), B: profile('B', 0) }, 'A')
  session.edit(profile('A', 11))
  const a = session.save()
  check(session.receive('B').name, 'B', 'Product selection immediately gets the selected product draft')
  session.edit(profile('B', 22))
  const b = session.save()
  await tick()
  session.setSource(calls[0].value, persist)
  check(session.receive('B').value, 22, 'An old product save cannot overwrite the selected product')
  calls[0].resolve()
  await a
  await tick()
  check(calls[1].value.A.value, 11, 'The next save preserves the previous product acknowledgement')
  check(calls[1].value.B.value, 22, 'The next save includes the latest selected product draft')
  calls[1].resolve()
  await b
}

// An external CFG import is adopted while clean; dirty conflicts are explicit.
{
  const { session, persist, calls } = fixture()
  session.setSource({ Product: profile('Product', 3) }, persist)
  check(session.receive('Product').value, 3, 'A clean draft adopts a configuration imported elsewhere')
  session.edit(profile('Product', 4))
  session.setSource({ Product: profile('Product', 5) }, persist)
  check(session.receive('Product').value, 4, 'An external import preserves a dirty local draft')
  check(session.conflicted, true, 'A dirty external update is reported as a conflict')
  await assert.rejects(session.save(), /external update/)
  check(calls.length, 0, 'Autosave and unmount cannot silently overwrite an external import')
  check(session.reload().value, 5, 'Reload explicitly adopts the external configuration')
  check(session.conflicted, false, 'Reload clears the conflict')
  session.edit(profile('Product', 6))
  session.setSource({ Product: profile('Product', 7) }, persist)
  session.receive('Product')
  session.acceptOverwrite()
  const overwrite = session.save()
  await tick()
  check(calls[0].value.Product.value, 6, 'Explicit overwrite saves the preserved draft')
  calls[0].resolve()
  await overwrite
}

// A conflict detected before a queued write starts blocks that write as well.
{
  const { session, calls, persist } = fixture({ A: profile('A', 0), B: profile('B', 0) }, 'A')
  session.edit(profile('A', 1))
  const a = session.save()
  session.receive('B')
  session.edit(profile('B', 2))
  const b = session.save()
  const rejected = assert.rejects(b, /external update/)
  await tick()
  session.setSource({ A: profile('A', 0), B: profile('B', 9) }, persist)
  session.receive('B')
  calls[0].resolve()
  await a
  await rejected
  check(calls.length, 1, 'Queued writes stop when a newer external configuration conflicts')
}

{
  const { session, calls } = fixture()
  session.edit(profile('Product', 1))
  session.forget('Product')
  await session.save()
  check(calls.length, 0, 'Unmount does not restore a product deleted by the user')
}

// Home's start barrier must also see B before B reaches the shared HTTP queue.
{
  const queue = { current: Promise.resolve() }, current = { current: null }, writes = []
  const persist = value => {
    const request = queue.current.then(async () => {
      const wait = deferred()
      writes.push({ value, ...wait })
      await wait.promise
      current.current = value
    })
    queue.current = request
    return request
  }
  const session = new m.ProductDraftSession({ Product: profile('Product', 0) }, 'Product', persist)
  session.edit(profile('Product', 'A'))
  const a = session.save()
  await tick()
  session.edit(profile('Product', 'B'))
  const b = session.save()
  let finished = false
  const startBarrier = m.waitForPendingSettings(queue, current).then(value => { finished = true; return value })
  writes[0].resolve()
  await a
  await tick()
  check(finished, false, 'Start waits for the final local draft, not just the first HTTP acknowledgement')
  check(writes[1].value.Product.value, 'B', 'The queued draft joins the shared settings queue before start')
  writes[1].resolve()
  await b
  check((await startBarrier).Product.value, 'B', 'Start receives the latest fully persisted product')
}

// Render the actual component: raw TReg profiles keep register units, and known
// basic CFG overrides are editable instead of being silently hidden in JSON.
{
  const p = structuredClone(Object.values(m.defaultProfiles())[0])
  p.timingSchema = 1
  p.params = [{ id: 1, name: 'TRCD', value: '8', checked: true },
    { id: 2, name: 'LogLevel', value: '2', checked: true },
    { id: 3, name: 'BadBlockMgmt', value: '1', checked: true },
    { id: 4, name: 'VDD2L(mV)', value: '0', checked: true }]
  p.cfgOverrides = { Density: 16, DieNum: 2, AgingTime: 50, PatternTest: 1, DvfsTest: 0, Mode: 0, LOG_TO_UART1: 1, Unknown: 12345 }
  const html = m.renderToStaticMarkup(m.createElement(m.ProductSettings, {
    profiles: { [p.name]: p }, productName: p.name, onSelectProduct() {}, onProfilesChange: async () => {},
  }))
  check(html.includes('测试板基础配置') || html.includes('继承机台基线'), false, 'No extra configuration section or internal baseline commentary')
  check(/aria-label="Density 配置值"[^>]*value="16"/.test(html), true, 'Imported Density is shown as the effective editable value')
  check(/aria-label="AgingTime 配置值"[^>]*value="50"/.test(html), true, 'Imported aging time is shown with the current product')
  check(html.includes('Unknown'), false, 'Arbitrary CFG keys are not exposed as editable configuration')
  check(html.includes('寄存器值') || html.includes('枚举值') || html.includes('0／1'), false, 'Unit placeholders (register value / enum / 0-1) are not displayed; only real units (Gb/min/mV/MT/s/ns)')
  check(html.includes('用户请求(ns)'), false, 'Raw register values do not inherit a misleading ns column header')
  check(html.includes('静默档') && html.includes('记录错误地址'), true, 'LogLevel and BadBlockMgmt have concrete usage descriptions')
  check(html.includes('保持该电压槽原值'), true, 'VDD2L explicitly documents the valid zero sentinel')
  check(Object.values(m.defaultProfiles())[0].params.some(row => row.name === 'LogLevel') &&
    Object.values(m.defaultProfiles())[0].params.some(row => row.name === 'BadBlockMgmt'), true,
  'Every product includes log-level and bad-block settings without requiring an import')
}

// Execute the actual button handlers with an imported disabled MemTester plan.
// Editing voltage and saving must not silently replace its original stage flags.
{
  const imported = structuredClone(Object.values(m.defaultProfiles())[0])
  imported.pl1Enabled = false
  imported.pl2Enabled = false
  delete imported.pl2.screeningVersion
  const { session, calls } = fixture({ [imported.name]: imported }, imported.name)
  const changed = { ...imported, params: imported.params.map(row => row.name === 'VDD1(mV)' ? { ...row, value: '1800', checked: true } : row) }
  session.edit(changed)
  const submitted = []
  const scope = { draft: changed, draftRef: { current: changed }, session, productName: imported.name,
    API_BASE: '', window: { confirm: () => true }, t: key => key,
    activeScreeningProfile: m.activeScreeningProfile,
    previewProduct: async candidate => { submitted.push(candidate); return { valid: true } },
    setChecking() {}, setPlanOpen() {}, setPlanError() {}, setPlan() {}, setSaving() {},
    setSavedFlash() {}, setDraftConflict() {}, setTimeout() {},
    setDraft(candidate) { session.edit(candidate); scope.draftRef.current = session.draft },
  }
  const source = fs.readFileSync(path.join(root, 'src/sections/ProductSettings.tsx'), 'utf8')
  const ast = ts.createSourceFile('ProductSettings.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  function handler(name) {
    let found
    const visit = node => { if (ts.isVariableDeclaration(node) && node.name.getText(ast) === name) found = node.initializer; ts.forEachChild(node, visit) }
    visit(ast)
    assert.ok(found, name + ' exists')
    return new Function('scope', `with (scope) { return (${found.getText(ast)}) }`)(scope)
  }
  await handler('handlePreview')()
  const save = handler('handleSave')()
  await tick()
  calls[0].resolve()
  await save
  check(submitted.every(p => !p.pl1Enabled && !p.pl2Enabled && p.pl2.screeningVersion === undefined), true,
    'Preview and manual Save preserve imported stage flags and screening semantics')
  check(calls[0].value[imported.name].pl2Enabled, false, 'The persisted voltage edit keeps MemTester disabled')
  const editor = m.renderToStaticMarkup(m.createElement(m.ProductConfigEditor, {
    profile: changed, initialCfgText: 'LOGLEVEL=1\n', initialError: '',
    settingsRevision: 'r1', onImported: () => {}, onClose() {},
  }))
  const text = editor.match(/<textarea[^>]*>([\s\S]*?)<\/textarea>/)[1]
    .replaceAll('&quot;', '"').replaceAll('&#x27;', "'").replaceAll('&lt;', '<').replaceAll('&gt;', '>').replaceAll('&amp;', '&')
  check(text.includes('LOGLEVEL=1'), true, 'Opening the CFG editor shows the cfg text compiled from the current draft')
}
console.log(`Product drafts and board settings: ${count} checks passed`)
