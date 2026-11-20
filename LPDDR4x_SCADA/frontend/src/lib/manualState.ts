import type { DutStatus } from '../types/dut'
import type { ManualPowerDut, ManualRunDut } from '../hooks/useServer'
import type { I18nKey } from './i18n'

export const RUN_STATE_META: Record<string, { textKey: I18nKey; color: string }> = {
  idle: { textKey: 'stIdleLamp', color: 'var(--st-idle)' },
  offline: { textKey: 'stOffline', color: 'var(--st-offline)' },
  wait_ready: { textKey: 'mdRunWaitReady', color: 'var(--st-testing)' },
  cfg_sent: { textKey: 'mdRunCfgSent', color: 'var(--st-testing)' },
  running: { textKey: 'mdRunRunning', color: 'var(--st-testing)' },
  timeout: { textKey: 'mdRunTimeout', color: 'var(--st-fail)' },
  pass: { textKey: 'stPass', color: 'var(--st-pass)' },
  fail: { textKey: 'stFail', color: 'var(--st-fail)' },
}

export function runElapsed(run: ManualRunDut, nowSec: number): number {
  // active 为可选字段；旧后端没有它时，从运行阶段判断，避免将快照秒数锁住。
  const active = run.active ?? ['wait_ready', 'cfg_sent', 'running'].includes(run.state)
  if (!active || !run.enteredAt) return run.sinceSec
  return Math.max(0, Math.round(nowSec - run.enteredAt))
}

// 一份 manual_state 决定本页电源、连接、测试灯，避免被节流的 dut_status 旧帧覆盖。
export function manualStatus(power: ManualPowerDut, run: ManualRunDut | undefined,
                             status: DutStatus | undefined, serverOnline: boolean,
                             nowSec: number): DutStatus {
  const base: DutStatus = status ?? {
    slot: power.channel ?? power.dut, connected: false, state: 'OFFLINE', step: '-',
    progress: 0, durationSec: 0, countdownSec: 0, successCount: 0, totalCount: 0, testInfo: '',
  }
  const connected = serverOnline && power.powerOn && (run?.connected ?? base.connected)
  if (!run) return { ...base, connected, state: !serverOnline && !['PASS', 'FAIL'].includes(base.state) ? 'OFFLINE' : base.state }
  const state = run.state === 'pass' ? 'PASS'
    : ['fail', 'timeout'].includes(run.state) ? 'FAIL'
    : !serverOnline ? 'OFFLINE'
    : ['wait_ready', 'cfg_sent', 'running'].includes(run.state) ? 'TESTING'
    : connected ? 'IDLE' : 'OFFLINE'
  // 现场模式的首次通用快照可能没有 DUT 行；手动快照是本轮进度的数据源。
  // 兼容没有 progress 字段的旧后端，但不能用上轮的非零值覆盖新轮的 0。
  const progress = run.progress ?? base.progress
  return {
    ...base, connected, state, durationSec: runElapsed(run, nowSec),
    step: run.step || base.step,
    result: state === 'PASS' || state === 'FAIL' ? state : undefined,
    failItem: state === 'FAIL' ? run.detail : undefined,
    progress: state === 'PASS' ? 100 : state === 'TESTING' && run.state === 'running'
      ? Number.isFinite(progress) ? Math.max(0, Math.min(99, progress)) : 0 : 0,
  }
}
