import { useEffect, useState } from 'react'
import { API_BASE } from '@/hooks/useServer'
import { apiErrorText } from '@/lib/productPlan'
import { t } from '@/lib/i18n'

interface Directory { path: string; parent: string; dirs: string[]; files: string[]; drives: string[]; selectionPath?: string }
export default function SettingsFilePicker({ initial, onSelect, onClose, directory = false }: {
  initial: string; onSelect: (path: string) => Promise<unknown>; onClose: () => void; directory?: boolean
}) {
  const [dir, setDir] = useState<Directory | null>(null)
  const [path, setPath] = useState(initial)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const browse = async (value: string) => {
    setBusy(true); setError('')
    try {
      const response = await fetch(API_BASE + '/api/settings/browse?path=' + encodeURIComponent(value))
      const body = await response.json()
      if (!response.ok) throw new Error(apiErrorText(body))
      setDir(body); setPath(body.path)
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  useEffect(() => { void browse(directory ? initial : initial.replace(/[\\/][^\\/]*$/, '')) }, [initial, directory])
  const choose = async (value: string) => {
    setBusy(true); setError('')
    try { await onSelect(value); onClose() }
    catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }
  const join = (name: string) => dir?.path.replace(/[\\/]$/, '') + '/' + name
  const title = t(directory ? 'logChooseDirectory' : 'settingsChoose')
  return <div role="dialog" aria-modal="true" aria-label={title}
    className="fixed inset-0 z-[80] bg-black/60 flex items-center justify-center p-4" onClick={e => e.stopPropagation()}
    onKeyDown={e => { if (e.key === 'Escape') { e.stopPropagation(); if (!busy) onClose() } }}>
    <div className="panel w-[700px] max-w-[90vw] p-4 space-y-3 text-[12px]">
      <div className="font-bold">{title}</div>
      <div className="flex gap-2">
        <input aria-label={t('settingsPath')} value={path} disabled={busy} onChange={e => setPath(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); void browse(path) } }}
          className="flex-1 min-w-0 px-2 py-1 bg-[var(--input)] border border-[var(--input-line)] font-mono" />
        <button disabled={busy} className="btn-gray px-3" onClick={() => { void browse(path) }}>{t('browse')}</button>
        <button disabled={busy || (directory && (!dir?.path || path !== dir.path))} className="btn-gray px-3"
          onClick={() => { void choose(directory ? dir!.selectionPath || dir!.path : path) }}>{t(directory ? 'logUseDirectory' : 'settingsUse')}</button>
      </div>
      <div className="flex gap-2">
        <button disabled={busy} className="btn-gray px-3" onClick={() => { void browse('') }}>{t('settingsDrives')}</button>
        <button disabled={busy || !dir?.parent} className="btn-gray px-3" onClick={() => { void browse(dir?.parent || '') }}>↑</button>
      </div>
      <div className="h-72 overflow-auto border border-[var(--line)] bg-[var(--table)]">
        {dir?.drives.map(name => <button key={name} disabled={busy} onClick={() => { void browse(name) }} className="block w-full text-left px-3 py-2 hover:bg-[var(--row-hover)]">📁 {name}</button>)}
        {dir?.dirs.map(name => <button key={name} disabled={busy} onClick={() => { void browse(join(name)) }} className="block w-full text-left px-3 py-2 hover:bg-[var(--row-hover)]">📁 {name}</button>)}
        {!directory && dir?.files.map(name => <button key={name} disabled={busy} onClick={() => { void choose(join(name)) }} className="block w-full text-left px-3 py-2 hover:bg-[var(--row-hover)]">{name}</button>)}
      </div>
      {error && <div role="alert" className="text-[var(--st-fail)] whitespace-pre-wrap">{error}</div>}
      <div className="text-right"><button disabled={busy} className="btn-gray px-3 py-1" onClick={onClose}>{t('planBack')}</button></div>
    </div>
  </div>
}
