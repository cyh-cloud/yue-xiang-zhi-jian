import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import { useStudentStore } from '@/stores/student'

import StudentProfileView from './StudentProfileView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

describe('StudentProfileView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('clears the top-level save error when the last field error is corrected', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/student/profile') {
        return {
          success: true,
          profile: {
            name: '林晓',
            contact: '13800000000',
            learning_direction: 'agriculture',
            tag_ids: []
          }
        } as never
      }

      return {
        success: true,
        tags: [
          { id: 1, group_key: 'crop', name: '荔枝' }
        ]
      } as never
    })

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/login', component: { template: '<div />' } },
        { path: '/register', component: { template: '<div />' } },
        { path: '/student', component: { template: '<div />' } },
        { path: '/student/profile', component: StudentProfileView }
      ]
    })
    await router.push('/student/profile')
    await router.isReady()

    const wrapper = mount(StudentProfileView, {
      global: { plugins: [router] }
    })
    await flushPromises()

    const student = useStudentStore()
    student.error = '资料校验失败'
    student.fieldErrors = {
      name: '姓名不能为空',
      contact: '联系方式格式不正确'
    }
    await wrapper.get('#profile-name').setValue('林晓')
    expect(student.error).toBe('资料校验失败')

    await wrapper.get('#profile-contact').setValue('13800000000')
    expect(student.error).toBe('')
    expect(student.fieldErrors).toEqual({})
  })
})
