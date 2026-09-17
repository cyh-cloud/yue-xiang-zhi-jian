import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'

import EcommerceCoursesView from './EcommerceCoursesView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const courses = [
  {
    id: 1,
    title: '有效测验课程',
    summary: '有效测验',
    teacher_name: '陈老师',
    published_at: '2026-09-16T00:00:00+00:00',
    duration_seconds: 100,
    tag_ids: [1],
    direction: 'ecommerce',
    status: 'published'
  },
  {
    id: 2,
    title: '无效测验课程',
    summary: '无效测验',
    teacher_name: '陈老师',
    published_at: '2026-09-16T00:00:00+00:00',
    duration_seconds: 100,
    tag_ids: [1],
    direction: 'ecommerce',
    status: 'published'
  },
  {
    id: 3,
    title: '无测验课程',
    summary: '无测验',
    teacher_name: '陈老师',
    published_at: '2026-09-16T00:00:00+00:00',
    duration_seconds: 100,
    tag_ids: [1],
    direction: 'ecommerce',
    status: 'published'
  }
]

function progress(courseId: number, quizAvailable: boolean) {
  return {
    course_id: courseId,
    duration_seconds: 100,
    furthest_position_seconds: 80,
    resume_position_seconds: 80,
    progress_percent: 80,
    watched_seconds: 80,
    completed_at: '2026-09-16T01:00:00+00:00',
    last_viewed_at: '2026-09-16T01:00:00+00:00',
    quiz_available: quizAvailable
  }
}

const attempts = [
  {
    id: 22,
    course_id: 1,
    score: 80,
    is_formal: true,
    is_current: true,
    is_latest: true,
    questions: [
      {
        id: 'q1',
        type: 'single_choice',
        prompt: '达到多少进度视为完成？',
        options: ['60%', '80%'],
        correct: true,
        explanation: '达到 80% 即完成。'
      }
    ],
    created_at: '2026-09-16T03:00:00+00:00'
  },
  {
    id: 21,
    course_id: 1,
    score: 0,
    is_formal: false,
    is_current: false,
    is_latest: false,
    questions: [
      {
        id: 'q1',
        type: 'single_choice',
        prompt: '达到多少进度视为完成？',
        options: ['60%', '80%'],
        correct: false,
        explanation: '应选择 80%。'
      }
    ],
    created_at: '2026-09-16T02:00:00+00:00'
  }
]

const submittedAttempt = {
  id: 23,
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
      options: ['60%', '80%'],
      correct: true,
      explanation: '达到 80% 即完成。'
    }
  ],
  created_at: '2026-09-16T04:00:00+00:00'
}

function mockApi() {
  mockedApiFetch.mockImplementation(async (path, options) => {
    if (path === '/api/ecommerce-training/courses') {
      return { success: true, courses } as never
    }
    if (path === '/api/ecommerce-training/recommendations') {
      return { success: true, courses: [] } as never
    }
    const progressMatch = path.match(
      /^\/api\/ecommerce-training\/courses\/(\d+)\/progress$/
    )
    if (progressMatch && !options?.method) {
      const courseId = Number(progressMatch[1])
      return {
        success: true,
        progress: progress(courseId, courseId === 1)
      } as never
    }
    if (
      path === '/api/ecommerce-training/courses/1/quiz' &&
      !options?.method
    ) {
      return {
        success: true,
        quiz: {
          course_id: 1,
          questions: [
            {
              id: 'q1',
              type: 'single_choice',
              prompt: '达到多少进度视为完成？',
              options: ['60%', '80%']
            }
          ]
        }
      } as never
    }
    if (path === '/api/ecommerce-training/courses/1/quiz/attempts') {
      return { success: true, attempts } as never
    }
    if (
      path === '/api/ecommerce-training/courses/1/quiz' &&
      options?.method === 'POST'
    ) {
      return { success: true, attempt: submittedAttempt } as never
    }
    throw new Error(`Unexpected request: ${path}`)
  })
}

function mountView(attachTo?: HTMLElement) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }]
  })

  return mount(EcommerceCoursesView, {
    attachTo,
    global: {
      plugins: [createPinia(), router]
    }
  })
}

describe('EcommerceCoursesView quiz availability and history', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('enables the quiz entry only for an available valid quiz at 80 percent', async () => {
    mockApi()
    const wrapper = mountView()
    await flushPromises()

    expect(
      wrapper.get('[data-test="quiz-entry-1"]').attributes('disabled')
    ).toBeUndefined()
    expect(
      wrapper.get('[data-test="quiz-entry-2"]').attributes('disabled')
    ).toBeDefined()
    expect(
      wrapper.get('[data-test="quiz-entry-3"]').attributes('disabled')
    ).toBeDefined()
    expect(wrapper.get('[data-test="quiz-gate-2"]').text()).toContain(
      '暂无可用测验'
    )
    expect(wrapper.get('[data-test="quiz-gate-3"]').text()).toContain(
      '暂无可用测验'
    )
  })

  it('loads and renders attempt history after a fresh mount', async () => {
    mockApi()
    const first = mountView()
    await flushPromises()
    await first.get('[data-test="quiz-entry-1"]').trigger('click')
    await flushPromises()

    expect(wrapperItems(first).length).toBe(2)
    expect(first.get('[data-test="quiz-history-22"]').text()).toContain(
      '正式成绩'
    )
    first.unmount()

    const refreshed = mountView()
    await flushPromises()
    await refreshed.get('[data-test="quiz-entry-1"]').trigger('click')
    await flushPromises()

    expect(wrapperItems(refreshed).length).toBe(2)
    expect(
      refreshed.get('[data-test="quiz-history-21"]').text()
    ).toContain('历史成绩')
    expect(
      refreshed.get('[data-test="quiz-history-22"]').text()
    ).toContain('2026-09-16 11:00:00')
    expect(
      refreshed.get('[data-test="quiz-history-22"]').text()
    ).not.toContain('2026-09-16T03:00:00+00:00')
    expect(refreshed.get('.course-card__head time').text()).toContain(
      '2026-09-16'
    )
    expect(refreshed.get('.course-card__head time').text()).not.toContain('/')
  })

  it('shows a disabled submit hint until every question is answered', async () => {
    mockApi()
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('[data-test="quiz-entry-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="quiz-retake-1"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="quiz-submit-hint-1"]').text()).toContain(
      '请选择一个选项'
    )
    expect(
      wrapper.get('[data-test="quiz-submit-1"]').attributes('aria-describedby')
    ).toBe('quiz-submit-hint-1')

    await wrapper.get('[data-test="quiz-option-0-1"]').setValue()

    expect(wrapper.find('[data-test="quiz-submit-hint-1"]').exists()).toBe(
      false
    )
    expect(
      wrapper.get('[data-test="quiz-submit-1"]').attributes('aria-describedby')
    ).toBeUndefined()
    expect(
      wrapper.get('[data-test="quiz-submit-1"]').attributes('disabled')
    ).toBeUndefined()
  })

  it('labels only the just-submitted result as current and refreshed results as latest history', async () => {
    mockApi()
    const submitted = mountView()
    await flushPromises()
    await submitted.get('[data-test="quiz-entry-1"]').trigger('click')
    await flushPromises()
    await submitted.get('[data-test="quiz-retake-1"]').trigger('click')
    await submitted.get('[data-test="quiz-option-0-1"]').setValue()
    await submitted.get('[data-test="quiz-form-1"]').trigger('submit')
    await flushPromises()

    expect(
      submitted.get('[data-test="quiz-result-label"]').text()
    ).toContain('本次成绩')
    expect(
      submitted.get('[data-test="quiz-feedback-label"]').text()
    ).toContain('本次解析')
    submitted.unmount()

    const refreshed = mountView()
    await flushPromises()
    await refreshed.get('[data-test="quiz-entry-1"]').trigger('click')
    await flushPromises()

    expect(
      refreshed.get('[data-test="quiz-result-label"]').text()
    ).toContain('最近成绩')
    expect(
      refreshed.get('[data-test="quiz-feedback-label"]').text()
    ).toContain('上次解析')
    expect(refreshed.get('.quiz-result').text()).not.toContain('本次')
  })

  it('starts a fresh attempt after submission while retaining history', async () => {
    mockApi()
    const wrapper = mountView(document.body)
    await flushPromises()
    await wrapper.get('[data-test="quiz-entry-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="quiz-retake-1"]').trigger('click')

    const submit = wrapper.get('[data-test="quiz-submit-1"]')
    expect(submit.text()).toContain('提交测验')
    expect(submit.attributes('disabled')).toBeDefined()

    await wrapper.get('[data-test="quiz-option-0-1"]').setValue()
    expect(submit.attributes('disabled')).toBeUndefined()
    await wrapper.get('[data-test="quiz-form-1"]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-test="quiz-retake-1"]').text()).toContain(
      '再次测验'
    )
    expect(wrapper.find('[data-test="quiz-form-1"]').exists()).toBe(false)
    expect(wrapperItems(wrapper)).toHaveLength(3)

    await wrapper.get('[data-test="quiz-retake-1"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="quiz-submit-1"]').text()).toContain(
      '提交测验'
    )
    expect(
      wrapper.get('[data-test="quiz-submit-1"]').attributes('disabled')
    ).toBeDefined()
    expect(wrapper.find('[data-test="quiz-result-1"]').exists()).toBe(false)
    expect(document.activeElement).toBe(
      wrapper.get('[data-test="quiz-option-0-0"]').element
    )
    expect(
      wrapper
        .findAll<HTMLInputElement>('input[type="radio"]')
        .every(input => !input.element.checked)
    ).toBe(true)
    expect(wrapperItems(wrapper)).toHaveLength(3)
    expect(
      wrapper.find('[data-test="quiz-history-23"]').exists()
    ).toBe(true)

    await wrapper.get('[data-test="quiz-option-0-1"]').setValue()
    expect(
      wrapper.get('[data-test="quiz-submit-1"]').attributes('disabled')
    ).toBeUndefined()
    wrapper.unmount()
  })
})

function wrapperItems(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('.quiz-history article')
}
