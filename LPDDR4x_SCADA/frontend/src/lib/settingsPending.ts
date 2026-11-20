// Product drafts can queue a newer save behind an in-flight acknowledgement.
// Register the whole local operation immediately, before its HTTP write joins
// useAppSettings' queue, so a start cannot slip between the two queues.
const pending = new Set<Promise<unknown>>()
const errorListeners = new Set<(message: string) => void>()

export function trackSettingsSave<T>(request: Promise<T>): Promise<T> {
  pending.add(request)
  void request.then(() => pending.delete(request), error => {
    pending.delete(request)
    const message = error instanceof Error ? error.message : String(error)
    for (const listener of errorListeners) listener(message)
  })
  return request
}

export function pendingSettingsSaves(): Promise<unknown>[] { return [...pending] }

export function onSettingsSaveError(listener: (message: string) => void): () => void {
  errorListeners.add(listener)
  return () => { errorListeners.delete(listener) }
}
