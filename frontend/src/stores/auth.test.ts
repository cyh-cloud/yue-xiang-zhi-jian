import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'

import { useAuthStore } from './auth'

vi.mock('@/api/client', () => ({
  apiFetch: vi.fn()
}))

const mockedApiFetch = vi.mocked(apiFetch)

const student = {
  id: 1,
  username: 'student01',
  name: '林晓',
  role: 'student' as const
}

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('restores an active cookie session from the server', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      state: 'active',
      user: student,
      default_path: '/student'
    } as never)
    const auth = useAuthStore()

    await auth.restoreSession()

    expect(mockedApiFetch).toHaveBeenCalledWith('/api/auth/session')
    expect(auth.sessionState).toBe('active')
    expect(auth.user).toEqual(student)
    expect(auth.defaultPath).toBe('/student')
    expect(auth.isAuthenticated).toBe(true)
  })

  it('restores a pending student without exposing an active user', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      state: 'pending',
      user: student,
      next_step: 'interest-tags',
      default_path: '/register/interest-tags'
    } as never)
    const auth = useAuthStore()

    await auth.restoreSession()

    expect(auth.sessionState).toBe('pending')
    expect(auth.user).toBeNull()
    expect(auth.nextStep).toBe('interest-tags')
    expect(auth.defaultPath).toBe('/register/interest-tags')
    expect(auth.isAuthenticated).toBe(false)
  })

  it('stores the authenticated user and default path after login', async () => {
    const response = {
      success: true as const,
      user: student,
      default_path: '/student'
    }
    mockedApiFetch.mockResolvedValue(response as never)
    const auth = useAuthStore()

    await expect(auth.login('student01', 'password8')).resolves.toEqual(response)

    expect(mockedApiFetch).toHaveBeenCalledWith('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        username: 'student01',
        password: 'password8'
      })
    })
    expect(auth.sessionState).toBe('active')
    expect(auth.user).toEqual(student)
    expect(auth.defaultPath).toBe('/student')
  })

  it('keeps a newly registered student pending until interest tags complete', async () => {
    const response = {
      success: true as const,
      next_step: 'interest-tags' as const,
      user: student,
      default_path: '/register/interest-tags'
    }
    mockedApiFetch.mockResolvedValue(response as never)
    const auth = useAuthStore()

    await expect(
      auth.register({
        username: 'student01',
        password: 'password8',
        confirm_password: 'password8',
        name: '林晓',
        role: 'student'
      })
    ).resolves.toEqual(response)

    expect(auth.sessionState).toBe('pending')
    expect(auth.user).toBeNull()
    expect(auth.nextStep).toBe('interest-tags')
    expect(auth.isAuthenticated).toBe(false)
  })

  it('activates the student after interest tags are completed', async () => {
    const auth = useAuthStore()
    auth.sessionState = 'pending'
    auth.nextStep = 'interest-tags'
    mockedApiFetch.mockResolvedValue({
      success: true,
      user: student,
      default_path: '/student'
    } as never)

    await auth.completeInterestTags([3, 7])

    expect(mockedApiFetch).toHaveBeenCalledWith('/api/auth/interest-tags', {
      method: 'POST',
      body: JSON.stringify({ tag_ids: [3, 7] })
    })
    expect(auth.sessionState).toBe('active')
    expect(auth.user).toEqual(student)
    expect(auth.nextStep).toBeNull()
    expect(auth.defaultPath).toBe('/student')
  })

  it('clears the in-memory session after logout', async () => {
    const auth = useAuthStore()
    auth.sessionState = 'active'
    auth.user = student
    auth.defaultPath = '/student'
    mockedApiFetch.mockResolvedValue({ success: true } as never)

    await auth.logout()

    expect(mockedApiFetch).toHaveBeenCalledWith('/api/auth/logout', {
      method: 'POST'
    })
    expect(auth.sessionState).toBe('anonymous')
    expect(auth.user).toBeNull()
    expect(auth.defaultPath).toBe('')
    expect(auth.isAuthenticated).toBe(false)
  })
})
