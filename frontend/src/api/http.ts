const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

export class HttpError extends Error {}

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
    throw new HttpError('系统异常')
  }
  if (!response.ok) throw new HttpError('系统异常')
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const get = <T>(path: string) => request<T>(path)
