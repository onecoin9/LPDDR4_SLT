import type { ProductProfile } from '../types/product'
import { getLang } from './i18n'

export interface PlanIssue {
  code?: string
  field?: string
  messageZh?: string
  messageEn?: string
}
export interface ProductPlan {
  configurationStatus?: 'partial' | 'complete'
  valid: boolean
  errors: PlanIssue[]
  warnings: PlanIssue[]
  algorithms: string[]
  effectiveParameters: { name: string; value: number | null; unit: string; source: string }[]
  stages: string[]
  cfgSha256: string
  mask: string | null
  testCount: number
  cfgText: string
  mcuMessage?: { command: string; payloadBytes: number; frameHex: string }
}

export function issueText(issue: PlanIssue): string {
  const message = getLang() === 'en' ? issue.messageEn : issue.messageZh
  return [issue.field, message ?? issue.messageEn ?? issue.messageZh ?? issue.code].filter(Boolean).join(': ')
}

export function apiErrorText(body: unknown): string {
  if (body && typeof body === 'object') {
    const detail = 'detail' in body ? (body as { detail: unknown }).detail : body
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map(e => String(e.msg ?? '')).join('\n')
    if (detail && typeof detail === 'object') {
      const value = detail as { errors?: PlanIssue[] } & PlanIssue
      if (Array.isArray(value.errors)) return value.errors.map(issueText).join('\n')
      const text = issueText(value)
      if (text) return text
    }
  }
  return getLang() === 'en' ? 'Request failed' : '请求失败'
}

export async function previewProduct(profile: ProductProfile, base: string): Promise<ProductPlan> {
  const response = await fetch(base + '/api/products/preview', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(profile),
  })
  const body = await response.json()
  if (!response.ok) throw new Error(apiErrorText(body))
  return body
}

export async function saveProduct(profile: ProductProfile, base: string): Promise<ProductPlan> {
  const response = await fetch(base + '/api/products', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(profile),
  })
  const body = await response.json()
  if (!response.ok || body.ok !== true || !body.plan?.valid) throw new Error(apiErrorText(body))
  return body.plan
}

// 与手动测试页同一条链路：key=value CFG 文本 → 后端解析并同步产品档案（校验+落盘一步完成）
export interface ImportedCfg {
  product: string
  profile: ProductProfile
  preview: ProductPlan
  settingsRevision: string
}

export async function importProductCfg(cfgText: string, product: string, settingsRevision: string, base: string): Promise<ImportedCfg> {
  const response = await fetch(base + '/api/products/import-cfg', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cfgText, product, settingsRevision }),
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new Error(apiErrorText(body))
  return body as ImportedCfg
}
