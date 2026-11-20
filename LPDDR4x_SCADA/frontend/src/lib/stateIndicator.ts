import type { DutState } from '../types/dut'

export function siteIndicator(states: DutState[]): DutState {
  if (states.includes('FAIL')) return 'FAIL'
  if (states.includes('TESTING')) return 'TESTING'
  if (!states.length || states.every(s => s === 'OFFLINE')) return 'OFFLINE'
  if (states.every(s => s === 'PASS')) return 'PASS'
  return 'IDLE'
}

export const STATE_COLOR: Record<DutState, string> = {
  IDLE: 'var(--st-idle)', TESTING: 'var(--st-testing)', PASS: 'var(--st-pass)',
  FAIL: 'var(--st-fail)', OFFLINE: 'var(--st-offline)',
}
