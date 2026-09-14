import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { RouteLocationNormalized } from 'vue-router'

import { apiFetch } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

import { authGuard, roleDefaultPath } from './roleRoutes'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function route(
  fullPath: string,
  meta: RouteLocationNormalized['meta'] = {}
): RouteLocationNormalized {
  return {
    fullPath,
    path: fullPath.split(/[?#]/, 1)[0],
    meta
  } as RouteLocationNormalized
}

describe('roleDefaultPath', () => {
  it.each([
    ['student', '/student'],
    ['teacher', '/teacher'],
    ['enterprise', '/enterprise'],
    ['government', '/government'],
    ['super_admin', '/admin'],
    ['admin', '/admin']
  ] as const)('maps %s to %s', (role, expected) => {
    expect(roleDefaultPath(role)).toBe(expected)
  })
})

describe('authGuard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('restores an unknown session once before evaluating protected routes', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      state: 'active',
      user: {
        id: 1,
        username: 'student01',
        name: '林晓',
        role: 'student'
      },
      default_path: '/student'
    } as never)
    const auth = useAuthStore()

    await expect(
      authGuard(
        route('/student/profile', { requiresAuth: true, roles: ['student'] }),
        auth
      )
    ).resolves.toBe(true)
    await expect(
      authGuard(
        route('/student/courses', { requiresAuth: true, roles: ['student'] }),
        auth
      )
    ).resolves.toBe(true)

    expect(mockedApiFetch).toHaveBeenCalledTimes(1)
  })

  it('redirects unauthenticated protected routes with the original target', async () => {
    const auth = useAuthStore()
    auth.sessionState = 'anonymous'

    await expect(
      authGuard(
        route('/teacher?tab=courses', { requiresAuth: true, roles: ['teacher'] }),
        auth
      )
    ).resolves.toBe('/login?redirect=%2Fteacher%3Ftab%3Dcourses')
  })

  it('redirects authenticated users away from login and registration', async () => {
    const auth = useAuthStore()
    auth.sessionState = 'active'
    auth.user = {
      id: 2,
      username: 'teacher01',
      name: '陈老师',
      role: 'teacher'
    }

    await expect(authGuard(route('/login'), auth)).resolves.toBe('/teacher')
    await expect(authGuard(route('/register'), auth)).resolves.toBe('/teacher')
  })

  it('redirects authenticated users away from auth routes with trailing slashes', async () => {
    const auth = useAuthStore()
    auth.sessionState = 'active'
    auth.user = {
      id: 2,
      username: 'teacher01',
      name: '陈老师',
      role: 'teacher'
    }

    await expect(authGuard(route('/login/'), auth)).resolves.toBe('/teacher')
    await expect(authGuard(route('/register/'), auth)).resolves.toBe('/teacher')
    await expect(
      authGuard(route('/register/interest-tags/'), auth)
    ).resolves.toBe('/teacher')
  })

  it('redirects users away from routes for another role', async () => {
    const auth = useAuthStore()
    auth.sessionState = 'active'
    auth.user = {
      id: 3,
      username: 'company01',
      name: '企业甲',
      role: 'enterprise'
    }

    await expect(
      authGuard(
        route('/government', { requiresAuth: true, roles: ['government'] }),
        auth
      )
    ).resolves.toBe('/enterprise')
  })

  it('allows the interest-tag route only for a pending registration', async () => {
    const auth = useAuthStore()
    auth.sessionState = 'pending'
    auth.nextStep = 'interest-tags'

    await expect(
      authGuard(route('/register/interest-tags'), auth)
    ).resolves.toBe(true)

    auth.sessionState = 'anonymous'
    auth.nextStep = null
    await expect(
      authGuard(route('/register/interest-tags'), auth)
    ).resolves.toBe('/login?redirect=%2Fregister%2Finterest-tags')
  })

  it('does not expose the interest-tag route with a trailing slash', async () => {
    const auth = useAuthStore()
    auth.sessionState = 'anonymous'

    await expect(
      authGuard(route('/register/interest-tags/'), auth)
    ).resolves.toBe('/login?redirect=%2Fregister%2Finterest-tags%2F')
  })
})
