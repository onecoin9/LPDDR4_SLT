import { t } from '@/lib/i18n'

interface Props {
  mode: 'operator' | 'engineer'
  operator: string
  logPath: string
}

export default function StatusBar({ mode, operator, logPath }: Props) {
  return (
    <footer className="h-7 flex items-center px-4 bg-[var(--chrome)] border-t border-[var(--line)] font-mono text-[11px] text-[var(--text2)] shrink-0">
      <span>
        {t('sbUser')} <span className="text-[var(--accent)]">[{operator || 'admin'}]</span>
        <span className="mx-2 text-[var(--line)]">|</span>
        {t('sbMode')} <span className="text-[var(--text)]">{mode === 'operator' ? t('modeOperator') : t('modeEngineer')}</span>
      </span>
      <span className="ml-auto flex items-center gap-3">
        <span className="text-[var(--text3)]">
          {t('sbLogPath')} <span className="text-[var(--text2)]">{logPath}</span>
        </span>
      </span>
    </footer>
  )
}
