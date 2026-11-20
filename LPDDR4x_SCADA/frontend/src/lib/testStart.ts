import type { IoControl, SessionConfig } from '@/types/dut'

export type StartBlockedReason = 'loading' | 'saving' | 'settings_error' | 'submitting' | 'product' | null

export function startBlockedReason(value: {
  ready: boolean; saving: boolean; error: string; submitting: boolean; hasProduct: boolean
}): StartBlockedReason {
  if (value.submitting) return 'submitting'
  if (value.error) return 'settings_error'
  if (!value.ready) return 'loading'
  if (value.saving) return 'saving'
  if (!value.hasProduct) return 'product'
  return null
}

interface StartOptions {
  config: () => SessionConfig
  ioControl: () => IoControl
  revision: () => string
  updateRevision: (revision: string) => void
  post: (path: string, body: unknown) => Promise<Response>
  busy: (value: boolean) => void
  error: (message: string) => void
  log: (message: string) => void
  started: () => void
  messages: () => { noProduct: string; noTarget: string; failed: string }
}

/** One shared submission lock for the all-site and single-site entry points. */
export function createTestStarter(options: StartOptions) {
  let pending = false
  return async (profile?: unknown, site?: number): Promise<boolean> => {
    if (pending) return false
    pending = true
    options.busy(true)
    options.error('')
    try {
      const config = options.config()
      if (!config.product) throw new Error(options.messages().noProduct)
      const configured = await options.post('/api/config', {
        ...config, settingsRevision: options.revision() || undefined,
        ioControl: options.ioControl(), ...(profile !== undefined ? { profile } : {}),
      })
      const configuration = await configured.json()
      if (typeof configuration.settingsRevision === 'string') options.updateRevision(configuration.settingsRevision)
      const response = await options.post('/api/test/start', site === undefined ? {} : { site })
      const result = await response.json()
      if (!Array.isArray(result.started) || result.started.length === 0) throw new Error(options.messages().noTarget)
      options.started()
      return true
    } catch (error) {
      const message = error instanceof Error ? error.message : options.messages().failed
      options.error(message)
      options.log(message)
      return false
    } finally {
      pending = false
      options.busy(false)
    }
  }
}
