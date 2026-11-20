import fs from 'node:fs'
import assert from 'node:assert/strict'
import ts from 'typescript'

const src = fs.readFileSync(new URL('../src/lib/manualProductConfig.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText
const { manualRuntimeSettings, manualConfigError, draftIsPreserved, syncManualProduct } = await import(
  `data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)

// Old session exports must not restore an independent CFG source.
const imported = manualRuntimeSettings({ board_host: '192.168.50.230', local_ip: '192.168.50.30',
  log_dir: 'C:\\logs', run_mode: 'full_run', ready_timeout_sec: 180, test_timeout_sec: 0,
  dut_channels: [5, 6, 7, 8], dut_lines: [4, 5, 6, 7],
  cfgContent: 'Freq=1600', cfgFile: 'C:\\old.cfg', cfg_file: 'C:\\old.cfg',
  cfgSource: 'file', cfgProduct: 'stale', settingsRevision: 'old', custom: true })
assert.deepEqual(imported.updates, { boardHost: '192.168.50.230', localIp: '192.168.50.30',
  logDir: 'C:\\logs', runMode: 'full_run', readyTimeoutSec: 180, testTimeoutSec: 0,
  dutChannels: [5, 6, 7, 8], dutLines: [4, 5, 6, 7] })
assert.equal(imported.skipped, 7)
assert.throws(() => manualRuntimeSettings(null))
assert.throws(() => manualRuntimeSettings([]))

// Backend validation errors remain readable, including line/key diagnostics.
assert.equal(manualConfigError({ errors: [{ line: 7, key: 'UnknownKey', message: 'Unsupported key: UnknownKey' },
  { msg: 'TReg: invalid field' }] }), 'Unsupported key: UnknownKey\nTReg: invalid field')
assert.equal(manualConfigError({ unknownKeys: ['Wrong'] }), '{"unknownKeys":["Wrong"]}')
assert.equal(manualConfigError('Product changed; refresh first'), 'Product changed; refresh first')
assert.equal(manualConfigError({ valid: false, errors: [{ code: 'cfg_import', field: 'BadKey',
  messageZh: 'Unsupported CFG key; nothing saved', messageEn: 'Unsupported CFG key; nothing saved' }], warnings: [] }),
  'BadKey: Unsupported CFG key; nothing saved')

// 2026-11-18 契约：保存写回用户原文。已应用的草稿在服务器编译结果未变时保持干净，
// 之后的新编辑、服务器端产品变更或从未应用（null）都不算 preserved。
assert.equal(draftIsPreserved('Freq=1600 # 注释', { text: 'Freq=1600 # 注释', canonical: 'Freq=1600\n' }, 'Freq=1600\n'), true)
assert.equal(draftIsPreserved('Freq=3200', { text: 'Freq=1600 # 注释', canonical: 'Freq=1600\n' }, 'Freq=1600\n'), false)
assert.equal(draftIsPreserved('Freq=1600 # 注释', { text: 'Freq=1600 # 注释', canonical: 'Freq=1600\n' }, 'Freq=3733\n'), false)
assert.equal(draftIsPreserved('Freq=1600', null, 'Freq=1600\n'), false)

const messages = { noProduct: 'no product', changed: 'selection changed' }
async function selectionCase(preferred, serverProduct, library, selectError = null) {
  const calls = []
  const local = []
  const product = await syncManualProduct(preferred, async (path, body) => {
    calls.push({ path, body })
    if (path.endsWith('/context')) return { product: serverProduct }
    if (path === '/api/products') return library
    if (path.endsWith('/select')) {
      if (selectError) throw selectError
      return { product: body.product, settingsRevision: 'revision' }
    }
    assert.fail(`Unexpected endpoint: ${path}`)
  }, value => local.push(value), messages)
  assert.deepEqual(local, [product])
  assert.deepEqual(calls.map(call => call.path), ['/api/products/context', '/api/products', '/api/products/select'])
  assert.deepEqual(calls.at(-1).body, { product })
  return product
}
assert.equal(await selectionCase('B', 'A', { A: {}, B: {} }), 'B', 'current browser selection must reach backend before CFG read')
assert.equal(await selectionCase('DELETED', 'B', { A: {}, B: {} }), 'B', 'a removed local product must use current server selection')
assert.equal(await selectionCase('', 'B', { A: {}, B: {} }), 'B', 'after waiting for cross-page saves, server selection wins')
assert.equal(await selectionCase('DELETED', 'REMOVED', { A: {} }), 'A', 'match startup fallback when both old names were removed')
assert.equal(await selectionCase('__proto__', 'B', { A: {}, B: {} }), 'B', 'prototype names are not library entries')
await assert.rejects(selectionCase('B', 'A', { A: {}, B: {} }, new Error('select denied')), /select denied/)
await assert.rejects(syncManualProduct('A', async path => path.endsWith('/context') ? { product: 'A' } : {},
  () => assert.fail('empty library must not update local selection'), messages), /no product/)
await assert.rejects(syncManualProduct('A', async path => path.endsWith('/context') ? { product: 'A' }
  : path.endsWith('/select') ? { product: 'WRONG' } : { A: {} },
  () => assert.fail('mismatched acknowledgement must not update local selection'), messages), /selection changed/)
await assert.rejects(syncManualProduct('A', async () => { throw new Error('offline') },
  () => assert.fail('offline server must not update local selection'), messages), /offline/)
console.log('manual product CFG: runtime import isolation, validation, pending edits and shared product selection passed')
