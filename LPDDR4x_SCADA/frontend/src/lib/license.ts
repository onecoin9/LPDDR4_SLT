import { useSyncExternalStore } from 'react'
import { API_BASE } from '@/hooks/useServer'

export type LicenseState = 'valid' | 'missing' | 'expired' | 'not_yet_valid' | 'invalid' | 'machine_mismatch' | 'clock_rollback' | 'storage_error' | 'machine_unavailable'
export interface LicenseStatus {
  state: LicenseState; allowedToStart: boolean; clientId: string | null
  expiresAt: string | null; daysRemaining: number | null
  customer: string | null; licenseId: string | null; message: string
}
const listeners = new Set<() => void>()
let snapshot: { status: LicenseStatus | null; failed: boolean } = { status: null, failed: false }
let timer: ReturnType<typeof setInterval> | undefined
let pending: Promise<void> | undefined

export function refreshLicense(): Promise<void> {
  if (pending) return pending
  pending = fetch(`${API_BASE}/api/license/status`, { cache: 'no-store' }).then(async response => {
    if (!response.ok) throw new Error('license-status')
    snapshot = { status: await response.json() as LicenseStatus, failed: false }
  }).catch(() => { snapshot = { ...snapshot, failed: true } }).finally(() => {
    pending = undefined
    listeners.forEach(fn => fn())
  })
  return pending
}
function subscribe(listener: () => void) {
  listeners.add(listener)
  if (listeners.size === 1) {
    void refreshLicense()
    timer = setInterval(() => { void refreshLicense() }, 60000)
  }
  return () => {
    listeners.delete(listener)
    if (!listeners.size && timer) { clearInterval(timer); timer = undefined }
  }
}
export function useLicense() { return useSyncExternalStore(subscribe, () => snapshot) }
