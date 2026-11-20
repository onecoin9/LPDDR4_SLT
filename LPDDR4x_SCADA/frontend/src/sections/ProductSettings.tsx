import { useEffect, useRef, useState } from 'react'
import type { Pl2Pattern, ProductProfile } from '@/types/product'
import { PL2_ASC_ORDERS, PL2_TEST_MODES, TIMING_BY_KEY, parseProfileJson, normalizeProfile, setAlgorithmChecked, setAlgorithmOrder, selectScreeningMode, activeScreeningProfile } from '@/types/product'
import { previewProduct } from '@/lib/productPlan'
import type { ProductPlan } from '@/lib/productPlan'
import MRConfigDialog from '@/sections/MRConfigDialog'
import ProductConfigEditor from '@/sections/ProductConfigEditor'
import RuntimePolicyEditor from '@/sections/RuntimePolicyEditor'
import { t, getLang } from '@/lib/i18n'
import type { I18nKey } from '@/lib/i18n'
import { API_BASE } from '@/hooks/useServer'
import { TIMING_NS_CATALOG } from '@/types/timingCatalog'
import { trackSettingsSave } from '@/lib/settingsPending'

type TimingRow = { minPending?: boolean; maxPending?: boolean; limitPending?: boolean; name: string; minNs: number | null; maxNs: number | null; actualNs: number | null; register?: number | null; half?: number | null; model: string; status: string; reason?: string }
type TimingReadback = { limitsKnown?: boolean; minNs?: number | null; maxNs?: number | null; name: string; requestNs: number | null; actualNs: number | null; verified: boolean; site: number; slot: number; channel: number | null; ckMHz: number; div: number | null; receivedAt: number; reason?: string }

// PL2 测试模式（存储值=中文枚举）→ i18n 词条
const PL2_MODE_I18N: Record<string, I18nKey> = {
  '快速筛查': 'pdModeQuick',
  '完整筛查': 'pdModeComplete',
  '坏区管理': 'pdModeBadArea',
}

// 标签展示名：去掉结尾括号中的单位（如 VDD1(mV) → VDD1）；数据键仍用原始 r.name
function displayLabel(name: string) {
  return name.replace(/\s*[（(][^）)]*[）)]\s*$/, '')
}

function parameterDetails(name: string) {
  const board = BOARD_CONFIG_FIELDS.find(field => field.key === name)
  if (board) return { min: board.min, max: board.max, step: 1,
    unit: board.unit === 'flag' || board.unit === 'enum' ? '' : board.unit || '',
    purpose: t(board.purpose) }
  const field = TIMING_BY_KEY.get(name)
  if (field) return { min: field.min, max: field.max, step: field.scale === 100 ? 0.01 : 1,
    unit: field.unit === 'ns' ? 'ns' : '',
    purpose: getLang() === 'en' ? field.purposeEn : field.purposeZh }
  const limits: Record<string, [number, number]> = { 'VDD1(mV)': [1000, 2400], 'VDD2H(mV)': [500, 1500], 'VDD2L(mV)': [0, 1500], 'VDDQ(mV)': [100, 1000] }
  if (name === 'VDD2L(mV)') return { min: 0, max: 1500, step: 1, unit: 'mV', purpose: t('pdBoardVdd2lPurpose') }
  if (limits[name]) return { min: limits[name][0], max: limits[name][1], step: 1, unit: 'mV', purpose: t('timingVoltagePurpose') }
  if (name === '测试频率(M)') return { min: 1600, max: 4266, step: 1, unit: 'MT/s', purpose: t('timingFrequencyPurpose') }
  if (name === 'LogLevel') return { min: 0, max: 2, step: 1, unit: '', purpose: t('pdBoardLogLevelPurpose') }
  if (name === 'BadBlockMgmt') return { min: 0, max: 1, step: 1, unit: '', purpose: t('pdBoardBadBlockPurpose') }
  return { min: undefined, max: undefined, step: 1, unit: '', purpose: t('pdTimUnsupported') }
}

interface Props {
  profiles: Record<string, ProductProfile>
  productName: string                       // 与前面板产品名同步
  onSelectProduct: (name: string) => void   // 切换产品（同步回前面板）
  settingsRevision?: string
  onProfilesChange: (p: Record<string, ProductProfile>) => Promise<void>  // 保存（持久化）
}

const inputCls = 'px-2 py-1 rounded-sm bg-[var(--input)] border border-[var(--input-line)] font-mono text-[12px] text-[var(--text)] outline-none focus:border-[var(--accent)] transition-colors'
const tabCls = (active: boolean) =>
  `px-3 py-1.5 font-mono text-[12px] font-bold border border-b-0 border-[var(--line)] transition-colors rounded-t-sm
   ${active ? 'bg-[var(--panel)] text-[var(--accent)]' : 'bg-[var(--strip)] text-[var(--text2)] hover:text-[var(--text)]'}`

type MainTab = 'slt' | 'ctrl' | 'board'
type PlTab = 'PL1' | 'PL2'

const BOARD_CONFIG_FIELDS: { key: string; unit: string; min: number; max: number; purpose: I18nKey }[] = [
  { key: 'Density', unit: 'Gb', min: 1, max: 64, purpose: 'pdBoardDensityPurpose' },
  { key: 'DieNum', unit: '', min: 1, max: 16, purpose: 'pdBoardDieNumPurpose' },
  { key: 'AgingTime', unit: 'min', min: 0, max: 1440, purpose: 'pdBoardAgingPurpose' },
  { key: 'PatternTest', unit: 'flag', min: 0, max: 1, purpose: 'pdBoardPatternPurpose' },
  { key: 'DvfsTest', unit: 'flag', min: 0, max: 1, purpose: 'pdBoardDvfsPurpose' },
  { key: 'VideoTest', unit: 'flag', min: 0, max: 1, purpose: 'pdBoardVideoPurpose' },
  { key: 'EngineerMode', unit: 'flag', min: 0, max: 1, purpose: 'pdBoardEngineerPurpose' },
  { key: 'Mode', unit: 'enum', min: 0, max: 3, purpose: 'pdBoardModePurpose' },
  { key: 'LOG_TO_UART1', unit: 'flag', min: 0, max: 1, purpose: 'pdBoardUartPurpose' },
]
const ORDINARY_CFG_KEYS: Record<string, string> = {
  'VDD1(mV)': 'VDD1', 'VDD2H(mV)': 'VDD2', 'VDD2L(mV)': 'VDD2L', 'VDDQ(mV)': 'VDDQ', '测试频率(M)': 'Freq',
  LogLevel: 'LogLevel', BadBlockMgmt: 'BadBlockMgmt',
}

type ProfileLibrary = Record<string, ProductProfile>
type DraftEntry = {
  draft: ProductProfile | null
  revision: number
  savedRevision: number
  pending: Map<number, Promise<void>>
  knownValues: Set<string>
  conflict: boolean
}

function profileValue(profile: ProductProfile | null) {
  // Home normalizes settings replies. Compare that same representation rather
  // than mistaking added defaults or catalogue ordering for an external edit.
  try { return JSON.stringify(profile ? normalizeProfile(normalizeProfile(structuredClone(profile))) : null) }
  catch { return JSON.stringify(profile) }
}

// A response acknowledges its submitted revision, never a newer local edit.
// All save entry points use this queue so leaving the page cannot race autosave.
export class ProductDraftSession {
  private profiles: ProfileLibrary
  private persist: (profiles: ProfileLibrary) => Promise<void>
  private entries = new Map<string, DraftEntry>()
  private tail: Promise<void> = Promise.resolve()
  productName: string

  constructor(profiles: ProfileLibrary, productName: string, persist: (profiles: ProfileLibrary) => Promise<void>) {
    this.profiles = profiles
    this.persist = persist
    this.productName = productName
  }

  setSource(profiles: ProfileLibrary, persist: (profiles: ProfileLibrary) => Promise<void>) {
    this.profiles = profiles
    this.persist = persist
  }

  private entry(name = this.productName) {
    let entry = this.entries.get(name)
    if (!entry) {
      entry = { draft: this.profiles[name] ? structuredClone(this.profiles[name]) : null,
        revision: 0, savedRevision: 0, pending: new Map(),
        knownValues: new Set([profileValue(this.profiles[name] ?? null)]), conflict: false }
      this.entries.set(name, entry)
    }
    return entry
  }

  get draft() { return this.entry().draft }
  get library() { return this.profiles }
  get revision() { return this.entry().revision }
  get conflicted() { return this.entry().conflict }

  receive(productName: string) {
    this.productName = productName
    const entry = this.entry()
    const incoming = this.profiles[productName] ?? null
    const value = profileValue(incoming)
    // Library refreshes also contain earlier autosave replies. Only clean drafts
    // may adopt them; a dirty revision stays visible until its own save completes.
    if (entry.revision !== entry.savedRevision && !entry.knownValues.has(value)) entry.conflict = true
    if (entry.revision === entry.savedRevision && profileValue(entry.draft) !== value) {
      entry.draft = incoming ? structuredClone(incoming) : null
      entry.revision++
      entry.savedRevision = entry.revision
      entry.knownValues.add(value)
      entry.conflict = false
    }
    return entry.draft
  }

  reload() {
    const entry = this.entry()
    entry.draft = this.profiles[this.productName] ? structuredClone(this.profiles[this.productName]) : null
    entry.revision++
    entry.savedRevision = entry.revision
    entry.knownValues = new Set([profileValue(entry.draft)])
    entry.conflict = false
    return entry.draft
  }

  acceptOverwrite() {
    const entry = this.entry()
    entry.knownValues.add(profileValue(this.profiles[this.productName] ?? null))
    entry.conflict = false
  }

  // 采纳 import-cfg 的返回档案：后端已校验并落盘，本地标记为已保存态，
  // 不再走 persist（避免把导入结果二次 PUT 覆盖或触发 revision 冲突）。
  adoptImported(name: string, imported: ProductProfile) {
    const entry = this.entry(name)
    entry.draft = structuredClone(imported)
    entry.revision++
    entry.savedRevision = entry.revision
    entry.knownValues = new Set([profileValue(entry.draft)])
    entry.conflict = false
    return entry.draft
  }

  edit(draft: ProductProfile) {
    const entry = this.entry()
    if (JSON.stringify(entry.draft) !== JSON.stringify(draft)) {
      entry.draft = draft
      entry.revision++
    }
    return entry.draft
  }

  forget(productName: string) {
    const entry = this.entry(productName)
    entry.draft = null
    entry.revision++
    entry.savedRevision = entry.revision
    entry.conflict = false
  }

  save(productName = this.productName): Promise<void> {
    const entry = this.entry(productName)
    const revision = entry.revision
    if (!entry.draft || revision === entry.savedRevision) return this.tail
    const pending = entry.pending.get(revision)
    if (pending) return pending
    const submitted = structuredClone(entry.draft)
    if (entry.conflict) return trackSettingsSave(Promise.reject(new Error('Product draft conflicts with an external update')))
    entry.knownValues.add(profileValue(submitted))
    const request = this.tail.then(async () => {
      if (entry.conflict) throw new Error('Product draft conflicts with an external update')
      const next = { ...this.profiles, [submitted.name]: submitted }
      await this.persist(next)
      this.profiles = { ...this.profiles, [submitted.name]: submitted }
      entry.savedRevision = Math.max(entry.savedRevision, revision)
    })
    // A failed request remains dirty and retryable, without blocking later saves.
    this.tail = request.catch(() => {})
    entry.pending.set(revision, request)
    void request.then(() => entry.pending.delete(revision), () => entry.pending.delete(revision))
    return trackSettingsSave(request)
  }
}

// 产品设置页（参照 SLT 上位机产品配置界面；配置为 JSON 文件，见 types/product.ts）
export default function ProductSettings({ profiles, productName, onSelectProduct, onProfilesChange, settingsRevision }: Props) {
  const [mainTab, setMainTab] = useState<MainTab>('board')
  const [plTab, setPlTab] = useState<PlTab>('PL1')
  const sessionRef = useRef<ProductDraftSession | null>(null)
  if (!sessionRef.current) sessionRef.current = new ProductDraftSession(profiles, productName, onProfilesChange)
  const session = sessionRef.current
  session.setSource(profiles, onProfilesChange)
  const [draft, setDraftState] = useState<ProductProfile | null>(session.draft)
  const [savedFlash, setSavedFlash] = useState(false)
  const [saving, setSaving] = useState(false)
  const [draftConflict, setDraftConflict] = useState(false)
  const [baseCfg, setBaseCfg] = useState<Record<string, number>>({})
  const [baseCfgError, setBaseCfgError] = useState('')
  const [checking, setChecking] = useState(false)
  const [plan, setPlan] = useState<ProductPlan | null>(null)
  const [planOpen, setPlanOpen] = useState(false)
  const [planError, setPlanError] = useState('')
  const [timingRows, setTimingRows] = useState<TimingRow[]>([])
  const [timingError, setTimingError] = useState('')
  const [timingTag,setTimingTag] = useState<string | null>(null)
  const [timingReadbacks,setTimingReadbacks] = useState<TimingReadback[]>([])
  const draftRef = useRef(draft)
  draftRef.current = draft
  const [mrEdit, setMrEdit] = useState<'ch1' | 'ch2' | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const setDraft = (next: ProductProfile) => {
    const edited = session.edit(next)
    draftRef.current = edited
    setDraftState(edited)
    setSavedFlash(false)
  }
  useEffect(() => () => { void session.save().catch(() => {}) }, [session])

  // Flush the previous product before switching; server replies preserve newer edits.
  useEffect(() => {
    if (session.productName !== productName) {
      void session.save().catch(error => setPlanError(error instanceof Error ? error.message : t('planRequestFailed')))
    }
    const next = session.receive(productName)
    draftRef.current = next
    setDraftState(next)
    setDraftConflict(session.conflicted)
  }, [productName, profiles, session])
  useEffect(() => { setPlan(null); setPlanError('') }, [draft])
  useEffect(() => { setSavedFlash(false) }, [productName])
  useEffect(() => {
    const abort = new AbortController()
    void fetch(API_BASE + '/api/products/context', { signal: abort.signal }).then(async response => {
      if (!response.ok) throw new Error(t('pdBoardBaseFailed'))
      const body = await response.json()
      if (!body.baseCfg || typeof body.baseCfg !== 'object') throw new Error(t('pdBoardBaseFailed'))
      setBaseCfg(Object.fromEntries(Object.entries(body.baseCfg).filter((entry): entry is [string, number] =>
        typeof entry[1] === 'number' && Number.isFinite(entry[1]))))
    }).catch(error => { if (!abort.signal.aborted) setBaseCfgError(String(error)) })
    return () => abort.abort()
  }, [])
  useEffect(() => {
    setTimingRows([]); setTimingError(''); setTimingTag(null); setTimingReadbacks([])
    if (draft?.timingSchema !== 2) return
    const abort = new AbortController()
    const timer = window.setTimeout(() => {
      void fetch(API_BASE + '/api/timing/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft), signal: abort.signal }).then(async response => {
        if (!response.ok) throw new Error(t('planRequestFailed'))
        const body = await response.json()
        setTimingRows(body.rows)
        setTimingTag(body.tag)
      }).catch(error => { if (!abort.signal.aborted) setTimingError(String(error)) })
    }, 200)
    return () => { window.clearTimeout(timer); abort.abort() }
  }, [draft])
  useEffect(() => {
    if (!timingTag) return
    const abort=new AbortController()
    const load=() => { void fetch(API_BASE+'/api/timing/readback?tag='+timingTag,{signal:abort.signal})
      .then(async response => { if(response.ok) setTimingReadbacks((await response.json()).rows) })
      .catch(() => {}) }
    load(); const timer=window.setInterval(load,2000)
    return () => { abort.abort(); window.clearInterval(timer) }
  },[timingTag])
  // Persist edited drafts as JSON; execution and the Save button still compile/validate.
  useEffect(() => {
    if (!draft || saving || draftConflict) return
    const revision = session.revision
    const timer = window.setTimeout(() => {
      void session.save(productName).catch(error => {
        if (session.productName === productName && session.revision === revision) {
          setPlanError(error instanceof Error ? error.message : t('planRequestFailed'))
        }
      })
    }, 600)
    return () => window.clearTimeout(timer)
  }, [draft, productName, saving, draftConflict, session])

  if (!draft) {
    return <div className="h-full flex items-center justify-center font-mono text-[12px] text-[var(--text3)]">-</div>
  }

  const names = Object.keys(profiles)
  const pl1Locked = false   // PL1 未启用：锁定阶段全局参数等三个子选项卡的全部内容
  const pl2Locked = draft.pl2.testMode === '完整筛查'   // PL2 未启用：同理锁定
  const parameters = [
    ...draft.params.filter(row => Object.hasOwn(ORDINARY_CFG_KEYS, row.name)),
    ...BOARD_CONFIG_FIELDS.map((field, index) => ({ id: index + 1, name: field.key,
      value: String(draft.cfgOverrides?.[field.key] ?? baseCfg[field.key] ?? ''),
      checked: Object.hasOwn(draft.cfgOverrides ?? {}, field.key),
      options: undefined as string[] | undefined, unsupported: false })),
    ...draft.params.filter(row => !Object.hasOwn(ORDINARY_CFG_KEYS, row.name)),
  ]

  const patch = (p: Partial<ProductProfile>) => { if (!saving) setDraft({ ...draft, ...p }) }
  const patchBoard = (key: string, value: number | undefined) => {
    if (saving || !BOARD_CONFIG_FIELDS.some(field => field.key === key)) return
    const overrides = { ...draft.cfgOverrides }
    if (value === undefined) delete overrides[key]
    else overrides[key] = value
    patch({ cfgOverrides: overrides })
  }
  const patchParam = (name: string, p: Partial<ProductProfile['params'][number]>) => {
    if (saving) return
    if (BOARD_CONFIG_FIELDS.some(field => field.key === name)) {
      const value = p.checked === false ? undefined : Number(p.value ?? draft.cfgOverrides?.[name] ?? baseCfg[name])
      patchBoard(name, value)
    } else {
      setSavedFlash(false)
      setDraft({ ...draft, params: draft.params.map(r => (r.name === name ? { ...r, ...p } : r)) })
    }
  }
  const patchPl2 = (p: Partial<ProductProfile['pl2']>) =>
    { if (!saving) { setSavedFlash(false); setDraft({ ...draft, pl2: { ...draft.pl2, ...p } }) } }
  const curPatterns = [...(draft.pl2.patterns[draft.pl2.testMode] ?? [])].sort((a, b) =>
    Number(b.checked) - Number(a.checked) || Number(draft.pl2.executionOrder?.[a.name] ?? a.order) - Number(draft.pl2.executionOrder?.[b.name] ?? b.order))
  const patchPl2Pattern = (name: string, p: Partial<Pl2Pattern>) => {
    const row = curPatterns.find(r => r.name === name)
    if (!row || saving) return
    if (typeof p.checked === 'boolean') setDraft(activeScreeningProfile(setAlgorithmChecked(draft, row.name, p.checked)))
    if (typeof p.order === 'string') setDraft(activeScreeningProfile(setAlgorithmOrder(draft, row.name, p.order)))
  }
  const canEnable = (r: ProductProfile['params'][number]) =>
    !r.unsupported && r.value.trim() !== ''
  const bulkParameters = (enabled: (row: ProductProfile['params'][number]) => boolean) => {
    const cfgOverrides = { ...draft.cfgOverrides }
    for (const row of parameters.filter(row => BOARD_CONFIG_FIELDS.some(field => field.key === row.name))) {
      if (enabled(row) && canEnable(row)) cfgOverrides[row.name] = Number(row.value)
      else delete cfgOverrides[row.name]
    }
    setDraft({ ...draft, cfgOverrides, params: draft.params.map(row => ({ ...row, checked: enabled(row) && canEnable(row) })) })
  }
  const setAll = (v: boolean) => {
    if (saving) return
    if (plTab === 'PL2') setDraft(activeScreeningProfile(curPatterns.reduce((p, r) => setAlgorithmChecked(p, r.name, v), draft)))
    else bulkParameters(() => v)
  }
  const invert = () => {
    if (saving) return
    if (plTab === 'PL2') setDraft(activeScreeningProfile(curPatterns.reduce((p, r) => setAlgorithmChecked(p, r.name, !r.checked), draft)))
    else bulkParameters(row => !row.checked)
  }


  // Validation and persistence are separate; the active settings file owns the library.
  const handlePreview = async () => {
    const submitted = draft
    const original = draft
    setChecking(true)
    setPlanOpen(true)
    setPlanError('')
    try {
      const result = await previewProduct(submitted, API_BASE)
      if (draftRef.current === original) setPlan(result)
    } catch (error) {
      if (draftRef.current === original) setPlanError(error instanceof Error ? error.message : t('planRequestFailed'))
    } finally { setChecking(false) }
  }
  const handleSave = async () => {
    const submitted = draft
    const original = draft
    let revision = session.revision
    setSaving(true)
    setPlanError('')
    try {
      const result = await previewProduct(submitted, API_BASE)
      if (draftRef.current !== original) return
      if (session.conflicted && !window.confirm(t('pdDraftOverwriteConfirm'))) return
      session.acceptOverwrite()
      setDraftConflict(false)
      setDraft(submitted)
      revision = session.revision
      await session.save()
      if (session.productName === productName && session.revision === revision) {
        setPlan(result)
        setSavedFlash(true)
        setTimeout(() => setSavedFlash(false), 1500)
      }
    } catch (error) {
      if (session.productName === productName && session.revision === revision) {
        setPlanError(error instanceof Error ? error.message : t('planRequestFailed'))
      }
    } finally { setSaving(false) }
  }

  const handleDelete = async () => {
    if (saving || names.length <= 1 || !window.confirm(t('pdDeleteConfirm'))) return
    setSaving(true)
    try {
      await session.save()
      const next = { ...session.library }
      delete next[draft.name]
      await onProfilesChange(next)
      session.forget(draft.name)
      onSelectProduct(Object.keys(next)[0])
    } catch (e) { setPlanError(e instanceof Error ? e.message : t('planRequestFailed')) }
    finally { setSaving(false) }
  }

  // 「选择...」= 从 JSON 文件导入产品档案（与前面板同一解析器；自包含实现，
  // 复用 onProfilesChange 持久化 + onSelectProduct 切换，不新增上层穿透 props）
  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''   // 允许重复选同一文件
    if (!file) return
    file.text().then(async text => {
      try {
        const p = parseProfileJson(text)
        setSaving(true)
        await session.save()
        await onProfilesChange({ ...session.library, [p.name]: p })
        onSelectProduct(p.name)
      } catch {
        window.alert(t('spBadProfileJson'))
      } finally { setSaving(false) }
    })
  }

  return (
    <div className="flex flex-col gap-3">
      {/* 顶部：产品名 + 操作按钮（产品名与前面板同步） */}
      <div className="flex items-center gap-2">
        <span className="font-mono text-[12px] font-bold text-[var(--text2)] w-14 shrink-0">{t('spProduct')}</span>
        <select disabled={saving} value={productName} onChange={e => onSelectProduct(e.target.value)} className={`${inputCls} flex-1`}>
          {names.map(n => <option key={n} value={n}>{n}</option>)}
        </select>
        {/* 导入配置：从 JSON 文件导入产品档案（2026-10-14 启用，与前面板同源） */}
        <input ref={fileRef} type="file" accept=".json,application/json" className="hidden" onChange={handleFile} />
        <button disabled={saving} onClick={() => fileRef.current?.click()} title={t('spChooseJson')} className="btn-gray px-2.5 py-1 rounded-sm text-[12px] whitespace-nowrap">
          {t('spChoose')}
        </button>
        <button onClick={handleDelete} disabled={saving || names.length <= 1} className="btn-gray px-2.5 py-1 rounded-sm text-[12px]">{t('pdDelete')}</button>
      </div>

      {draftConflict && <div role="alert" className="flex items-center gap-3 text-[12px] text-[var(--st-fail)]">
        <span>{t('pdDraftConflict')}</span>
        <button disabled={saving} className="btn-gray px-2 py-1 shrink-0" onClick={() => {
          const next = session.reload()
          draftRef.current = next
          setDraftState(next)
          setDraftConflict(false)
          setSavedFlash(false)
        }}>{t('pdDraftReload')}</button>
      </div>}

      {/* Rank启用 + Rank 容量 + CH 使能（Rank 启用与 PL1 启用相互独立） */}
      <div className="flex items-center gap-4 flex-wrap">
        <label className="flex items-center gap-1.5 font-mono text-[12px] text-[var(--text)] cursor-pointer">
          <input type="checkbox" checked={draft.rankEnabled} onChange={e => patch({ rankEnabled: e.target.checked })} className="accent-[var(--accent)]" />
          {t('pdEnable')}
        </label>
        {([0, 1] as const).map(i => (
          <label key={i} className="flex items-center gap-1.5 font-mono text-[12px] text-[var(--text2)]">
            {i === 0 ? t('pdRank0') : t('pdRank1')}
            <input
              type="number" min={0} step={0.5}
              value={draft.rankCapacityGb[i]}
              disabled={!draft.rankEnabled}
              title={draft.rankEnabled ? undefined : t('pdRankLocked')}
              onChange={e => {
                const v = [...draft.rankCapacityGb] as [number, number]
                v[i] = Number(e.target.value) || 0
                patch({ rankCapacityGb: v })
              }}
              className={`${inputCls} w-20 disabled:opacity-40 disabled:cursor-not-allowed`}
            />
          </label>
        ))}
        <div className="ml-auto flex items-center gap-4">
          {(['ch1', 'ch2'] as const).map((ch, i) => (
            <label key={ch} className="flex items-center gap-1.5 font-mono text-[12px] text-[var(--text)] cursor-pointer">
              <input
                type="checkbox"
                checked={draft.channels[ch]}
                onChange={e => patch({ channels: { ...draft.channels, [ch]: e.target.checked } })}
                className="accent-[var(--accent)]"
              />
              {i === 0 ? t('pdCH1') : t('pdCH2')}
            </label>
          ))}
          {/* MR 配置按通道分组；通道未启用（颗粒无此通道）时锁定。填了值才会下发校验 */}
          {(['ch1', 'ch2'] as const).map((ck, i) => (
            <button
              key={`mr-${ck}`}
              onClick={() => setMrEdit(ck)}
              disabled={!draft.channels[ck]}
              title={!draft.channels[ck] ? t('pdMrLocked') : t('pdMrHint')}
              className="btn-gray px-2.5 py-1 rounded-sm text-[12px] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {i === 0 ? 'CH1' : 'CH2'} {t('pdMR')}
            </button>
          ))}
        </div>
      </div>

      {/* 主选项卡 */}
      <div className="flex gap-0.5 border-b border-[var(--line)]">
        <button className={tabCls(mainTab === 'slt')} onClick={() => setMainTab('slt')}>{t('pdTabSlt')}</button>
        <button className={tabCls(mainTab === 'board')} onClick={() => setMainTab('board')}>{t('pdTabBoard')}</button>
      </div>

      {mainTab === 'slt' ? <RuntimePolicyEditor settingsRevision={settingsRevision} /> : (
        /* 测试板配置：左侧 PL1/PL2/APK 竖排选项卡 */
        <div className="flex border border-[var(--line)] rounded-sm overflow-hidden bg-[var(--strip)]">
          <div className="shrink-0 flex flex-col border-r border-[var(--line)]">
            {(['PL1', 'PL2'] as PlTab[]).map(p => (
              <button
                key={p}
                onClick={() => setPlTab(p)}
                className={`w-9 py-3 font-mono text-[11px] font-bold transition-colors [writing-mode:vertical-lr]
                  ${plTab === p ? 'bg-[var(--panel)] text-[var(--accent)]' : 'text-[var(--text2)] hover:text-[var(--text)]'}`}
              >
                {p}
              </button>
            ))}
          </div>

          <div className="flex-1 min-w-0 bg-[var(--panel)] p-3 flex flex-col gap-2">
            {plTab === 'PL2' ? (
              <>
                <div>
                {(
                  /* Pattern及关联参数（参照 SLT 产品配置 PL2 页截图） */
                  <div className="flex flex-col gap-2 pt-1">
                    {/* 测试模式 + 升降序 */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-[12px] font-bold text-[var(--text2)]">{t('pdTestMode')}</span>
                      <select value={draft.pl2.testMode} onChange={e => setDraft(selectScreeningMode(draft, e.target.value))} className={`${inputCls} w-56`}>
                        {PL2_TEST_MODES.map(m => <option key={m} value={m}>{t(PL2_MODE_I18N[m] ?? 'pdTestMode')}</option>)}
                      </select>
                      <span className="text-[12px] text-[var(--text2)]">{t('pdAscDesc')}</span>
                      <select value={draft.pl2.ascOrder} onChange={e => patchPl2({ ascOrder: e.target.value })} className={`${inputCls} w-24`}>
                        {PL2_ASC_ORDERS.map(o => <option key={o} value={o}>{o === '升序' ? t('pdAsc') : t('pdDesc')}</option>)}
                      </select>
                    </div>
                    {/* Pattern 表：勾选 = 启用该 Pattern */}
                    <div className="border border-[var(--line)] rounded-sm overflow-hidden">
                      <div className="max-h-[240px] overflow-y-auto bg-[var(--table)]">
                        <table className="w-full border-collapse text-[12px]">
                          <thead className="sticky top-0 z-10">
                            <tr className="bg-[var(--strip)]">
                              {[t('colNo'), t('colPattern'), t('colExecOrder')].map((c, i) => (
                                <th key={i} className="px-2 py-1.5 border border-[var(--line)] text-left font-mono text-[11px] font-bold text-[var(--text2)] whitespace-nowrap">
                                  {c}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {curPatterns.map((r, idx) => (
                              <tr key={r.name} className={idx % 2 === 1 ? 'bg-[var(--zebra)]' : ''}>
                                <td className="px-2 py-1 border border-[var(--line)] whitespace-nowrap w-16">
                                  <span className="inline-flex items-center gap-1.5">
                                    <input
                                      type="checkbox"
                                      checked={r.checked}
                                      disabled={pl2Locked}
                                      onChange={e => patchPl2Pattern(r.name, { checked: e.target.checked })}
                                      className="accent-[var(--accent)]"
                                    />
                                    <span className="font-mono text-[var(--text3)]">{r.id}</span>
                                  </span>
                                </td>
                                <td className="px-2 py-1 border border-[var(--line)] font-mono text-[var(--text)] whitespace-nowrap">{r.name}</td>
                                <td className="px-1 py-0.5 border border-[var(--line)] w-24">
                                  <input type="number" min={1} max={9999} disabled={!r.checked} value={r.checked ? draft.pl2.executionOrder?.[r.name] ?? r.order : ''} onChange={e => patchPl2Pattern(r.name, { order: e.target.value })} aria-label={`${t('colExecOrder')} ${r.name}`} className={inputCls + ' w-full disabled:opacity-40'} />
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}
                </div>
              </>
            ) : (
              <>
                <div>
                {draft.timingSchema !== 2 && <button className="btn-gray px-3 py-1 mb-2" disabled={saving}
                  onClick={() => {
                    const retained = draft.params.filter(r => !TIMING_BY_KEY.has(r.name))
                    patch({ timingSchema: 2, timingReviewRequired: false,
                      params: [...retained, ...TIMING_NS_CATALOG.map((r,i) => ({ id: retained.length+i+1, name: r.key, value: '', checked: false }))] })
                  }}>{t('timingNsSwitch')}</button>}
                {timingError && <p role="alert" className="text-[12px] text-[var(--st-fail)]">{timingError}</p>}
                {baseCfgError && <p role="alert" className="text-[12px] text-[var(--st-fail)]">{baseCfgError}</p>}
                {draft.timingReviewRequired && <div role="alert" className="flex items-center gap-3 p-2 text-[12px] text-[var(--st-fail)]">
                  <span>{t('timingReviewMessage')} · {draft.timingMigration?.params.map(r => r.name).join(', ')}</span>
                  <button className="btn-gray px-2 py-1 shrink-0" onClick={() => patch({ timingReviewRequired: false })}>{t('timingReviewConfirm')}</button>
                </div>}

                {(
                  /* 参数表：勾选 = 启用该测试项 */
                  <div className="border border-[var(--line)] rounded-sm overflow-hidden">
                    <div className="max-h-[380px] overflow-auto bg-[var(--table)]">
                      <table className="w-full min-w-[880px] border-collapse text-[12px]">
                        <thead className="sticky top-0 z-10">
                          <tr className="bg-[var(--strip)]">
                            {['', t('colNo'), t('timingColLabel'), t('colMin'), t('colMax'), t('pdBoardRequested'), t('pdBoardEffective'), t('colRemark')].map((c, i) => (
                              <th key={i} className="px-2 py-1.5 border border-[var(--line)] text-left font-mono text-[11px] font-bold text-[var(--text2)] whitespace-nowrap">
                                {c}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {parameters.map((r, idx) => { const raw = parameterDetails(r.name); const ns = draft.timingSchema === 2 && TIMING_BY_KEY.has(r.name)
                            const ordinaryKey = BOARD_CONFIG_FIELDS.some(field => field.key === r.name) ? r.name : ORDINARY_CFG_KEYS[r.name]
                            const inherited = !!ordinaryKey && !r.checked
                            const shownValue = inherited ? String(baseCfg[ordinaryKey] ?? '') : r.value
                            const effectiveValue = ordinaryKey ? (r.checked ? r.value : baseCfg[ordinaryKey]) : undefined
                            const result = timingRows.find(x => x.name === r.name)
                            const nsField = TIMING_NS_CATALOG.find(x => x.key === r.name)
                            const reported = [...timingReadbacks].reverse().find(x => x.name===r.name && (x.reason || x.requestNs===Number(r.value)))
                            const info = ns ? { ...raw, unit: 'ns', step: 0.01, min: reported?.minNs ?? result?.minNs ?? undefined, max: reported?.maxNs ?? result?.maxNs ?? undefined,
                              purpose: nsField ? getLang() === 'en' ? nsField.purposeEn : nsField.purposeZh : raw.purpose } : raw
                            return (
                            <tr key={r.name} className={`${idx % 2 === 1 ? 'bg-[var(--zebra)]' : ''} ${r.unsupported ? 'opacity-40' : ''}`}>
                              <td className="px-2 py-1 border border-[var(--line)] text-center">
                                <input
                                  type="checkbox"
                                  checked={r.checked}
                                  disabled={saving || (r.unsupported && !r.checked) || (!!ordinaryKey && !shownValue.trim())}
                                  title={r.unsupported ? t('pdTimUnsupported') : undefined}
                                  onChange={e => patchParam(r.name, { checked: e.target.checked,
                                    ...(e.target.checked && !r.value.trim() && ordinaryKey && baseCfg[ordinaryKey] != null ? { value: String(baseCfg[ordinaryKey]) } : {}) })}
                                  className="accent-[var(--accent)]"
                                />
                              </td>
                              <td className="px-2 py-1 border border-[var(--line)] font-mono text-[var(--text3)]">{idx + 1}</td>
                              <td className="px-2 py-1 border border-[var(--line)] font-mono whitespace-nowrap text-[var(--text)]">
                                {displayLabel(r.name)}
                              </td>
                              <td className="px-2 py-1 border border-[var(--line)] font-mono whitespace-nowrap text-[var(--text3)]">{info.min == null ? '—' : Number(info.min.toFixed(3))}</td>
                              <td className="px-2 py-1 border border-[var(--line)] font-mono whitespace-nowrap text-[var(--text3)]">{info.max ?? '—'}</td>
                              <td className="px-1 py-0.5 border border-[var(--line)]">
                                <div className="flex items-center gap-1">
                                  {r.options ? (
                                    <select value={shownValue} disabled={saving || inherited} onChange={e => patchParam(r.name, { value: e.target.value })} className={`${inputCls} flex-1 min-w-0 disabled:opacity-60`}>
                                      {!r.options.includes(shownValue) && <option value={shownValue} disabled>{shownValue || '—'}{shownValue ? ` · ${t('planUnsupportedValue')}` : ''}</option>}
                                      {r.options.map(o => <option key={o} value={o}>{o}</option>)}
                                    </select>
                                  ) : (
                                    <input type="number" min={info.min} max={info.max} step={info.step} aria-label={`${r.name} ${t('pdBoardRequested')}`} value={shownValue} disabled={saving || r.unsupported || inherited} title={r.unsupported ? t('pdTimUnsupported') : undefined} onChange={e => patchParam(r.name, { value: e.target.value })} className={`${inputCls} w-[88px] disabled:opacity-60`} />
                                  )}
                                  {info.unit && <span className="text-[10px] text-[var(--text3)] whitespace-nowrap">{info.unit}</span>}
                                </div>
                              </td>
                              <td className="px-2 py-1 border border-[var(--line)] font-mono text-[var(--text2)]">
                                {result?.status === 'rejected' ? <span title={result.reason} className="text-[var(--st-fail)]">{t(result.reason === 'hardware_range' ? 'timingNsHardwareRange' : result.reason === 'no_legal_tick' ? 'timingNsNoTick' : result.reason?.endsWith('range') ? 'timingNsOutOfRange' : 'timingNsRejected')}</span> : ordinaryKey ? effectiveValue ?? '—' : ns ? result?.actualNs ?? '—' : r.checked ? r.value : '—'}
                              </td>
                              <td className="px-2 py-1 border border-[var(--line)] min-w-[200px] max-w-[340px] whitespace-normal break-words text-[11px] text-[var(--text2)]">
                                {info.purpose}
                              </td>
                            </tr>
                          ) })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {planError && !planOpen && <div role="alert" className="text-[12px] whitespace-pre-wrap text-[var(--st-fail)]">{planError}</div>}
      {/* 底部：反选/全选/全不选 + 导出/保存（PL1 未启用时锁定参数批量操作） */}
      {mainTab !== 'slt' && <div className="flex items-center gap-2">
        <button onClick={invert} disabled={saving || (plTab === 'PL2' ? pl2Locked : pl1Locked)} title={pl1Locked ? t('pdPl1Locked') : undefined} className="btn-gray px-3 py-1 rounded-sm text-[12px] disabled:opacity-40 disabled:cursor-not-allowed">{t('btnInvert')}</button>
        <button onClick={() => setAll(true)} disabled={saving || (plTab === 'PL2' ? pl2Locked : pl1Locked)} title={pl1Locked ? t('pdPl1Locked') : undefined} className="btn-gray px-3 py-1 rounded-sm text-[12px] disabled:opacity-40 disabled:cursor-not-allowed">{t('btnAll')}</button>
        <button onClick={() => setAll(false)} disabled={saving || (plTab === 'PL2' ? pl2Locked : pl1Locked)} title={pl1Locked ? t('pdPl1Locked') : undefined} className="btn-gray px-3 py-1 rounded-sm text-[12px] disabled:opacity-40 disabled:cursor-not-allowed">{t('btnNone')}</button>
        <span className="ml-auto" />
        <button onClick={handlePreview} disabled={checking || saving} className="btn-gray px-3 py-1 rounded-sm text-[12px] disabled:opacity-40">{checking ? t('planChecking') : t('planPreview')}</button>
        <button
          onClick={handleSave}
          disabled={saving || checking}
          className="px-6 py-1.5 rounded-sm bg-gradient-to-b from-[var(--accent-hi)] to-[var(--accent-to)] border border-[var(--accent-line)] text-[var(--accent-text)] text-[13px] font-extrabold hover:brightness-110 transition-all"
        >
          {saving ? t('planSaving') : savedFlash ? t('savedOk') : t('btnSave')}
        </button>
      </div>}

      {planOpen && !checking && <ProductConfigEditor profile={draft} initialCfgText={plan?.cfgText ?? ''} initialError={planError}
        settingsRevision={settingsRevision ?? ''}
        onImported={result => {
          setDraftState(session.adoptImported(result.product, result.profile))
          setDraftConflict(false)
          setSavedFlash(true)
          setPlanOpen(false)
        }}
        onClose={() => setPlanOpen(false)} />}
      {/* MR 配置弹窗（按 CH1/CH2 通道分组；填了期望值才会下发校验，留空不校验） */}
      {mrEdit && (
        <MRConfigDialog
          title={`${t('mrTitle')} · ${mrEdit.toUpperCase()}`}
          rows={draft.mr[mrEdit]}
          onOk={rows => {
            patch({ mr: { ...draft.mr, [mrEdit]: rows } })
            setMrEdit(null)
          }}
          onCancel={() => setMrEdit(null)}
        />
      )}
    </div>
  )
}
