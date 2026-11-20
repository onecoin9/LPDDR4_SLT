import { THEMES, type ThemeId } from '@/lib/theme'
import { t, getLang } from '@/lib/i18n'

interface Props {
  theme: ThemeId
  onSelect: (t: ThemeId) => void
}

// 界面样式选择（8 套主题卡片，实时切换并本地记忆）
export default function ThemePicker({ theme, onSelect }: Props) {
  const en = getLang() === 'en'
  return (
    <div>
      <div className="grid grid-cols-4 gap-3">
        {THEMES.map(th => {
          const active = theme === th.id
          return (
            <button
              key={th.id}
              onClick={() => onSelect(th.id)}
              className={`rounded-sm panel overflow-hidden text-left transition-all
                ${active ? 'outline outline-2 outline-[var(--accent)] outline-offset-1' : 'hover:-translate-y-0.5 hover:shadow-lg'}`}
            >
              {/* 主题预览：mini 界面示意 */}
              <div className="p-2.5" style={{ backgroundColor: th.preview.bg }}>
                <div className="h-2.5 rounded-[2px] mb-1.5" style={{ backgroundColor: th.preview.accent, opacity: 0.9 }} />
                <div className="rounded-[3px] p-2" style={{ backgroundColor: th.preview.panel, border: `1px solid ${th.preview.line}` }}>
                  <div className="h-1.5 w-2/3 rounded-full mb-2" style={{ backgroundColor: th.preview.text, opacity: 0.55 }} />
                  <div className="h-1.5 w-1/3 rounded-full mb-2.5" style={{ backgroundColor: th.preview.text, opacity: 0.25 }} />
                  <div className="flex gap-1.5">
                    {th.preview.st.map(c => (
                      <span key={c} className="w-3 h-3 rounded-full" style={{ backgroundColor: c, border: `1px solid ${th.preview.line}` }} />
                    ))}
                    <span className="ml-auto h-3 w-8 rounded-full" style={{ backgroundColor: th.preview.accent }} />
                  </div>
                </div>
              </div>
              {/* 名称与说明 */}
              <div className="px-3 py-2.5 border-t border-[var(--line)] flex items-center gap-2">
                <div>
                  <div className="font-bold text-[13px] text-[var(--text)]">{en ? th.nameEn : th.name}</div>
                </div>
                {active && (
                  <span className="ml-auto shrink-0 px-2 py-0.5 rounded-full bg-[var(--accent)] text-[var(--accent-text)] font-mono text-[10px] font-bold">
                    {t('inUse')}
                  </span>
                )}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
