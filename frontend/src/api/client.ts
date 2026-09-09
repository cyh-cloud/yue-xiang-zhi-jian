export class ApiError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface RequestOptions extends Omit<RequestInit, 'headers'> {
  sessionId?: string
  headers?: Record<string, string>
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
  const headers: Record<string, string> = {
    ...options.headers
  }

  if (options.sessionId) {
    headers['X-Session-Id'] = options.sessionId
  }

  if (options.body) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(`${baseUrl}${path}`, {
    ...options,
    headers,
    credentials: 'same-origin'
  })

  const contentType = response.headers.get('content-type') ?? ''
  const payload = contentType.includes('application/json')
    ? await response.json()
    : await response.text()

  if (!response.ok || typeof payload !== 'object' || payload === null || payload.success !== true) {
    const message =
      typeof payload === 'object' && payload !== null && 'message' in payload
        ? String(payload.message)
        : `接口请求失败：${response.status}`
    throw new ApiError(message, response.status)
  }

  return payload as T
}
