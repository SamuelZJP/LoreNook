import { inject, provide, ref, type InjectionKey, type Ref } from 'vue'

export type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

/**
 * Saves as the user edits. Each field schedules its own save under a key; a newer
 * schedule for the same key replaces a pending one. Saves run one at a time, in order,
 * so a save reads the state the previous one left.
 */
export interface SaveTracker {
  status: Ref<SaveStatus>
  error: Ref<unknown>
  schedule(key: string, save: () => Promise<void>, delay?: number): void
  /** Run every pending save now; resolves true when nothing failed. */
  flush(): Promise<boolean>
  retry(): void
}

export function createSaveTracker(): SaveTracker {
  const status = ref<SaveStatus>('idle')
  const error = ref<unknown>(null)
  const pending = new Map<string, { timer: ReturnType<typeof setTimeout>; save: () => Promise<void> }>()
  let chain: Promise<void> = Promise.resolve()
  let failed: (() => Promise<void>) | null = null

  function enqueue(save: () => Promise<void>) {
    chain = chain.then(async () => {
      status.value = 'saving'
      try {
        await save()
        if (status.value === 'saving') status.value = 'saved'
        failed = null
        error.value = null
      } catch (e) {
        failed = save
        error.value = e
        status.value = 'error'
      }
    })
    return chain
  }
  function run(key: string) {
    const entry = pending.get(key)
    if (!entry) return
    clearTimeout(entry.timer)
    pending.delete(key)
    return enqueue(entry.save)
  }

  return {
    status,
    error,
    schedule(key, save, delay = 0) {
      const old = pending.get(key)
      if (old) clearTimeout(old.timer)
      pending.set(key, { save, timer: setTimeout(() => run(key), delay) })
    },
    async flush() {
      for (const key of [...pending.keys()]) run(key)
      await chain
      return status.value !== 'error'
    },
    retry() {
      if (failed) enqueue(failed)
    },
  }
}

const KEY: InjectionKey<SaveTracker> = Symbol('save-tracker')

export function provideSaveTracker(): SaveTracker {
  const tracker = createSaveTracker()
  provide(KEY, tracker)
  return tracker
}

/** The tracker of the surrounding settings view, or a private one outside it. */
export function useSaveTracker(): SaveTracker {
  return inject(KEY, null) ?? createSaveTracker()
}
