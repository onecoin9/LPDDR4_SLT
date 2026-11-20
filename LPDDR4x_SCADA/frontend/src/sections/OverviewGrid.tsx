import type { DutState, SiteStatus } from '@/types/dut'
import { t } from '@/lib/i18n'

const pad = (n: number) => String(n).padStart(2, '0')

// 状态灯（主题变量 + i18n 标签）：红=FAIL 绿=PASS 黄=测试中 白=空闲 灰=离线
const LAMP_COLOR: Record<DutState, { color: string; glow: boolean }> = {
  IDLE:    { color: 'var(--st-idle)',    glow: false },
  TESTING: { color: 'var(--st-testing)', glow: true },
  PASS:    { color: 'var(--st-pass)',    glow: true },
  FAIL:    { color: 'var(--st-fail)',    glow: true },
  OFFLINE: { color: 'var(--st-offline)', glow: false },
}

const LAMP_LABEL: Record<DutState, () => string> = {
  IDLE: () => t('stIdleLamp'),
  TESTING: () => t('stTesting'),
  PASS: () => t('stPass'),
  FAIL: () => t('stFail'),
  OFFLINE: () => t('stOffline'),
}

// 通讯板聚合状态（板1 = CH01-12，板2 = CH13-24）：
// 板灯是 DUT 连接汇总；全部 DUT 关闭不能推断通讯板故障。
// 芯片测试 FAIL 不影响板灯（芯片红点自行表达测试失败）。
function boardState(duts: SiteStatus['duts']): DutState {
  if (!duts.some(d => d.connected)) return 'OFFLINE'
  if (duts.some(d => d.state === 'TESTING')) return 'TESTING'
  if (duts.every(d => d.state === 'PASS')) return 'PASS'
  return 'IDLE'
}

// 站点聚合状态：有 FAIL→FAIL；有测试中→TESTING；全离线→OFFLINE；否则就绪
function siteState(site: SiteStatus): DutState | 'READY' {
  if (site.duts.some(d => d.state === 'FAIL')) return 'FAIL'
  if (site.duts.some(d => d.state === 'TESTING')) return 'TESTING'
  if (!site.duts.some(d => d.connected)) return 'OFFLINE'
  return 'READY'
}

const SITE_STATE_LABEL: Record<DutState | 'READY', () => string> = {
  ...LAMP_LABEL,
  READY: () => t('ovReady'),
}

const SITE_STATE_COLOR: Record<DutState | 'READY', string> = {
  IDLE: 'var(--text2)',
  TESTING: 'var(--st-testing)',
  PASS: 'var(--st-pass)',
  FAIL: 'var(--st-fail)',
  OFFLINE: 'var(--text3)',
  READY: 'var(--st-pass)',
}

const fmtHms = (sec: number) => {
  const s = Math.max(0, Math.floor(sec))
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`
}

// DUT 芯片图标：TSOP 风格（上下各 6 个引脚 + 本体 + 1 脚标记点），本体色 = 状态色，宽随框缩放
function ChipIcon({ state }: { state: DutState }) {
  const lamp = LAMP_COLOR[state]
  const pins = [0, 1, 2, 3, 4, 5]
  return (
    <svg
      viewBox="0 0 30 16"
      className={state === 'TESTING' ? 'animate-pulse' : ''}
      style={{
        width: 'clamp(14px, min(2.6vh, 1.15vw), 28px)',
        height: 'auto',
        opacity: state === 'OFFLINE' ? 0.45 : 1,
        filter: lamp.glow ? `drop-shadow(0 0 3px color-mix(in srgb, ${lamp.color} 60%, transparent))` : 'none',
      }}
    >
      {pins.map(i => (
        <rect key={`t${i}`} x={3 + i * 4.4} y={0} width={2.2} height={3} fill="var(--text3)" />
      ))}
      {pins.map(i => (
        <rect key={`b${i}`} x={3 + i * 4.4} y={13} width={2.2} height={3} fill="var(--text3)" />
      ))}
      <rect x={1.5} y={3} width={27} height={10} rx={1.5}
            fill={lamp.color} stroke="var(--line)" strokeWidth={0.8} />
      <circle cx={5} cy={8} r={1.1} fill="rgba(0,0,0,0.35)" />
    </svg>
  )
}

interface Props {
  sites: SiteStatus[]
  onSelectSite: (siteId: number, slot?: number) => void
}

// 总览（2026-09-01 v5）：固定 5 列 × 10 行，正序 01→50（左上 S01，右下 S50）。
// 每框 = 左侧状态块（状态文字 / 大号编号 + 两板状态灯 / 计时）
// + 右侧 24 芯片图标（两行各 12 = 板1/板2，行间虚线分隔）。
export default function OverviewGrid({ sites, onSelectSite }: Props) {
  return (
    <section className="flex-1 min-h-0 overflow-hidden p-2">
      <div
        className="grid gap-1.5 h-full"
        style={{
          gridTemplateColumns: 'repeat(5, 1fr)',
          gridTemplateRows: 'repeat(10, 1fr)',
        }}
      >
        {sites.map(site => {
          const st = siteState(site)
          const abnormal = st === 'FAIL' || st === 'OFFLINE'
          const online = site.duts.filter(d => d.connected).length
          const elapsed = Math.max(0, ...site.duts.map(d => d.durationSec))
          return (
            <div
              key={site.id}
              className="rounded panel overflow-hidden flex transition-shadow hover:shadow-lg"
              style={abnormal
                ? { borderColor: 'var(--st-fail)', boxShadow: '0 0 8px color-mix(in srgb, var(--st-fail) 30%, transparent)' }
                : undefined}
              title={`SITE ${pad(site.id)} · ${t('ovOnline')} ${online}/24 · ${SITE_STATE_LABEL[st]()}`}
            >
              {/* 左：状态块（状态文字 / 大号编号 + 两板状态灯 / 计时），点击进 site 页 */}
              <button
                onClick={() => onSelectSite(site.id)}
                className="w-[64px] shrink-0 flex flex-col items-center justify-center gap-0.5 bg-[var(--strip)] border-r border-[var(--line)] hover:bg-[var(--row-hover)] transition-colors"
              >
                <span
                  className="font-mono text-[9px] font-bold leading-none"
                  style={{ color: SITE_STATE_COLOR[st] }}
                >
                  {SITE_STATE_LABEL[st]()}
                </span>
                <span className="flex items-center gap-1">
                  <span
                    className="font-mono text-[16px] font-extrabold leading-none"
                    style={{ color: abnormal ? 'var(--st-fail)' : 'var(--text)' }}
                  >
                    {pad(site.id)}
                  </span>
                  <span className="flex flex-col gap-0.5">
                    {[0, 1].map(bi => {
                      const bs = boardState(site.duts.slice(bi * 12, bi * 12 + 12))
                      const lamp = LAMP_COLOR[bs]
                      return (
                        <span
                          key={bi}
                          title={`${t('ovDutLinkGroup')} ${bi + 1} · CH ${pad(bi * 12 + 1)}-${pad(bi * 12 + 12)} · ${LAMP_LABEL[bs]()}`}
                          className="inline-block w-1.5 h-1.5 rounded-full border border-[var(--line)]"
                          style={{
                            backgroundColor: lamp.color,
                            boxShadow: lamp.glow ? `0 0 4px color-mix(in srgb, ${lamp.color} 55%, transparent)` : 'none',
                          }}
                        />
                      )
                    })}
                  </span>
                </span>
                <span className="font-mono text-[9px] text-[var(--text3)] leading-none">
                  {fmtHms(elapsed)}
                </span>
              </button>

              {/* 右：24 芯片图标（两行各 12 = 通讯板1/2，行间虚线分隔） */}
              <div className="flex-1 min-w-0 flex flex-col px-1.5 py-1">
                {[site.duts.slice(0, 12), site.duts.slice(12, 24)].map((boardDuts, bi) => (
                  <div
                    key={bi}
                    className={`flex-1 min-h-0 grid grid-cols-12 ${bi === 0 ? 'border-b border-dashed border-[var(--line)]' : ''}`}
                  >
                    {boardDuts.map(d => (
                      <button
                        key={d.slot}
                        onClick={() => onSelectSite(site.id, d.slot)}
                        title={`SITE ${pad(site.id)} · CH ${pad(d.slot)} · ${LAMP_LABEL[d.state]()}`}
                        className="flex items-center justify-center min-h-0 rounded-[2px] hover:bg-[var(--row-hover)] transition-colors"
                      >
                        <ChipIcon state={d.state} />
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
