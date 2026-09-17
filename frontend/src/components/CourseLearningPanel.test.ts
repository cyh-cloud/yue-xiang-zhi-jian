import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'

import CourseLearningPanel from './CourseLearningPanel.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() })
}))

const mockedApiFetch = vi.mocked(apiFetch)

describe('CourseLearningPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
    mockedApiFetch.mockResolvedValue({
      success: true,
      courses: []
    } as never)
  })

  it('labels the handcraft course direction without changing other directions', async () => {
    const wrapper = shallowMount(CourseLearningPanel, {
      props: {
        direction: 'handcraft',
        moduleCode: '05',
        title: '手工课程',
        description: '学习手工课程',
        apiPrefix: '/api/handcraft-inheritance'
      },
      global: {
        stubs: {
          AppHeader: true
        }
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('HANDCRAFT COURSES')
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/handcraft-inheritance/courses'
    )
  })
})
