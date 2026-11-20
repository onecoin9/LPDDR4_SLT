import { useNavigate } from 'react-router'
import type { DutStatus } from '@/types/dut'
import { t } from '@/lib/i18n'

export type NavId = 'monitor' | 'settings'

interface Props {
  mode: 'operator' | 'engineer'
  onModeChange: (m: 'operator' | 'engineer') => void
  duts: DutStatus[]
  settingsOpen: boolean
  onNavigate: (n: NavId) => void
  zoom: number
  onZoomIn: () => void
  onZoomOut: () => void
  onZoomReset: () => void
}

export default function TopBar({ mode, onModeChange, duts, settingsOpen, onNavigate, zoom, onZoomIn, onZoomOut, onZoomReset }: Props) {
  const testing = duts.filter(d => d.state === 'TESTING').length
  const nav = useNavigate()

  const NAV: { id: NavId | 'data' | 'help'; label: string; enabled: boolean }[] = [
    { id: 'monitor', label: t('navMonitor'), enabled: true },
    { id: 'settings', label: t('navSettings'), enabled: true },
  ]

  const isActive = (id: string) =>
    (id === 'monitor' && !settingsOpen) || (id === 'settings' && settingsOpen)

  return (
    <header className="h-14 flex items-stretch px-4 bg-gradient-to-b from-[var(--topbar-from)] to-[var(--topbar-to)] border-b border-[var(--line)] shrink-0">
      {/* 左侧：公司 Logo（Acroview）+ 版本号 */}
      <div className="flex items-center pr-5 border-r border-[var(--line)]">
        <div className="leading-tight">
          <div className="font-mono font-extrabold text-[19px] tracking-wide text-[var(--logo)]">
            Acroview
          </div>
          <div className="font-mono text-[10px] text-[var(--topbar-sub)]">
            LPDDR4x SLT · V0.1.0
          </div>
        </div>
      </div>

      {/* 中部：导航 */}
      <nav className="flex items-stretch ml-2">
        {NAV.map(n => (
          <button
            key={n.id}
            disabled={!n.enabled}
            title={n.enabled ? undefined : t('navSoon')}
            onClick={n.enabled ? () => onNavigate(n.id as NavId) : undefined}
            className={`px-4 text-[13px] font-bold border-b-2 transition-colors ${
              n.enabled && isActive(n.id)
                ? 'text-[var(--accent)] border-[var(--accent)]'
                : 'text-[var(--topbar-nav)] border-transparent hover:text-[var(--topbar-text)] disabled:opacity-50 disabled:cursor-not-allowed'
            }`}
          >
            {n.label}
          </button>
        ))}
        {/* 手动版调试入口（debug/manual-4dut 分支）：跳转 /manual 独立界面 */}
        <button
          onClick={() => nav('/manual')}
          className="px-4 text-[13px] font-bold border-b-2 border-transparent transition-colors text-[var(--topbar-nav)] hover:text-[var(--topbar-text)]"
        >
          {t('navManual')}
        </button>
      </nav>

      <div className="ml-auto flex items-center gap-2">
        <span className={`px-2.5 py-1 rounded-full border font-mono text-[11px] font-bold ${testing > 0 ? 'text-[var(--accent)] border-[var(--accent)] animate-pulse' : 'text-[var(--topbar-sub)] border-[var(--line)]'}`}>
          {testing > 0 ? `${testing} TESTING` : 'IDLE'}
        </span>

        <div className="flex rounded overflow-hidden border border-[var(--line)]">
          <button
            onClick={() => onModeChange('operator')}
            className={`px-3 py-1.5 text-[12px] font-bold transition-colors ${mode === 'operator' ? 'bg-[var(--accent)] text-[var(--accent-text)]' : 'bg-transparent text-[var(--topbar-nav)] hover:text-[var(--topbar-text)]'}`}
          >
            {t('modeOperator')}
          </button>
          <button
            onClick={() => onModeChange('engineer')}
            className={`px-3 py-1.5 text-[12px] font-bold transition-colors ${mode === 'engineer' ? 'bg-[var(--accent)] text-[var(--accent-text)]' : 'bg-transparent text-[var(--topbar-nav)] hover:text-[var(--topbar-text)]'}`}
          >
            {t('modeEngineer')}
          </button>
        </div>

        {/* 页面缩放：− / 百分比(点击重置) / ＋，快捷键 Ctrl± / Ctrl+0 */}
        <div className="flex items-stretch rounded overflow-hidden border border-[var(--line)] font-mono text-[11px] font-bold">
          <button
            onClick={onZoomOut}
            title={t('zoomOut')}
            className="px-2 text-[var(--topbar-nav)] hover:text-[var(--topbar-text)] hover:bg-white/5 transition-colors"
          >
            −
          </button>
          <button
            onClick={onZoomReset}
            title={t('zoomReset')}
            className="w-12 text-center py-1.5 text-[var(--topbar-text)] hover:bg-white/5 transition-colors"
          >
            {Math.round(zoom * 100)}%
          </button>
          <button
            onClick={onZoomIn}
            title={t('zoomIn')}
            className="px-2 text-[var(--topbar-nav)] hover:text-[var(--topbar-text)] hover:bg-white/5 transition-colors"
          >
            ＋
          </button>
        </div>

        <span className="px-2.5 py-1 rounded bg-[var(--accent)] font-mono text-[11px] font-bold text-[var(--accent-text)]">admin</span>
      </div>
    </header>
  )
}
