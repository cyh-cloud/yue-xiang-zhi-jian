import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { RouteLocationNormalized } from 'vue-router'

import { apiFetch } from '@/api/client'
import { portalDefinitions } from '@/data/portal-guides'
import { useAuthStore } from '@/stores/auth'

import router from './index'
import { authGuard } from './roleRoutes'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const handcraftRoutes = [
  {
    path: '/student/handcraft-inheritance',
    visitPath: '/student/handcraft-inheritance',
    name: 'student-handcraft-inheritance'
  },
  {
    path: '/student/handcraft-inheritance/crafts/:craftKey',
    visitPath: '/student/handcraft-inheritance/crafts/guangxiu',
    name: 'student-handcraft-craft'
  },
  {
    path: '/student/handcraft-inheritance/points',
    visitPath: '/student/handcraft-inheritance/points',
    name: 'student-handcraft-points'
  },
  {
    path: '/student/handcraft-inheritance/rewards',
    visitPath: '/student/handcraft-inheritance/rewards',
    name: 'student-handcraft-rewards'
  },
  {
    path: '/student/handcraft-inheritance/courses',
    visitPath: '/student/handcraft-inheritance/courses',
    name: 'student-handcraft-courses'
  }
] as const

function route(
  path: string,
  meta: RouteLocationNormalized['meta'] = {}
): RouteLocationNormalized {
  return {
    fullPath: path,
    path,
    meta
  } as RouteLocationNormalized
}

describe('handcraft inheritance routes', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it.each(handcraftRoutes)(
    'registers $path as $name for students',
    ({ path, name }) => {
      expect(router.resolve(path).matched[0]).toMatchObject({
        path,
        name,
        meta: {
          requiresAuth: true,
          roles: ['student']
        }
      })
    }
  )

  it.each(handcraftRoutes)(
    'redirects an anonymous visit to $visitPath to login',
    async ({ visitPath }) => {
      const auth = useAuthStore()
      auth.sessionState = 'anonymous'
      const target = router.resolve(visitPath)

      await expect(
        authGuard(
          route(visitPath, target.matched[0]?.meta),
          auth
        )
      ).resolves.toBe(`/login?redirect=${encodeURIComponent(visitPath)}`)
    }
  )

  it('redirects a non-student away from a handcraft route', async () => {
    const auth = useAuthStore()
    auth.sessionState = 'active'
    auth.user = {
      id: 4,
      username: 'company02',
      name: '企业乙',
      role: 'enterprise'
    }
    const target = router.resolve('/student/handcraft-inheritance/points')

    await expect(
      authGuard(
        route(
          '/student/handcraft-inheritance/points',
          target.matched[0]?.meta
        ),
        auth
      )
    ).resolves.toBe('/enterprise')
  })

  it('adds handcraft links to the student portal and onboarding guide', () => {
    expect(portalDefinitions.student.entries).toContainEqual({
      id: 'student-handcraft-inheritance',
      title: '手工传承',
      description: '非遗技艺、学习积分、奖品兑换与手工课程。',
      href: '/student/handcraft-inheritance'
    })
    expect(portalDefinitions.student.steps).toContainEqual({
      selector: '#student-handcraft-inheritance',
      title: '手工传承',
      description: '从手工传承入口进入非遗技艺、积分、奖品和课程。'
    })
  })
})
