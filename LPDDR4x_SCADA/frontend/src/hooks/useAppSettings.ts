import { useEffect, useRef, useState } from 'react'
import { API_BASE } from '@/hooks/useServer'
import { apiErrorText } from '@/lib/productPlan'
import type { ThemeId } from '@/lib/theme'
import type { Lang } from '@/lib/i18n'
import type { IoControl, HandlerSettings } from '@/types/dut'
import type { ProductProfile } from '@/types/product'
import type { RuntimePolicy } from '@/lib/runtimePolicy'
import { pendingSettingsSaves, onSettingsSaveError, trackSettingsSave } from '@/lib/settingsPending'

export interface AppSettings {
  schemaVersion: 1
  basic: { language: Lang; theme: ThemeId; logPath: string }
  ioControl: IoControl
  handler: Pick<HandlerSettings, 'rx_port' | 'tx_host' | 'tx_port'>
  runtimePolicy: RuntimePolicy
  products: Record<string, ProductProfile>
  browserMigrationPending: ('basic' | 'ioControl' | 'products')[]
}
export interface SettingsState {
  valid: boolean; error: string | null; path: string; revision: string
  settings: AppSettings; handlerStatus: HandlerSettings
}
export type SettingsPatch = Partial<Omit<AppSettings, 'basic' | 'handler' | 'ioControl'>> & {
  basic?: Partial<AppSettings['basic']>; handler?: Partial<AppSettings['handler']>; ioControl?: Partial<IoControl>
}

// Wait again if another save was queued while the previous one was in flight.
// Product editors must enqueue their final draft when unmounting; a future,
// untriggered debounce is not an acknowledged save.
export async function waitForPendingSettings<T>(queue: { current: Promise<unknown> }, current: { current: T }) {
  for (;;) {
    const pending = queue.current
    await Promise.all([pending, ...pendingSettingsSaves()])
    if (pending === queue.current && pendingSettingsSaves().length === 0) return current.current
  }
}

export default function useAppSettings(seed: Pick<AppSettings, 'basic' | 'ioControl' | 'products'>,
  onApply: (value: AppSettings, revision: string) => void) {
  const [state, setState] = useState<SettingsState | null>(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const current = useRef<SettingsState | null>(null)
  const apply = useRef(onApply); apply.current = onApply
  const initial = useRef(seed)
  const browserSeed = useRef<{ io: boolean; products: boolean; log: boolean } | null>(null)
  if (browserSeed.current === null) {
    try {
      const cached = JSON.parse(localStorage.getItem('slt-products') || 'null')
      browserSeed.current = { io: !!localStorage.getItem('slt-io-control'),
        log: !!localStorage.getItem('slt-log-path'),
        products: !!cached && typeof cached === 'object' && !Array.isArray(cached) && Object.keys(cached).length > 0 }
    } catch { browserSeed.current = { io: false, products: false, log: false } }
  }
  const queue = useRef<Promise<unknown>>(Promise.resolve())
  const request = async (path: string, body?: unknown, revision?: string): Promise<SettingsState> => {
    const response = await fetch(API_BASE + path, body === undefined ? undefined : {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...(revision ? { 'If-Match': revision } : {}) },
      body: JSON.stringify(body),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(apiErrorText(result))
    if (!result.valid) { setState(result); throw new Error(result.error || 'Invalid settings file') }
    current.current = result; setState(result); apply.current(result.settings, result.revision)
    return result
  }
  const enqueue = <T,>(action: () => Promise<T>) => {
    const next = queue.current.catch(() => {}).then(async () => {
      setSaving(true); setError('')
      try { return await action() }
      catch (e) {
        setError(e instanceof Error ? e.message : String(e))
        if (current.current) apply.current(current.current.settings, current.current.revision)
        throw e
      } finally { setSaving(false) }
    })
    queue.current = next
    return trackSettingsSave(next)
  }
  const refresh = () => enqueue(() => request('/api/settings'))
  const reload = () => enqueue(() => {
    const path = current.current?.path || state?.path
    return path ? request('/api/settings/select', { path }) : request('/api/settings')
  })
  const patch = (value: SettingsPatch) => enqueue(() => {
    if (!current.current) throw new Error('Settings not loaded')
    return request('/api/settings', value, current.current.revision)
  })
  const select = (path: string) => enqueue(() => request('/api/settings/select', { path }))
  const selectProduct = (product: string) => enqueue(async () => {
    if (!current.current) throw new Error('Settings not loaded')
    const response = await fetch(API_BASE + '/api/products/select', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product, settingsRevision: current.current.revision }),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(apiErrorText(result))
    if (typeof result.product !== 'string' || typeof result.settingsRevision !== 'string') throw new Error('Invalid product selection response')
    const updated = { ...current.current, revision: result.settingsRevision }
    current.current = updated; setState(updated); apply.current(updated.settings, updated.revision)
    return result as { product: string; settingsRevision: string }
  })
  const flush = () => waitForPendingSettings(queue, current)

  useEffect(() => onSettingsSaveError(message => setError(message)), [])

  useEffect(() => {
    void enqueue(async () => {
      const result = await request('/api/settings')
      const pending = result.settings.browserMigrationPending
      if (pending.length) {
        const migration: SettingsPatch = { browserMigrationPending: [] }
        if (pending.includes('basic')) migration.basic = { ...initial.current.basic,
          logPath: browserSeed.current?.log ? initial.current.basic.logPath : result.settings.basic.logPath }
        if (pending.includes('ioControl') && browserSeed.current?.io) migration.ioControl = initial.current.ioControl
        if (pending.includes('products')) migration.products = { ...result.settings.products,
          ...(browserSeed.current?.products || !Object.keys(result.settings.products).length ? initial.current.products : {}) }
        await request('/api/settings', migration, result.revision)
      }
    }).catch(() => {})
    const onChange = () => { void refresh().catch(() => {}) }
    window.addEventListener('slt-settings-changed', onChange)
    return () => window.removeEventListener('slt-settings-changed', onChange)
    // Initialization is intentionally once per mount; refs hold the latest consumer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return { state, error, saving, ready: state?.valid === true, patch, select, selectProduct, reload, refresh, flush }
}
