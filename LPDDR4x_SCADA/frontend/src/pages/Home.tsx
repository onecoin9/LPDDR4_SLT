import { useState, useEffect, useRef } from 'react'
import TopBar, { type NavId } from '@/sections/TopBar'
import SidePanel from '@/sections/SidePanel'
import StatusBar from '@/sections/StatusBar'
import OverviewGrid from '@/sections/OverviewGrid'
import SiteDetail from '@/sections/SiteDetail'
import SettingsWindow from '@/sections/SettingsWindow'
import DutLogDialog from '@/sections/DutLogDialog'
import { useServer } from '@/hooks/useServer'
import useAppSettings from '@/hooks/useAppSettings'
import { STATE_COLOR, siteIndicator } from '@/lib/stateIndicator'
import { initTheme, applyTheme, type ThemeId } from '@/lib/theme'
import { loadZoom, saveZoom, zoomIn, zoomOut } from '@/lib/zoom'
import { getLang, setLang, t, type Lang } from '@/lib/i18n'
import { loadProfiles, normalizeProfile } from '@/types/product'
import type { ProductProfile } from '@/types/product'
import type { SessionConfig, SiteStatus } from '@/types/dut'
import { startBlockedReason } from '@/lib/testStart'

const pad = (n: number) => String(n).padStart(2, '0')

// site 是否异常：任一 DUT FAIL 或 OFFLINE → 标签页标红
function siteAbnormal(site: SiteStatus) {
  return site.duts.some(d => d.state === 'FAIL' || d.state === 'OFFLINE')
}

// 少量离线工位不能覆盖正在测试的站点；仅全部通过才显示 PASS。
function siteDot(site: SiteStatus): string {
  return STATE_COLOR[siteIndicator(site.duts.map(d => d.state))]
}

export default function Home() {
  const [mode, setMode] = useState<'operator' | 'engineer'>('operator')
  const [settingsOpen, setSettingsOpen] = useState(() => new URLSearchParams(window.location.search).get('settings') === 'product')
  const requestedProduct = useRef(new URLSearchParams(window.location.search).get('product'))
  const selectionPending = useRef(0)
  const initialSelectionDone = useRef(false)
  const [theme, setTheme] = useState<ThemeId>(initTheme)
  const [lang, setLangState] = useState<Lang>(getLang)
  const [zoom, setZoom] = useState<number>(loadZoom)
  const [activeTab, setActiveTab] = useState<string>('overview')
  const [selectedSlot, setSelectedSlot] = useState<number | null>(null)
  // DUT 日志弹框：点击通道行打开（实时滚动该通道日志）
  const [logSlot, setLogSlot] = useState<number | null>(null)
  // Legacy cache is read once for migration; the backend settings JSON is authoritative.
  const [logPath, setLogPathState] = useState(() => {
    try { return localStorage.getItem('slt-log-path') || 'records' }
    catch { return 'records' }
  })
  // 产品配置（JSON 档案，见 types/product.ts）：与前面板产品名双向同步
  const [profiles, setProfiles] = useState(loadProfiles)
  const [preparingStart, setPreparingStart] = useState(false)
  const [preparationError, setPreparationError] = useState('')
  const startLock = useRef(false)
  const sim = useServer()
  const appSettings = useAppSettings({ basic: { language: lang, theme, logPath }, products: profiles,
    ioControl: sim.ioControl }, (value, revision) => {
    sim.setSettingsRevision(revision)
    applyTheme(value.basic.theme); setTheme(value.basic.theme)
    setLang(value.basic.language); setLangState(value.basic.language)
    setLogPathState(value.basic.logPath)
    const library = Object.fromEntries(Object.entries(value.products).map(([name, p]) => [name, normalizeProfile(structuredClone(p))]))
    setProfiles(library)
    sim.setIoControl(value.ioControl)
    if (!selectionPending.current) {
      const local = sim.getConfig().product
      const requested = requestedProduct.current
      requestedProduct.current = null
      const selected = requested && library[requested] ? requested : library[local] ? local : Object.keys(library)[0] || ''
      if (selected && (!initialSelectionDone.current || selected !== local)) {
        initialSelectionDone.current = true
        void handleSelectProduct(selected)
      }
    }
  })

  const handleSelectProduct = async (product: string) => {
    selectionPending.current++
    setPreparationError('')
    try {
      const selected = await appSettings.selectProduct(product)
      sim.setConfig({ ...sim.getConfig(), product: selected.product })
      sim.setSettingsRevision(selected.settingsRevision)
    } catch (error) {
      setPreparationError(error instanceof Error ? error.message : t('planRequestFailed'))
    } finally { selectionPending.current-- }
  }

  const handleConfigChange = (next: SessionConfig) => {
    const current = sim.getConfig()
    sim.setConfig({ ...next, product: current.product })
    if (next.product !== current.product) void handleSelectProduct(next.product)
  }

  const handleProfilesChange = async (p: typeof profiles) => {
    await appSettings.patch({ products: p })
  }

  const handleStart = async (site?: number) => {
    if (startLock.current) return
    startLock.current = true
    setPreparingStart(true); setPreparationError('')
    let submitted = false
    try {
      const saved = await appSettings.flush()
      if (!saved?.valid) throw new Error(t('startSettingsUnavailable'))
      const profile = saved.settings.products[sim.getConfig().product]
      if (!profile) throw new Error(t('srvNoProduct'))
      sim.setSettingsRevision(saved.revision)
      submitted = true
      if (site === undefined) await sim.startAll(profile)
      else await sim.startSite(site, profile)
    } catch (error) {
      setPreparationError(error instanceof Error ? error.message : t('srvStartFail'))
    } finally {
      // /api/config may persist the selected profile and advance its revision.
      // GET refresh is allowed during tests; reselecting the file is not.
      if (submitted) await appSettings.refresh().catch(() => {})
      setPreparingStart(false); startLock.current = false
    }
  }
  const startBlock = startBlockedReason({ ready: appSettings.ready, saving: appSettings.saving,
    error: appSettings.error, submitting: preparingStart || sim.starting,
    hasProduct: !!profiles[sim.config.product] })
  const startHint = startBlock === 'loading' ? t('startSettingsLoading')
    : startBlock === 'saving' ? t('startSettingsSaving')
    : startBlock === 'settings_error' ? t('startSettingsUnavailable')
    : startBlock === 'submitting' ? t('startSubmitting')
    : startBlock === 'product' ? t('srvNoProduct') : ''

  // 前面板「选择」按钮：从 JSON 文件导入产品档案 → 入 profiles 持久化 + 选中为当前产品
  const handleImportProfile = async (p: ProductProfile) => {
    try {
      await handleProfilesChange({ ...profiles, [p.name]: p })
      await handleSelectProduct(p.name)
    } catch { /* The settings error banner displays the server failure. */ }
  }

  // 缩放变更时持久化
  const changeZoom = (z: number) => { saveZoom(z); setZoom(z) }

  // 快捷键：Ctrl/⌘ + '+' 放大，'-' 缩小，'0' 重置（输入框聚焦时不劫持）
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.key === '=' || e.key === '+') { e.preventDefault(); changeZoom(zoomIn(zoom)) }
      else if (e.key === '-') { e.preventDefault(); changeZoom(zoomOut(zoom)) }
      else if (e.key === '0') { e.preventDefault(); changeZoom(1) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [zoom])

  const activeSiteId = activeTab.startsWith('site-') ? Number(activeTab.slice(5)) : null
  const activeSite = activeSiteId !== null ? sim.sites.find(s => s.id === activeSiteId) : undefined

  // 点击总览中的 site / 灯 → 跳转到对应 site 标签页（可带通道定位）
  const openSite = (siteId: number, slot?: number) => {
    setActiveTab(`site-${siteId}`)
    setSelectedSlot(slot ?? null)
  }

  const handleSelectTheme = (th: ThemeId) => {
    applyTheme(th)
    setTheme(th)
    void appSettings.patch({ basic: { theme: th } }).catch(() => {})
  }

  const handleLangChange = (l: Lang) => {
    setLang(l)
    setLangState(l) // 触发整树重渲染，t() 即刻切换
    void appSettings.patch({ basic: { language: l } }).catch(() => {})
  }

  const handleNavigate = (n: NavId) => {
    setSettingsOpen(n === 'settings')
  }

  const tabBtn = (active: boolean, abnormal: boolean) =>
    `shrink-0 px-4 py-2 font-mono text-[12px] font-bold border-r border-[var(--line)] transition-colors flex items-center gap-1.5
     ${active
       ? abnormal
         ? 'bg-[var(--panel)] text-[var(--st-fail)] border-t-2 border-t-[var(--st-fail)]'
         : 'bg-[var(--panel)] text-[var(--text)] border-t-2 border-t-[var(--accent)]'
       : abnormal
         ? 'text-[var(--st-fail)] hover:bg-[var(--row-hover)]'
         : 'text-[var(--chrome-text)] hover:bg-[var(--strip)] hover:text-[var(--text)]'
     }`

  return (
    <div className="h-screen flex flex-col bg-[var(--bg)] text-[var(--text)] overflow-hidden" style={{ zoom }}>
      <TopBar
        mode={mode} onModeChange={setMode} duts={sim.duts}
        settingsOpen={settingsOpen} onNavigate={handleNavigate}
        zoom={zoom}
        onZoomIn={() => changeZoom(zoomIn(zoom))}
        onZoomOut={() => changeZoom(zoomOut(zoom))}
        onZoomReset={() => changeZoom(1)}
      />
      {appSettings.error && <div role="alert" className="px-3 py-1.5 text-[12px] text-[var(--st-fail)] bg-[var(--panel)]">
        {appSettings.error}
        <button onClick={() => { void appSettings.reload().catch(() => {}) }} className="btn-gray ml-3 px-2">{t('rpReload')}</button>
      </div>}

      {/* 设备监控主界面 */}
      <div className="flex-1 flex gap-2 p-2 min-h-0">
        {/* 左侧：配置面板 */}
        <SidePanel
          duts={sim.duts}
          logs={sim.logs}
          config={sim.config}
          onConfigChange={handleConfigChange}
          products={Object.keys(profiles)}
          onImportProfile={handleImportProfile}
          sessionElapsed={sim.sessionElapsed}
          totalSuccess={sim.totalSuccess}
          totalRuns={sim.totalRuns}
          siteFilter={activeSiteId}
          slotFilter={activeSiteId !== null ? selectedSlot : null}
          onStart={() => { void handleStart() }}
          startDisabled={startBlock !== null}
          startHint={startHint}
          starting={preparingStart || sim.starting}
          startError={preparationError || sim.startError}
          onStop={sim.stopAll}
        />

        {/* 右侧主区：内容在上，标签栏在下 */}
        <div className="flex-1 min-w-0 flex flex-col panel rounded-sm overflow-hidden">
          {/* 标签页内容 */}
          <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
            {activeTab === 'overview' && (
              <OverviewGrid sites={sim.sites} onSelectSite={openSite} />
            )}
            {activeSite && (
              <SiteDetail
                site={activeSite}
                engineer={mode === 'engineer'}
                selectedSlot={logSlot}
                onSelectSlot={(slot) => setLogSlot(slot)}
                onStartSite={() => { void handleStart(activeSite.id) }}
                startDisabled={startBlock !== null}
                startHint={startHint}
                onStopSite={() => sim.stopSite(activeSite.id)}
                dutLogs={sim.dutLogs}
              />
            )}
            {activeTab.startsWith('site-') && !activeSite && (
              <div className="flex-1 flex items-center justify-center text-[var(--text3)] font-mono text-[13px]">
                {t('pickSite')}
              </div>
            )}
          </div>

          {/* 底部标签栏 */}
          <div
            className="flex items-stretch border-t border-[var(--line)] bg-[var(--chrome)] overflow-x-auto shrink-0"
            style={{ scrollbarWidth: 'thin', scrollbarColor: 'var(--scrollbar) var(--chrome)' }}
          >
            {/* 总览标签 */}
            <button
              onClick={() => { setActiveTab('overview'); setSelectedSlot(null) }}
              className={tabBtn(activeTab === 'overview', false)}
            >
              {t('tabOverview')}
            </button>

            {/* Site 标签 01..N：有异常（FAIL/OFFLINE）则标红 */}
            {sim.sites.map(site => {
              const abnormal = siteAbnormal(site)
              return (
                <button
                  key={site.id}
                  onClick={() => openSite(site.id)}
                  className={tabBtn(activeTab === `site-${site.id}`, abnormal)}
                >
                  <span
                    className="inline-block w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: siteDot(site) }}
                  />
                  SITE {pad(site.id)}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      <StatusBar mode={mode} operator={sim.config.operator} logPath={logPath} />

      {/* 设置窗口（模态） */}
      {settingsOpen && (
        <SettingsWindow
          lang={lang}
          onLangChange={handleLangChange}
          theme={theme}
          onThemeChange={handleSelectTheme}
          logPath={logPath}
          onLogPathChange={(p) => { void appSettings.patch({ basic: { logPath: p } }).catch(() => {}) }}
          profiles={profiles}
          productName={sim.config.product}
          onSelectProduct={(n) => { void handleSelectProduct(n) }}
          onProfilesChange={handleProfilesChange}
          ioControl={sim.ioControl}
          onIoControlChange={(c) => { void appSettings.patch({ ioControl: c }).catch(() => {}) }}
          appSettings={appSettings}
          onClose={() => setSettingsOpen(false)}
        />
      )}

      {/* DUT 日志弹框：点击通道行打开，实时滚动 */}
      {logSlot !== null && activeSite && (
        <DutLogDialog
          siteId={activeSite.id}
          slot={logSlot}
          entries={sim.dutLogs[`${activeSite.id}:${logSlot}`] ?? []}
          onClose={() => setLogSlot(null)}
        />
      )}
    </div>
  )
}
