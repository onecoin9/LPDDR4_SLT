// 页面缩放：CSS zoom 驱动，localStorage 记忆
// 快捷键（在 Home 中注册）：Ctrl + '+' 放大 / Ctrl + '-' 缩小 / Ctrl + '0' 重置

export const ZOOM_MIN = 0.6
export const ZOOM_MAX = 1.6
export const ZOOM_STEP = 0.1

const STORAGE_KEY = 'slt-zoom'

const clamp = (z: number) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(z * 100) / 100))

export function loadZoom(): number {
  try {
    const s = Number(localStorage.getItem(STORAGE_KEY))
    if (Number.isFinite(s) && s > 0) return clamp(s)
  } catch { /* 忽略隐私模式 */ }
  return 1
}

export function saveZoom(z: number) {
  try { localStorage.setItem(STORAGE_KEY, String(z)) } catch { /* 忽略 */ }
}

export const zoomIn = (z: number) => clamp(z + ZOOM_STEP)
export const zoomOut = (z: number) => clamp(z - ZOOM_STEP)
