import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'

import PortalShell from './PortalShell.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

describe('PortalShell', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('links implemented student entries and keeps future entries inert', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      required: false,
      portal: 'student'
    } as never)

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/login', component: { template: '<div />' } },
        { path: '/register', component: { template: '<div />' } },
        { path: '/student', component: { template: '<div />' } },
        { path: '/student/courses', component: { template: '<div />' } },
        { path: '/student/profile', component: { template: '<div />' } }
      ]
    })

    const wrapper = mount(PortalShell, {
      props: { portal: 'student' },
      global: { plugins: [router] }
    })
    await flushPromises()

    expect(wrapper.get('#student-courses a').attributes('href')).toBe(
      '/student/courses'
    )
    expect(wrapper.get('#student-profile a').attributes('href')).toBe(
      '/student/profile'
    )
    expect(wrapper.find('#student-learning-direction a').exists()).toBe(false)
    expect(wrapper.get('#student-learning-direction').text()).toContain(
      '后续开放'
    )
  })
})
