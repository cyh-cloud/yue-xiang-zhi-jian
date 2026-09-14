import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'

import LoginView from './LoginView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

describe('LoginView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('returns the student to a retained course route after login', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      user: {
        id: 1,
        username: 'student01',
        name: '林晓',
        role: 'student'
      },
      default_path: '/student'
    } as never)

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/login', component: LoginView },
        { path: '/register', component: { template: '<div />' } },
        { path: '/student', component: { template: '<div />' } },
        { path: '/student/courses', component: { template: '<div />' } }
      ]
    })
    await router.push('/login?redirect=/student/courses')
    await router.isReady()

    const wrapper = mount(LoginView, {
      global: { plugins: [router] }
    })
    await wrapper.get('#login-username').setValue('student01')
    await wrapper.get('#login-password').setValue('password8')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenCalledWith('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        username: 'student01',
        password: 'password8'
      })
    })
    expect(router.currentRoute.value.path).toBe('/student/courses')
  })
})
