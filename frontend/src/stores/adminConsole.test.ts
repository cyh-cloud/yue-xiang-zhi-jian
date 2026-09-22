import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

import { useAdminConsoleStore, widenModerationDay } from './adminConsole'

describe('adminConsole store shell', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('derives platform-management capability from the authenticated role', () => {
    const auth = useAuthStore()
    const store = useAdminConsoleStore()

    auth.user = {
      id: 2,
      username: 'content-admin',
      name: '内容管理员',
      role: 'admin'
    }
    expect(store.canManagePlatform).toBe(false)

    auth.user = {
      id: 1,
      username: 'super-admin',
      name: '超级管理员',
      role: 'super_admin'
    }
    expect(store.canManagePlatform).toBe(true)
  })

  it('captures API errors and clears the shell error state', () => {
    const store = useAdminConsoleStore()

    store.captureError(new ApiError('无权访问账号管理', 403), '加载失败')
    expect(store.error).toBe('无权访问账号管理')

    store.clearError()
    expect(store.error).toBe('')
  })
})

describe('widenModerationDay', () => {
  it('widens bare date values into the platform day boundaries', () => {
    expect(
      widenModerationDay({ created_from: '2026-09-01', created_to: '2026-09-30' })
    ).toEqual({
      created_from: '2026-09-01T00:00:00+08:00',
      created_to: '2026-09-30T23:59:59+08:00'
    })
  })

  it('keeps empty boundaries empty so the filter is dropped from the query', () => {
    expect(
      widenModerationDay({ created_from: '', created_to: '' })
    ).toEqual({ created_from: '', created_to: '' })
  })

  it('is idempotent and never double-appends a timezone to an ISO stamp', () => {
    // 经过 store 默认参数回灌的已是加宽 ISO 串，再次加宽必须原样透传，否则会变成
    // `...T00:00:00+08:00T00:00:00+08:00`。
    const widened = {
      created_from: '2026-09-01T00:00:00+08:00',
      created_to: '2026-09-30T23:59:59+08:00'
    }
    expect(widenModerationDay(widened)).toEqual(widened)
  })
})
