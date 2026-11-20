import { useEffect, useRef, useState } from 'react'
import type { DutState, DutStatus, IoControl, LogEntry, SessionConfig, SiteStatus } from '@/types/dut'
import { DEFAULT_IO_CONTROL } from '@/types/dut'
import { t } from '@/lib/i18n'
import { apiErrorText } from '@/lib/productPlan'
import { createTestStarter } from '@/lib/testStart'

// 真实数据源（FE-1）：WebSocket 订阅 + REST 控制，替代 useSimulation 的纯前端 mock。
// 对外暴露的接口与 useSimulation 完全一致，Home.tsx 仅替换 hook 引用，界面组件不改。
// 契约：agent.md §5.2/§5.3；每条 WS 消息带可选 site 字段（单 site 恒为 1，多 site 扩展）。
// 断线自动重连：指数退避 1s→2s→4s…（上限 10s），断连时打系统日志，不白屏。

// dev（vite :3000）→ 后端 :8000（后端已开 CORS）；生产同源（后端托管 dist /
// 桌面版 exe 随机端口）→ 相对寻址，端口跟随页面来源，勿写死 8000
// （2026-09-07 桌面版踩坑：写死 localhost:8000 导致 exe 内 WS 连不上、总览/SITE 标签不渲染）
const dev = import.meta.env.DEV
export const API_BASE = dev ? 'http://localhost:8000' : ''
const WS_URL = dev
  ? 'ws://localhost:8000/ws'
  : `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`

let logId = 0
const nowFull = () => {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}/${p(d.getMonth() + 1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

// ---- 扫描状态（/api/sweep/status；Phase 2 shmoo）----
export interface SweepPointResult {
  index: number
  value: string
  batch: string
  pass: number
  total: number
  per_key: Record<string, { result: string; failItem: string }>
}

export interface SweepState {
  running: boolean
  axis?: string
  points?: number[]
  current_index?: number | null
  results?: SweepPointResult[]
  csv_path?: string | null
  aborted?: string | null
  error?: string | null
  summary?: {
    pass_boundary?: { from: string; to: string; points: number } | null
    aborted?: string | null
  } | null
}

// ---- WS 消息类型（与 backend/app/ws.py 逐字段对应；site 为可选扩展字段） ----
interface WsStatus {
  type: 'dut_status'
  site?: number
  slot: number
  connected: boolean
  state: DutState
  step: string
  progress: number
  durationSec: number
  countdownSec: number
  successCount: number
  totalCount: number
  testInfo: string
  result?: DutStatus['result']
  failItem?: DutStatus['failItem']
}
interface WsResult {
  type: 'dut_result'
  site?: number
  slot: number
  result: 'PASS' | 'FAIL'
  failItem?: string
  durationSec: number
}
interface WsLog {
  type: 'log'
  site?: number | null
  slot?: number | null
  level: 'INFO' | 'WARN' | 'ERROR'
  cat?: LogEntry['cat']
  msg: string
}
interface WsSnapshot {
  siteCount: number
  sites: { id: number; duts: DutStatus[] }[]
}
// manual_state（2026-10-10 事件驱动）：手动调试页完整快照，后端在电源变化 /
// 状态机转换 / 新客户端连接时主动推送，前端不再轮询 info / run_state
export interface ManualPowerDut { dut: number; line: number; channel?: number; powerOn: boolean }
export interface ManualRunDut {
  dut: number; channel?: number; state: string; detail: string
  active?: boolean; connected?: boolean; runId?: number; powerError?: string
  powerAction?: '' | 'turning_on' | 'turning_off'
  sinceSec: number; enteredAt?: number | null   // enteredAt = 服务端墙钟（秒）
  progress?: number; step?: string   // 手动轮次自带进度，不依赖首页 DUT 列表
}
export interface ManualState {
  enabled: boolean
  duts: ManualPowerDut[]
  run: { mode: string; duts: ManualRunDut[] }
}
interface WsManualState extends ManualState { type: 'manual_state' }
type WsMsg = WsStatus | WsResult | WsLog | WsSnapshot | WsManualState

function isSnapshot(m: WsMsg): m is WsSnapshot {
  return (m as WsSnapshot).siteCount !== undefined
}

async function postJson(path: string, body: unknown): Promise<Response> {
  const response = await fetch(API_BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(apiErrorText(payload))
  }
  return response
}

// ---- 日志本地持久化（2026-09-19）----
// 浏览器会把后台/息屏的标签页整页丢弃（Edge 睡眠标签页 / Chrome 内存节省），
// 亮屏后页面重载、内存日志归零。把最近日志持续写入 localStorage，
// 初始化时载回，页面重载/被丢弃后历史仍在。
const LOG_STORE_KEY = 'slt-log-history'
const LOG_STORE_MAX = 20000
function loadLogHistory(): LogEntry[] {
  try {
    const raw = localStorage.getItem(LOG_STORE_KEY)
    if (!raw) return []
    const arr = JSON.parse(raw) as LogEntry[]
    if (Array.isArray(arr) && arr.length > 0) {
      logId = Math.max(logId, ...arr.map(e => e.id)) + 1
    }
    return Array.isArray(arr) ? arr : []
  } catch { return [] }
}
let logStoreTimer: number | null = null
function scheduleLogStore(logs: LogEntry[]) {
  if (logStoreTimer !== null) return
  logStoreTimer = window.setTimeout(() => {
    logStoreTimer = null
    try {
      let tail = logs.slice(-LOG_STORE_MAX)
      for (let n = 2; n <= 5; n *= 2) {          // 超配额则减半重试
        try {
          localStorage.setItem(LOG_STORE_KEY, JSON.stringify(tail))
          return
        } catch {
          tail = tail.slice(-Math.floor(LOG_STORE_MAX / n))
          if (tail.length === 0) return
        }
      }
    } catch { /* 隐私模式等场景静默放弃 */ }
  }, 3000)
}

export function useServer() {
  const [sites, setSites] = useState<SiteStatus[]>([])
  const [logs, setLogs] = useState<LogEntry[]>(loadLogHistory)
  // 机台配置（产品/工单/LOT/操作员）：localStorage 持久化，下次打开上位机
  // 自动恢复，随「确定/启动本站」POST /api/config 上送后端（2026-10-10）
  const [config, setConfigState] = useState<SessionConfig>(() => {
    const dflt = { product: 'LPDDR4x-16Gb', workOrder: '', lotNo: '', operator: 'admin' }
    try {
      const raw = localStorage.getItem('slt-session-config')
      if (raw) return { ...dflt, ...JSON.parse(raw) }
    } catch { /* 损坏则回落默认 */ }
    return dflt
  })
  const [sessionElapsed, setSessionElapsed] = useState(0)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState('')
  // 手动调试页快照（manual_state 推送）：电源 + 完整运行状态机。
  // 断线重连后服务端随连接即重发，状态自然恢复
  const [serverOnline, setServerOnline] = useState(false)
  const [manualState, setManualState] = useState<ManualState | null>(null)
  // REST 操作应答回来后立即对齐本地（不等推送）：拨杆/全部上下电用
  const patchManualPower = (dut: number | 'all', on: boolean) => {
    setManualState(prev => prev && ({
      ...prev,
      duts: prev.duts.map(d => (dut === 'all' || d.dut === dut) ? { ...d, powerOn: on } : d),
    }))
  }
  // IO 控制（设置页「通道设置」；旧上位机「无操作/测试板开机/下载模式」语义）。
  // localStorage 持久化，随「确定/启动本站」的 POST /api/config 一起上送
  const [ioControl, setIoControlState] = useState<IoControl>(() => {
    try {
      const raw = localStorage.getItem('slt-io-control')
      if (raw) return { ...DEFAULT_IO_CONTROL, ...JSON.parse(raw) }
    } catch { /* 损坏则回落默认 */ }
    return DEFAULT_IO_CONTROL
  })
  const ioControlRef = useRef(ioControl)
  const settingsRevisionRef = useRef('')
  const setSettingsRevision = (revision: string) => { settingsRevisionRef.current = revision }
  useEffect(() => {
    ioControlRef.current = ioControl
  }, [ioControl])
  const setIoControl = (c: IoControl) => { ioControlRef.current = c; setIoControlState(c) }

  const sitesRef = useRef(sites)
  const configRef = useRef(config)
  useEffect(() => { sitesRef.current = sites }, [sites])
  useEffect(() => {
    configRef.current = config
    try { localStorage.setItem('slt-session-config', JSON.stringify(config)) } catch { /* 忽略 */ }
  }, [config])

  // ---- DUT 状态合并 ----
  const mergeDut = (siteId: number, slot: number, patch: Partial<DutStatus>) => {
    setSites(prev => prev.map(s => s.id !== siteId ? s : ({
      ...s,
      duts: s.duts.map(d => d.slot !== slot ? d : { ...d, ...patch }),
    })))
  }

  // ---- 日志通路（2026-09-18 优化） ----
  // 旧实现只靠 250ms setInterval 把日志搬进 state。窗口不可见时浏览器会节流该
  // 定时器（≥1s；隐藏超 5 分钟触发 intensive throttling，最低约每分钟一次），
  // 表现为「攒一大批才一起回显」。现改为 rAF 逐帧刷新 + 切回前台立即 flush。
  const LOG_TAIL = 50000      // 主面板保留量（2026-09-18 现场要求：全程日志可回看，不再只留尾部）
  const LOG_BUF_MAX = 2000    // 洪泛/后台期间缓冲上限，超过立刻刷，防止无界增长
  const DUT_LOG_CAP = 5000    // 每通道日志缓冲上限（通道弹框回看用）

  const logBuf = useRef<LogEntry[]>([])
  const logRaf = useRef<number | null>(null)
  const logTimer = useRef<number | null>(null)
  const [dutLogs, setDutLogs] = useState<Record<string, LogEntry[]>>({})

  const applyLogs = (items: LogEntry[]) => {
    setLogs(prev => {
      const next = [...prev, ...items].slice(-LOG_TAIL)
      scheduleLogStore(next)
      return next
    })
    // 追加每通道日志缓冲
    const perSlot: Record<string, LogEntry[]> = {}
    for (const it of items) {
      if (it.slot !== null && it.siteId !== null) {
        (perSlot[`${it.siteId}:${it.slot}`] ??= []).push(it)
      }
    }
    if (Object.keys(perSlot).length > 0) {
      setDutLogs(prev => {
        const next = { ...prev }
        for (const [k, arr] of Object.entries(perSlot)) {
          next[k] = [...(next[k] ?? []), ...arr].slice(-DUT_LOG_CAP)
        }
        return next
      })
    }
  }

  const cancelLogFlush = () => {
    if (logRaf.current !== null) { cancelAnimationFrame(logRaf.current); logRaf.current = null }
    if (logTimer.current !== null) { clearTimeout(logTimer.current); logTimer.current = null }
  }

  const flushLogs = () => {
    cancelLogFlush()
    if (logBuf.current.length === 0) return
    const items = logBuf.current
    logBuf.current = []
    applyLogs(items)
  }

  const scheduleLogFlush = () => {
    if (logRaf.current !== null || logTimer.current !== null) return
    const canPaint = typeof requestAnimationFrame === 'function'
      && typeof document !== 'undefined' && document.visibilityState === 'visible'
    if (canPaint) {
      // 与绘制同频（约 16ms），同一帧内的多条日志合并成一次 setState
      logRaf.current = requestAnimationFrame(() => { logRaf.current = null; flushLogs() })
    } else {
      // 后台标签页 rAF 不执行；用定时器兜底让缓冲持续消化（浏览器自行节流）
      logTimer.current = window.setTimeout(() => { logTimer.current = null; flushLogs() }, 250)
    }
  }

  const bufLog = (siteId: number | null, slot: number | null,
                  level: LogEntry['level'], msg: string, cat?: LogEntry['cat']) => {
    logBuf.current.push({ id: logId++, ts: nowFull(), siteId, slot, level, msg,
      cat: cat ?? (slot === null ? 'system' : 'dut') })
    if (logBuf.current.length >= LOG_BUF_MAX) { flushLogs(); return }
    scheduleLogFlush()
  }

  // 连接/告警这类关键日志立刻可见，不排队
  const pushLog = (siteId: number | null, slot: number | null,
                   level: LogEntry['level'], msg: string, cat?: LogEntry['cat']) => {
    bufLog(siteId, slot, level, msg, cat)
    flushLogs()
  }

  // 从后台切回前台时，立即把后台期间攒下的日志补齐
  useEffect(() => {
    const onVisibility = () => { if (document.visibilityState === 'visible') flushLogs() }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [])

  // 1200 路并发节流：dut_status 先入缓冲，250ms 合并成一次 setState（同一 DUT 只留最新帧）
  const patchBuf = useRef(new Map<string, Partial<DutStatus>>())
  useEffect(() => {
    const timer = setInterval(() => {
      if (patchBuf.current.size === 0) return
      const patches = patchBuf.current
      patchBuf.current = new Map()
      setSites(prev => prev.map(s => {
        let touched = false
        const duts = s.duts.map(d => {
          const p = patches.get(`${s.id}:${d.slot}`)
          if (!p) return d
          touched = true
          return { ...d, ...p }
        })
        return touched ? { ...s, duts } : s
      }))
    }, 250)
    return () => clearInterval(timer)
  }, [])

  // ---- WebSocket 连接（含重连） ----
  useEffect(() => {
    let ws: WebSocket | null = null
    let closed = false
    let timer: ReturnType<typeof setTimeout> | undefined
    let attempt = 0

    const connect = () => {
      if (closed) return
      ws = new WebSocket(WS_URL)

      ws.onopen = () => {
        setServerOnline(true)
        attempt = 0
      }
      ws.onmessage = (ev) => {
        let m: WsMsg
        try { m = JSON.parse(ev.data as string) } catch { return }
        if (isSnapshot(m)) {
          setSites(m.sites.map(s => ({ id: s.id, duts: s.duts })))
          bufLog(null, null, 'INFO',
            `${t('srvConnected')} ${m.siteCount} ${t('srvSiteUnit')} × 24 ${t('spChannelUnit')}`,
            'conn')
          return
        }
        if (m.type === 'dut_status') {
          const site = m.site ?? 1
          patchBuf.current.set(`${site}:${m.slot}`, {
            connected: m.connected, state: m.state, step: m.step, progress: m.progress,
            durationSec: m.durationSec, countdownSec: m.countdownSec,
            successCount: m.successCount, totalCount: m.totalCount, testInfo: m.testInfo,
            result: m.result, failItem: m.failItem,
          })
        } else if (m.type === 'dut_result') {
          const site = m.site ?? 1
          // 结果立即生效：清掉该通道在缓冲中的旧状态帧，避免被过期 TESTING 帧覆盖
          patchBuf.current.delete(`${site}:${m.slot}`)
          mergeDut(site, m.slot, {
            state: m.result, result: m.result, failItem: m.failItem,
            durationSec: m.durationSec,
          })
        } else if (m.type === 'log') {
          bufLog(m.slot === null || m.slot === undefined ? null : (m.site ?? 1),
                 m.slot ?? null, m.level, m.msg, m.cat)
        } else if (m.type === 'manual_state') {
          setManualState({ enabled: m.enabled, duts: m.duts, run: m.run })
        }
      }
      ws.onclose = () => {
        if (closed) return
        setServerOnline(false)
        patchBuf.current.clear()
        setSites(prev => prev.map(site => ({ ...site, duts: site.duts.map(d => ({
          ...d, connected: false,
          state: d.state === 'PASS' || d.state === 'FAIL' ? d.state : 'OFFLINE',
        })) })))
        pushLog(null, null, 'WARN', t('srvDisconnected'), 'conn')
        const delay = Math.min(1000 * 2 ** attempt, 10000)
        attempt += 1
        timer = setTimeout(connect, delay)
      }
      ws.onerror = () => { /* onclose 会接着触发，重连在那里统一处理 */ }
    }

    pushLog(null, null, 'INFO', t('srvConnecting'), 'conn')
    connect()
    return () => {
      closed = true
      if (timer) clearTimeout(timer)
      ws?.close()
    }
  }, [])

  // ---- 会话时长：任一通道测试中则每秒 +1（与 mock 行为一致） ----
  useEffect(() => {
    const timer = setInterval(() => {
      if (sitesRef.current.some(s => s.duts.some(d => d.state === 'TESTING'))) {
        setSessionElapsed(e => e + 1)
      }
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  // ---- 控制：确定 = 下发配置（含所选产品档案 JSON，后端编译 .cfg 留档）+ 启动全部在线空闲通道 ----
  const starter = useRef<ReturnType<typeof createTestStarter> | null>(null)
  if (!starter.current) starter.current = createTestStarter({
    config: () => configRef.current, ioControl: () => ioControlRef.current,
    revision: () => settingsRevisionRef.current, updateRevision: setSettingsRevision,
    post: postJson, busy: setStarting, error: setStartError,
    log: message => pushLog(null, null, 'ERROR', message), started: () => setSessionElapsed(0),
    messages: () => ({ noProduct: t('srvNoProduct'), noTarget: t('srvNoTarget'), failed: t('srvStartFail') }),
  })
  const startAll = (profile?: unknown) => starter.current!(profile)

  // ---- 结束 = 停止全部测试中通道 ----
  const stopAll = async () => {
    try {
      await postJson('/api/test/stop', {})
    } catch {
      pushLog(null, null, 'ERROR', t('srvStopFail'))
    }
  }

  // ---- 工程师：单 SITE 启动/停止（不影响其他站） ----
  const startSite = (site: number, profile?: unknown) => starter.current!(profile, site)

  const stopSite = async (site: number) => {
    try {
      await postJson('/api/test/stop', { site })
    } catch {
      pushLog(null, null, 'ERROR', t('srvStopFail'))
    }
  }

  // 配置仅更新本地；随「确定」一起下发（避免每个按键都打后端）
  const setConfig = (c: SessionConfig) => {
    configRef.current = c
    // Selection may finish after navigation has unmounted this hook. Persist
    // immediately so the next page cannot restore the previous product.
    try { localStorage.setItem('slt-session-config', JSON.stringify(c)) } catch { /* Ignore unavailable storage. */ }
    setConfigState(c)
  }

  const duts = sites.flatMap(s => s.duts)
  const totalSuccess = duts.reduce((sum, d) => sum + d.successCount, 0)
  const totalRuns = duts.reduce((sum, d) => sum + d.totalCount, 0)

  return {
    sites, duts, logs, config, setConfig, getConfig: () => configRef.current, sessionElapsed,
    totalSuccess, totalRuns, dutLogs,
    startAll, stopAll, startSite, stopSite, starting, startError,
    ioControl, setIoControl, setSettingsRevision,
    manualState, patchManualPower, serverOnline,
  }
}
