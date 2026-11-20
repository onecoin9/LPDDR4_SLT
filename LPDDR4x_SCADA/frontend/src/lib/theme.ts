// 主题系统：8 套配色，通过 <html data-theme="..."> 切换 CSS 变量（见 index.css）
// 新增主题 = 在 THEMES 加一项 + 在 index.css 加一组 [data-theme='xxx'] 变量

export const THEMES = [
  {
    id: 'dark',
    name: '深色', nameEn: 'Dark',
    desc: '石墨 × 琥珀 · 深色控制台', descEn: 'Graphite × Amber console',
    preview: { bg: '#141519', panel: '#1d1f26', line: '#33363f', accent: '#f0a028', text: '#e8e6e1', st: ['#3fb950', '#f85149', '#ffd60a', '#e8e6e1'] },
  },
  {
    id: 'light',
    name: '浅色', nameEn: 'Light',
    desc: '暖白极简 · 琥珀点缀', descEn: 'Warm white minimal · amber accent',
    preview: { bg: '#f4f5f7', panel: '#ffffff', line: '#d8dbe0', accent: '#d97e12', text: '#23252b', st: ['#1a7f37', '#cf222e', '#c98f00', '#c9cdd4'] },
  },
  {
    id: 'industrial',
    name: '工业灰', nameEn: 'Industrial',
    desc: '经典工控 · 青蓝点缀', descEn: 'Classic HMI gray · cyan accent',
    preview: { bg: '#f2f2f2', panel: '#f7f7f7', line: '#c9c9c9', accent: '#2aa9e0', text: '#333333', st: ['#1a7f37', '#cf222e', '#e8a800', '#e0e0e0'] },
  },
  {
    id: 'gundam',
    name: '高达', nameEn: 'Gundam',
    desc: 'RX-78 白 · 藏青 · 红蓝黄', descEn: 'RX-78 white · navy · red/blue/yellow',
    preview: { bg: '#e8eaef', panel: '#ffffff', line: '#2a4a8a', accent: '#d2342c', text: '#1a2233', st: ['#1f9d55', '#d2342c', '#e3a008', '#eef1f7'] },
  },
  {
    id: 'cyberpunk',
    name: '赛博朋克', nameEn: 'Cyberpunk',
    desc: '夜之城 · 霓虹青 × 品红 · 扫描线', descEn: 'Night City · neon cyan × magenta · scanlines',
    preview: { bg: '#050308', panel: '#0b0614', line: '#2b1245', accent: '#00f0ff', text: '#d9f2ff', st: ['#39ff88', '#ff2e63', '#f9f002', '#c8b8e8'] },
  },
  {
    id: 'meadow',
    name: '原野', nameEn: 'Meadow',
    desc: '手绘水彩 · 奶油纸 × 天空蓝', descEn: 'Hand-painted watercolor · cream paper × sky blue',
    preview: { bg: '#f3ecd9', panel: '#faf5e8', line: '#d9cbaa', accent: '#5b9bc4', text: '#4a4238', st: ['#6fa15c', '#d25b4e', '#e0a92e', '#f2e9d2'] },
  },
  {
    id: 'nord',
    name: '极光', nameEn: 'Nord',
    desc: 'Nord 冷蓝灰 · 克制的高级感', descEn: 'Nord polar blue-gray · restrained elegance',
    preview: { bg: '#2e3440', panel: '#3b4252', line: '#4c566a', accent: '#88c0d0', text: '#eceff4', st: ['#a3be8c', '#bf616a', '#ebcb8b', '#d8dee9'] },
  },
  {
    id: 'solarized',
    name: '暖阳', nameEn: 'Solarized',
    desc: 'Solarized 米纸 · 强光车间可读', descEn: 'Solarized cream · readable under bright light',
    preview: { bg: '#fdf6e3', panel: '#faf3de', line: '#ddd0ae', accent: '#cb4b16', text: '#586e75', st: ['#859900', '#dc322f', '#b58900', '#eee8d5'] },
  },
] as const

export type ThemeId = (typeof THEMES)[number]['id']

const STORAGE_KEY = 'slt-theme'

export function applyTheme(id: ThemeId) {
  document.documentElement.dataset.theme = id
  try { localStorage.setItem(STORAGE_KEY, id) } catch { /* 忽略隐私模式 */ }
}

// 应用启动时调用：读取本地保存的主题并应用，返回当前主题 id
export function initTheme(): ThemeId {
  let saved: string | null = null
  try { saved = localStorage.getItem(STORAGE_KEY) } catch { /* 忽略 */ }
  const valid = THEMES.some(t => t.id === saved)
  const id = (valid ? saved : 'dark') as ThemeId
  applyTheme(id)
  return id
}
