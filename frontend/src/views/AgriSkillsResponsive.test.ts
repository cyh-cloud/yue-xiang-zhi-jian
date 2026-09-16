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
import AgriSkillsHomeView from './AgriSkillsHomeView.vue'
import agriCalendarSource from './AgriCalendarView.vue?raw'
import agriCoursesSource from './AgriCoursesView.vue?raw'
import agriDiagnosisSource from './AgriDiagnosisView.vue?raw'
import agriQaSource from './AgriQaView.vue?raw'
import agriSkillsHomeSource from './AgriSkillsHomeView.vue?raw'

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
      last_viewed_at: '2026-09-16T00:00:00+00:00',
      quiz_available: true
    }
  }
}

function mediaBlock(source: string, maxWidth: number): string {
  const marker = `@media (max-width: ${maxWidth}px)`
  const start = source.indexOf(marker)
  expect(start).toBeGreaterThanOrEqual(0)
  return source.slice(start)
}

function cssRule(css: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(
    new RegExp(
      `(?:^|[{}])\\s*[^{}]*?${escaped}[^{}]*?\\s*\\{([\\s\\S]*?)\\}`
    )
  )
  expect(match).not.toBeNull()
  return (match?.[1] ?? '').replace(/\s+/g, ' ').trim()
}

describe('AgriSkillsResponsive', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  // jsdom does not calculate layout; real overflow and overlap remain browser acceptance checks.
  it('declares real 375px CSS contracts across all 03 views', () => {
    const calendarMobile = mediaBlock(agriCalendarSource, 760)
    expect(cssRule(agriCalendarSource, '.calendar-page')).toContain(
      'min-width: 0'
    )
    expect(cssRule(agriCalendarSource, '.calendar-page')).toContain(
      'overflow-x: clip'
    )
    expect(cssRule(calendarMobile, '.calendar-controls')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(calendarMobile, '.month-control')).toContain(
      'width: 100%'
    )
    expect(cssRule(calendarMobile, '.subscription-toggle')).toContain(
      'width: 100%'
    )

    const qaMobile = mediaBlock(agriQaSource, 760)
    expect(cssRule(agriQaSource, '.agri-qa-page')).toContain(
      'overflow-x: clip'
    )
    expect(cssRule(qaMobile, '.agri-qa-workspace')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(qaMobile, '.qa-composer__row')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(qaMobile, '.qa-composer__submit')).toContain(
      'width: 100%'
    )

    const diagnosisMobile = mediaBlock(agriDiagnosisSource, 760)
    expect(cssRule(agriDiagnosisSource, '.diagnosis-page')).toContain(
      'overflow-x: clip'
    )
    expect(cssRule(diagnosisMobile, '.diagnosis-workspace')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(diagnosisMobile, '.diagnosis-start__grid')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(diagnosisMobile, '.answer-composer__row')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )

    const coursesMobile = mediaBlock(agriCoursesSource, 760)
    expect(cssRule(agriCoursesSource, '.agri-courses-page')).toContain(
      'overflow-x: clip'
    )
    expect(cssRule(coursesMobile, '.recommendation-list')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(
      cssRule(coursesMobile, '.course-card__actions button')
    ).toContain('flex: 1 1 160px')
    expect(cssRule(coursesMobile, '.quiz-submit')).toContain('width: 100%')

    const homeMobile = mediaBlock(agriSkillsHomeSource, 640)
    expect(cssRule(agriSkillsHomeSource, '.agri-skills-home')).toContain(
      'min-width: 0'
    )
    expect(cssRule(agriSkillsHomeSource, '.agri-skills-home')).toContain(
      'overflow-x: clip'
    )
    expect(cssRule(agriSkillsHomeSource, '.agri-skills-home__grid')).toContain(
      'repeat(auto-fit, minmax(250px, 1fr))'
    )
    expect(cssRule(homeMobile, '.agri-skills-home__main')).toContain(
      'padding: 32px 14px 48px'
    )
  })

  it('keeps calendar controls in the responsive calendar container', async () => {
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
  })

  it('keeps diagnosis question and answer controls in a single-column DOM flow', async () => {
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
    expect(
      question.element.compareDocumentPosition(answerForm.element) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
    expect(
      cssRule(
        mediaBlock(agriDiagnosisSource, 760),
        '.answer-composer__row'
      )
    ).toContain('grid-template-columns: minmax(0, 1fr)')
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

  it('mounts the Q&A view with the responsive composer structure', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/qa/conversations') {
        return { success: true, conversations: [] } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    const wrapper = mountAt375(AgriQaView)
    await flushPromises()

    expect(wrapper.find('.qa-composer').exists()).toBe(true)
    expect(
      wrapper.get('.qa-composer').element.closest('.qa-conversation')
    ).not.toBeNull()
  })

  it('mounts the agricultural skills home and all entries at 375px', async () => {
    const wrapper = mountAt375(AgriSkillsHomeView)

    expect(wrapper.find('.agri-skills-home').exists()).toBe(true)
    expect(wrapper.findAll('.agri-skills-card')).toHaveLength(5)
    expect(wrapper.get('.agri-skills-home__grid').element.children).toHaveLength(
      5
    )
  })
})
