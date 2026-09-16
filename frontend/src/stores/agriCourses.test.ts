import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'
import type {
  AgriculturalCourse,
  CourseProgress,
  CourseQuizAttempt
} from '@/api/types'

import { useAgriCoursesStore } from './agriCourses'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

type CourseRow = AgriculturalCourse & {
  direction: string
  status?: string
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
  course_id: 1,
  duration_seconds: 100,
  furthest_position_seconds: 80,
  resume_position_seconds: 80,
  progress_percent: 80,
  watched_seconds: 80,
  completed_at: '2026-09-16T01:00:00+00:00',
  last_viewed_at: '2026-09-16T01:00:00+00:00'
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
    store.recommendations = [{ ...courseFixture }]
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

    expect(store.attempts[0].is_formal).toBe(false)
    expect(store.attempts[1].is_formal).toBe(true)
    expect(store.attempts.map(attempt => attempt.id)).toEqual([1, 2])
  })
})
