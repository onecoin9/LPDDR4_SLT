#!/usr/bin/env node
// 客户文案检查（docs/UI文案标准.md 的机器执行部分）。
// 扫描 frontend/src/lib/i18n.ts 的 zh/en 词条值；命中禁用词即失败。
// 白名单条目需在 LEGACY 注明原因，且只允许临时存在（见标准「已知遗留」）。
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'lib', 'i18n.ts'), 'utf8')

// 禁用词：开发状态词 / 实现细节（寄存器编码、帧号）
const BANNED = [
  '预留', '即将推出', '暂不可用', '暂无可配置', '待实现', 'TODO',
  'reg×', 'regx2', '05T', '0x10日志', '(reserved)',
]

// 遗留白名单：SettingsWindow.tsx 被并行开发占用，词条待该文件合入后删除
const LEGACY_KEYS = new Set(['navSoon', 'spSoon', 'secSoon'])

// 提取 zh/en 两个对象体内的 key: 'value' / key: "value" 对
const body = src.slice(src.indexOf('const zh'), src.indexOf('export type I18nKey'))
const re = /([A-Za-z0-9_]+)\s*:\s*(['"])((?:\\.|(?!\2).)*)\2/g
const failures = []
let m
while ((m = re.exec(body)) !== null) {
  const [, key, , val] = m
  if (LEGACY_KEYS.has(key)) continue
  for (const bad of BANNED) {
    if (val.includes(bad)) failures.push(`  ${key}: 命中禁用词「${bad}」 → ${val}`)
  }
}

if (failures.length) {
  console.error('UI 文案检查未通过（docs/UI文案标准.md）：')
  console.error(failures.join('\n'))
  process.exit(1)
}
console.log('UI 文案检查通过')
