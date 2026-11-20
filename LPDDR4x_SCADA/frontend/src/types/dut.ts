// 与 agent.md §5.2 WebSocket 消息约定保持一致
// 后端就绪后，本类型即前后端共享契约

export type DutState = 'IDLE' | 'TESTING' | 'PASS' | 'FAIL' | 'OFFLINE'

export interface DutStatus {
  slot: number            // 通道号（工位号）01-24
  connected: boolean      // TCP 连接状态
  state: DutState
  step: string            // 当前测试项（TBD：占位测试流程）
  progress: number        // 0-100
  durationSec: number     // 本次测试时长（秒）
  countdownSec: number    // 倒计时（秒，预估）
  successCount: number    // 累计成功数
  totalCount: number      // 累计测试数
  testInfo: string        // 测试信息（一行文本）
  result?: 'PASS' | 'FAIL' | null
  failItem?: string | null
}

export type LogCat = 'system' | 'dut' | 'sys' | 'conn'
// conn = 连接事件（上下线/前后端断连）；sys = 主控板系统运行日志（[SYS] 行标签，
// HSG-LOG 2026-09-16），与上位机自身 system 分开

export interface LogEntry {
  id: number
  ts: string
  siteId: number | null   // null = 系统级日志
  slot: number | null     // null = 系统级日志
  level: 'INFO' | 'WARN' | 'ERROR'
  cat: LogCat
  msg: string
}

// 一个 site = 24 个 DUT（对应一台测试机的两块通讯板）
export interface SiteStatus {
  id: number              // site 编号 01..
  duts: DutStatus[]       // 固定 24 个 DUT
}

// mock 站点数（每 site 24 DUT）；后端就绪后按实际配置替换
export const SITE_COUNT = 4

// 机台表单配置（对应参考界面右侧面板）
export interface SessionConfig {
  product: string         // 产品名
  workOrder: string       // 工单号
  lotNo: string           // LOT号
  operator: string        // 操作员
}

// IO 控制（设置页「通道设置」，2026-09-07 按旧上位机 SettingForm 原样移植；
// 契约 = backend/app/models.py IoControlConfig，随 POST /api/config 上送）
// action: none=无操作 / power_key=测试板开机（MCU_PWR 分批按键）/
//         download=测试板进入下载模式（MCU_KPCOL，调试用）
export interface IoControl {
  action: 'none' | 'power_key' | 'download'
  batch: number          // 每批路数（12 路分几批错峰）
  startDelaySec: number  // 首批延迟（秒）
  intervalSec: number    // 批间隔（秒）
  pulseMs: number        // 按键时长（毫秒）
}

export const DEFAULT_IO_CONTROL: IoControl = {
  action: 'none', batch: 4, startDelaySec: 0, intervalSec: 5, pulseMs: 200,
}

// Handler 分选机对接设置（设置页「Handler 设置」，2026-10-13；
// 契约 = backend/app/handler.py HandlerService.snapshot()，
// GET/POST /api/handler/settings 即时生效并持久化 handler_settings.json；
// 仅作用于首页量产测试（自动轨），手动调试页不使用）
export interface HandlerSettings {
  enabled: boolean
  rx_port: number         // 本机侦听端口（Handler → 上位机，旧 DestPort 默认 7000）
  tx_host: string         // 上报目标 IP；空 = 自动学习入站连接源 IP
  tx_port: number         // 上报端口（上位机 → Handler，旧 HandlerReplyPort 默认 64100）
  running?: boolean
  learned_host?: string
}

// TBD 占位测试流程 —— 正式测试项清单待定（见 agent.md §7），
// 架构上测试项为可配置插件，此处仅为界面演示
export const PLACEHOLDER_STEPS = [
  'init',
  'mr_write',
  'march_write',
  'march_read',
  'verify',
] as const

// 占位：单次测试预估时长（秒），用于倒计时列
export const EST_DURATION_SEC = 90

// mock：License 剩余天数（后端就绪后由 /api/config 或授权模块提供）
export const LICENSE_DAYS_LEFT = 128
