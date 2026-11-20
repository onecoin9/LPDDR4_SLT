import { useEffect, useRef, useState } from 'react'
import type { DutStatus, LogEntry, SessionConfig } from '@/types/dut'
import type { ProductProfile } from '@/types/product'
import { parseProfileJson } from '@/types/product'
import { t, type I18nKey } from '@/lib/i18n'

// 日志配色（主题变量驱动）
const LEVEL_COLOR: Record<LogEntry['level'], string> = {
  INFO: 'text-[var(--log-info)]',
  WARN: 'text-[var(--log-warn)]',
  ERROR: 'text-[var(--st-fail)]',
}

// 日志分类筛选：前五个按 cat，后两个按 level
type LogFilter = 'all' | 'system' | 'dut' | 'sys' | 'conn' | 'WARN' | 'ERROR'
const LOG_FILTERS: { key: LogFilter; labelKey: I18nKey }[] = [
  { key: 'all', labelKey: 'logCatAll' },
  { key: 'system', labelKey: 'logCatSystem' },
  { key: 'dut', labelKey: 'logCatDut' },
  { key: 'sys', labelKey: 'logCatSys' },
  { key: 'conn', labelKey: 'logCatConn' },
  { key: 'WARN', labelKey: 'logCatWarn' },
  { key: 'ERROR', labelKey: 'logCatError' },
]

interface Props {
  duts: DutStatus[]        // 全部 site 的扁平 DUT 列表
  logs: LogEntry[]
  config: SessionConfig
  onConfigChange: (c: SessionConfig) => void
  products: string[]       // 产品名列表（与设置-产品设置的 JSON 配置同步）
  onImportProfile: (p: ProductProfile) => void   // 选择按钮：从 JSON 文件导入产品档案并选中
  sessionElapsed: number
  totalSuccess: number
  totalRuns: number
  siteFilter: number | null   // null = 总览（全部 site）
  slotFilter: number | null
  onStart: () => void
  startDisabled?: boolean
  startHint?: string
  starting?: boolean
  startError?: string
  onStop: () => void
}

const inputCls = 'w-full px-2.5 py-1.5 rounded-sm bg-[var(--input)] border border-[var(--input-line)] font-mono text-[12px] text-[var(--text)] outline-none focus:border-[var(--accent)] placeholder:text-[var(--text3)] transition-colors'
const labelCls = 'font-mono text-[11px] font-bold text-[var(--text2)]'

export default function SidePanel(props: Props) {
  const { duts, logs, config, onConfigChange, products, sessionElapsed, totalSuccess, totalRuns, siteFilter, slotFilter } = props
  const logRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const [logFilter, setLogFilter] = useState<LogFilter>('all')

  const online = duts.filter(d => d.connected).length
  const testing = duts.filter(d => d.state === 'TESTING').length
  // 日志筛选：先按分类（cat/level），再按 site/通道；系统日志不受 site 筛选影响
  const filtered = logs.filter(l => {
    if (logFilter === 'WARN' || logFilter === 'ERROR') {
      if (l.level !== logFilter) return false
    } else if (logFilter !== 'all' && l.cat !== logFilter) {
      return false
    }
    if (l.slot === null) return true
    if (siteFilter === null) return true
    if (l.siteId !== siteFilter) return false
    return slotFilter === null || l.slot === slotFilter
  })
  const yieldStr = totalRuns > 0 ? `${((totalSuccess / totalRuns) * 100).toFixed(1)}%` : '-'

  // 日志区标题
  const p2 = (n: number) => String(n).padStart(2, '0')
  const filterLabel = siteFilter === null
    ? t('spAllSites')
    : slotFilter === null
      ? `SITE ${p2(siteFilter)}`
      : `SITE ${p2(siteFilter)} · CH ${p2(slotFilter)}`

  useEffect(() => {
    const el = logRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [filtered.length])

  const set = (k: keyof SessionConfig) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    onConfigChange({ ...config, [k]: e.target.value })

  // 选择按钮（导入配置）：从 JSON 文件导入产品档案（2026-10-13 恢复启用）
  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''   // 允许重复选同一文件
    if (!file) return
    file.text().then(text => {
      try {
        props.onImportProfile(parseProfileJson(text))
      } catch {
        window.alert(t('spBadProfileJson'))
      }
    })
  }

  return (
    <aside className="w-[340px] shrink-0 flex flex-col gap-2 min-h-0">
      {/* 机台信息 */}
      <section className="rounded-sm panel p-3">
        <h3 className={`${labelCls} mb-2`}>{t('spMachine')}</h3>
        <div className="space-y-1.5 text-[12px]">
          <div className="flex justify-between">
            <span className="text-[var(--text2)]">{t('spConn')}</span>
            <span className={`font-mono font-bold ${online > 0 ? 'text-[var(--st-pass)]' : 'text-[var(--st-fail)]'}`}>
              {online > 0 ? `${t('spConnected')} (${online}/${duts.length} ${t('connOnline')})` : t('spDisconnected')}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--text2)]">{t('spDevState')}</span>
            <span className={`font-mono font-bold ${testing > 0 ? 'text-[var(--st-testing)]' : 'text-[var(--text)]'}`}>
              {testing > 0 ? `${t('spTesting')} (${testing} ${t('spChannelUnit')})` : t('spReady')}
            </span>
          </div>
        </div>
      </section>

      {/* 产品 / 工单表单 */}
      <section className="rounded-sm panel p-3 space-y-2">
        <div className="flex items-center gap-2">
          <span className={`${labelCls} w-14 shrink-0`}>{t('spProduct')}</span>
          <select disabled={props.starting} value={config.product} onChange={set('product')} className={inputCls}>
            {products.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          {/* 导入配置入口：从 JSON 文件导入产品档案（2026-10-13 恢复） */}
          <input ref={fileRef} type="file" accept=".json,application/json" className="hidden" onChange={handleFile} />
          <button disabled={props.starting} onClick={() => fileRef.current?.click()} title={t('spChooseJson')} className="btn-gray px-2.5 py-1.5 rounded-sm text-[12px] whitespace-nowrap">
            {t('spChoose')}
          </button>
        </div>
        {([[t('spWo'), 'workOrder', 'WO-2026-XXXX'], [t('spLot'), 'lotNo', 'LOT-XXXX'], [t('spOperator'), 'operator', 'admin']] as const).map(([label, key, ph]) => (
          <div key={key} className="flex items-center gap-2">
            <span className={`${labelCls} w-14 shrink-0`}>{label}</span>
            <input disabled={props.starting} value={config[key]} onChange={set(key)} placeholder={ph} className={inputCls} />
          </div>
        ))}
        <div className="grid grid-cols-2 gap-2 pt-1">
          <button onClick={props.onStart} disabled={props.startDisabled} title={props.startHint || undefined}
            aria-describedby={props.startHint ? 'monitor-start-status' : undefined}
            className="py-2 rounded-sm bg-gradient-to-b from-[var(--accent-hi)] to-[var(--accent-to)] border border-[var(--accent-line)] text-[var(--accent-text)] text-[13px] font-extrabold hover:brightness-110 transition-all disabled:opacity-50 disabled:cursor-not-allowed">
            {props.starting ? t('startSubmitting') : t('spOk')}
          </button>
          <button onClick={props.onStop}
            className="btn-gray py-2 rounded-sm text-[13px] font-bold">
            {t('spStop')}
          </button>
          {/* 导出/导入按钮：暂不需要，注释隐藏备以后启用（2026-09-01）
          <button disabled title={t('spSoon')} className="btn-gray py-1.5 rounded-sm text-[12px]">
            {t('spExport')}
          </button>
          <button disabled title={t('spSoon')} className="btn-gray py-1.5 rounded-sm text-[12px]">
            {t('spImport')}
          </button>
          */}
        </div>
        {props.startHint && <p id="monitor-start-status" role="status" className="text-[12px] text-[var(--text2)]">{props.startHint}</p>}
        {props.startError && <p role="alert" className="text-[12px] text-[var(--st-fail)] whitespace-pre-wrap">{props.startError}</p>}
      </section>

      {/* 测试时长 / 总良率（主色条，紧凑版：把空间让给运行日志） */}
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-sm bg-gradient-to-br from-[var(--accent)] to-[var(--accent-to)] px-2 py-1 flex items-baseline gap-1.5">
          <span className="font-mono text-[9px] font-bold text-[var(--accent-text)] opacity-70">{t('spDuration')}</span>
          <span className="font-mono text-[13px] font-extrabold text-[var(--accent-text)]">{Math.round(sessionElapsed)} s</span>
        </div>
        <div className="rounded-sm bg-gradient-to-br from-[var(--accent)] to-[var(--accent-to)] px-2 py-1 flex items-baseline gap-1.5">
          <span className="font-mono text-[9px] font-bold text-[var(--accent-text)] opacity-70">{t('spYield')}</span>
          <span className="font-mono text-[13px] font-extrabold text-[var(--accent-text)]">{yieldStr}</span>
        </div>
      </div>

      {/* 日志区 */}
      <section className="flex-1 min-h-0 flex flex-col rounded-sm panel overflow-hidden">
        <header className="px-3 py-2 border-b border-[var(--line)] bg-[var(--strip)] flex items-center justify-between">
          <span className={labelCls}>{t('spLog')}</span>
          <span className="font-mono text-[10px] text-[var(--text3)]">
            {filterLabel}
          </span>
        </header>
        {/* 分类筛选 chips */}
        <div className="px-2 py-1.5 border-b border-[var(--line)] bg-[var(--strip)] flex flex-wrap gap-1">
          {LOG_FILTERS.map(f => {
            const active = logFilter === f.key
            return (
              <button
                key={f.key}
                onClick={() => setLogFilter(f.key)}
                className={`px-2 py-0.5 rounded-sm font-mono text-[10px] font-bold border transition-colors ${
                  active
                    ? 'bg-[var(--accent)] text-[var(--accent-text)] border-[var(--accent)]'
                    : 'bg-transparent text-[var(--text3)] border-[var(--line)] hover:text-[var(--text)] hover:border-[var(--accent)]'
                }`}
              >
                {t(f.labelKey)}
              </button>
            )
          })}
          <span className="ml-auto font-mono text-[10px] text-[var(--text3)] self-center">
            {filtered.length}
          </span>
        </div>
        <div ref={logRef} className="flex-1 overflow-y-auto bg-[var(--log-bg)] px-3 py-2 font-mono text-[11px] leading-relaxed">
          {filtered.map(l => (
            <div key={l.id} className="whitespace-pre-wrap break-all">
              <span className="text-[var(--log-ts)]">{l.ts}</span>{' '}
              <span className="text-[var(--log-ch)]">
                {l.slot === null ? 'SYS' : `S${p2(l.siteId ?? 0)}·CH${p2(l.slot)}`}
              </span>{' '}
              <span className={LEVEL_COLOR[l.level]}>[{l.level}] {l.msg}</span>
            </div>
          ))}
        </div>
      </section>
    </aside>
  )
}
