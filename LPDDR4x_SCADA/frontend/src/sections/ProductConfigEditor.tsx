import { useState } from 'react'
import type { ProductProfile } from '@/types/product'
import { importProductCfg } from '@/lib/productPlan'
import { API_BASE } from '@/hooks/useServer'
import { t } from '@/lib/i18n'

// 配置文件编辑器：编辑 key=value CFG 文本，与手动测试页同构——单栏编辑 + 底部错误条。
// 保存走 /api/products/import-cfg，后端解析校验并同步产品档案，失败不落盘。
export default function ProductConfigEditor({ profile, initialCfgText, initialError, settingsRevision, onImported, onClose }: {
  profile: ProductProfile; initialCfgText: string
  initialError: string
  settingsRevision: string
  onImported: (result: { product: string; profile: ProductProfile; settingsRevision: string }) => void
  onClose: () => void
}) {
  const [text, setText] = useState(initialCfgText)
  const [error, setError] = useState(initialError)
  const [busy, setBusy] = useState(false)

  const save = async () => {
    setBusy(true); setError('')
    try {
      const result = await importProductCfg(text, profile.name, settingsRevision, API_BASE)
      onImported(result)
    } catch (err) { setError(err instanceof Error ? err.message : t('planRequestFailed')) }
    finally { setBusy(false) }
  }

  return <div role="dialog" aria-modal="true" aria-label={t('planPreview')}
    className="fixed inset-0 z-[70] bg-black/60 flex items-center justify-center p-3"
    onKeyDown={e => { if (e.key === 'Escape' && !busy) { e.stopPropagation(); onClose() } }}>
    <div className="w-full max-w-4xl bg-[var(--panel)] border border-[var(--line)] rounded-sm shadow-xl flex flex-col max-h-[90vh]">
      <div className="flex justify-between items-center px-4 py-3 border-b border-[var(--line)] font-bold">
        <span>{t('planPreview')}</span>
        <button autoFocus disabled={busy} onClick={onClose} className="btn-gray px-3 py-1 text-[12px]">{t('planBack')}</button>
      </div>
      <label className="flex flex-col gap-2 p-3 min-h-0 text-[12px]">
        <span className="font-bold">{t('planCfgFile')} · {profile.name}.cfg</span>
        <textarea aria-label={t('planCfgFile')} spellCheck={false} disabled={busy} value={text}
          onChange={e => { setText(e.target.value); setError('') }}
          className="h-[60vh] min-h-[280px] resize-none p-3 font-mono text-[12px] text-[var(--text)] bg-[var(--input)] border border-[var(--input-line)] outline-none focus:border-[var(--accent)]" />
      </label>
      {error && <div role="alert" className="px-4 text-[12px] text-[var(--st-fail)] whitespace-pre-wrap">{error}</div>}
      <div className="flex justify-end gap-3 items-center p-3 border-t border-[var(--line)] text-[12px]">
        <div className="flex gap-2 shrink-0">
          <button disabled={busy} onClick={() => { void save() }} className="btn-gray px-3 py-1">{busy ? t('planSaving') : t('btnSave')}</button>
        </div>
      </div>
    </div>
  </div>
}
