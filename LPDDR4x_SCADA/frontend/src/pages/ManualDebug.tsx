import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { useServer, API_BASE, type ManualRunDut } from '@/hooks/useServer'
import { applyTheme, initTheme } from '@/lib/theme'
import { loadZoom } from '@/lib/zoom'
import { fmtDur } from '@/lib/utils'
import { t } from '@/lib/i18n'
import { manualStatus, runElapsed, RUN_STATE_META } from '@/lib/manualState'
import { clearManualLogs, mergeManualLogs, visibleManualLogs, type ManualLogCursor } from '@/lib/manualLogs'
import { draftIsPreserved, manualConfigError, manualRuntimeSettings, syncManualProduct } from '@/lib/manualProductConfig'
import { pendingSettingsSaves } from '@/lib/settingsPending'
import type { LogEntry } from '@/types/dut'

// 手动版调试页 v2（电源控制台风格）：1 块原版通讯板 + N 块测试主板。
// - 头部：通讯板链路心跳（3s 轮询 0xF001）+ 全部上电（错峰 1s）/ 全部下电
// - DUT 通道模块：机械拨杆式电源开关（cmd7 PWR_EN），上电辉光 / FAIL 红脉冲 /
//   测试中显示步骤与进度条
// - 日志台：终端风格，顶部页签（总览 + 每 DUT），自动滚动开关

interface ManualDut { dut: number; line: number; powerOn: boolean; channel?: number }
interface ManualInfo {
  enabled: boolean
  boardHost: string
  mbPort: number
  runMode?: string
  duts: ManualDut[]
}

// 「设置」区（GET/POST /api/manual/settings）
interface ManualSettings {
  boardHost: string
  localIp: string
  logDir: string
  latestRunDir?: string
  cfgSource: 'product'
  cfgFile: string
  cfgProduct: string
  cfgContent: string
  cfgSha256?: string
  settingsRevision?: string | number
  runMode: string
  readyTimeoutSec: number
  testTimeoutSec: number
}

// 完整运行每路状态（GET /api/manual/run_state）
type RunDutState = ManualRunDut
interface RunState { mode: string; duts: RunDutState[] }


const pad = (n: number) => String(n).padStart(2, '0')

const LEVEL_COLOR: Record<string, string> = {
  ERROR: 'var(--st-fail)',
  WARN: 'var(--st-testing)',
  INFO: 'var(--text)',
}

// 日志类别小徽章（cat: system=上位机 / dut=主控板测试 / sys=主控板系统 / conn=连接）
const CAT_CHIP: Record<string, { text: string; color: string } | undefined> = {
  system: { text: 'HOST', color: 'var(--accent)' },
  sys: { text: 'SYS', color: 'var(--st-testing)' },
  conn: { text: 'CONN', color: 'var(--text3)' },
}

type LinkState = 'check' | 'ok' | 'down'

async function manualJson(path: string, payload?: Record<string, unknown>) {
  const response = await fetch(`${API_BASE}${path}`, payload === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new Error(manualConfigError(body?.detail) || String(response.status))
  return body
}

async function settleSharedSettings() {
  let waited = false
  for (;;) {
    const pending = pendingSettingsSaves()
    if (!pending.length) return waited
    waited = true
    await Promise.all(pending)
  }
}

export default function ManualDebug() {
  const nav = useNavigate()
  const sim = useServer()
  const simRef = useRef(sim)
  simRef.current = sim
  const [info, setInfo] = useState<ManualInfo | null>(null)
  const [notice, setNotice] = useState('')
  const [tab, setTab] = useState<string>('all')
  const [busy, setBusy] = useState<number | 'all' | 'add' | null>(null)
  const [link, setLink] = useState<LinkState>('check')
  const [autoScroll, setAutoScroll] = useState(true)
  // 页面初次打开隐藏旧历史；后续上电只清对应通道，其他 DUT 保持原显示。
  const [logClear, setLogClear] = useState<ManualLogCursor>(
    () => ({ all: sim.logs.at(-1)?.id ?? 0, channels: {} }))
  const logRef = useRef<HTMLDivElement>(null)
  // 「设置」区
  const [showSettings, setShowSettings] = useState(false)
  const [form, setForm] = useState<ManualSettings | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [cfgDraft, setCfgDraft] = useState('')
  const [cfgFile, setCfgFile] = useState('')
  const [cfgApplying, setCfgApplying] = useState(false)
  const [cfgReady, setCfgReady] = useState(false)
  const [cfgMsg, setCfgMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const cfgSnapshot = useRef<ManualSettings | null>(null)
  const cfgDraftRef = useRef('')
  cfgDraftRef.current = cfgDraft
  // 2026-11-18 契约：文件保存用户编辑原文。appliedRef 记录最近一次成功应用的
  // 原文与当时的编译产物——草稿等于已应用原文时语义已在产品档案，不算脏。
  const appliedRef = useRef<{ text: string; canonical: string } | null>(null)
  const cfgDirty = !!form && cfgDraft !== form.cfgContent
    && cfgDraft !== appliedRef.current?.text
  const runState: RunState | null = sim.manualState?.run ?? null
  const settingsFileRef = useRef<HTMLInputElement>(null)
  // 目录/文件浏览弹窗（Log 路径=目录, 手动运行设置=json 文件）
  const [browse, setBrowse] = useState<{ path: string; parent: string; dirs: string[]; files?: string[]; drives: string[] } | null>(null)
  const [browseMode, setBrowseMode] = useState<'dir' | 'json' | 'cfg'>('dir')
  // 设置文件预览弹窗（「读取设置」→ 选文件 → 预览 → 导入）
  const [settingsFile, setSettingsFile] = useState<{ path: string; content: string; exists: boolean } | null>(null)

  useEffect(() => { applyTheme(initTheme()) }, [])

  const refreshInfo = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/api/manual/info`)
      if (r.ok) setInfo(await r.json())
    } catch { /* 后端未起时 WS 重连日志已提示 */ }
  }, [])
  useEffect(() => { refreshInfo() }, [refreshInfo])

  const refreshSettings = useCallback(async () => {
    setCfgReady(false)
    try {
      const waited = await settleSharedSettings()
      const selected = await syncManualProduct(waited ? '' : simRef.current.getConfig().product, manualJson,
        product => simRef.current.setConfig({ ...simRef.current.getConfig(), product }),
        { noProduct: t('mdNoProduct'), changed: t('mdCfgProductChanged') })
      const body = await manualJson('/api/manual/settings')
      if (body?.cfgProduct !== selected) throw new Error(t('mdCfgProductChanged'))
      const previous = cfgSnapshot.current
      if (previous && previous.cfgProduct !== body.cfgProduct) appliedRef.current = null
      // Keep a draft's original revision for conflict detection when settings reopen.
      // 已应用原文且服务器编译结果未变：草稿视为干净，保留用户字面内容。
      const preserved = draftIsPreserved(cfgDraftRef.current, appliedRef.current, body.cfgContent)
      const dirty = previous && cfgDraftRef.current !== previous.cfgContent && !preserved
      if (dirty && previous.cfgProduct !== body.cfgProduct) throw new Error(t('mdCfgProductChanged'))
      const settings = dirty ? { ...body, cfgContent: previous.cfgContent,
        cfgSource: previous.cfgSource, cfgProduct: previous.cfgProduct,
        cfgSha256: previous.cfgSha256, settingsRevision: previous.settingsRevision } : body
      cfgSnapshot.current = settings
      setForm(settings)
      if (!dirty) {
        if (preserved) setCfgFile(settings.cfgFile || '')
        else { appliedRef.current = null; setCfgDraft(settings.cfgContent); setCfgFile(settings.cfgFile || '') }
      }
      setCfgReady(true)
      return settings as ManualSettings
    } catch (error) { setCfgReady(false); throw error }
  }, [])

  useEffect(() => {
    void refreshSettings().catch(error => setSaveMsg({ ok: false,
      text: `${t('mdReqFail')}: ${manualConfigError(error.message)}` }))
  }, [showSettings, refreshSettings])

  const [clockSec, setClockSec] = useState(() => Date.now() / 1000)
  useEffect(() => {
    if (!sim.manualState) return
    setInfo(prev => ({ ...prev, enabled: sim.manualState!.enabled,
      boardHost: prev?.boardHost ?? '', mbPort: prev?.mbPort ?? 501,
      runMode: sim.manualState!.run.mode, duts: sim.manualState!.duts }))
  }, [sim.manualState])
  useEffect(() => {
    const timer = setInterval(() => setClockSec(Date.now() / 1000), 1000)
    return () => clearInterval(timer)
  }, [])

  const saveSettings = async () => {
    if (!form) return
    setSaving(true)
    setSaveMsg(null)
    if (!await saveCfg()) { setSaving(false); return }
    try {
      const r = await fetch(`${API_BASE}/api/manual/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(manualRuntimeSettings({
          boardHost: form.boardHost,
          localIp: form.localIp,
          ...(form.logDir ? { logDir: form.logDir } : {}),
          runMode: form.runMode,
          readyTimeoutSec: form.readyTimeoutSec,
          testTimeoutSec: form.testTimeoutSec,
        }).updates),
      })
      const body = await r.json().catch(() => null)
      if (!r.ok) {
        setSaveMsg({ ok: false, text: `${t('mdReqFail')}: ${body?.detail ?? r.status}` })
      } else {
        await refreshSettings()
        setSaveMsg({ ok: true, text: t('mdSaved') })
        refreshInfo()
      }
    } catch {
      setSaveMsg({ ok: false, text: t('mdReqFail') })
    }
    setSaving(false)
  }

  const applyProductCfg = async () => {
    if (!form?.cfgProduct) return false
    const submitted = cfgDraftRef.current
    setCfgApplying(true)
    setCfgReady(false)
    setCfgMsg(null)
    try {
      const r = await fetch(`${API_BASE}/api/products/import-cfg`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cfgText: submitted, product: form.cfgProduct,
          settingsRevision: form.settingsRevision }),
      })
      const result = await r.json().catch(() => null)
      if (!r.ok) throw new Error(manualConfigError(result?.detail ?? result?.errors) || String(r.status))
      const response = await fetch(`${API_BASE}/api/manual/settings`)
      const settings = await response.json().catch(() => null)
      if (!response.ok) throw new Error(manualConfigError(settings?.detail) || String(response.status))
      if (settings.cfgProduct !== result.product) throw new Error(t('mdCfgProductChanged'))
      cfgSnapshot.current = settings
      appliedRef.current = { text: submitted, canonical: settings.cfgContent }
      // Import changes the shared product, while pending runtime fields stay local.
      // 编辑框保持用户原文（2026-11-18 契约），不再回填编译产物。
      setForm(current => current ? { ...current, cfgSource: settings.cfgSource,
        cfgProduct: settings.cfgProduct, cfgContent: settings.cfgContent,
        cfgSha256: settings.cfgSha256, settingsRevision: settings.settingsRevision } : settings)
      setCfgMsg({ ok: true, text: t('mdProductCfgApplied') })
      setCfgReady(true)
      return true
    } catch (error) {
      setCfgReady(false)
      setCfgMsg({ ok: false, text: manualConfigError(error instanceof Error ? error.message : error) })
      return false
    } finally { setCfgApplying(false) }
  }

  const saveCfg = async () => {
    if (!form?.cfgProduct || !cfgFile.trim()) {
      setCfgMsg({ ok: false, text: t('mdChooseCfgFile') })
      return false
    }
    if (cfgDirty && !await applyProductCfg()) return false
    const settings = cfgSnapshot.current
    try {
      await manualJson('/api/manual/cfg_file', { path: cfgFile, text: cfgDraftRef.current,
        product: settings?.cfgProduct, settingsRevision: settings?.settingsRevision })
      setCfgMsg({ ok: true, text: t('mdSaved') })
      return true
    } catch (error) {
      setCfgMsg({ ok: false, text: manualConfigError(error instanceof Error ? error.message : error) })
      return false
    }
  }

  const loadCfgFile = async (path = cfgFile) => {
    try {
      const data = await manualJson('/api/manual/read_file?path=' + encodeURIComponent(path))
      if (!data.exists) throw new Error(t('mdCfgFileMissing'))
      setCfgFile(data.path)
      setCfgDraft(data.content)
      // 读回的正是刚保存的原文时保持干净态；其他读取内容须重新应用才能完整运行
      if (data.content !== appliedRef.current?.text) appliedRef.current = null
      setCfgMsg(null)
    } catch (error) {
      setCfgMsg({ ok: false, text: manualConfigError(error instanceof Error ? error.message : error) })
    }
  }

  const openProductSettings = async () => {
    setSaving(true)
    try {
      if (cfgDirty && !await saveCfg()) return
      const product = cfgReady ? form?.cfgProduct : simRef.current.getConfig().product
      nav(`/?settings=product&product=${encodeURIComponent(product ?? '')}`)
    } finally { setSaving(false) }
  }

  // 通讯板链路心跳：3s 轮询 0xF001（原版固件 Modbus，读成功 = 板在线）
  useEffect(() => {
    let dead = false
    const poll = async () => {
      try {
        const r = await fetch(`${API_BASE}/api/manual/board_state`)
        if (dead) return
        if (r.ok) {
          await r.json()
          setLink('ok')
        } else {
          setLink('down')
        }
      } catch {
        if (!dead) setLink('down')
      }

    }
    poll()
    const timer = setInterval(poll, 3000)
    return () => { dead = true; clearInterval(timer) }
  }, [])

  useEffect(() => {
    if (autoScroll) logRef.current?.scrollTo({ top: logRef.current.scrollHeight })
  }, [sim.logs, tab, autoScroll, logClear])

  const setPower = async (dut: number, on: boolean): Promise<boolean> => {
    if (on && (runState?.mode ?? info?.runMode) !== 'power_only' && (!cfgReady || cfgDirty || cfgApplying)) {
      setNotice(t(cfgReady ? 'mdProductCfgApplyFirst' : 'mdProductCfgUnavailable'))
      setShowSettings(true)
      return false
    }
    setNotice('')
    const target = sim.manualState?.duts.find(d => d.dut === dut)
      ?? info?.duts.find(d => d.dut === dut)
    const channel = target?.channel ?? dut
    const wasPowered = target?.powerOn ?? false
    // Capture before the request: boot logs may arrive before its HTTP response.
    const through = sim.logs.at(-1)?.id ?? 0
    try {
      const r = await fetch(`${API_BASE}/api/manual/power`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dut, on }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => null)
        setNotice(`${t('mdReqFail')}: ${body?.detail ?? r.status}`)
        return false
      }
      const res = await r.json()
      setInfo(prev => prev && ({
        ...prev,
        duts: prev.duts.map(d => d.dut === dut ? { ...d, powerOn: res.powerOn } : d),
      }))
      // 只隐藏该通道上一轮的显示；失败、下电和重复上电均保留日志。
      if (on && res.powerOn && !wasPowered) {
        setLogClear(prev => clearManualLogs(prev, channel, through))
      }
      return true
    } catch {
      setNotice(t('mdReqFail'))
      return false
    }
  }

  // 设置区「运行模式」按钮：点击即时生效（不等「保存」）。
  // 只开机=上电不发配置(烧录用)；完整运行=自动测试。
  // 切到只开机时后端自动解除全部已布防会话（设置端点内置）。
  // 目录/文件浏览(后端列目录,浏览器拿不到绝对路径所以走后端)
  const openBrowse = async (start: string, mode: 'dir' | 'json' | 'cfg' = 'dir') => {
    setBrowseMode(mode)
    try {
      const p = start ? `?path=${encodeURIComponent(start)}` : ''
      const ext = mode === 'dir' ? '' : mode
      const f = ext ? (p ? '&' : '?') + `files=${ext}` : ''
      const r = await fetch(`${API_BASE}/api/manual/browse${p}${f}`)
      if (r.ok) setBrowse(await r.json())
    } catch { setNotice(t('mdReqFail')) }
  }

  // 设置区「运行模式」按钮：只改表单值(高亮切换),不自动保存——
  // 所有修改统一走「保存设置」按钮生效(消除隐性保存)
  const applyRunMode = (m: 'power_only' | 'full_run') => {
    setForm(f => f ? { ...f, runMode: m } : f)
  }

  const toggleOne = async (dut: number, on: boolean) => {
    setBusy(dut)
    await setPower(dut, on)
    setBusy(null)
  }

  // 「+」添加卡片：新增一路 DUT（默认 4 路、最多 8 路）。成功后端返回最新
  // info（含新 DUT 的线号/通道/电源态），直接刷新界面；失败显示后端 detail
  const addDut = async () => {
    setBusy('add')
    setNotice('')
    try {
      const r = await fetch(`${API_BASE}/api/manual/duts/add`, { method: 'POST' })
      if (!r.ok) {
        const body = await r.json().catch(() => null)
        setNotice(`${t('mdReqFail')}: ${body?.detail ?? r.status}`)
      } else {
        setInfo(await r.json())
      }
    } catch {
      setNotice(t('mdReqFail'))
    }
    setBusy(null)
  }

  // 卡片「−」：移除该路 DUT。身份用 d.dut（后端 dut 序号），禁止用显示下标
  const removeDut = async (dut: number) => {
    setBusy(dut)
    setNotice('')
    try {
      const r = await fetch(`${API_BASE}/api/manual/duts/remove`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dut }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => null)
        setNotice(`${t('mdReqFail')}: ${body?.detail ?? r.status}`)
      } else {
        setInfo(await r.json())
      }
    } catch {
      setNotice(t('mdReqFail'))
    }
    setBusy(null)
  }

  // 全部上电：逐路错峰 1s（防浪涌，沿用旧上位机分批语义）；
  // 全部下电：整组原子一包（0xA2 位掩码直控寄存器，立即锁存）
  const powerAll = async (on: boolean) => {
    if (!info) return
    if (on && (runState?.mode ?? info.runMode) !== 'power_only' && (!cfgReady || cfgDirty || cfgApplying)) {
      setNotice(t(cfgReady ? 'mdProductCfgApplyFirst' : 'mdProductCfgUnavailable'))
      setShowSettings(true)
      return
    }
    setBusy('all')
    setNotice('')
    if (on) {
      for (const d of info.duts) {
        if (!d.powerOn) await setPower(d.dut, true)
        await new Promise(r => setTimeout(r, 1000))
      }
    } else {
      try {
        const r = await fetch(`${API_BASE}/api/manual/power_all`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ on: false }),
        })
        if (!r.ok) {
          const body = await r.json().catch(() => null)
          setNotice(`${t('mdReqFail')}: ${body?.detail ?? r.status}`)
        } else {
          await refreshInfo()
        }
      } catch {
        setNotice(t('mdReqFail'))
      }
    }
    setBusy(null)
  }

  const duts: ManualDut[] = sim.manualState?.duts ?? info?.duts ?? [1, 2, 3, 4].map(d => ({ dut: d, line: d - 1, powerOn: false }))
  // 「+」添加卡片：未达 8 路且调试启用时挂在卡片排末尾（空槽位风格）
  const canAdd = (info?.enabled ?? false) && duts.length < 8
  // 真实值 = 通讯板通道号（2026-09-23 用户指令）：卡片/日志页签/日志过滤/
  // run_state 映射统一按通道号（后端 63001 日志 [DUTx] 与 manualrun 的归属
  // 已对齐通道号）；后端未带 channel 时回退序号
  const chOf = (d: { channel?: number; dut: number }) => d.channel ?? d.dut
  const site1 = sim.sites.find(s => s.id === 1)
  const dutStatus = (ch: number) => {
    const d = duts.find(d => (d.channel ?? d.dut) === ch)
    const rs = runState?.duts.find(d => (d.channel ?? d.dut) === ch)
    const st = site1?.duts.find(d => d.slot === ch)
    return d ? manualStatus(d, rs, st, sim.serverOnline, clockSec) : st
  }

  const manualLogs = useMemo(() => mergeManualLogs(sim.logs, sim.dutLogs, duts.map(chOf)),
    [sim.logs, sim.dutLogs, duts])
  const visibleLogs = useMemo(() => visibleManualLogs(manualLogs, logClear), [manualLogs, logClear])
  const logs = tab === 'all' ? visibleLogs
    : visibleLogs.filter(e => e.siteId === 1 && e.slot === Number(tab.slice(4)))

  // ── 总览 = 里程碑日志：只保留阶段进入行 / 错误 / 连接事件(上电·READY·配置·结果) ──
  // 阶段判据（2026-09-18 现场日志实证的标记行）：
  //   PL = preloader 横幅 / ready；LK = [LEDS]LK / [LK_ENV]；APK = Linux 启动 / memtester
  const runningDut = (() => {
    const rs = runState?.duts.filter(x => x.state === 'running') ?? []
    return rs.length === 1 ? (rs[0].channel ?? rs[0].dut) : null
  })()
  const STAGE_RE: { stage: 'pl' | 'lk' | 'apk'; re: RegExp }[] = [
    { stage: 'pl', re: /FIRMWARE UPDATE COMPLETE|preloader ready/i },
    { stage: 'lk', re: /\[LEDS\]LK|\[LK_ENV\]|Welcome to lk|jump to LK/i },
    { stage: 'apk', re: /Booting Linux|Linux version|\[MEMTEST\]|memtester|memtest\.sh|Loop \d+ \(/i },
  ]
  const stageOf = (msg: string): 'pl' | 'lk' | 'apk' | null => {
    for (const { stage, re } of STAGE_RE) if (re.test(msg)) return stage
    return null
  }
  // 已知良性告警（2026-09-19 逐条溯源确认不影响 DRAM 测试；完整日志页签仍可见）：
  //   RPMB 密钥未编程（只影响刷机写保护）/ LK ota-fail（无升级包）/ DCM·SSMR 可选
  //   属性缺失（手机参考设计遗留）/ WDT DDR reserve（冷启动正常路径）/ SCP 控制器
  const BENIGN_RE = [
    /RPMB|rpmb_|Authentication Key|write_protect|Lock (boot region|md1img|seccfg|lk|preloader)/i,
    /\[LK\] ota-fail/,
    /\[DCM\] get property info fail/,
    /memory_ssmr_fixup/,
    /WDT DDR reserve mode FAIL/,
    /SCPCTL\]: scpctl fail/,
  ]
  const isBenign = (msg: string) => BENIGN_RE.some(re => re.test(msg))
  const events = useMemo(() => {
    const seen = new Set<string>()
    const out: LogEntry[] = []
    for (const e of visibleLogs) {
      const slot = e.slot ?? runningDut
      const stg = stageOf(e.msg)
      const key = `${slot}|${stg}`
      const benign = e.level === 'ERROR' && isBenign(e.msg)
      const isEvent = !benign && (e.cat === 'conn'
        || e.level === 'ERROR'
        || (stg && !seen.has(key)))            // 每阶段只保留首达行
      if (stg) seen.add(key)
      if (isEvent) out.push(e)
    }
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleLogs, runState])
  const benignCount = useMemo(
    () => visibleLogs.filter(e => e.level === 'ERROR' && isBenign(e.msg)).length,
    [visibleLogs])
  // 总览页签展示里程碑日志；DUT 页签展示该路完整日志（均在下方统一终端渲染）
  const viewLogs = tab === 'all' ? events : logs

  const linkMeta: Record<LinkState, { dot: string; text: string; pulse: boolean }> = {
    check: { dot: 'var(--st-testing)', text: t('mdLinkCheck'), pulse: true },
    ok: { dot: 'var(--st-pass)', text: t('mdLinkOk'), pulse: false },
    down: { dot: 'var(--st-fail)', text: t('mdLinkDown'), pulse: true },
  }
  const lm = linkMeta[link]

  const tabBtn = (active: boolean, abnormal: boolean) =>
    `shrink-0 px-4 py-1.5 font-mono text-[11px] font-bold transition-colors flex items-center gap-1.5 border-b-2
     ${active
       ? abnormal
         ? 'text-[var(--st-fail)] border-[var(--st-fail)] bg-[var(--bg)]'
         : 'text-[var(--text)] border-[var(--accent)] bg-[var(--bg)]'
       : abnormal
         ? 'text-[var(--st-fail)] border-transparent hover:bg-[var(--row-hover)]'
         : 'text-[var(--chrome-text)] border-transparent hover:text-[var(--text)] hover:bg-[var(--strip)]'
     }`

  return (
    <div className="h-screen flex flex-col bg-[var(--bg)] text-[var(--text)] overflow-hidden"
         style={{ zoom: loadZoom() }}>
      {/* ══ 控制台顶栏 ══ */}
      <header className="h-12 flex items-center gap-3 px-4 bg-gradient-to-b from-[var(--topbar-from)] to-[var(--topbar-to)] border-b border-[var(--line)] shrink-0">
        <button
          onClick={() => nav('/')}
          className="px-3 py-1 rounded-sm border border-[var(--line)] text-[12px] font-bold text-[var(--topbar-nav)] hover:text-[var(--topbar-text)] hover:bg-white/5 transition-colors"
        >
          {t('mdBack')}
        </button>
        <div className="leading-none">
          <div className="font-mono font-extrabold text-[15px] tracking-widest text-[var(--logo)]">
            {t('mdTitle')}
          </div>
        </div>

        {/* 通讯板链路心跳徽章 */}
        {info && (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-[var(--line)] font-mono text-[11px] font-bold"
                style={{ color: lm.dot }}>
            <span className={`inline-block w-2 h-2 rounded-full ${lm.pulse ? 'animate-pulse' : ''}`}
                  style={{ backgroundColor: lm.dot, boxShadow: `0 0 6px ${lm.dot}` }} />
            {lm.text}
            <span className="text-[var(--topbar-sub)] font-normal">
              {info.boardHost}:{info.mbPort}
            </span>
          </span>
        )}

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => setShowSettings(v => !v)}
            className={`px-3 py-1.5 rounded-sm font-mono text-[12px] font-bold border transition-colors ${
              showSettings
                ? 'border-[var(--accent)] text-[var(--accent)] bg-[var(--accent)]/10'
                : 'border-[var(--line)] text-[var(--topbar-nav)] hover:text-[var(--topbar-text)] hover:bg-white/5'}`}
          >
            ⚙ {t('mdSettings')}
          </button>
          {notice && (
            <span className="font-mono text-[12px] font-bold text-[var(--st-fail)] max-w-[420px] truncate"
                  title={notice}>{notice}</span>
          )}
          <button
            disabled={busy !== null || !info?.enabled}
            onClick={() => powerAll(true)}
            className="px-3 py-1.5 rounded-sm font-mono text-[12px] font-bold border border-[var(--st-pass)] text-[var(--st-pass)] bg-[var(--st-pass)]/10 hover:bg-[var(--st-pass)]/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {busy === 'all' ? t('mdBatchOn') : `▶ ${t('mdAllOn')}`}
          </button>
          <button
            disabled={busy !== null || !info?.enabled}
            onClick={() => powerAll(false)}
            className="px-3 py-1.5 rounded-sm font-mono text-[12px] font-bold border border-[var(--st-fail)] text-[var(--st-fail)] bg-[var(--st-fail)]/10 hover:bg-[var(--st-fail)]/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ■ {t('mdAllOff')}
          </button>
        </div>
      </header>

      {saveMsg && (!showSettings || !form) && !saveMsg.ok && (
        <div role="alert" className="mx-3 mt-2 text-[12px] text-[var(--st-fail)] whitespace-pre-wrap">{saveMsg.text}</div>
      )}

      {info && !info.enabled && (
        <div className="mx-3 mt-2 px-3 py-2 rounded-sm border border-[var(--st-testing)] text-[var(--st-testing)] font-mono text-[12px] shrink-0">
          {t('mdDisabled')}
        </div>
      )}

      {/* ══ DUT 电源通道排：固定 4 列网格，≤4 路一行、5-8 路两行 ══ */}
      <div className="grid gap-3 p-3 shrink-0"
           style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
        {duts.map(d => {
          const ch = chOf(d)
          const st = dutStatus(ch)
          const connected = st?.connected ?? false
          const failed = st?.state === 'FAIL'
          const testing = st?.state === 'TESTING'
          const powerAction = runState?.duts.find(x => (x.channel ?? x.dut) === ch)?.powerAction
          return (
            <div key={d.dut}
                 className={`group/card relative panel rounded-sm p-3 min-h-[120px] flex flex-col gap-2 border transition-shadow ${
                   failed ? 'border-[var(--st-fail)] animate-pulse' : 'border-[var(--line)]'}`}
                 style={testing
                   ? { boxShadow: '0 0 18px -6px var(--st-testing), inset 0 0 12px -8px var(--st-testing)' }
                   : undefined}>

              {/* 移除按钮：绝对定位右上角，卡片 hover 淡入；移除中常显「…」。
                  身份 = d.dut 后端序号（上电中/运行中后端会拒绝） */}
              <button
                onClick={() => removeDut(d.dut)}
                disabled={busy !== null || (info !== null && !info.enabled)}
                title={t('mdRemoveDut')}
                className={`absolute top-1.5 right-1.5 z-10 w-[18px] h-[18px] flex items-center justify-center
                            rounded-sm font-light text-[14px] leading-none
                            text-[var(--text3)] hover:text-[var(--st-fail)]
                            transition-opacity disabled:cursor-not-allowed
                            ${busy === d.dut ? 'opacity-100' : 'opacity-0 group-hover/card:opacity-100 disabled:opacity-0 group-hover/card:disabled:opacity-40'}`}
              >
                {busy === d.dut ? '…' : '×'}
              </button>

              {/* 模块头：编号（真实通道号） + 连接灯 */}
              <div className="flex items-center justify-between">
                <span className="font-mono font-extrabold text-[18px] tracking-wide leading-none">
                  DUT <span className="text-[var(--accent)]">{pad(ch)}</span>
                </span>
                <span className="flex items-center gap-1.5 font-mono text-[10px] text-[var(--text3)] whitespace-nowrap">
                  <span className={`inline-block w-2.5 h-2.5 rounded-full ${
                    connected ? 'bg-[var(--st-pass)]' : 'bg-[var(--st-offline)] border border-[var(--line)]'}`}
                    style={connected ? { boxShadow: '0 0 6px var(--st-pass)' } : undefined} />
                  {connected ? t('connOnline') : t('connOffline')}
                </span>
              </div>

              {/* 机械拨杆开关 */}
              <button
                disabled={busy !== null || (info !== null && !info.enabled)}
                onClick={() => toggleOne(d.dut, !d.powerOn)}
                aria-label={`DUT ${pad(ch)} ${d.powerOn ? t('mdPowerOff') : t('mdPowerOn')}`}
                className="group flex items-center gap-3 py-1 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <span className={`relative w-14 h-7 rounded-full border transition-colors shrink-0 ${
                  d.powerOn ? 'bg-[var(--accent)]/20 border-[var(--accent)]' : 'bg-[var(--bg)] border-[var(--line)]'
                }`}>
                  <span
                    className="absolute top-0.5 rounded-full transition-all duration-200"
                    style={{
                      height: 22, width: 22,
                      left: d.powerOn ? 'calc(100% - 24px)' : 2,
                      backgroundColor: d.powerOn ? 'var(--accent)' : 'var(--text3)',
                      boxShadow: d.powerOn ? '0 0 10px var(--accent)' : 'none',
                    }}
                  />
                </span>
                <span className={`font-mono text-[13px] font-extrabold tracking-widest whitespace-nowrap ${
                  d.powerOn ? 'text-[var(--accent)]' : 'text-[var(--text3)] group-hover:text-[var(--text)]'
                }`}>
                  {powerAction === 'turning_on' ? t('mdPoweringOn')
                    : powerAction === 'turning_off' ? t('mdPoweringOff')
                    : busy === d.dut || busy === 'all' ? '…'
                    : d.powerOn ? t('mdPowered') : t('mdOff')}
                </span>
              </button>

              {/* 完整运行状态（full_run 模式；READY→cfg→ACK 状态机） */}
              {runState?.mode === 'full_run' && (() => {
                const rs = runState.duts.find(x => (x.channel ?? x.dut) === ch)
                const phase = rs && (!sim.serverOnline && !['pass', 'fail', 'timeout'].includes(rs.state) ? 'offline' : rs.state)
                const meta = phase && RUN_STATE_META[phase]
                if (!rs || !meta) return null
                return (
                  <div className="font-mono text-[10px] font-bold flex justify-between"
                       style={{ color: meta.color }}
                       title={rs.powerError ? `${rs.detail} · ${t('mdReqFail')}: ${rs.powerError}` : rs.detail}>
                    <span className={rs.state === 'wait_ready' || rs.state === 'cfg_sent' ? 'animate-pulse' : ''}>
                      {t(meta.textKey as Parameters<typeof t>[0])}
                    </span>
                    <span className="text-[var(--text3)] font-normal">
                      {fmtDur(runElapsed(rs, clockSec))}{rs.detail ? ` · ${rs.detail}` : ''}{rs.powerError ? ` · ${t('mdReqFail')}: ${rs.powerError}` : ''}
                    </span>
                  </div>
                )
              })()}

              {/* 测试状态 / 进度 */}
              <div className="min-h-[26px]">
                {testing ? (
                  <div>
                    <div className="flex justify-between font-mono text-[10px] text-[var(--st-testing)] mb-1">
                      <span className="truncate">{st?.step || t('stTesting')}</span>
                      <span>{st?.progress ?? 0}%</span>
                    </div>
                    <div className="h-1 rounded-full bg-[var(--line)] overflow-hidden">
                      <div className="h-full bg-[var(--st-testing)] transition-all duration-500"
                           style={{ width: `${st?.progress ?? 0}%` }} />
                    </div>
                  </div>
                ) : (
                  <div className="font-mono text-[10px]" style={{
                    color: failed ? 'var(--st-fail)'
                      : st?.state === 'PASS' ? 'var(--st-pass)' : 'var(--text3)',
                  }}>
                    {failed ? `FAIL ${st?.failItem ?? ''}`
                      : st?.state === 'PASS' ? `PASS · ${fmtDur(st?.durationSec ?? 0)}`
                      : st?.state ?? 'OFFLINE'}
                  </div>
                )}
              </div>
            </div>
          )
        })}

        {/* 「+」添加卡片（游戏空槽位风格）：虚线边框 + 圆环细体 +，与卡片等高 */}
        {canAdd && (
          <button
            onClick={addDut}
            disabled={busy !== null}
            title={t('mdAddDutTip')}
            className="group/slot rounded-sm p-3 min-h-[120px] flex flex-col items-center justify-center gap-2
                       border border-dashed border-[var(--line)] text-[var(--text3)]
                       hover:border-[var(--accent)] hover:text-[var(--accent)]
                       hover:shadow-[0_0_14px_-6px_var(--accent)]
                       transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <span className={`w-10 h-10 rounded-full border flex items-center justify-center
                              font-light text-[24px] leading-none select-none
                              border-[var(--line)] group-hover/slot:border-[var(--accent)]
                              transition-colors ${busy === 'add' ? 'animate-pulse' : ''}`}>
              {busy === 'add' ? '…' : '+'}
            </span>
            <span className="font-mono text-[10px] font-bold tracking-widest whitespace-nowrap">
              {t('mdAddDut')}
            </span>
          </button>
        )}
      </div>

      {/* ══ 设置区（可折叠） ══ */}
      {showSettings && form && (
        <div className="mx-3 mb-3 panel rounded-sm border border-[var(--line)] shrink-0 max-h-[46vh] overflow-y-auto">
          <div className="grid gap-3 p-3 lg:grid-cols-2">
            {/* 左列：IP / 日志路径 / 运行模式 */}
            <div className="flex flex-col gap-3">
              <div>
                <div className="font-mono text-[10px] font-bold tracking-widest text-[var(--text3)] mb-1.5">
                  {t('mdSecIp')}
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <label className="flex flex-col gap-1">
                    <span className="font-mono text-[10px] text-[var(--text3)]">{t('mdBoardIp')}</span>
                    <input
                      value={form.boardHost}
                      onChange={e => setForm({ ...form, boardHost: e.target.value })}
                      className="px-2 py-1 rounded-sm border border-[var(--line)] bg-[var(--bg)] font-mono text-[12px] text-[var(--text)] outline-none focus:border-[var(--accent)]"
                    />
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className="font-mono text-[10px] text-[var(--text3)]">{t('mdLocalIp')}</span>
                    <input
                      value={form.localIp}
                      onChange={e => setForm({ ...form, localIp: e.target.value })}
                      className="px-2 py-1 rounded-sm border border-[var(--line)] bg-[var(--bg)] font-mono text-[12px] text-[var(--text)] outline-none focus:border-[var(--accent)]"
                    />
                  </label>
                </div>
              </div>

              <div>
                <div className="font-mono text-[10px] font-bold tracking-widest text-[var(--text3)] mb-1.5">
                  {t('mdSecLog')}
                </div>
                <div className="flex gap-1.5">
                  <input
                    value={form.logDir}
                    placeholder={t('mdLogDirPh')}
                    onChange={e => setForm({ ...form, logDir: e.target.value })}
                    className="flex-1 min-w-0 px-2 py-1 rounded-sm border border-[var(--line)] bg-[var(--bg)] font-mono text-[12px] text-[var(--text)] outline-none focus:border-[var(--accent)]"
                  />
                  <button
                    onClick={() => openBrowse(form.logDir || form.latestRunDir || '')}
                    className="px-2.5 rounded-sm border border-[var(--line)] text-[12px] text-[var(--text3)] hover:text-[var(--text)] hover:border-[var(--accent)] transition-colors shrink-0"
                    title={t('mdBrowse')}
                  >
                    📂
                  </button>
                </div>
              </div>

              <div>
                <div className="font-mono text-[10px] font-bold tracking-widest text-[var(--text3)] mb-1.5">
                  {t('mdSecRun')}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  {(['power_only', 'full_run'] as const).map(m => (
                    <button
                      key={m}
                      onClick={() => applyRunMode(m)}
                      className={`px-3 py-1 rounded-sm font-mono text-[12px] font-bold border transition-colors ${
                        form.runMode === m
                          ? 'border-[var(--accent)] text-[var(--accent)] bg-[var(--accent)]/10'
                          : 'border-[var(--line)] text-[var(--text3)] hover:text-[var(--text)]'}`}
                    >
                      {m === 'power_only' ? t('mdModePower') : t('mdModeFull')}
                    </button>
                  ))}
                  <label className="flex items-center gap-1.5 ml-2">
                    <span className="font-mono text-[10px] text-[var(--text3)]">{t('mdReadyTimeout')}</span>
                    <input
                      type="number"
                      min={5}
                      max={3600}
                      value={form.readyTimeoutSec}
                      onChange={e => setForm({ ...form, readyTimeoutSec: Number(e.target.value) })}
                      className="w-20 px-2 py-1 rounded-sm border border-[var(--line)] bg-[var(--bg)] font-mono text-[12px] text-[var(--text)] outline-none focus:border-[var(--accent)]"
                    />
                  </label>
                  <label className="flex items-center gap-1.5 ml-2" title={t('mdTestTimeoutTip')}>
                    <span className="font-mono text-[10px] text-[var(--text3)]">{t('mdTestTimeout')}</span>
                    <input
                      type="number"
                      min={0}
                      max={86400}
                      value={form.testTimeoutSec}
                      onChange={e => setForm({ ...form, testTimeoutSec: Number(e.target.value) })}
                      className="w-20 px-2 py-1 rounded-sm border border-[var(--line)] bg-[var(--bg)] font-mono text-[12px] text-[var(--text)] outline-none focus:border-[var(--accent)]"
                    />
                  </label>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <label htmlFor="manual-cfg-file" className="text-[12px] whitespace-nowrap">{t('mdCfgFile')}</label>
                <input id="manual-cfg-file" value={cfgFile} onChange={e => setCfgFile(e.target.value)}
                  className="min-w-0 flex-1 px-2 py-1 rounded-sm border border-[var(--line)] bg-[var(--bg)] font-mono text-[12px] text-[var(--text)]" />
                <button disabled={cfgApplying || saving} onClick={() => {
                  const path = cfgFile.replace(/[/\\][^/\\]*$/, '')
                  void openBrowse(path, 'cfg')
                }} className="btn-gray px-2 py-1 text-[12px]">{t('spChoose')}</button>
                <button disabled={cfgApplying || saving} onClick={() => { void loadCfgFile() }}
                  className="btn-gray px-2 py-1 text-[12px]">{t('mdCfgRead')}</button>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[12px] text-[var(--text2)] flex-1">{form.cfgProduct}</span>
                <button disabled={cfgApplying || saving || !form.cfgProduct} onClick={async () => {
                  setSaving(true)
                  try { await saveCfg() } finally { setSaving(false) }
                }} className="btn-gray px-3 py-1 text-[12px]">{cfgApplying || saving ? t('mdSaving') : t('btnSave')}</button>
                <button disabled={cfgApplying || saving} onClick={() => { void openProductSettings() }}
                  className="btn-gray px-3 py-1 text-[12px]">{t('mdOpenProductSettings')}</button>
              </div>
              <textarea aria-label="CFG" value={cfgDraft}
                onChange={e => { setCfgDraft(e.target.value); setCfgMsg(null); setNotice('') }} spellCheck={false}
                className="flex-1 min-h-[180px] px-2 py-1.5 rounded-sm border border-[var(--line)] bg-[var(--bg)] font-mono text-[11px] leading-[1.6] text-[var(--text)] outline-none focus:border-[var(--accent)] resize-y" />
              {cfgMsg && <div role={cfgMsg.ok ? 'status' : 'alert'} className="text-[11px] whitespace-pre-wrap break-words"
                style={{ color: cfgMsg.ok ? 'var(--st-pass)' : 'var(--st-fail)' }}>{cfgMsg.text}</div>}
            </div>
          </div>

          {/* 保存行 */}
          <div className="flex items-center gap-3 px-3 pb-3">
            <button
              disabled={saving || cfgApplying}
              onClick={saveSettings}
              className="px-4 py-1.5 rounded-sm font-mono text-[12px] font-bold border border-[var(--accent)] text-[var(--accent)] bg-[var(--accent)]/10 hover:bg-[var(--accent)]/25 transition-colors disabled:opacity-40"
            >
              {saving ? t('mdSaving') : t('mdSave')}
            </button>
            <button
              onClick={async () => {
                // 先跳转到当前 session_settings.json 所在目录,浏览弹窗选 .json 文件
                try {
                  const s = await fetch(`${API_BASE}/api/manual/settings`).then(r => r.json())
                  const sfDir = s.settingsFile ? s.settingsFile.replace(/\\[^\\]+$/, '') : ''
                  const p = sfDir ? `?path=${encodeURIComponent(sfDir)}` : ''
                  const r = await fetch(`${API_BASE}/api/manual/browse${p}${p ? '&' : '?'}files=json`)
                  if (r.ok) {
                    setBrowseMode('json')
                    setBrowse(await r.json())
                  }
                } catch { /* 静默 */ }
              }}
              className="px-3 py-1.5 rounded-sm font-mono text-[12px] font-bold border border-[var(--line)] text-[var(--text3)] hover:text-[var(--text)] hover:border-[var(--accent)] transition-colors"
              title={t('mdOpenSettingsFileTip')}
            >
              {t('mdOpenSettingsFile')}
            </button>

            {/* 隐藏的文件选择器(读取设置按钮触发) */}
            <input
              ref={settingsFileRef}
              type="file"
              accept=".json"
              className="hidden"
              onChange={e => {
                const file = e.target.files?.[0]
                if (!file) return
                const reader = new FileReader()
                reader.onload = () => {
                  setSettingsFile({
                    path: file.name,
                    content: String(reader.result ?? ''),
                    exists: true,
                  })
                }
                reader.readAsText(file)
                e.target.value = ''
              }}
            />
            {saveMsg && (
              <span className="font-mono text-[11px] font-bold"
                    style={{ color: saveMsg.ok ? 'var(--st-pass)' : 'var(--st-fail)' }}>
                {saveMsg.text}
              </span>
            )}
          </div>
        </div>
      )}

      {/* ══ 日志台 ══ */}
      <div className="flex-1 min-h-0 mx-3 mb-3 flex flex-col panel rounded-sm overflow-hidden">
        {/* 页签排（顶部）：总览 + 每 DUT */}
        <div className="flex items-stretch border-b border-[var(--line)] bg-[var(--chrome)] overflow-x-auto shrink-0"
             style={{ scrollbarWidth: 'thin', scrollbarColor: 'var(--scrollbar) var(--chrome)' }}>
          <button onClick={() => setTab('all')} className={tabBtn(tab === 'all', false)}>
            {t('mdTabAll')}
          </button>
          {duts.map(d => {
            const ch = chOf(d)
            const failed = dutStatus(ch)?.state === 'FAIL'
            const on = dutStatus(ch)?.connected
            return (
              <button key={d.dut} onClick={() => setTab(`dut-${ch}`)}
                      className={tabBtn(tab === `dut-${ch}`, failed)}>
                <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${
                  failed ? 'bg-[var(--st-fail)]' : on ? 'bg-[var(--st-pass)]' : 'bg-[var(--st-offline)]'}`} />
                DUT {pad(ch)}
              </button>
            )
          })}
          <div className="ml-auto flex items-center gap-3 px-3 shrink-0">
            {tab === 'all' && benignCount > 0 && (
              <span className="font-mono text-[10px] text-[var(--text3)] select-none"
                    title={t('mdBenignTip')}>
                {t('mdBenign')} ×{benignCount}
              </span>
            )}
            <button
              onClick={() => setAutoScroll(v => !v)}
              className={`font-mono text-[10px] font-bold px-2 py-0.5 rounded-sm border transition-colors ${
                autoScroll
                  ? 'border-[var(--accent)] text-[var(--accent)]'
                  : 'border-[var(--line)] text-[var(--text3)] hover:text-[var(--text)]'}`}
            >
              {t('mdAutoScroll')}
            </button>
            <button
              onClick={() => setLogClear(prev => clearManualLogs(prev,
                tab === 'all' ? null : Number(tab.slice(4)), manualLogs.at(-1)?.id ?? 0))}
              className="font-mono text-[10px] font-bold px-2 py-0.5 rounded-sm border border-[var(--line)] text-[var(--text3)] hover:text-[var(--st-fail)] hover:border-[var(--st-fail)] transition-colors"
              title={t('mdClearLogTip')}
            >
              ⌫ {t('mdClearLog')}
            </button>
          </div>
        </div>

        {/* 终端本体：总览=里程碑日志（阶段进入/错误/开始测试）；DUT 页签=完整日志 */}
        <div ref={logRef}
             className="flex-1 min-h-0 overflow-y-auto px-3 py-2 font-mono text-[12px] leading-[1.7] bg-[var(--bg)]">
          {viewLogs.length === 0 && (
            <div className="text-[var(--text3)] py-6 text-center tracking-widest">
              —— {tab === 'all' ? t('mdNoEvents') : t('dutLogEmpty')} ——
            </div>
          )}
          {(() => {
            const rows: { id: number; ts: string; cat: LogEntry['cat']; level: LogEntry['level']; msg: string; n: number }[] = []
            const pos = new Map<string, number>()
            for (const e of viewLogs) {
              const k = `${e.slot}|${e.msg}`
              const i = pos.get(k)
              if (i === undefined) {
                pos.set(k, rows.length)
                rows.push({ id: e.id, ts: e.ts, cat: e.cat, level: e.level, msg: e.msg, n: 1 })
              } else {
                rows[i].n++
              }
            }
            const STAGE_CHIP: Record<string, { text: string; color: string }> = {
              pl: { text: 'PL', color: 'var(--st-testing)' },
              lk: { text: 'LK', color: 'var(--accent)' },
              apk: { text: 'APK', color: 'var(--st-pass)' },
            }
            return rows.map(r => {
              const chip = CAT_CHIP[r.cat]
              const stg = tab === 'all' ? stageOf(r.msg) : null
              const sc = stg ? STAGE_CHIP[stg] : undefined
              return (
                <div key={r.id}
                     className="whitespace-pre-wrap break-all hover:bg-[var(--row-hover)]"
                     style={{ contentVisibility: 'auto', containIntrinsicSize: 'auto 20px' }}>
                  <span className="text-[var(--text3)] select-none">{r.ts.slice(11)}</span>
                  {chip && (
                    <span className="mx-1.5 px-1 rounded-sm text-[9px] font-bold border select-none"
                          style={{ color: chip.color, borderColor: chip.color }}>
                      {chip.text}
                    </span>
                  )}
                  {sc && (
                    <span className="mr-1 px-1 rounded-sm text-[9px] font-bold border select-none"
                          style={{ color: sc.color, borderColor: sc.color }}>
                      ▶ {sc.text}
                    </span>
                  )}
                  {r.n > 1 && (
                    <span className="mr-1 px-1 rounded-sm text-[9px] font-bold select-none bg-[var(--text3)]/20 text-[var(--text3)]">
                      ×{r.n}
                    </span>
                  )}
                  <span className={chip ? '' : 'ml-1.5'}
                        style={{ color: LEVEL_COLOR[r.level] ?? 'var(--text)' }}>
                    {r.msg}
                  </span>
                </div>
              )
            })
          })()}
        </div>
      </div>

      {/* 目录/文件浏览弹窗（Log 路径=目录模式, cfg 路径=文件模式） */}
      {browse && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
             onClick={() => setBrowse(null)}>
          <div className="w-[480px] max-h-[70vh] flex flex-col panel rounded-sm border border-[var(--line)] bg-[var(--bg)]"
               onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--line)]">
              <button onClick={() => openBrowse(browse.parent, browseMode)} disabled={!browse.parent}
                      className="px-2 py-0.5 rounded-sm border border-[var(--line)] text-[12px] text-[var(--text3)] hover:text-[var(--text)] disabled:opacity-30">
                ⬆
              </button>
              <span className="flex-1 truncate font-mono text-[12px] text-[var(--text)]">
                {browse.path || t('mdBrowseRoot')}
              </span>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto p-1">
              {browse.drives.map(d => (
                <button key={d} onClick={() => openBrowse(d, browseMode)}
                        className="w-full text-left px-3 py-1 font-mono text-[12px] text-[var(--text)] hover:bg-[var(--row-hover)] rounded-sm">
                  💾 {d}
                </button>
              ))}
              {browse.dirs.map(d => (
                <button key={d} onClick={() => openBrowse(browse.path + '\\' + d, browseMode)}
                        className="w-full text-left px-3 py-1 font-mono text-[12px] text-[var(--text)] hover:bg-[var(--row-hover)] rounded-sm">
                  📁 {d}
                </button>
              ))}
              {browseMode !== 'dir' && browse.files?.map(f => (
                <button key={f} onClick={async () => {
                  const fullPath = browse.path + '\\' + f
                  if (browseMode === 'cfg') { await loadCfgFile(fullPath); setBrowse(null); return }
                  // 读文件内容 → 弹设置预览+导入弹窗
                  try {
                    // 用 FileReader 不行(拿不到绝对路径),改走后端读文件
                    const sf = await fetch(`${API_BASE}/api/manual/read_file?path=${encodeURIComponent(fullPath)}`)
                    if (sf.ok) {
                      const data = await sf.json()
                      setSettingsFile({ path: fullPath, content: data.content, exists: true })
                    }
                  } catch { /* 静默 */ }
                  setBrowse(null)
                }}
                        className="w-full text-left px-3 py-1 font-mono text-[12px] text-[var(--accent)] hover:bg-[var(--row-hover)] rounded-sm">
                  📄 {f}
                </button>
              ))}
              {!browse.drives.length && !browse.dirs.length && !(browseMode !== 'dir' && browse.files?.length) && (
                <div className="text-center text-[var(--text3)] text-[12px] py-4">—</div>
              )}
            </div>
            <div className="flex items-center gap-2 px-3 py-2 border-t border-[var(--line)]">
              <button onClick={() => setBrowse(null)}
                      className="px-3 py-1 rounded-sm border border-[var(--line)] text-[12px] text-[var(--text3)] hover:text-[var(--text)]">
                {t('mdBrowseCancel')}
              </button>
              {browseMode === 'dir' && (
                <button onClick={() => { setForm(f => f ? { ...f, logDir: browse.path } : f); setBrowse(null) }}
                        disabled={!browse.path}
                        className="ml-auto px-4 py-1 rounded-sm border border-[var(--accent)] text-[var(--accent)] bg-[var(--accent)]/10 text-[12px] font-bold hover:bg-[var(--accent)]/25 disabled:opacity-40">
                  {t('mdBrowsePick')}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 设置文件预览 + 导入弹窗（「读取设置」→ 选文件 → 预览 → 导入） */}
      {settingsFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
             onClick={() => setSettingsFile(null)}>
          <div className="w-[560px] max-h-[70vh] flex flex-col panel rounded-sm border border-[var(--line)] bg-[var(--bg)]"
               onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--line)]">
              <span className="text-[12px] font-bold text-[var(--text)]">📄 {settingsFile.path}</span>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto px-3 py-2">
              <pre className="font-mono text-[11px] text-[var(--text)] whitespace-pre-wrap break-all leading-[1.6]">
                {settingsFile.content}
              </pre>
            </div>
            <div className="flex items-center gap-2 px-3 py-2 border-t border-[var(--line)]">
              <button onClick={() => settingsFileRef.current?.click()}
                      className="px-3 py-1 rounded-sm border border-[var(--line)] text-[12px] text-[var(--text3)] hover:text-[var(--text)]">
                {t('mdRePickFile')}
              </button>
              <button
                onClick={async () => {
                  try {
                    const json = JSON.parse(settingsFile.content)
                    const { updates, skipped } = manualRuntimeSettings(json)
                    const r = await fetch(`${API_BASE}/api/manual/settings`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify(updates),
                    })
                    if (r.ok) {
                      await refreshSettings()
                      setSaveMsg({ ok: true, text: skipped > 0
                        ? `${t('mdImported')} · ${t('mdRuntimeSkipped')}: ${skipped}` : t('mdImported') })
                      refreshInfo()
                      setSettingsFile(null)
                    } else {
                      const body = await r.json().catch(() => null)
                      setSaveMsg({ ok: false, text: `${t('mdReqFail')}: ${body?.detail ?? r.status}` })
                    }
                  } catch { setSaveMsg({ ok: false, text: t('mdReqFail') }) }
                }}
                className="px-4 py-1 rounded-sm border border-[var(--accent)] text-[var(--accent)] bg-[var(--accent)]/10 text-[12px] font-bold hover:bg-[var(--accent)]/25 transition-colors">
                {t('mdImportSettingsFile')}
              </button>
              <button onClick={() => setSettingsFile(null)}
                      className="ml-auto px-4 py-1 rounded-sm border border-[var(--line)] text-[12px] text-[var(--text3)] hover:text-[var(--text)]">
                {t('mdBrowseCancel')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
