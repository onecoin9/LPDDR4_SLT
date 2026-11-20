import { useEffect, useState } from 'react'
import { getLang, t } from '@/lib/i18n'
import { useLicense } from '@/lib/license'
import LicensePanel from './LicensePanel'

export default function LicenseNotice() {
  const { status, failed } = useLicense()
  const [open, setOpen] = useState(false)
  const [, setLanguage] = useState(getLang())
  useEffect(() => {
    const language = () => setLanguage(getLang())
    window.addEventListener('slt-language-change', language)
    return () => window.removeEventListener('slt-language-change', language)
  }, [])
  useEffect(() => {
    if (!open) return
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', escape)
    return () => window.removeEventListener('keydown', escape)
  }, [open])
  return <>
    <button onClick={() => setOpen(true)} className="fixed bottom-3 right-3 z-40 rounded-sm border border-[var(--line)] bg-[var(--panel)] px-3 py-1.5 text-[12px] text-[var(--text)] shadow-lg" aria-label={t('licTitle')}>
      {failed ? t('licConnectionFailed') : status ? t(`licState_${status.state}`) : t('licLoading')}
      {status?.allowedToStart && status.daysRemaining != null && ` · ${status.daysRemaining} ${t('licDays')}`}
    </button>
    {open && <div role="dialog" aria-modal="true" aria-label={t('licTitle')} className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50" onClick={() => setOpen(false)}>
      <div className="panel max-w-[94vw] w-[640px] max-h-[88vh] overflow-y-auto rounded-sm p-5 shadow-2xl" onClick={event => event.stopPropagation()}>
        <div className="mb-3 flex justify-end"><button onClick={() => setOpen(false)} aria-label={t('licClose')} className="px-2 text-[var(--text)]">✕</button></div>
        <LicensePanel />
      </div>
    </div>}
  </>
}
