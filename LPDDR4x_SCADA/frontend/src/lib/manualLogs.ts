import type { LogEntry } from '../types/dut'

export interface ManualLogCursor {
  all: number
  channels: Record<number, number>
}

// null means the overview's explicit clear button. Single-DUT actions only
// advance that channel's cursor, including when viewed in the overview.
export function clearManualLogs(cursor: ManualLogCursor, channel: number | null,
                                through: number): ManualLogCursor {
  return channel === null
    ? { all: Math.max(cursor.all, through), channels: cursor.channels }
    : { ...cursor, channels: { ...cursor.channels,
        [channel]: Math.max(cursor.channels[channel] ?? 0, through) } }
}

export function visibleManualLogs(logs: LogEntry[], cursor: ManualLogCursor): LogEntry[] {
  return logs.filter(e => e.id > cursor.all && (e.siteId !== 1 || e.slot === null
    || e.id > (cursor.channels[e.slot] ?? 0)))
}

// The shared stream is a chronological tail. Keep peer channels' independent
// tails too, so a boot-log burst cannot evict every line of a quieter DUT.
// Only prepend entries older than the shared tail: overlapping IDs stay unique.
export function mergeManualLogs(shared: LogEntry[], perDut: Record<string, LogEntry[]>,
                                channels: number[]): LogEntry[] {
  const first = shared[0]?.id ?? Infinity
  const older: LogEntry[] = []
  for (const channel of new Set(channels)) {
    for (const entry of perDut[`1:${channel}`] ?? []) {
      if (entry.id < first && entry.siteId === 1 && entry.slot === channel) older.push(entry)
    }
  }
  return older.length ? [...older.sort((a, b) => a.id - b.id), ...shared] : shared
}
