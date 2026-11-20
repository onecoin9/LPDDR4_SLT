import { useRef, useState } from 'react'
import { getLang, t } from '@/lib/i18n'
import { refreshLicense, useLicense } from '@/lib/license'
import { API_BASE } from '@/hooks/useServer'

export default function LicensePanel() {
  const { status, failed } = useLicense()
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [success, setSuccess] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const button = 'px-3 py-2 rounded-sm border border-[var(--line)] bg-[var(--strip)] text-[var(--text)] hover:bg-[var(--row-hover)] disabled:opacity-50'
  async function importFile(file?: File) {
    if (!file || busy) return
    setMessage(''); setSuccess(false)
    if (file.size > 32768) { setMessage(t('licFileLarge')); return }
    setBusy(true)
    try {
      const response = await fetch(`${API_BASE}/api/license/import`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: await file.text() }) })
      const data = await response.json()
      if (!response.ok || !data.allowedToStart) { setMessage(t('licImportFailed')) }
      else { setSuccess(true); setMessage(t('licImported')) }
      await refreshLicense()
    } catch { setMessage(t('licConnectionFailed')) }
    finally { setBusy(false); if (input.current) input.current.value = '' }
  }
  const stateText = status ? t(`licState_${status.state}`) : t('licLoading')
  const expires = status?.expiresAt ? new Date(status.expiresAt).toLocaleString(getLang() === 'zh' ? 'zh-CN' : 'en-US', { hour12: false }) : '—'
  return <section className="space-y-5 text-[13px] text-[var(--text)]" aria-label={t('licTitle')}>
    <div className="rounded-sm border border-[var(--line)] bg-[var(--strip)] p-4">
      <h2 className="font-bold text-[15px]">{t('licTitle')}</h2>
      <p className="mt-2 font-bold text-[var(--accent)]">{failed ? t('licConnectionFailed') : stateText}</p>
      <p className="mt-2 text-[var(--text2)]">{t('licPolicy')}</p>
    </div>
    <dl className="grid grid-cols-[100px_1fr] gap-x-4 gap-y-3">
      <dt className="text-[var(--text2)]">{t('licCustomer')}</dt><dd>{status?.customer || '—'}</dd>
      <dt className="text-[var(--text2)]">{t('licExpiry')}</dt><dd>{expires}</dd>
      <dt className="text-[var(--text2)]">{t('licRemaining')}</dt><dd>{status?.daysRemaining == null ? '—' : `${Math.max(0, status.daysRemaining)} ${t('licDays')}`}</dd>
      <dt className="text-[var(--text2)]">{t('licMachine')}</dt><dd className="font-mono text-[11px] break-all select-text">{status?.clientId || '—'}</dd>
    </dl>
    <ol className="list-decimal pl-5 space-y-2 text-[var(--text2)]">
      <li>{t('licStepExport')}</li><li>{t('licStepReceive')}</li><li>{t('licStepImport')}</li>
    </ol>
    <div className="flex flex-wrap gap-3">
      <a className={button} href={`${API_BASE}/api/license/request`} download="client_id">{t('licExport')}</a>
      <button className={button} disabled={busy} onClick={() => input.current?.click()}>{busy ? t('licImporting') : t('licImport')}</button>
      <button className={button} disabled={busy} onClick={() => { void refreshLicense() }}>{t('licRefresh')}</button>
      <input ref={input} type="file" accept=".lic" className="hidden" aria-label={t('licImport')} onChange={event => { void importFile(event.target.files?.[0]) }} />
    </div>
    {message && <p role="status" className={success ? 'text-[var(--accent)]' : 'text-[var(--text)]'}>{message}</p>}
    <p className="text-[12px] text-[var(--text3)]">{t('licMachineNote')}</p>
  </section>
}
