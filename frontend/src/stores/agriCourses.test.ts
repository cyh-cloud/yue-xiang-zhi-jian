import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type {
  AgriculturalCourse,
  CourseProgress,
  CourseQuizAttempt
} from '@/api/types'

import {
  useAgriCoursesStore,
  type AgriCourse
} from './agriCourses'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

type CourseRow = AgriculturalCourse & {
  direction?: string | null
  status?: string | null
  publication_status?: string | null
  is_published?: boolean | null
  return_to?: string
}

const courseFixture: CourseRow = {
  id: 1,
  title: '荔枝保果技术',
  summary: '掌握花期与果期管理。',
  teacher_name: '林老师',
  published_at: '2026-09-01T00:00:00+00:00',
  tag_ids: [1],
  duration_seconds: 100,
  direction: 'agriculture',
  return_to: '/student/courses/1?comment=1#comments'
}

const progressFixture: CourseProgress = {
  user_id: 1,
  course_id: 1,
  duration_seconds: 100,
  furthest_position_seconds: 80,
  resume_position_seconds: 80,
  progress_percent: 80,
  watched_seconds: 80,
  completed_at: '2026-09-16T01:00:00+00:00',
  last_viewed_at: '2026-09-16T01:00:00+00:00',
  updated_at: '2026-09-16T01:00:00+00:00',
  quiz_available: true
}

function attemptFixture(
  id: number,
  answer: string,
  isFormal = true
): CourseQuizAttempt {
  return {
    id,
    course_id: 1,
    score: answer === 'A' ? 100 : 0,
    is_formal: isFormal,
    is_current: isFormal,
    is_latest: id === 2,
    questions: [
      {
        id: 'q1',
        type: 'single_choice',
        prompt: '达到多少进度视为完成？',
        options: ['A', 'B'],
        correct: answer === 'A',
        explanation: answer === 'A' ? '达到 80% 即完成。' : '应选择 A。'
      }
    ],
    created_at: `2026-09-16T0${id}:00:00+00:00`
  }
}

describe('agriCourses store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('loads progress only for eligible published agriculture courses', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/courses') {
        return {
          success: true,
          courses: [
            courseFixture,
            { ...courseFixture, id: 2, title: '下架课程', status: 'offline' },
            {
              ...courseFixture,
              id: 3,
              title: '电商课程',
              direction: 'ecommerce'
            }
          ]
        } as never
      }
      if (path === '/api/agri-skills/courses/1/progress') {
        return { success: true, progress: progressFixture } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const store = useAgriCoursesStore()
    await store.loadCourses()

    expect(store.courses.map(course => course.id)).toEqual([1])
    expect(store.progressByCourse[1]).toEqual(progressFixture)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/courses/1/progress'
    )
  })

  it('accepts the authoritative agriculture payload and rejects malformed metadata', async () => {
    const recommendation = {
      id: 9,
      title: '推荐课程',
      summary: '基于学习行为推荐。',
      teacher_name: '陈老师',
      published_at: '2026-09-02T00:00:00+00:00'
    }
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/courses') {
        return {
          success: true,
          courses: [
            courseFixture,
            { ...courseFixture, id: 2, title: '缺少状态', status: undefined },
            { ...courseFixture, id: 3, title: '空状态', status: null },
            {
              ...courseFixture,
              id: 4,
              title: '缺少方向',
              direction: undefined
            },
            { ...courseFixture, id: 5, title: '空方向', direction: null },
            { ...courseFixture, id: 6, title: '下架课程', status: 'offline' },
            {
              ...courseFixture,
              id: 7,
              title: '电商课程',
              direction: 'ecommerce'
            },
            {
              ...courseFixture,
              id: 8,
              title: '空发布状态',
              publication_status: null
            },
            {
              ...courseFixture,
              id: 9,
              title: '空发布布尔值',
              is_published: null
            },
            { ...courseFixture, id: 10, title: '异常发布状态', status: 'unknown' }
          ]
        } as never
      }
      if (path === '/api/agri-skills/recommendations') {
        return {
          success: true,
          courses: [
            recommendation,
            { ...recommendation, id: 10, status: 'offline' },
            { ...recommendation, id: 11, direction: 'ecommerce' }
          ]
        } as never
      }
      if (path === '/api/agri-skills/courses/1/progress') {
        return { success: true, progress: progressFixture } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const store = useAgriCoursesStore()
    await store.loadCourses()
    await store.loadRecommendations()

    expect(store.courses.map(course => course.id)).toEqual([1])
    expect(store.recommendations.map(course => course.id)).toEqual([9])
  })

  it('surfaces per-course progress failures without fabricating zero progress', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/courses') {
        return { success: true, courses: [courseFixture] } as never
      }
      if (path === '/api/agri-skills/courses/1/progress') {
        throw new ApiError('学习进度暂时不可用', 503)
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const store = useAgriCoursesStore()
    await store.loadCourses()

    expect(store.progressByCourse[1]).toBeUndefined()
    expect(store.progressErrorsByCourse[1]).toBe('学习进度暂时不可用')
  })

  it('sends the exact progress body and refreshes completed recommendations', async () => {
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (
        path === '/api/agri-skills/courses/1/progress' &&
        options?.method === 'PUT'
      ) {
        return { success: true, progress: progressFixture } as never
      }
      if (path === '/api/agri-skills/recommendations') {
        return { success: true, courses: [] } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const store = useAgriCoursesStore()
    const recommendationCourse = {
      ...courseFixture,
      direction: 'agriculture',
      status: 'published'
    } as AgriCourse
    store.recommendations = [recommendationCourse]
    await store.saveProgress(1, 80, 20)

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/courses/1/progress',
      {
        method: 'PUT',
        body: JSON.stringify({
          position_seconds: 80,
          watched_delta_seconds: 20
        })
      }
    )
    expect(store.progressByCourse[1]).toEqual(progressFixture)
    expect(store.recommendations).toEqual([])
    expect(mockedApiFetch.mock.calls.map(([path]) => path)).toEqual([
      '/api/agri-skills/courses/1/progress',
      '/api/agri-skills/recommendations'
    ])
  })

  it('removes a completed course before reporting a failed recommendation refresh', async () => {
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (
        path === '/api/agri-skills/courses/1/progress' &&
        options?.method === 'PUT'
      ) {
        return { success: true, progress: progressFixture } as never
      }
      if (path === '/api/agri-skills/recommendations') {
        throw new ApiError('推荐刷新失败', 503)
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const store = useAgriCoursesStore()
    const recommendationCourse = {
      ...courseFixture,
      direction: 'agriculture',
      status: 'published'
    } as AgriCourse
    store.recommendations = [recommendationCourse]

    const succeeded = await store.saveProgress(1, 80, 20)

    expect(succeeded).toBe(false)
    expect(store.progressByCourse[1]).toEqual(progressFixture)
    expect(store.recommendations).toEqual([])
    expect(store.recommendationError).toBe('推荐刷新失败')
  })

  it('preserves backend ordering for courses and recommendations', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/courses') {
        return {
          success: true,
          courses: [
            { ...courseFixture, id: 7, title: '后置课程' },
            { ...courseFixture, id: 2, title: '前置课程' }
          ]
        } as never
      }
      if (path === '/api/agri-skills/recommendations') {
        return {
          success: true,
          courses: [
            { id: 9, title: '推荐九', summary: '', teacher_name: '' },
            { id: 3, title: '推荐三', summary: '', teacher_name: '' }
          ]
        } as never
      }
      const progressMatch = path.match(
        /^\/api\/agri-skills\/courses\/(\d+)\/progress$/
      )
      if (progressMatch) {
        const courseId = Number(progressMatch[1])
        return {
          success: true,
          progress: { ...progressFixture, course_id: courseId }
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const store = useAgriCoursesStore()
    await store.loadCourses()
    await store.loadRecommendations()

    expect(store.courses.map(course => course.id)).toEqual([7, 2])
    expect(store.recommendations.map(course => course.id)).toEqual([9, 3])
  })

  it('replaces the formal result with the latest attempt', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        attempt: attemptFixture(1, 'A')
      } as never)
      .mockResolvedValueOnce({
        success: true,
        attempt: attemptFixture(2, 'B')
      } as never)

    const store = useAgriCoursesStore()
    await store.submitQuiz(1, { q1: 'A' })
    await store.submitQuiz(1, { q1: 'B' })

    expect(store.attempts[0].is_formal).toBe(true)
    expect(store.attempts[1].is_formal).toBe(false)
    expect(store.attempts.map(attempt => attempt.id)).toEqual([2, 1])
  })
})
