import { describe, expect, it } from 'vitest'
import type { RouteLocationNormalized } from 'vue-router'

import { portalDefinitions } from '@/data/portal-guides'

import router from './index'
import { authGuard, type AuthRouteStore } from './roleRoutes'

const governmentRoutes = [
  {
    path: '/government/policies',
    name: 'government-policies'
  },
  {
    path: '/government/news',
    name: 'government-news'
  },
  {
    path: '/government/dashboard',
    name: 'government-dashboard'
  }
] as const

function routeLocation(path: string): RouteLocationNormalized {
  const target = router.resolve(path)
  return {
    fullPath: path,
    path,
    meta: target.meta
  } as RouteLocationNormalized
}

function authStore(user: AuthRouteStore['user']): AuthRouteStore {
  return {
    sessionState: 'active',
    user,
    nextStep: null,
    isAuthenticated: true,
    isPendingRegistration: false,
    restoreSession: async () => undefined
  }
}

describe('government routes', () => {
  it('protects every government route with the government role', () => {
    const routes = router.getRoutes()

    for (const expected of governmentRoutes) {
      const route = routes.find(item => item.path === expected.path)
      expect(route).toMatchObject({
        path: expected.path,
        name: expected.name,
        meta: {
          requiresAuth: true,
          roles: ['government']
        }
      })
      expect(route?.components?.default).toBeTruthy()
    }
  })

  it('redirects non-government users through the existing role guard', async () => {
    const result = await authGuard(
      routeLocation('/government/dashboard'),
      authStore({
        id: 1,
        username: 'student01',
        name: '学员甲',
        role: 'student'
      })
    )

    expect(result).toBe('/student')
  })

  it('links the government portal and onboarding entries to exact paths', () => {
    const expectedEntries = [
      {
        id: 'government-policy-publish',
        href: '/government/policies'
      },
      {
        id: 'government-news-publish',
        href: '/government/news'
      },
      {
        id: 'government-dashboard',
        href: '/government/dashboard'
      }
    ] as const

    for (const expected of expectedEntries) {
      expect(portalDefinitions.government.entries).toContainEqual(
        expect.objectContaining(expected)
      )
    }

    const selectors = portalDefinitions.government.steps.map(
      step => step.selector
    )
    expect(selectors).toEqual([
      '#government-policy-publish',
      '#government-news-publish',
      '#government-dashboard'
    ])
  })
})
