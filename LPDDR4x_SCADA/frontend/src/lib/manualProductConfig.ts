// Manual runtime settings and product CFG have different save endpoints.
// Old session JSON must not turn an imported CFG into a hidden override.
export function manualRuntimeSettings(input: unknown) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new Error('Expected a settings object')
  }
  const aliases: Record<string, string> = {
    board_host: 'boardHost', local_ip: 'localIp', log_dir: 'logDir',
    run_mode: 'runMode', ready_timeout_sec: 'readyTimeoutSec',
    test_timeout_sec: 'testTimeoutSec', dut_channels: 'dutChannels', dut_lines: 'dutLines',
  }
  const allowed = new Set(['boardHost', 'localIp', 'logDir', 'runMode',
    'readyTimeoutSec', 'testTimeoutSec', 'dutChannels', 'dutLines'])
  const updates: Record<string, unknown> = {}
  let skipped = 0
  for (const [key, value] of Object.entries(input)) {
    const target = aliases[key] ?? key
    if (allowed.has(target)) updates[target] = value
    else skipped++
  }
  return { updates, skipped }
}

export function manualConfigError(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(manualConfigError).filter(Boolean).join('\n')
  if (detail && typeof detail === 'object') {
    const value = detail as Record<string, unknown>
    const messages = ['message', 'msg', 'detail', 'errors'].map(key => value[key])
      .filter(item => item != null).map(manualConfigError).filter(Boolean)
    if (!messages.length) {
      for (const item of [value.messageZh, value.messageEn]) {
        if (typeof item === 'string' && item.length > 0 && !messages.includes(item)) messages.push(item)
      }
    }
    if (messages.length) return `${typeof value.field === 'string' ? `${value.field}: ` : ''}${messages.join('\n')}`
    return JSON.stringify(detail)
  }
  return detail == null ? '' : String(detail)
}

// 2026-11-18 契约：CFG 文件保存用户编辑原文，不再用编译产物回填编辑框。
// applied 记录最近一次成功应用的原文与当时的编译产物；草稿等于该原文且服务器
// 编译结果未再变化时，草稿语义已在产品档案中——保留字面内容、不阻塞完整运行。
export function draftIsPreserved(draft: string,
  applied: { text: string; canonical: string } | null, incomingCanonical: string): boolean {
  return !!applied && draft === applied.text && applied.canonical === incomingCanonical
}

// Validate browser selection against the current library before persisting it.
// Deleted browser entries must not resurrect an old, independent product.
export async function syncManualProduct(preferred: string,
  request: (path: string, body?: Record<string, unknown>) => Promise<unknown>,
  updateLocal: (product: string) => void,
  messages: { noProduct: string; changed: string }): Promise<string> {
  const [context, rawLibrary] = await Promise.all([
    request('/api/products/context'), request('/api/products'),
  ])
  const library = rawLibrary && typeof rawLibrary === 'object' && !Array.isArray(rawLibrary)
    ? rawLibrary as Record<string, unknown> : {}
  const serverProduct = context && typeof context === 'object' && 'product' in context
    ? String(context.product ?? '') : ''
  const contains = (name: string) => Object.hasOwn(library, name)
  const product = contains(preferred) ? preferred : contains(serverProduct)
    ? serverProduct : Object.keys(library)[0]
  if (!product) throw new Error(messages.noProduct)
  const selected = await request('/api/products/select', { product })
  if (!selected || typeof selected !== 'object' || !('product' in selected) || selected.product !== product) {
    throw new Error(messages.changed)
  }
  updateLocal(product)
  return product
}
