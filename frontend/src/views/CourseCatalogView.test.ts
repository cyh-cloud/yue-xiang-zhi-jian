import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'

import CourseCatalogView from './CourseCatalogView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/',
        component: { template: '<div />' }
      },
      {
        path: '/login',
        component: { template: '<div />' }
      },
      {
        path: '/register',
        component: { template: '<div />' }
      },
      {
        path: '/student',
        component: { template: '<div />' }
      },
      {
        path: '/student/courses',
        component: { template: '<div />' }
      }
    ]
  })

  return mount(CourseCatalogView, {
    global: { plugins: [createPinia(), router] }
  })
}

describe('CourseCatalogView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('loads agriculture by default and refetches when the direction changes', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        courses: [
          {
            id: 1,
            title: '荔枝保果技术',
            direction: 'agriculture',
            summary: '掌握花期与果期管理。',
            teacher_name: '李老师',
            published_at: '2026-09-12T08:00:00+00:00',
            interest_match: true
          }
        ]
      } as never)
      .mockResolvedValueOnce({ success: true, courses: [] } as never)

    const wrapper = mountView()
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/student/courses?direction=agriculture'
    )
    expect(wrapper.text()).toContain('荔枝保果技术')
    expect(wrapper.text()).toContain('推荐')

    await wrapper.get('[data-test="direction-handcraft"]').trigger('click')
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/student/courses?direction=handcraft'
    )
  })

  it('renders the exact empty state', async () => {
    mockedApiFetch.mockResolvedValue({ success: true, courses: [] } as never)
    const wrapper = mountView()
    await wrapper.get('[data-test="direction-handcraft"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('暂无课程')
  })
})
