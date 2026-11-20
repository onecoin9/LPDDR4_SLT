import { useEffect, useState } from 'react'
import { API_BASE } from '@/hooks/useServer'
import { t } from '@/lib/i18n'
import { apiErrorText } from '@/lib/productPlan'
import { defaultRuntimePolicy, validRuntimePolicy } from '@/lib/runtimePolicy'
import type { RuntimePolicy } from '@/lib/runtimePolicy'

const inputCls = 'w-28 px-2 py-1 rounded-sm bg-[var(--input)] border border-[var(--input-line)] font-mono text-[12px] text-[var(--text)] outline-none focus:border-[var(--accent)]'

export default function RuntimePolicyEditor({ settingsRevision }: { settingsRevision?: string }) {
  const [policy, setPolicy] = useState<RuntimePolicy>(defaultRuntimePolicy)
  const [revision, setRevision] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    fetch(API_BASE + '/api/runtime-policy').then(async response => {
      const body = await response.json()
      if (!response.ok) throw new Error(apiErrorText(body))
      if (active) {
        setPolicy(body.policy)
        setRevision(body.revision)
        setError(body.valid ? '' : t('rpCorrupt'))
        setSaved(false)
      }
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : t('planRequestFailed')) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [reload, settingsRevision])

  const patch = (value: Partial<RuntimePolicy>) => {
    if (saving) return
    setPolicy({ ...policy, ...value })
    setSaved(false)
  }
  const save = async () => {
    if (!validRuntimePolicy(policy)) { setError(t('rpInvalid')); return }
    setSaving(true)
    setError('')
    try {
      const response = await fetch(API_BASE + '/api/runtime-policy', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'If-Match': revision },
        body: JSON.stringify(policy),
      })
      const body = await response.json()
      if (!response.ok || body.ok !== true || !body.valid) throw new Error(apiErrorText(body))
      setPolicy(body.policy)
      setRevision(body.revision)
      setSaved(true)
      window.dispatchEvent(new Event('slt-settings-changed'))
    } catch (e) { setError(e instanceof Error ? e.message : t('planRequestFailed')) }
    finally { setSaving(false) }
  }

  return (
    <section className="p-3 border border-[var(--line)] rounded-sm bg-[var(--panel)] space-y-3 text-[12px]">
      <div className="font-bold text-[var(--text)]">{t('rpTitle')}</div>
      <fieldset disabled={loading || saving || !revision} className="space-y-3 disabled:opacity-50">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="flex items-center justify-between gap-2">{t('rpAck')} (s)
            <input aria-label={t('rpAck')} type="number" min={0} max={3600} step="any" value={policy.cfgAckTimeoutSec}
              onChange={e => patch({ cfgAckTimeoutSec: Number(e.target.value) })} className={inputCls} />
          </label>
          <label className="flex items-center justify-between gap-2">{t('rpRetry')} (s)
            <input aria-label={t('rpRetry')} type="number" min={0} max={600} step="any" value={policy.cfgRetryIntervalSec}
              onChange={e => patch({ cfgRetryIntervalSec: Number(e.target.value) })} className={inputCls} />
          </label>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {(['PL', 'LK', 'APK'] as const).map(stage => (
            <label key={stage} className="flex items-center justify-between gap-2">{stage} {t('rpBudget')} (s)
              <input aria-label={stage + ' ' + t('rpBudget')} type="number" min={0} max={86400} step="any"
                value={policy.stageTimeoutSec[stage]} onChange={e => patch({
                  stageTimeoutSec: { ...policy.stageTimeoutSec, [stage]: Number(e.target.value) },
                })} className={inputCls} />
            </label>
          ))}
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={policy.checkReadyVersion}
              onChange={e => patch({ checkReadyVersion: e.target.checked })} className="accent-[var(--accent)]" />
            {t('rpVersionCheck')}
          </label>
          <input aria-label={t('rpExpectedVersion')} disabled={!policy.checkReadyVersion} maxLength={64}
            value={policy.expectedReadyVersion} placeholder="M80-_6785"
            onChange={e => patch({ expectedReadyVersion: e.target.value })}
            className={inputCls + ' flex-1 min-w-36 disabled:opacity-50'} />
        </div>
      </fieldset>
      {error && <div role="alert" className="whitespace-pre-wrap text-[var(--st-fail)]">{error}</div>}
      <div className="flex items-center justify-end gap-2">
        <button disabled={saving || loading} onClick={() => setReload(v => v + 1)} className="btn-gray px-3 py-1.5">{t('rpReload')}</button>
        <button disabled={saving || loading || !revision} onClick={save} className="px-3 py-1.5 rounded-sm bg-gradient-to-b from-[var(--accent-hi)] to-[var(--accent-to)] border border-[var(--accent-line)] text-[var(--accent-text)] font-bold hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed">
          {saving ? t('planSaving') : saved ? t('savedOk') : t('rpSave')}
        </button>
      </div>
    </section>
  )
}
