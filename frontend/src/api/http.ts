const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

export const SYSTEM_ERROR_MESSAGE = '系统异常'

export class HttpError extends Error {
  constructor() {
    super(SYSTEM_ERROR_MESSAGE)
    this.name = 'HttpError'
  }
}

export async function request<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${baseUrl}${path}`, {
      method: options.method || 'GET',
      headers: {
        Accept: 'application/json',
        ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
      signal: AbortSignal.timeout(8000),
    })
  } catch {
    throw new HttpError()
  }
  if (!response.ok) throw new HttpError()
  if (response.status === 204) return undefined as T
  try {
    return await response.json() as T
  } catch {
    throw new HttpError()
  }
}

export const get = <T>(path: string) => request<T>(path)
