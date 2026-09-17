import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError, apiFetch } from '@/api/client'
import type {
  AgriculturalCourse,
  CourseProgress,
  CourseQuizAttempt
} from '@/api/types'
import { useAgriCoursesStore } from '@/stores/agriCourses'

import AgriCoursesView from './AgriCoursesView.vue'

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
  status?: string | null
  return_to?: string
}

const publishedCourse: CourseRow = {
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

function progress(
  courseId: number,
  progressPercent: number
): CourseProgress {
  return {
    user_id: 1,
    course_id: courseId,
    duration_seconds: 100,
    furthest_position_seconds: progressPercent,
    resume_position_seconds: progressPercent === 100 ? 40 : progressPercent,
    progress_percent: progressPercent,
    watched_seconds: progressPercent,
    completed_at:
      progressPercent >= 80 ? '2026-09-16T01:00:00+00:00' : null,
    last_viewed_at: '2026-09-16T01:00:00+00:00',
    updated_at: '2026-09-16T01:00:00+00:00',
    quiz_available: true
  }
}

const gradedAttempt: CourseQuizAttempt = {
  id: 9,
  course_id: 1,
  score: 100,
  is_formal: true,
  is_current: true,
  is_latest: true,
  questions: [
    {
      id: 'q1',
      type: 'single_choice',
      prompt: '达到多少进度视为完成？',
      options: ['A', 'B'],
      correct: true,
      explanation: '达到 80% 即完成。'
    }
  ],
  created_at: '2026-09-16T02:00:00+00:00'
}

function mockApi(
  courses: CourseRow[] = [publishedCourse],
  recommendations: Array<Partial<CourseRow>> = [],
  progressByCourse: Record<number, CourseProgress> = {
    1: progress(1, 80)
  }
) {
  mockedApiFetch.mockImplementation(async (path, options) => {
    if (path === '/api/agri-skills/courses') {
      return { success: true, courses } as never
    }
    if (path === '/api/agri-skills/recommendations') {
      return { success: true, courses: recommendations } as never
    }

    const progressMatch = path.match(
      /^\/api\/agri-skills\/courses\/(\d+)\/progress$/
    )
    if (progressMatch && !options?.method) {
      return {
        success: true,
        progress: progressByCourse[Number(progressMatch[1])]
      } as never
    }
    if (path === '/api/agri-skills/courses/1/quiz' && !options?.method) {
      return {
        success: true,
        quiz: {
          course_id: 1,
          questions: [
            {
              id: 'q1',
              type: 'single_choice',
              prompt: '达到多少进度视为完成？',
              options: ['A', 'B']
            }
          ]
        }
      } as never
    }
    if (path === '/api/agri-skills/courses/1/quiz' && options?.method === 'POST') {
      return { success: true, attempt: gradedAttempt } as never
    }
    if (path === '/api/agri-skills/courses/1/quiz/attempts') {
      return { success: true, attempts: [] } as never
    }
    throw new Error(`Unexpected request: ${path}`)
  })
}

function mountView() {
  const pinia = createPinia()
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      '/',
      '/login',
      '/register',
      '/student',
      '/student/agri-skills',
      '/student/agri-skills/calendar',
      '/student/agri-skills/qa',
      '/student/agri-skills/diagnosis',
      '/student/agri-skills/courses',
      '/student/courses/1'
    ].map(path => ({ path, component: { template: '<div />' } }))
  })

  const wrapper = mount(AgriCoursesView, {
    global: {
      plugins: [pinia, router]
    }
  })
  return { pinia, wrapper }
}

describe('AgriCoursesView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('shows independent course and recommendation empty states', async () => {
    mockApi([], [], {})
    const { wrapper } = mountView()
    await flushPromises()

    expect(wrapper.get('[data-test="course-empty"]').text()).toBe('暂无课程')
    expect(wrapper.get('[data-test="recommendation-empty"]').text()).toBe(
      '暂无推荐'
    )
  })

  it('does not render malformed unpublished or non-agriculture rows', async () => {
    const offline = {
      ...publishedCourse,
      id: 2,
      title: '下架农业课程',
      status: 'offline'
    }
    const ecommerce = {
      ...publishedCourse,
      id: 3,
      title: '电商课程',
      direction: 'ecommerce'
    }
    mockApi(
      [publishedCourse, offline, ecommerce],
      [offline, ecommerce],
      { 1: progress(1, 80) }
    )

    const { wrapper } = mountView()
    await flushPromises()

    expect(wrapper.find('[data-test="course-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="course-2"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="course-3"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('下架农业课程')
    expect(wrapper.text()).not.toContain('电商课程')
    expect(
      wrapper.get('[data-test="course-comments-1"]').attributes('href')
    ).toBe('/student/courses/1?comment=1#comments')
  })

  it('renders progress, resume position and gates quiz entry at 80 percent', async () => {
    const secondCourse = {
      ...publishedCourse,
      id: 4,
      title: '水稻种植技术'
    }
    mockApi(
      [publishedCourse, secondCourse],
      [],
      { 1: progress(1, 79), 4: progress(4, 80) }
    )

    const { wrapper } = mountView()
    await flushPromises()

    expect(wrapper.get('[data-test="course-progress-1"]').attributes('value')).toBe(
      '79'
    )
    expect(wrapper.get('[data-test="course-resume-1"]').text()).toContain(
      '续播 01:19'
    )
    expect(
      wrapper.get('[data-test="quiz-entry-1"]').attributes('disabled')
    ).toBeDefined()
    expect(
      wrapper.get('[data-test="quiz-entry-4"]').attributes('disabled')
    ).toBeUndefined()
  })

  it('renders quiz questions, score, correctness and explanations', async () => {
    mockApi()
    const { wrapper } = mountView()
    await flushPromises()

    await wrapper.get('[data-test="quiz-entry-1"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="quiz-1"]').element).toBeTruthy()
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/courses/1/quiz/attempts'
    )
    expect(wrapper.get('[data-test="quiz-1"]').text()).toContain(
      '达到多少进度视为完成？'
    )
    await wrapper.get('[data-test="quiz-option-0-0"]').setValue()
    await wrapper.get('[data-test="quiz-form-1"]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-test="quiz-score-1"]').text()).toContain('100 分')
    expect(wrapper.get('[data-test="quiz-result-0"]').text()).toContain('正确')
    expect(wrapper.get('[data-test="quiz-explanation-0"]').text()).toBe(
      '达到 80% 即完成。'
    )
  })

  it('preserves backend ordering for courses and recommendations', async () => {
    mockApi(
      [
        { ...publishedCourse, id: 7, title: '后置课程' },
        { ...publishedCourse, id: 2, title: '前置课程' }
      ],
      [
        { id: 9, title: '推荐九', summary: '推荐九摘要' },
        { id: 3, title: '推荐三', summary: '推荐三摘要' }
      ],
      { 7: progress(7, 80), 2: progress(2, 80) }
    )
    const { wrapper } = mountView()
    await flushPromises()

    expect(
      wrapper
        .findAll('.course-card')
        .map(course => course.attributes('data-test'))
    ).toEqual(['course-7', 'course-2'])
    expect(
      wrapper
        .findAll('.recommendation-item')
        .map(course => course.attributes('data-test'))
    ).toEqual(['recommendation-9', 'recommendation-3'])
  })

  it('shows a course progress failure instead of presenting zero progress', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/courses') {
        return { success: true, courses: [publishedCourse] } as never
      }
      if (path === '/api/agri-skills/recommendations') {
        return { success: true, courses: [] } as never
      }
      if (path === '/api/agri-skills/courses/1/progress') {
        throw new ApiError('学习进度暂时不可用', 503)
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    const { wrapper } = mountView()
    await flushPromises()

    expect(
      wrapper.get('[data-test="course-progress-error-1"]').text()
    ).toContain('学习进度暂时不可用')
    expect(wrapper.find('[data-test="course-progress-1"]').exists()).toBe(false)
  })

  it('keeps a recommendation retry path after a completed refresh fails', async () => {
    let recommendationCalls = 0
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === '/api/agri-skills/courses') {
        return { success: true, courses: [publishedCourse] } as never
      }
      if (path === '/api/agri-skills/recommendations') {
        recommendationCalls += 1
        if (recommendationCalls === 1) {
          return {
            success: true,
            courses: [{ id: 1, title: '荔枝保果技术', summary: '' }]
          } as never
        }
        throw new ApiError('推荐刷新失败', 503)
      }
      if (
        path === '/api/agri-skills/courses/1/progress' &&
        options?.method === 'PUT'
      ) {
        return { success: true, progress: progress(1, 80) } as never
      }
      if (path === '/api/agri-skills/courses/1/progress') {
        return { success: true, progress: progress(1, 79) } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    const { pinia, wrapper } = mountView()
    await flushPromises()

    const store = useAgriCoursesStore(pinia)
    await store.saveProgress(1, 80, 20)
    await nextTick()

    expect(store.recommendations).toEqual([])
    expect(wrapper.get('[data-test="recommendation-error"]').text()).toContain(
      '推荐刷新失败'
    )
    expect(wrapper.find('[data-test="recommendation-retry"]').exists()).toBe(
      true
    )
  })
})
