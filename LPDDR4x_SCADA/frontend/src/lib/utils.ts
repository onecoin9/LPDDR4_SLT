import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// 运行时长（2026-09-24 用户指令）：整数秒；<60s → "12s"；≥60s → "3m 05s"；
// ≥60m → "2h 03m 05s"（低位段补零对齐）
export function fmtDur(sec: number): string {
  const s = Math.max(0, Math.floor(sec))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const r = String(s % 60).padStart(2, "0")
  if (m < 60) return `${m}m ${r}s`
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m ${r}s`
}
