import type { ApiFieldErrors } from './types'

export class ApiError extends Error {
  readonly status: number
  readonly errors: ApiFieldErrors
  readonly redirect?: string

  constructor(
    message: string,
    status: number,
    errors: ApiFieldErrors = {},
    redirect?: string
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.errors = errors
    this.redirect = redirect
  }
}

type SessionExpiredHandler = (error: ApiError) => Promise<void> | void

let sessionExpiredHandler: SessionExpiredHandler | null = null

export function setSessionExpiredHandler(
  handler: SessionExpiredHandler | null
): () => void {
  const previousHandler = sessionExpiredHandler
  sessionExpiredHandler = handler
  return () => {
    if (sessionExpiredHandler === handler) {
      sessionExpiredHandler = previousHandler
    }
  }
}

interface RequestOptions extends Omit<RequestInit, 'headers'> {
  headers?: HeadersInit
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${baseUrl}${path}`, {
    ...options,
    headers,
    credentials: 'include'
  })

  const contentType = response.headers.get('content-type') ?? ''
  const payload = contentType.includes('application/json')
    ? await response.json()
    : await response.text()

  if (
    !response.ok ||
    typeof payload !== 'object' ||
    payload === null ||
    payload.success !== true
  ) {
    const payloadRecord =
      typeof payload === 'object' && payload !== null
        ? (payload as Record<string, unknown>)
        : null
    const message =
      typeof payloadRecord?.message === 'string'
        ? payloadRecord.message
        : `接口请求失败：${response.status}`
    const errors =
      typeof payloadRecord?.errors === 'object' &&
      payloadRecord.errors !== null &&
      !Array.isArray(payloadRecord.errors)
        ? Object.fromEntries(
            Object.entries(payloadRecord.errors as Record<string, unknown>).map(
              ([field, value]) => [field, String(value)]
            )
          )
        : {}
    const redirect =
      typeof payloadRecord?.redirect === 'string' ? payloadRecord.redirect : undefined

    const error = new ApiError(message, response.status, errors, redirect)
    if (response.status === 401 && error.redirect && sessionExpiredHandler) {
      await sessionExpiredHandler(error)
    }

    throw error
  }

  return payload as T
}
