import { useEffect, useRef } from 'react'
import type { LogEntry } from '@/types/dut'
import { t } from '@/lib/i18n'

// DUT 运行日志弹框：点击通道行打开，实时滚动显示该通道日志（终端风格）
// 移植自旧上位机按 DUT 显示运行日志的交互形态

const LEVEL_COLOR: Record<LogEntry['level'], string> = {
  INFO: 'text-[var(--text2)]',
  WARN: 'text-[var(--log-warn)]',
  ERROR: 'text-[var(--st-fail)]',
}

const pad = (n: number) => String(n).padStart(2, '0')

interface Props {
  siteId: number
  slot: number
  entries: LogEntry[]
  onClose: () => void
}

export default function DutLogDialog({ siteId, slot, entries, onClose }: Props) {
  const bodyRef = useRef<HTMLDivElement>(null)

  // 新日志到达自动滚到底
  useEffect(() => {
    const el = bodyRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [entries.length])

  // Esc 关闭
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6"
      onClick={onClose}
    >
      <div
        className="w-[720px] max-w-full h-[70vh] flex flex-col rounded-sm panel overflow-hidden border border-[var(--line)] shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--line)] bg-[var(--chrome)] shrink-0">
          <div className="font-mono text-[13px] font-bold text-[var(--text)]">
            <span className="text-[var(--accent)]">SITE {pad(siteId)}</span>
            <span className="mx-2 text-[var(--text3)]">·</span>
            <span className="text-[var(--accent)]">CH {pad(slot)}</span>
            <span className="ml-3 text-[var(--text2)] font-normal">{t('dutLogTitle')}</span>
          </div>
          <button
            onClick={onClose}
            className="px-3 py-1 rounded-sm font-mono text-[12px] border border-[var(--line)]
                       text-[var(--text2)] hover:text-[var(--text)] hover:border-[var(--accent)] transition-colors"
          >
            ✕ {t('cancel')}
          </button>
        </div>
        {/* 日志终端 */}
        <div
          ref={bodyRef}
          className="flex-1 overflow-y-auto bg-[#0f1014] px-4 py-2 font-mono text-[12px] leading-relaxed"
          style={{ scrollbarWidth: 'thin', scrollbarColor: 'var(--scrollbar) #0f1014' }}
        >
          {entries.length === 0 && (
            <div className="text-[var(--text3)] py-4">{t('dutLogEmpty')}</div>
          )}
          {entries.map(e => (
            <div key={e.id} className="whitespace-pre-wrap break-all">
              <span className="text-[var(--text3)]">{e.ts.slice(11)} </span>
              <span className={LEVEL_COLOR[e.level]}>[{e.level}]</span>
              <span className="text-[var(--text)]"> {e.msg.replace(/^CH\d+\s*/, '')}</span>
            </div>
          ))}
        </div>
        {/* 底栏 */}
        <div className="px-4 py-1.5 border-t border-[var(--line)] bg-[var(--chrome)] font-mono text-[11px] text-[var(--text3)] shrink-0">
          {entries.length} {t('dutLogCount')} · Esc {t('cancel')}
        </div>
      </div>
    </div>
  )
}
