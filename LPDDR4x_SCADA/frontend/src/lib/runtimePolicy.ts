export interface RuntimePolicy {
  cfgAckTimeoutSec: number
  cfgRetryIntervalSec: number
  stageTimeoutSec: { PL: number; LK: number; APK: number }
  checkReadyVersion: boolean
  expectedReadyVersion: string
}

export const defaultRuntimePolicy = (): RuntimePolicy => ({
  cfgAckTimeoutSec: 0, cfgRetryIntervalSec: 0, stageTimeoutSec: { PL: 0, LK: 0, APK: 0 },
  checkReadyVersion: false, expectedReadyVersion: '',
})

export function validRuntimePolicy(policy: RuntimePolicy): boolean {
  const finite = (n: number, max: number) => Number.isFinite(n) && n >= 0 && n <= max
  return finite(policy.cfgAckTimeoutSec, 3600) && finite(policy.cfgRetryIntervalSec, 600) &&
    Object.values(policy.stageTimeoutSec).every(n => finite(n, 86400)) &&
    /^[\x20-\x7E]{0,64}$/.test(policy.expectedReadyVersion) &&
    (!policy.checkReadyVersion || !!policy.expectedReadyVersion.trim())
}
