import { useEffect, useState } from 'react'
import ThemePicker from '@/sections/ThemePicker'
import ProductSettings from '@/sections/ProductSettings'
import LicensePanel from '@/sections/LicensePanel'
import type { ThemeId } from '@/lib/theme'
import type { ProductProfile } from '@/types/product'
import type { IoControl, HandlerSettings } from '@/types/dut'
import { t, type Lang } from '@/lib/i18n'
import SettingsFilePicker from '@/sections/SettingsFilePicker'
import type useAppSettings from '@/hooks/useAppSettings'

type SectionId = 'basic' | 'handler' | 'iface' | 'channel' | 'product' | 'general' | 'license'

interface Props {
  lang: Lang
  onLangChange: (l: Lang) => void
  theme: ThemeId
  onThemeChange: (t: ThemeId) => void
  logPath: string
  onLogPathChange: (p: string) => void
  profiles: Record<string, ProductProfile>
  productName: string
  onSelectProduct: (name: string) => void
  onProfilesChange: (p: Record<string, ProductProfile>) => Promise<void>
  ioControl: IoControl
  onIoControlChange: (c: IoControl) => void
  appSettings: ReturnType<typeof useAppSettings>
  onClose: () => void}

const inputCls = 'flex-1 px-2.5 py-1.5 rounded-sm bg-[var(--input)] border border-[var(--input-line)] font-mono text-[12px] text-[var(--text)] outline-none focus:border-[var(--accent)] transition-colors'
const labelCls = 'w-28 shrink-0 font-mono text-[12px] font-bold text-[var(--text2)] text-right'

// 设置窗口：模态弹窗，左侧分类树 + 右侧内容
export default function SettingsWindow({ lang, onLangChange, theme, onThemeChange, logPath, onLogPathChange, profiles, productName, onSelectProduct, onProfilesChange, ioControl, onIoControlChange, appSettings, onClose }: Props) {
  const [sec, setSec] = useState<SectionId>(() =>
    new URLSearchParams(window.location.search).get('settings') === 'product' ? 'product' : 'basic')

  // Esc 关闭
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const [filePicker, setFilePicker] = useState(false)
  const [logPicker, setLogPicker] = useState(false)
  const [logDraft, setLogDraft] = useState(logPath)
  const [ioDraft, setIoDraft] = useState(ioControl)
  const [hd, setHd] = useState<HandlerSettings | null>(null)
  const [hdMsg, setHdMsg] = useState('')
  useEffect(() => { setLogDraft(logPath) }, [logPath])
  useEffect(() => { setIoDraft(ioControl) }, [ioControl])
  useEffect(() => { setHd(appSettings.state?.handlerStatus || null) }, [appSettings.state])
  useEffect(() => { setHdMsg('') }, [appSettings.state?.path])
  const saveHandler = async () => {
    if (!hd) return
    setHdMsg('')
    try {
      await appSettings.patch({ handler: { rx_port: hd.rx_port, tx_host: hd.tx_host, tx_port: hd.tx_port } })
      setHdMsg(t('hdSaved'))
    } catch { /* The shared error banner displays the failure. */ }
  }

  const groups: { group: string; items: { id: SectionId; label: string }[] }[] = [
    {
      group: t('grpSystem'),
      items: [
        { id: 'basic', label: t('secBasic') },
        { id: 'channel', label: t('secChannel') },
        { id: 'handler', label: t('secHandler') },
        { id: 'license', label: t('licTitle') },
      ],
    },
    { group: t('grpProduct'), items: [{ id: 'product', label: t('grpProduct') }] },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      {/* 窗口体 */}
      <div
        className="w-[1200px] max-w-[96vw] h-[760px] max-h-[92vh] panel rounded-sm shadow-2xl flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div className="h-10 shrink-0 flex items-center px-3 bg-gradient-to-b from-[var(--topbar-from)] to-[var(--topbar-to)] border-b border-[var(--line)]">
          <span className="font-bold text-[13px] text-[var(--topbar-text)]">{t('stTitle')}</span>
          <button
            onClick={onClose}
            className="ml-auto w-7 h-7 grid place-items-center rounded-sm text-[var(--topbar-nav)] hover:text-[var(--topbar-text)] hover:bg-white/10 transition-colors"
            title="Esc"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 flex min-h-0">
          {/* 左侧分类树 */}
          <nav className="w-44 shrink-0 border-r border-[var(--line)] bg-[var(--strip)] overflow-y-auto py-2">
            {groups.map(g => (
              <div key={g.group} className="mb-2">
                <div className="px-3 py-1.5 font-mono text-[10px] font-bold text-[var(--text3)] tracking-wider">
                  {g.group}
                </div>
                {g.items.map(item => (
                  <button
                    key={item.id}
                    onClick={() => setSec(item.id)}
                    className={`w-full text-left px-5 py-1.5 text-[12px] font-bold transition-colors border-l-2
                      ${sec === item.id
                        ? 'text-[var(--accent)] border-[var(--accent)] bg-[var(--panel)]'
                        : 'text-[var(--text2)] border-transparent hover:text-[var(--text)] hover:bg-[var(--row-hover)]'
                      }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            ))}
          </nav>

          {/* 右侧内容 */}
          <fieldset disabled={appSettings.saving} className="flex-1 min-w-0 overflow-y-auto p-4 bg-[var(--panel)]">
            {appSettings.error && <div role="alert" className="mb-3 text-[12px] text-[var(--st-fail)]">{appSettings.error}</div>}
            {sec === 'license' && <LicensePanel />}
            {sec === 'basic' && (
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <span className={labelCls}>{t('settingsFile')}</span>
                  <input readOnly value={appSettings.state?.path || ''} className={inputCls} />
                  <button onClick={() => setFilePicker(true)} className="btn-gray px-2.5 py-1.5 text-[12px]">{t('spChoose')}</button>
                  <button onClick={() => { void appSettings.reload().catch(() => {}) }} className="btn-gray px-2.5 py-1.5 text-[12px]">{t('rpReload')}</button>
                </div>
                {/* 语言 */}
                <div className="flex items-center gap-3">
                  <span className={labelCls}>{t('fLang')}</span>
                  <select
                    value={lang}
                    onChange={e => onLangChange(e.target.value as Lang)}
                    className={`${inputCls} max-w-[220px]`}
                  >
                    <option value="zh">中文</option>
                    <option value="en">English</option>
                  </select>
                </div>

                {/* 日志路径 */}
                <div className="flex items-center gap-3">
                  <span className={labelCls}>{t('fLogPath')}</span>
                  <input aria-label={t('fLogPath')} value={logDraft} onChange={e => setLogDraft(e.target.value)} onBlur={() => { if (logDraft !== logPath) onLogPathChange(logDraft) }} className={inputCls} />
                  <button onClick={() => setLogPicker(true)} className="btn-gray px-2.5 py-1.5 text-[12px] whitespace-nowrap">{t('logChooseDirectory')}</button>
                </div>

                {/* 界面样式 */}
                <div className="pt-2 border-t border-[var(--line)]">
                  <div className="font-mono text-[12px] font-bold text-[var(--text2)] mb-3">{t('fTheme')}</div>
                  <ThemePicker theme={theme} onSelect={onThemeChange} />
                </div>

              </div>
            )}

            {sec === 'product' && (
              <ProductSettings
                profiles={profiles}
                productName={productName}
                onSelectProduct={onSelectProduct}
                onProfilesChange={onProfilesChange}
                settingsRevision={appSettings.state?.revision || ''}
              />
            )}

            {sec === 'channel' && (
              /* IO 控制：旧上位机 SettingForm「无操作/测试板开机/下载模式」原样移植
                 （2026-09-07）；随「确定/启动本站」的 POST /api/config 上送后端 */
              <div className="space-y-4">
                <div className="font-mono text-[12px] font-bold text-[var(--text2)]">
                  {t('ioTitle')}
                </div>

                <div className="flex items-center gap-3">
                  <span className={labelCls}>{t('ioTitle')}</span>
                  <select
                    value={ioDraft.action}
                    onChange={e => onIoControlChange({ ...ioControl, action: e.target.value as IoControl['action'] })}
                    className={`${inputCls} max-w-[280px]`}
                  >
                    <option value="none">{t('ioNone')}</option>
                    <option value="power_key">{t('ioPowerKey')}</option>
                    <option value="download">{t('ioDownload')}</option>
                  </select>
                </div>

                {ioDraft.action !== 'none' && (
                  <div className="grid grid-cols-2 gap-3 max-w-[560px] pl-[140px]">
                    {([
                      ['ioBatch', 'batch', 1, 12],
                      ['ioStartDelay', 'startDelaySec', 0, 600],
                      ['ioInterval', 'intervalSec', 0, 600],
                      ['ioPulse', 'pulseMs', 10, 10000],
                    ] as const).map(([labelKey, field, min, max]) => (
                      <label key={field} className="flex items-center gap-2">
                        <span className="font-mono text-[11px] text-[var(--text2)] whitespace-nowrap">
                          {t(labelKey)}
                        </span>
                        <input
                          type="number"
                          min={min}
                          max={max}
                          value={ioDraft[field]}
                          onChange={e => {
                            const v = Math.max(min, Math.min(max, Number(e.target.value) || min))
                            setIoDraft({ ...ioDraft, [field]: v })
                          }}
                          onBlur={() => onIoControlChange(ioDraft)}
                          className={`${inputCls} max-w-[110px]`}
                        />
                      </label>
                    ))}
                  </div>
                )}


              </div>
            )}

            {sec === 'handler' && (
              /* Handler 分选机对接（2026-10-13，参照旧上位机 SettingForm「机台参数」）：
                 独立即时保存（POST /api/handler/settings 重建服务生效），
                 仅作用于首页量产测试；手动调试页不使用 Handler */
              <div className="space-y-4">
                <div className="font-mono text-[12px] font-bold text-[var(--text2)]">
                  {t('secHandler')}
                </div>

                {!hd ? (
                  <div className="font-mono text-[12px] text-[var(--text3)]">...</div>
                ) : (
                  <>
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-[11px] text-[var(--text3)]">
                        {hd.running ? t('hdRunning') : t('hdStopped')}
                      </span>
                    </div>

                    <div className="flex items-center gap-3">
                      <span className={labelCls}>{t('hdHost')}</span>
                      <input
                        aria-label={t('hdHost')}
                        value={hd.tx_host}
                        onChange={e => setHd({ ...hd, tx_host: e.target.value })}
                        onBlur={() => { void saveHandler() }}
                        className={`${inputCls} max-w-[180px]`}
                      />
                    </div>

                    <div className="flex items-center gap-3">
                      <span className={labelCls}>{t('hdTxPort')}</span>
                      <input
                        aria-label={t('hdTxPort')}
                        type="number" min={1} max={65535}
                        value={hd.tx_port}
                        onChange={e => setHd({ ...hd, tx_port: Math.max(1, Math.min(65535, Number(e.target.value) || 1)) })}
                        onBlur={() => { void saveHandler() }}
                        className={`${inputCls} max-w-[140px]`}
                      />
                    </div>

                    <div className="flex items-center gap-3">
                      <span className={labelCls}>{t('hdRxPort')}</span>
                      <input
                        aria-label={t('hdRxPort')}
                        type="number" min={1} max={65535}
                        value={hd.rx_port}
                        onChange={e => setHd({ ...hd, rx_port: Math.max(1, Math.min(65535, Number(e.target.value) || 1)) })}
                        onBlur={() => { void saveHandler() }}
                        className={`${inputCls} max-w-[140px]`}
                      />
                    </div>

                    <div className="flex items-center gap-3 pl-[140px]">
                      <button
                        onClick={saveHandler}
                        className="px-4 py-1.5 rounded-sm font-mono text-[12px] font-bold border border-[var(--accent)] text-[var(--accent)] bg-[var(--accent)]/10 hover:bg-[var(--accent)]/25 transition-colors"
                      >
                        {t('hdSave')}
                      </button>
                      {hdMsg && (
                        <span className={`font-mono text-[12px] ${hdMsg === t('hdSaved') ? 'text-[var(--st-pass)]' : 'text-[var(--st-fail)]'}`}>
                          {hdMsg}
                        </span>
                      )}
                    </div>


                  </>
                )}
              </div>
            )}

            {sec !== 'basic' && sec !== 'product' && sec !== 'channel' && sec !== 'handler' && sec !== 'license' && (
              <div className="h-full flex flex-col items-center justify-center gap-2 text-[var(--text3)]">
                <span className="font-mono text-[24px] opacity-40">⚙</span>
                <span className="font-mono text-[12px]">{t('secSoon')}</span>
              </div>
            )}
          </fieldset>
        </div>
      </div>
      {filePicker && <SettingsFilePicker initial={appSettings.state?.path || ''} onSelect={appSettings.select} onClose={() => setFilePicker(false)} />}
      {logPicker && <SettingsFilePicker directory initial={logPath}
        onSelect={async path => { await appSettings.patch({ basic: { logPath: path } }) }} onClose={() => setLogPicker(false)} />}
    </div>
  )
}
