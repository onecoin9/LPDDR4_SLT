import type { LogEntry, SiteStatus } from '@/types/dut'
import ChannelTable from '@/sections/ChannelTable'
import { t } from '@/lib/i18n'

const pad = (n: number) => String(n).padStart(2, '0')

interface Props {
  site: SiteStatus
  engineer: boolean
  selectedSlot: number | null
  onSelectSlot: (slot: number | null) => void
  onStartSite: () => void
  startDisabled?: boolean
  startHint?: string
  onStopSite: () => void
  dutLogs: Record<string, LogEntry[]>
}

// Site 标签页：该 site 的具体测试情况 —— 概要条 + 24 通道明细表
// 工程师模式额外提供单站启停（不影响其他 site）
export default function SiteDetail({ site, engineer, selectedSlot, onSelectSlot, onStartSite, onStopSite, dutLogs, startDisabled, startHint }: Props) {
  const online = site.duts.filter(d => d.connected).length
  const testing = site.duts.filter(d => d.state === 'TESTING').length
  const pass = site.duts.filter(d => d.state === 'PASS').length
  const fail = site.duts.filter(d => d.state === 'FAIL').length

  const chip = (label: string, value: string | number, cls = 'text-[var(--text)]') => (
    <div className="rounded-sm panel px-3 py-1.5">
      <span className="font-mono text-[10px] text-[var(--text3)] font-bold mr-2">{label}</span>
      <span className={`font-mono text-[14px] font-extrabold ${cls}`}>{value}</span>
    </div>
  )

  return (
    <section className="flex-1 min-h-0 flex flex-col p-2 gap-2">
      {/* 概要条 */}
      <div className="flex items-stretch gap-2 shrink-0 flex-wrap">
        <div className="rounded-sm panel px-3 py-1.5 flex items-baseline gap-2">
          <span className="font-mono text-[10px] text-[var(--text3)] font-bold">SITE</span>
          <span className="font-mono text-[18px] font-extrabold text-[var(--text)]">{pad(site.id)}</span>
        </div>
        {chip(t('chipOnline'), `${online}/24`, online === 24 ? 'text-[var(--st-pass)]' : 'text-[var(--st-fail)]')}
        {chip(t('chipTesting'), testing, testing > 0 ? 'text-[var(--st-testing)]' : 'text-[var(--text3)]')}
        {chip(t('stPass'), pass, pass > 0 ? 'text-[var(--st-pass)]' : 'text-[var(--text3)]')}
        {chip(t('stFail'), fail, fail > 0 ? 'text-[var(--st-fail)]' : 'text-[var(--text3)]')}
        {engineer && (
          <div className="flex items-center gap-2 ml-auto shrink-0">
            <button
              onClick={onStartSite}
              disabled={startDisabled}
              title={startHint || undefined}
              className="px-4 py-1.5 rounded-sm font-mono text-[12px] font-bold text-black
                         bg-[var(--accent)] hover:opacity-90 transition-opacity whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
            >
              ▶ {t('sdStartSite')}
            </button>
            <button
              onClick={onStopSite}
              className="px-4 py-1.5 rounded-sm font-mono text-[12px] font-bold
                         border border-[var(--st-fail)] text-[var(--st-fail)]
                         hover:bg-[var(--st-fail)] hover:text-black transition-colors whitespace-nowrap"
            >
              ■ {t('sdStopSite')}
            </button>
          </div>
        )}
      </div>

      {/* 24 通道明细表（点击行 → 打开该 DUT 日志弹框） */}
      <ChannelTable
        siteId={site.id}
        duts={site.duts}
        engineer={engineer}
        selectedSlot={selectedSlot}
        onSelect={onSelectSlot}
        dutLogs={dutLogs}
      />
    </section>
  )
}
