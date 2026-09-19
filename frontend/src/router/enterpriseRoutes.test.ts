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

const enterpriseRoutes = [
  {
    path: '/enterprise',
    visitPath: '/enterprise',
    name: 'enterprise-portal'
  },
  {
    path: '/enterprise/jobs',
    visitPath: '/enterprise/jobs',
    name: 'enterprise-jobs'
  },
  {
    path: '/enterprise/applications',
    visitPath: '/enterprise/applications',
    name: 'enterprise-applications'
  },
  {
    path: '/enterprise/applications/:applicationId',
    visitPath: '/enterprise/applications/application-demo-pending',
    name: 'enterprise-application-detail'
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

describe('enterprise console routes', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(apiFetch).mockReset()
  })

  it.each(enterpriseRoutes)(
    'registers $path as $name for enterprise users',
    ({ path, name }) => {
      expect(router.resolve(path).matched[0]).toMatchObject({
        path,
        name,
        meta: {
          requiresAuth: true,
          roles: ['enterprise']
        }
      })
    }
  )

  it.each(enterpriseRoutes)(
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

  it('redirects a non-enterprise user to their own portal', async () => {
    const auth = useAuthStore()
    auth.sessionState = 'active'
    auth.user = {
      id: 11,
      username: 'student-demo',
      name: '本地学员',
      role: 'student'
    }
    const target = router.resolve(
      '/enterprise/applications/application-demo-pending'
    )

    await expect(
      authGuard(
        route(
          '/enterprise/applications/application-demo-pending',
          target.matched[0]?.meta
        ),
        auth
      )
    ).resolves.toBe('/student')
  })

  it('links every enterprise portal entry to the registered route', () => {
    expect(portalDefinitions.enterprise.entries).toContainEqual({
      id: 'enterprise-job-publish',
      title: '职位发布',
      description: '发布岗位需求并维护招聘信息。',
      href: '/enterprise/jobs'
    })
    expect(portalDefinitions.enterprise.entries).toContainEqual({
      id: 'enterprise-applications',
      title: '申请处理',
      description: '查看并处理学员投递的职位申请。',
      href: '/enterprise/applications'
    })
    expect(portalDefinitions.enterprise.entries).toContainEqual({
      id: 'enterprise-dashboard',
      title: '企业看板',
      description: '查看岗位与申请数据的经营概览。',
      href: '/enterprise'
    })
  })
})
