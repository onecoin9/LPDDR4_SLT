import { useEffect, useState } from 'react'
import type { MrRow } from '@/types/product'
import { t } from '@/lib/i18n'

interface Props {
  title: string                    // 如 "MR配置 · CH1"
  rows: MrRow[]
  onOk: (rows: MrRow[]) => void
  onCancel: () => void
}

const inputCls = 'w-full px-2 py-1 rounded-sm bg-[var(--input)] border border-[var(--input-line)] font-mono text-[12px] text-[var(--text)] outline-none focus:border-[var(--accent)] transition-colors'

// MR 配置弹窗（参照 SLT 上位机 MR配置 对话框）
export default function MRConfigDialog({ title, rows, onOk, onCancel }: Props) {
  const [draft, setDraft] = useState<MrRow[]>(() => structuredClone(rows))

  // Esc = 取消
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel])

  const patch = (i: number, p: Partial<MrRow>) =>
    setDraft(draft.map((r, idx) => (idx === i ? { ...r, ...p } : r)))

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50" onClick={onCancel}>
      <div
        className="w-[420px] max-w-[92vw] panel rounded-sm shadow-2xl flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div className="h-9 shrink-0 flex items-center px-3 bg-gradient-to-b from-[var(--topbar-from)] to-[var(--topbar-to)] border-b border-[var(--line)]">
          <span className="font-bold text-[12px] text-[var(--topbar-text)]">{title}</span>
          <button
            onClick={onCancel}
            className="ml-auto w-6 h-6 grid place-items-center rounded-sm text-[var(--topbar-nav)] hover:text-[var(--topbar-text)] hover:bg-white/10 transition-colors text-[11px]"
            title="Esc"
          >
            ✕
          </button>
        </div>

        {/* MR 表（无勾选项：填了期望值才校验，留空不校验） */}
        <div className="p-3">
          <div className="border border-[var(--line)] rounded-sm overflow-hidden">
            <table className="w-full border-collapse text-[12px]">
              <thead>
                <tr className="bg-[var(--strip)]">
                  {[t('colNo'), t('mrName'), t('mrValue')].map((c, i) => (
                    <th key={i} className="px-2 py-1.5 border border-[var(--line)] text-left font-mono text-[11px] font-bold text-[var(--text2)]">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {draft.map((r, i) => (
                  <tr key={r.name} className={i % 2 === 1 ? 'bg-[var(--zebra)]' : ''}>
                    <td className="px-2 py-1 border border-[var(--line)] font-mono text-[var(--text3)] w-12">{i + 1}</td>
                    <td className="px-2 py-1 border border-[var(--line)] font-mono font-bold text-[var(--text)]">{r.name}</td>
                    <td className="px-1 py-0.5 border border-[var(--line)]">
                      <input value={r.value} onChange={e => patch(i, { value: e.target.value })} className={inputCls} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* 确定 / 取消 */}
        <div className="flex justify-center gap-3 pb-3">
          <button
            onClick={() => onOk(draft)}
            className="px-6 py-1.5 rounded-sm bg-gradient-to-b from-[var(--accent-hi)] to-[var(--accent-to)] border border-[var(--accent-line)] text-[var(--accent-text)] text-[12px] font-extrabold hover:brightness-110 transition-all"
          >
            {t('ok')}
          </button>
          <button onClick={onCancel} className="btn-gray px-6 py-1.5 rounded-sm text-[12px] font-bold">
            {t('cancel')}
          </button>
        </div>
      </div>
    </div>
  )
}
