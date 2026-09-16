import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { installSessionExpiredHandler } from '@/api/session-expiry'
import { useAgriCoursesStore } from '@/stores/agriCourses'
import { useAuthStore } from '@/stores/auth'

describe('AgriCoursesView session expiry', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('redirects a 401 progress request to the current course route', async () => {
    const auth = useAuthStore()
    auth.sessionState = 'active'
    auth.user = {
      id: 1,
      username: 'student01',
      name: '林晓',
      role: 'student'
    }
    auth.defaultPath = '/student'

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/login', component: { template: '<div />' } },
        {
          path: '/student/agri-skills/courses',
          component: { template: '<div />' }
        }
      ]
    })
    await router.push('/student/agri-skills/courses')
    await router.isReady()

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        headers: new Headers({ 'Content-Type': 'application/json' }),
        json: async () => ({
          success: false,
          message: '未登录或会话已过期',
          redirect: '/login?redirect=%2Fapi%2Fagri-skills%2Fcourses'
        })
      })
    )

    const stopHandler = installSessionExpiredHandler(auth, router)
    try {
      await useAgriCoursesStore().saveProgress(1, 10, 10)
    } finally {
      stopHandler()
    }

    expect(auth.sessionState).toBe('anonymous')
    expect(auth.user).toBeNull()
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe(
      '/student/agri-skills/courses'
    )
  })
})
