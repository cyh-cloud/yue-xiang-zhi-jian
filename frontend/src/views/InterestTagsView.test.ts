import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'

import InterestTagsView from './InterestTagsView.vue'

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
      { path: '/student', component: { template: '<div />' } }
    ]
  })
}

describe('InterestTagsView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('can skip without selecting any tags and routes to student portal', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/interest-tags') {
        return {
          success: true,
          tags: [
            { id: 1, group_key: 'crop', name: '荔枝' },
            { id: 2, group_key: 'skill', name: '直播运营' },
            { id: 3, group_key: 'job', name: '农产品销售' }
          ]
        } as never
      }

      return {
        success: true,
        user: {
          id: 1,
          username: 'student01',
          name: '林晓',
          role: 'student'
        },
        default_path: '/student'
      } as never
    })

    const router = createTestRouter()
    const push = vi.spyOn(router, 'push')
    const wrapper = mount(InterestTagsView, {
      global: {
        plugins: [createPinia(), router]
      }
    })

    await flushPromises()
    await wrapper.get('[data-test="skip-tags"]').trigger('click')
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenCalledWith('/api/auth/interest-tags', {
      method: 'POST',
      body: JSON.stringify({ tag_ids: [] })
    })
    expect(push).toHaveBeenCalledWith('/student')
  })
})
