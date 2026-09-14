import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError, apiFetch } from '@/api/client'

import RegisterView from './RegisterView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/login', component: { template: '<div />' } },
      { path: '/register/interest-tags', component: { template: '<div />' } },
      { path: '/teacher', component: { template: '<div />' } }
    ]
  })
}

describe('RegisterView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    document.body.innerHTML = ''
  })

  it('focuses the first invalid field and shows backend errors', async () => {
    mockedApiFetch.mockRejectedValue(
      new ApiError('注册失败', 400, {
        username: '用户名格式不正确'
      })
    )

    const wrapper = mount(RegisterView, {
      attachTo: document.body,
      global: {
        plugins: [createPinia(), createTestRouter()]
      }
    })

    await wrapper.get('#register-username').setValue('1bad')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('#register-username-error').text()).toContain('用户名格式不正确')
    expect(document.activeElement?.id).toBe('register-username')
  })
})
