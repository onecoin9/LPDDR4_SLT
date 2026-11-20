import { Fragment, useState } from 'react'
import type { DutState, DutStatus, LogEntry } from '@/types/dut'
import { t } from '@/lib/i18n'
import { fmtDur } from '@/lib/utils'

// 通道表（主题变量 + i18n）
const STATE_CLS: Record<DutState, string> = {
  IDLE: 'text-[var(--text2)]',
  TESTING: 'text-[var(--st-testing)]',
  PASS: 'text-[var(--st-pass)]',
  FAIL: 'text-[var(--st-fail)]',
  OFFLINE: 'text-[var(--st-offline)]',
}

const STATE_LABEL: Record<DutState, () => string> = {
  IDLE: () => t('stIdleTable'),
  TESTING: () => t('stTestingEn'),
  PASS: () => t('stPass'),
  FAIL: () => t('stFail'),
  OFFLINE: () => t('stOffline'),
}

interface Props {
  siteId: number
  duts: DutStatus[]
  engineer: boolean
  selectedSlot: number | null
  onSelect: (slot: number | null) => void      // 点击行 → 打开该 DUT 日志弹框
  dutLogs: Record<string, LogEntry[]>          // key: `${siteId}:${slot}`
}

export default function ChannelTable({ siteId, duts, engineer, selectedSlot, onSelect, dutLogs }: Props) {
  const [hover, setHover] = useState<number | null>(null)

  // 双模式列差异化：操作员=极简（看通过/失败）；工程师=失败诊断（异常时回看最后 10 条日志）
  const cols = engineer
    ? [t('colCh'), t('colConn'), t('colState'), t('colDur'), t('colFail')]
    : [t('colCh'), t('colConn'), t('colState'), t('colDur')]
  const DUR_IDX = 3   // 测试时长列：收窄

  return (
    <section className="flex-1 min-w-0 flex flex-col rounded-sm panel overflow-hidden">
      <div className="flex-1 overflow-y-auto bg-[var(--table)]">
        <table className="w-full border-collapse text-[13px]">
          <thead className="sticky top-0 z-10">
            <tr className="bg-[var(--strip)]">
              {cols.map((c, i) => (
                <th key={c} className={`px-3 py-2.5 border border-[var(--line)] text-left font-mono text-[11px] font-bold text-[var(--text2)] whitespace-nowrap ${i === DUR_IDX ? 'w-[64px] px-2' : ''}`}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {duts.map((d, idx) => {
              const selected = selectedSlot === d.slot
              // 异常（FAIL/OFFLINE）时回看该通道最后 10 条 DUT 日志
              const abnormal = d.state === 'FAIL' || d.state === 'OFFLINE'
              const failTail = abnormal
                ? (dutLogs[`${siteId}:${d.slot}`] ?? []).slice(-10)
                : []
              // 隔行变色（斑马纹）；选中行高亮
              const zebra = idx % 2 === 1 ? 'bg-[var(--zebra)]' : 'bg-[var(--table)]'
              const rowCls = selected
                ? 'bg-[var(--sel)] text-[var(--sel-text)]'
                : `${d.state === 'OFFLINE' ? 'opacity-40' : ''} ${hover === d.slot ? 'bg-[var(--row-hover)]' : zebra}`
              const tdMain = selected ? 'text-[var(--sel-text)]' : 'text-[var(--text)]'
              const tdSub = selected ? 'text-[var(--sel-sub)]' : ''
              return (
                <Fragment key={d.slot}>
                  <tr
                    onClick={() => onSelect(selected ? null : d.slot)}
                    onMouseEnter={() => setHover(d.slot)}
                    onMouseLeave={() => setHover(null)}
                    className={`cursor-pointer transition-colors ${rowCls}`}
                  >
                    <td className={`px-3 py-2 border border-[var(--line)] font-mono font-bold ${tdMain}`}>
                      {String(d.slot).padStart(2, '0')}
                    </td>
                    <td className={`px-3 py-2 border border-[var(--line)] font-mono text-[12px] ${tdSub}`}>
                      {d.connected
                        ? <span className={selected ? '' : 'text-[var(--st-pass)]'}>● {t('connOnline')}</span>
                        : <span className={selected ? '' : 'text-[var(--st-offline)]'}>○ {t('connOffline')}</span>}
                    </td>
                    <td className={`px-3 py-2 border border-[var(--line)] font-mono font-bold ${selected ? '' : STATE_CLS[d.state]}`}>
                      {d.state === 'TESTING' && (
                        <span className={`inline-block w-16 h-1.5 mr-2 rounded align-middle overflow-hidden ${selected ? 'bg-black/30' : 'bg-[var(--line)]'}`}>
                          <span className="block h-full bg-[var(--accent)]" style={{ width: `${d.progress}%` }} />
                        </span>
                      )}
                      {STATE_LABEL[d.state]()}
                    </td>
                    <td className={`px-2 py-2 border border-[var(--line)] font-mono text-[12px] whitespace-nowrap ${tdMain}`}>
                      {d.state === 'IDLE' || d.state === 'OFFLINE' ? '-' : fmtDur(d.durationSec)}
                    </td>
                    {engineer && (
                      <td className="px-2 py-1 border border-[var(--line)] align-top">
                        {abnormal && failTail.length > 0 ? (
                          <div className="max-h-[64px] overflow-y-auto font-mono text-[10px] leading-snug" title={d.failItem ?? undefined}>
                            {failTail.map(e => (
                              <div
                                key={e.id}
                                className={`whitespace-nowrap ${e.level === 'ERROR' ? 'text-[var(--st-fail)]'
                                  : e.level === 'WARN' ? 'text-[var(--log-warn)]'
                                  : 'text-[var(--text2)]'}`}
                              >
                                {e.msg.replace(/^CH\d+\s*/, '')}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <span className={`font-mono text-[12px] ${d.failItem ? 'font-bold text-[var(--st-fail)]' : 'text-[var(--text3)]'}`}>
                            {d.failItem || '-'}
                          </span>
                        )}
                      </td>
                    )}
                  </tr>
                  {/* CH12 / CH13 之间加间隔带，区分两块通讯板（板1: 01-12 / 板2: 13-24） */}
                  {d.slot === 12 && (
                    <tr aria-hidden>
                      <td colSpan={cols.length} className="p-0 border border-[var(--line)]">
                        <div className="h-2.5 bg-[var(--chrome)]" />
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
