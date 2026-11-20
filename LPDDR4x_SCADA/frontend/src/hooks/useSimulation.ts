import { useEffect, useRef, useState } from 'react'
import type { DutStatus, LogEntry, SessionConfig, SiteStatus } from '@/types/dut'
import { PLACEHOLDER_STEPS, EST_DURATION_SEC, SITE_COUNT } from '@/types/dut'

// Mock 数据源：模拟 agent.md §5.2 的 WebSocket 推送
// 结构：N 个 site，每个 site 24 个 DUT（一台测试机 = 2 通讯板 × 12 通道）
// 后端就绪后用真实 WebSocket 替换本 hook，组件无需改动

let logId = 0
const now = () => new Date().toLocaleTimeString('zh-CN', { hour12: false })
const nowFull = () => {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}/${p(d.getMonth() + 1)}/${p(d.getDate())} ${now()}`
}
const pad = (n: number) => String(n).padStart(2, '0')

function initialSites(): SiteStatus[] {
  return Array.from({ length: SITE_COUNT }, (_, s) => ({
    id: s + 1,
    duts: Array.from({ length: 24 }, (_, i) => {
      const slot = i + 1
      // 演示异常：SITE 02 的 CH18、SITE 03 的 CH05 离线（标签页标红演示）
      const offline = (s === 1 && slot === 18) || (s === 2 && slot === 5)
      return {
        slot,
        connected: !offline,
        state: (offline ? 'OFFLINE' : 'IDLE') as DutStatus['state'],
        step: '-',
        progress: 0,
        durationSec: 0,
        countdownSec: 0,
        successCount: 0,
        totalCount: 0,
        testInfo: offline ? '连接失败' : '',
      }
    }),
  }))
}

export function useSimulation() {
  const [sites, setSites] = useState<SiteStatus[]>(initialSites)
  const [logs, setLogs] = useState<LogEntry[]>([
    { id: logId++, ts: nowFull(), siteId: null, slot: null, level: 'INFO', cat: 'conn', msg: '正在连接机台...' },
    { id: logId++, ts: nowFull(), siteId: null, slot: null, level: 'INFO', cat: 'conn', msg: `连接机台成功！${SITE_COUNT} 个 SITE，每个 24 通道 (mock)` },
  ])
  const [config, setConfig] = useState<SessionConfig>({
    product: 'LPDDR4x-16Gb',
    workOrder: '',
    lotNo: '',
    operator: 'admin',
  })
  const [sessionElapsed, setSessionElapsed] = useState(0)

  const sitesRef = useRef(sites)
  const configRef = useRef(config)
  useEffect(() => { sitesRef.current = sites }, [sites])
  useEffect(() => { configRef.current = config }, [config])

  const pushLog = (siteId: number | null, slot: number | null, level: LogEntry['level'],
                   msg: string, cat?: LogEntry['cat']) => {
    setLogs(prev => [...prev.slice(-400), { id: logId++, ts: nowFull(), siteId, slot, level, msg,
      cat: cat ?? (slot === null ? 'system' : 'dut') }])
  }

  // 批次标识 = 工单号-LOT号（CSV 记录的 batch 字段，见 agent.md §3）
  const batchOf = () => {
    const c = configRef.current
    return [c.workOrder, c.lotNo].filter(Boolean).join('-') || 'NO-BATCH'
  }

  // 确定 = 启动全部 site 的全部在线通道
  const startAll = () => {
    const c = configRef.current
    if (!c.product) {
      pushLog(null, null, 'WARN', '没有配置产品名，停止测试。')
      return
    }
    const targets = new Set<string>()
    sitesRef.current.forEach(s =>
      s.duts.forEach(d => {
        if (d.connected && d.state !== 'TESTING') targets.add(`${s.id}:${d.slot}`)
      })
    )
    if (targets.size === 0) return
    setSessionElapsed(0)
    setSites(prev => prev.map(s => ({
      ...s,
      duts: s.duts.map(d =>
        targets.has(`${s.id}:${d.slot}`)
          ? { ...d, state: 'TESTING' as const, step: PLACEHOLDER_STEPS[0], progress: 0, durationSec: 0, countdownSec: EST_DURATION_SEC, result: undefined, failItem: undefined, testInfo: `${PLACEHOLDER_STEPS[0]} 进行中` }
          : d
      ),
    })))
    pushLog(null, null, 'INFO', `收到机台命令: @START_TEST ALL (${targets.size} 通道)`)
    pushLog(null, null, 'INFO', `产品名: ${c.product}，模式配置成功。 batch=${batchOf()}`)
  }

  // 结束 = 停止全部 site
  const stopAll = () => {
    const testing = sitesRef.current.flatMap(s =>
      s.duts.filter(d => d.state === 'TESTING').map(d => ({ siteId: s.id, slot: d.slot }))
    )
    if (testing.length === 0) return
    setSites(prev => prev.map(s => ({
      ...s,
      duts: s.duts.map(d =>
        d.state === 'TESTING' ? { ...d, state: 'IDLE' as const, step: '-', progress: 0, countdownSec: 0, testInfo: '手动停止' } : d
      ),
    })))
    testing.forEach(t => pushLog(t.siteId, t.slot, 'WARN', '操作员结束测试'))
    pushLog(null, null, 'WARN', '断开机台测试流程！')
  }

  // 模拟推进：每 500ms 推进所有 site 的 TESTING 通道
  useEffect(() => {
    const timer = setInterval(() => {
      const prev = sitesRef.current
      const next = prev.map(s => ({
        ...s,
        duts: s.duts.map(d => {
          if (d.state !== 'TESTING') return d
          const progress = Math.min(100, d.progress + 2 + Math.random() * 4)
          const stepIdx = Math.min(PLACEHOLDER_STEPS.length - 1, Math.floor(progress / (100 / PLACEHOLDER_STEPS.length)))
          const durationSec = d.durationSec + 0.5
          const countdownSec = Math.max(0, d.countdownSec - 0.5)
          if (progress >= 100) {
            const pass = Math.random() < 0.88
            return {
              ...d,
              progress: 100,
              durationSec,
              countdownSec: 0,
              state: (pass ? 'PASS' : 'FAIL') as DutStatus['state'],
              result: (pass ? 'PASS' : 'FAIL') as 'PASS' | 'FAIL',
              step: pass ? 'done' : PLACEHOLDER_STEPS[stepIdx],
              failItem: pass ? undefined : PLACEHOLDER_STEPS[stepIdx],
              successCount: d.successCount + (pass ? 1 : 0),
              totalCount: d.totalCount + 1,
              testInfo: pass ? 'PASS' : `FAIL: ${PLACEHOLDER_STEPS[stepIdx]}`,
            }
          }
          return { ...d, progress, step: PLACEHOLDER_STEPS[stepIdx], durationSec, countdownSec, testInfo: `${PLACEHOLDER_STEPS[stepIdx]} 进行中` }
        }),
      }))

      next.forEach((s, si) => {
        s.duts.forEach((u, di) => {
          const p = prev[si].duts[di]
          if (p.state === 'TESTING' && u.state === 'PASS') {
            pushLog(s.id, u.slot, 'INFO', `@TEST_DONE S${pad(s.id)} CH${pad(u.slot)} PASS · 耗时 ${u.durationSec.toFixed(1)}s`)
          }
          if (p.state === 'TESTING' && u.state === 'FAIL') {
            pushLog(s.id, u.slot, 'ERROR', `@TEST_DONE S${pad(s.id)} CH${pad(u.slot)} FF · fail_item=${u.failItem} · 耗时 ${u.durationSec.toFixed(1)}s`)
          }
        })
      })

      if (next.some(s => s.duts.some(d => d.state === 'TESTING'))) {
        setSessionElapsed(e => e + 0.5)
      }

      sitesRef.current = next
      setSites(next)
    }, 500)
    return () => clearInterval(timer)
  }, [])

  // 扁平化的全部 DUT（供侧栏/顶栏统计）
  const duts = sites.flatMap(s => s.duts)
  const totalSuccess = duts.reduce((sum, d) => sum + d.successCount, 0)
  const totalRuns = duts.reduce((sum, d) => sum + d.totalCount, 0)

  return {
    sites, duts, logs, config, setConfig, sessionElapsed,
    totalSuccess, totalRuns,
    startAll, stopAll,
  }
}
