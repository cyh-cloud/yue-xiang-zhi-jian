import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type { EcommerceCourse } from '@/api/types'

import { useAgriCoursesStore } from './agriCourses'
import { useCourseLearningStore } from './courseLearning'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function course(
  id: number,
  direction: EcommerceCourse['direction']
): EcommerceCourse {
  return {
    id,
    title: direction === 'ecommerce' ? '电商课程' : '农业课程',
    direction,
    status: 'published',
    interest_match: true,
    summary: '课程摘要',
    teacher_name: '教师',
    published_at: '2026-09-17T00:00:00+00:00',
    tag_ids: [],
    duration_seconds: 300
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('courseLearning store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('switches course endpoints and direction without creating another store', async () => {
    const store = useCourseLearningStore()
    store.configure('/api/ecommerce-training', 'ecommerce')
    mockedApiFetch.mockResolvedValueOnce({ success: true, courses: [] })
    await store.loadCourses()
    expect(apiFetch).toHaveBeenCalledWith('/api/ecommerce-training/courses')
    expect(store.direction).toBe('ecommerce')
    expect(store.apiPrefix).toBe('/api/ecommerce-training')
  })

  it('keeps agriculture defaults for the legacy store', async () => {
    const store = useAgriCoursesStore()
    mockedApiFetch.mockResolvedValueOnce({ success: true, courses: [] })
    await store.loadCourses()
    expect(apiFetch).toHaveBeenCalledWith('/api/agri-skills/courses')
  })

  it('ignores a stale recommendation response after switching direction', async () => {
    const store = useCourseLearningStore()
    const agricultureRequest = deferred<{
      success: true
      courses: EcommerceCourse[]
    }>()
    mockedApiFetch.mockReturnValueOnce(agricultureRequest.promise)
    const agricultureLoad = store.loadRecommendations()

    store.configure('/api/ecommerce-training', 'ecommerce')
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      courses: [course(2, 'ecommerce')]
    })
    expect(await store.loadRecommendations()).toBe(true)
    expect(store.recommendations.map(item => item.id)).toEqual([2])

    agricultureRequest.resolve({
      success: true,
      courses: [course(1, 'agriculture')]
    })
    expect(await agricultureLoad).toBe(false)

    expect(store.recommendations.map(item => item.id)).toEqual([2])
    expect(store.recommendationError).toBe('')
  })

  it('ignores a stale rejection without clearing current loading', async () => {
    const store = useCourseLearningStore()
    const agricultureRequest = deferred<{
      success: true
      courses: EcommerceCourse[]
    }>()
    mockedApiFetch.mockReturnValueOnce(agricultureRequest.promise)
    const agricultureLoad = store.loadRecommendations()

    store.configure('/api/ecommerce-training', 'ecommerce')
    const ecommerceRequest = deferred<{
      success: true
      courses: EcommerceCourse[]
    }>()
    mockedApiFetch.mockReturnValueOnce(ecommerceRequest.promise)
    const ecommerceLoad = store.loadRecommendations()

    agricultureRequest.reject(new ApiError('旧请求失败', 500))
    expect(await agricultureLoad).toBe(false)

    expect(store.recommendationError).toBe('')
    expect(store.loading).toBe(true)

    ecommerceRequest.resolve({
      success: true,
      courses: [course(2, 'ecommerce')]
    })
    expect(await ecommerceLoad).toBe(true)
    expect(store.recommendations.map(item => item.id)).toEqual([2])
    expect(store.loading).toBe(false)
  })
})
