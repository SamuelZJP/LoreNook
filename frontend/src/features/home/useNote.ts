import { onScopeDispose, ref } from 'vue'

/** A short line that shows for a moment, such as "registration is not open". */
export function useNote() {
  const note = ref('')
  let timer: ReturnType<typeof setTimeout> | undefined
  function show(text: string) {
    clearTimeout(timer)
    note.value = text
    timer = setTimeout(() => (note.value = ''), 2600)
  }
  onScopeDispose(() => clearTimeout(timer))
  return { note, show }
}

export const REGISTRATION_CLOSED = '注册暂未开放，敬请期待'
