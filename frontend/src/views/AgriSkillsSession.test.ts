import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Component } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { installSessionExpiredHandler } from '@/api/session-expiry'
import { useAuthStore } from '@/stores/auth'

import AgriCalendarView from './AgriCalendarView.vue'
import AgriCoursesView from './AgriCoursesView.vue'
import AgriDiagnosisView from './AgriDiagnosisView.vue'
import AgriQaView from './AgriQaView.vue'

const cases: Array<{
  name: string
  path: string
  component: Component
}> = [
  {
    name: 'calendar',
    path: '/student/agri-skills/calendar',
    component: AgriCalendarView
  },
  {
    name: 'Q&A',
    path: '/student/agri-skills/qa',
    component: AgriQaView
  },
  {
    name: 'diagnosis',
    path: '/student/agri-skills/diagnosis',
    component: AgriDiagnosisView
  },
  {
    name: 'courses',
    path: '/student/agri-skills/courses',
    component: AgriCoursesView
  }
]

describe.each(cases)('$name session expiry', ({ path, component }) => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('redirects a 401 initial load to login with the current route', async () => {
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
        { path: '/student', component: { template: '<div />' } },
        { path, component }
      ]
    })
    await router.push(path)
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
          redirect: `/login?redirect=${encodeURIComponent(path)}`
        })
      })
    )

    const stopHandler = installSessionExpiredHandler(auth, router)
    try {
      mount(component, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()
    } finally {
      stopHandler()
    }

    expect(auth.sessionState).toBe('anonymous')
    expect(auth.user).toBeNull()
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe(path)
  })
})
