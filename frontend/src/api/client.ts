import type { components } from './schema'

export type Schemas = components['schemas']
export type ArchiveProgress = Schemas['ArchiveProgress']

/** Normalized backend error. `detail` keeps its original shape for diagnostics. */
export class ApiError extends Error {
  status: number
  detail: unknown
  archive: ArchiveProgress | null
  /** True when the request never got an HTTP answer (network failure, abort, lost response). */
  transport: boolean

  constructor(status: number, detail: unknown, archive: ArchiveProgress | null = null, transport = false) {
    super(describeDetail(status, detail, transport))
    this.status = status
    this.detail = detail
    this.archive = archive
    this.transport = transport
  }
}

export interface ValidationItem {
  loc?: (string | number)[]
  msg?: string
  type?: string
}

export interface TemplateErrorDetail {
  definition_id: string
  message: string
  line: number | null
}

export function isTemplateError(detail: unknown): detail is TemplateErrorDetail {
  return typeof detail === 'object' && detail !== null && 'definition_id' in detail
}

/** Turn any `detail` form (string, validation array, structured object) into readable text. */
export function describeDetail(status: number, detail: unknown, transport = false): string {
  if (transport) return '网络请求未获得响应，服务器可能仍在处理'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return (detail as ValidationItem[])
      .map((item) => {
        const loc = (item.loc ?? []).filter((p) => p !== 'body').join('.')
        return loc ? `${loc}: ${item.msg ?? ''}` : item.msg ?? JSON.stringify(item)
      })
      .join('\n')
  }
  if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>
    if (isTemplateError(d)) return `定义 ${d.definition_id}${d.line ? ` 第 ${d.line} 行` : ''}: ${d.message}`
    if ('stage' in d) return `预设 ${String(d.stage)} 阶段：${String(d.message)}`
    if ('kind' in d) {
      const upstream = d.upstream_status ? `（上游 HTTP ${d.upstream_status}）` : ''
      return `模型调用失败 [${String(d.kind)}]：${String(d.message)}${upstream}`
    }
    return JSON.stringify(d)
  }
  return `请求失败（HTTP ${status}）`
}

let onUnauthorized: (() => void) | null = null

/** Called when a request answers 401 because the session ended; sign-in requests excepted. */
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

function checkSession(path: string, status: number) {
  if (status === 401 && !path.startsWith('/api/auth/')) onUnauthorized?.()
}

export interface RequestOptions {
  method?: string
  body?: unknown
  query?: Record<string, string | number | boolean | undefined>
  signal?: AbortSignal
  /** Sent as the request body as-is, instead of `body` as JSON. */
  file?: Blob
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let url = path
  if (options.query) {
    const params = new URLSearchParams()
    for (const [k, v] of Object.entries(options.query)) if (v !== undefined) params.set(k, String(v))
    const qs = params.toString()
    if (qs) url += `?${qs}`
  }
  let response: Response
  try {
    response = await fetch(url, {
      method: options.method ?? 'GET',
      headers: options.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: options.file ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined),
      signal: options.signal,
    })
  } catch (error) {
    throw new ApiError(0, String(error), null, true)
  }
  if (response.status === 204) return undefined as T
  const text = await response.text()
  let data: unknown = undefined
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }
  if (!response.ok) {
    checkSession(path, response.status)
    const body = (data ?? {}) as { detail?: unknown; archive?: ArchiveProgress }
    // Without a JSON `detail` the answer came from a proxy or a crash, not a handled backend error:
    // the outcome of the request is unknown.
    const transport = typeof data !== 'object' || data === null || !('detail' in data)
    throw new ApiError(response.status, body.detail ?? data, body.archive ?? null, transport)
  }
  return data as T
}

/** The filename a download response names, preferring the UTF-8 form. */
function filenameOf(response: Response, fallback: string): string {
  const header = response.headers.get('content-disposition') ?? ''
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header)
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1])
    } catch {
      // Fall through to the plain name.
    }
  }
  return /filename="([^"]+)"/i.exec(header)?.[1] ?? fallback
}

/** Fetch a file and hand it to the browser as a download. Errors are thrown like `request`'s. */
export async function download(path: string, fallback: string): Promise<void> {
  let response: Response
  try {
    response = await fetch(path)
  } catch (error) {
    throw new ApiError(0, String(error), null, true)
  }
  if (!response.ok) {
    checkSession(path, response.status)
    const text = await response.text()
    let detail: unknown = text
    try {
      detail = (JSON.parse(text) as { detail?: unknown }).detail ?? text
    } catch {
      // Not JSON: keep the text.
    }
    throw new ApiError(response.status, detail)
  }
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filenameOf(response, fallback)
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
