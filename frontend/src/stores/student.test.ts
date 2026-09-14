import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'
import type { CourseSummary, StudentProfile } from '@/api/types'

import { useStudentStore } from './student'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const profileFixture: StudentProfile = {
  name: '林晓',
  contact: '13800000000',
  learning_direction: 'agriculture',
  tag_ids: [1]
}

const recommendedAfterUpdate: CourseSummary[] = [
  {
    id: 9,
    title: '电商直播实操',
    direction: 'ecommerce',
    summary: '从选品到开播的完整演练。',
    teacher_name: '陈老师',
    published_at: '2026-09-12T08:00:00+00:00',
    interest_match: true
  }
]

describe('useStudentStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('updates profile then refreshes recommendations from new preference values', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, profile: profileFixture } as never)
      .mockResolvedValueOnce({
        success: true,
        profile: { ...profileFixture, learning_direction: 'ecommerce' }
      } as never)
      .mockResolvedValueOnce({
        success: true,
        courses: recommendedAfterUpdate
      } as never)

    const store = useStudentStore()
    await store.loadProfile()
    await store.saveProfile({
      ...profileFixture,
      learning_direction: 'ecommerce'
    })
    await store.loadCourses('ecommerce')

    expect(store.courses[0].interest_match).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(1, '/api/student/profile')
    expect(mockedApiFetch).toHaveBeenNthCalledWith(2, '/api/student/profile', {
      method: 'PUT',
      body: JSON.stringify({
        ...profileFixture,
        learning_direction: 'ecommerce'
      })
    })
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/student/courses?direction=ecommerce'
    )
  })

  it('keeps backend field errors when a profile save is rejected', async () => {
    const { ApiError } = await vi.importActual<typeof import('@/api/client')>(
      '@/api/client'
    )
    mockedApiFetch.mockRejectedValue(
      new ApiError('资料校验失败', 400, { name: '姓名不能为空' })
    )
    const store = useStudentStore()

    await expect(
      store.saveProfile({ ...profileFixture, name: '' })
    ).resolves.toBeNull()

    expect(store.error).toBe('资料校验失败')
    expect(store.fieldErrors).toEqual({ name: '姓名不能为空' })
  })
})
