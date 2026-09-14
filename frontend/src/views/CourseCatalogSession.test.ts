import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { installSessionExpiredHandler } from '@/api/session-expiry'
import { useAuthStore } from '@/stores/auth'

import CourseCatalogView from './CourseCatalogView.vue'

describe('CourseCatalogView session expiry', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('redirects an expired course request to login with the current route', async () => {
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
        { path: '/register', component: { template: '<div />' } },
        { path: '/student', component: { template: '<div />' } },
        { path: '/student/courses', component: CourseCatalogView }
      ]
    })
    await router.push('/student/courses')
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
          redirect: '/login?redirect=%2Fapi%2Fstudent%2Fcourses'
        })
      })
    )

    const stopHandler = installSessionExpiredHandler(auth, router)
    try {
      mount(CourseCatalogView, {
        global: { plugins: [router] }
      })
      await flushPromises()
    } finally {
      stopHandler()
    }

    expect(auth.sessionState).toBe('anonymous')
    expect(auth.user).toBeNull()
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe('/student/courses')
  })
})
