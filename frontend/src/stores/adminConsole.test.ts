import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

import { useAdminConsoleStore } from './adminConsole'

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
