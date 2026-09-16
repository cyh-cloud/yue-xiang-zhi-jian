import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type {
  AgriculturalCourse,
  CourseProgress,
  DiagnosisSession
} from '@/api/types'
import { useAgriDiagnosisStore } from '@/stores/agriDiagnosis'

import AgriCalendarView from './AgriCalendarView.vue'
import AgriCoursesView from './AgriCoursesView.vue'
import AgriDiagnosisView from './AgriDiagnosisView.vue'
import AgriQaView from './AgriQaView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn(),
    apiStream: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const product = {
  key: 'litchi',
  name: '荔枝',
  sort_order: 1
}

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      '/',
      '/login',
      '/student',
      '/student/agri-skills',
      '/student/agri-skills/calendar',
      '/student/agri-skills/qa',
      '/student/agri-skills/diagnosis',
      '/student/agri-skills/courses'
    ].map(path => ({ path, component: { template: '<div />' } }))
  })
}

function mountAt375(component: typeof AgriCalendarView) {
  vi.stubGlobal('innerWidth', 375)
  Object.defineProperty(document.documentElement, 'scrollWidth', {
    configurable: true,
    value: 375
  })
  return mount(component, {
    global: {
      plugins: [createPinia(), testRouter()]
    }
  })
}

function courseFixture(
  id: number,
  progressPercent: number
): {
  course: AgriculturalCourse & {
    direction: string
    status: string
  }
  progress: CourseProgress
} {
  return {
    course: {
      id,
      title: `农业课程 ${id}`,
      summary: '农业课程简介',
      teacher_name: '林老师',
      published_at: '2026-09-01T00:00:00+00:00',
      tag_ids: [1],
      duration_seconds: 100,
      direction: 'agriculture',
      status: 'published'
    },
    progress: {
      course_id: id,
      duration_seconds: 100,
      furthest_position_seconds: progressPercent,
      resume_position_seconds: progressPercent,
      progress_percent: progressPercent,
      watched_seconds: progressPercent,
      completed_at:
        progressPercent >= 80 ? '2026-09-16T00:00:00+00:00' : null,
      last_viewed_at: '2026-09-16T00:00:00+00:00'
    }
  }
}

describe('AgriSkillsResponsive', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('keeps calendar controls inside the container without horizontal overflow', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/products') {
        return { success: true, products: [product] } as never
      }
      if (path.startsWith('/api/agri-skills/calendar?')) {
        return {
          success: true,
          calendar: {
            product,
            month: 4,
            tasks: ['保果'],
            management: ['排水'],
            solar_terms: ['清明'],
            reminder: '关注落果',
            empty_state: null
          }
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = mountAt375(AgriCalendarView)
    await flushPromises()

    const controls = wrapper.get('.calendar-controls')
    expect(
      controls.find('[data-test="product-select"]').exists()
    ).toBe(true)
    expect(controls.find('[data-test="month-previous"]').exists()).toBe(true)
    expect(controls.find('[data-test="month-next"]').exists()).toBe(true)
    expect(controls.find('[data-test="subscribe-litchi"]').exists()).toBe(true)
    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(375)
  })

  it('keeps diagnosis questions and answer controls in separate vertical regions', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/diagnoses') {
        return { success: true, diagnoses: [] } as never
      }
      if (path === '/api/agri-skills/products') {
        return { success: true, products: [product] } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    const wrapper = mountAt375(AgriDiagnosisView)
    await flushPromises()
    const store = useAgriDiagnosisStore()
    store.activeSession = {
      id: 12,
      product,
      product_key: 'litchi',
      affected_part: 'fruit',
      symptoms: ['虫蛀'],
      status: 'in_progress',
      round_count: 0,
      conclusion: null,
      limited: false,
      answers: [],
      followups: [],
      source_session_id: null,
      source_followup_id: null,
      source_available: true,
      created_at: '2026-09-16T00:00:00+00:00',
      updated_at: '2026-09-16T00:00:00+00:00',
      pending_question: '请补充症状出现时间',
      pending_question_round: 1
    } as DiagnosisSession
    await wrapper.vm.$nextTick()

    const question = wrapper.get('[data-test="pending-question"]')
    const answerForm = wrapper.get('[data-test="diagnosis-answer-form"]')
    const questionRect = {
      top: 120,
      bottom: 180,
      left: 16,
      right: 359,
      width: 343,
      height: 60,
      x: 16,
      y: 120,
      toJSON: () => ({})
    }
    const answerRect = {
      top: 200,
      bottom: 320,
      left: 16,
      right: 359,
      width: 343,
      height: 120,
      x: 16,
      y: 200,
      toJSON: () => ({})
    }
    vi.spyOn(question.element, 'getBoundingClientRect').mockReturnValue(
      questionRect
    )
    vi.spyOn(answerForm.element, 'getBoundingClientRect').mockReturnValue(
      answerRect
    )

    expect(questionRect.bottom).toBeLessThanOrEqual(answerRect.top)
    expect(questionRect.left).toBeGreaterThanOrEqual(0)
    expect(answerRect.right).toBeLessThanOrEqual(375)
  })

  it('keeps course and recommendation empty states separate', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/courses') {
        return { success: true, courses: [] } as never
      }
      if (path === '/api/agri-skills/recommendations') {
        return { success: true, courses: [] } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    const wrapper = mountAt375(AgriCoursesView)
    await flushPromises()

    const courseEmpty = wrapper.get('[data-test="course-empty"]')
    const recommendationEmpty = wrapper.get(
      '[data-test="recommendation-empty"]'
    )
    expect(courseEmpty.text()).toBe('暂无课程')
    expect(recommendationEmpty.text()).toBe('暂无推荐')
    expect(courseEmpty.element).not.toBe(recommendationEmpty.element)
    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(375)
  })

  it('gates the quiz entry before 80 percent and enables it at 80 percent', async () => {
    const below = courseFixture(1, 79)
    const ready = courseFixture(2, 80)
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/courses') {
        return {
          success: true,
          courses: [below.course, ready.course]
        } as never
      }
      if (path === '/api/agri-skills/recommendations') {
        return { success: true, courses: [] } as never
      }
      if (path === '/api/agri-skills/courses/1/progress') {
        return { success: true, progress: below.progress } as never
      }
      if (path === '/api/agri-skills/courses/2/progress') {
        return { success: true, progress: ready.progress } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    const wrapper = mountAt375(AgriCoursesView)
    await flushPromises()

    expect(
      wrapper.get('[data-test="quiz-entry-1"]').attributes('disabled')
    ).toBeDefined()
    expect(
      wrapper.get('[data-test="quiz-entry-2"]').attributes('disabled')
    ).toBeUndefined()
  })

  it('mounts the Q&A view without horizontal overflow at 375px', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/qa/conversations') {
        return { success: true, conversations: [] } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    const wrapper = mountAt375(AgriQaView)
    await flushPromises()

    expect(wrapper.find('.qa-composer').exists()).toBe(true)
    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(375)
  })
})
