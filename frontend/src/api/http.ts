const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

export const SYSTEM_ERROR_MESSAGE = '系统异常'

export class HttpError extends Error {
  constructor() {
    super(SYSTEM_ERROR_MESSAGE)
    this.name = 'HttpError'
  }
}

interface RequestOptions { method?: string; body?: unknown; timeoutMs?: number; signal?: AbortSignal }

function requestSignal(options: RequestOptions): AbortSignal {
  const timeout = AbortSignal.timeout(options.timeoutMs ?? 8000)
  return options.signal ? AbortSignal.any([timeout, options.signal]) : timeout
}

async function sendRequest(path: string, options: RequestOptions, accept: string): Promise<Response> {
  let response: Response
  try {
    response = await fetch(`${baseUrl}${path}`, {
      method: options.method || 'GET',
      headers: {
        Accept: accept,
        ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
      signal: requestSignal(options),
    })
  } catch {
    throw new HttpError()
  }
  if (!response.ok) throw new HttpError()
  return response
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await sendRequest(path, options, 'application/json')
  if (response.status === 204) return undefined as T
  try {
    return await response.json() as T
  } catch {
    throw new HttpError()
  }
}

export const get = <T>(path: string) => request<T>(path)

export async function getBlob(path: string, mediaType: string): Promise<Blob> {
  const response = await sendRequest(path, {}, mediaType)
  if (response.headers.get('content-type')?.split(';')[0]?.trim().toLowerCase() !== mediaType) throw new HttpError()
  try {
    return await response.blob()
  } catch {
    throw new HttpError()
  }
}

export async function streamRequest<T>(path: string, options: RequestOptions & { onToken: (text: string) => void; validateResult: (value: unknown) => value is T }): Promise<T> {
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      method: options.method ?? 'POST',
      headers: { Accept: 'text/event-stream', 'Content-Type': 'application/json' },
      body: JSON.stringify(options.body),
      signal: requestSignal(options),
    })
    if (!response.ok || !response.body || !response.headers.get('content-type')?.toLowerCase().includes('text/event-stream')) throw new HttpError()
    reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8', { fatal: true })
    let buffer = ''
    let event = ''
    let data: string[] = []
    let result: T | undefined
    let completed = false
    const dispatch = () => {
      if (!event && !data.length) return
      if (!['token', 'done', 'error'].includes(event) || !data.length) throw new HttpError()
      let payload: unknown
      try { payload = JSON.parse(data.join('\n')) } catch { throw new HttpError() }
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new HttpError()
      const value = payload as Record<string, unknown>
      if (event === 'token') {
        if (typeof value.text !== 'string') throw new HttpError()
        options.onToken(value.text)
      } else if (event === 'done') {
        if (!options.validateResult(value.session)) throw new HttpError()
        result = value.session
        completed = true
      } else {
        throw new HttpError()
      }
      event = ''
      data = []
    }
    // Retain an incomplete line across chunks, including a CR at the chunk boundary.
    while (!completed) {
      const chunk = await reader.read()
      buffer += decoder.decode(chunk.value, { stream: !chunk.done })
      let index = 0
      while (index < buffer.length) {
        const end = buffer.slice(index).search(/[\r\n]/)
        if (end < 0) break
        const position = index + end
        if (buffer[position] === '\r' && position === buffer.length - 1 && !chunk.done) break
        const line = buffer.slice(index, position)
        index = position + (buffer[position] === '\r' && buffer[position + 1] === '\n' ? 2 : 1)
        if (!line) dispatch()
        else if (line.startsWith('event:')) event = line.slice(6).trimStart()
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
        else if (!line.startsWith(':') && !line.startsWith('id:') && !line.startsWith('retry:')) throw new HttpError()
        if (completed) break
      }
      buffer = buffer.slice(index)
      if (chunk.done) break
    }
    if (!completed || result === undefined) throw new HttpError()
    return result
  } catch {
    throw new HttpError()
  } finally {
    if (reader) void reader.cancel().catch(() => undefined)
  }
}
