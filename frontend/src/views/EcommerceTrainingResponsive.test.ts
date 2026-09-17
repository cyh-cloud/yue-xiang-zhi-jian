import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, type Component } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { installSessionExpiredHandler } from '@/api/session-expiry'
import courseLearningPanelSource from '@/components/CourseLearningPanel.vue?raw'
import ecommerceTrainingNavSource from '@/components/EcommerceTrainingNav.vue?raw'
import { useAuthStore } from '@/stores/auth'
import { useCourseLearningStore } from '@/stores/courseLearning'
import { useEcommerceCopyTrainingStore } from '@/stores/ecommerceCopyTraining'
import { useEcommerceCustomerServiceStore } from '@/stores/ecommerceCustomerService'
import { useEcommerceLiveScriptStore } from '@/stores/ecommerceLiveScript'
import { useEcommerceSimulationStore } from '@/stores/ecommerceSimulation'
import { useEcommerceStoreGuidanceStore } from '@/stores/ecommerceStoreGuidance'

import EcommerceCopyTrainingView from './EcommerceCopyTrainingView.vue'
import EcommerceCoursesView from './EcommerceCoursesView.vue'
import EcommerceCustomerServiceView from './EcommerceCustomerServiceView.vue'
import EcommerceLiveScriptView from './EcommerceLiveScriptView.vue'
import EcommerceSimulationView from './EcommerceSimulationView.vue'
import EcommerceStoreGuidanceView from './EcommerceStoreGuidanceView.vue'
import ecommerceCopyTrainingSource from './EcommerceCopyTrainingView.vue?raw'
import ecommerceCustomerServiceSource from './EcommerceCustomerServiceView.vue?raw'
import ecommerceLiveScriptSource from './EcommerceLiveScriptView.vue?raw'
import ecommerceSimulationSource from './EcommerceSimulationView.vue?raw'
import ecommerceStoreGuidanceSource from './EcommerceStoreGuidanceView.vue?raw'
import ecommerceTrainingHomeSource from './EcommerceTrainingHomeView.vue?raw'

const paths = [
  '/student/ecommerce-training',
  '/student/ecommerce-training/live-script',
  '/student/ecommerce-training/simulation',
  '/student/ecommerce-training/copy-training',
  '/student/ecommerce-training/store-guidance',
  '/student/ecommerce-training/customer-service',
  '/student/ecommerce-training/courses'
]

const sessionCases: Array<{
  name: string
  path: string
  component: Component
}> = [
  {
    name: 'live script',
    path: '/student/ecommerce-training/live-script',
    component: EcommerceLiveScriptView
  },
  {
    name: 'simulation',
    path: '/student/ecommerce-training/simulation',
    component: EcommerceSimulationView
  },
  {
    name: 'copy training',
    path: '/student/ecommerce-training/copy-training',
    component: EcommerceCopyTrainingView
  },
  {
    name: 'store guidance',
    path: '/student/ecommerce-training/store-guidance',
    component: EcommerceStoreGuidanceView
  },
  {
    name: 'customer service',
    path: '/student/ecommerce-training/customer-service',
    component: EcommerceCustomerServiceView
  },
  {
    name: 'courses',
    path: '/student/ecommerce-training/courses',
    component: EcommerceCoursesView
  }
]

const widths = [1280, 768, 375]
const longChinese =
  '这是一段用于验证超长中文内容不会造成横向溢出的电商运营实训说明，包含商品信息、训练步骤、评分依据、改进建议、历史记录与后续操作。'.repeat(
    4
  )

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      '/',
      '/login',
      '/student',
      ...paths
    ].map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}

function successResponse(payload: Record<string, unknown>) {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    json: async () => payload
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

const responsiveCases: Array<{
  name: string
  component: Component
  prepare: (
    pinia: ReturnType<typeof createPinia>
  ) => Promise<void> | void
}> = [
  {
    name: 'live script',
    component: EcommerceLiveScriptView,
    prepare: pinia => {
      useEcommerceLiveScriptStore(pinia).current = {
        id: 1,
        product_name: longChinese,
        selling_points: [longChinese],
        price_text: longChinese,
        style: 'enthusiastic',
        script: {
          opening: longChinese,
          product_intro: longChinese,
          interaction: longChinese,
          closing: longChinese
        },
        is_current: true,
        created_at: '2026-09-17T08:00:00+08:00'
      } as never
    }
  },
  {
    name: 'simulation',
    component: EcommerceSimulationView,
    prepare: pinia => {
      useEcommerceSimulationStore(pinia).current = {
        id: 1,
        scene_key: 'opening',
        scene_label: longChinese,
        segments: [
          { key: 'greeting', label: longChinese, text: longChinese }
        ],
        status: 'completed',
        scores: {
          pacing: 80,
          emotion: 70,
          interaction: 90,
          selling_point: 60
        },
        suggestions: {
          pacing: longChinese,
          emotion: longChinese,
          interaction: longChinese,
          selling_point: longChinese
        },
        total_score: 64,
        created_at: '2026-09-17T08:00:00+08:00',
        updated_at: '2026-09-17T08:00:00+08:00',
        completed_at: '2026-09-17T08:10:00+08:00'
      } as never
    }
  },
  {
    name: 'copy training',
    component: EcommerceCopyTrainingView,
    prepare: pinia => {
      useEcommerceCopyTrainingStore(pinia).current = {
        id: 1,
        product_type: 'food',
        scene: 'social_commerce',
        status: 'completed',
        case: {
          copy_text: longChinese,
          is_teaching_case: true,
          defect_categories: [longChinese, longChinese]
        },
        learner_critique: longChinese,
        reference: {
          reference_critique: longChinese,
          consistency_score: 67,
          reason: longChinese
        },
        optimized_prompt: longChinese,
        revised_copy: longChinese,
        optimization: {
          differences: [longChinese, longChinese],
          optimization_score: 88,
          evidence: longChinese
        },
        created_at: '2026-09-17T08:00:00+08:00',
        updated_at: '2026-09-17T08:00:00+08:00',
        completed_at: '2026-09-17T08:10:00+08:00'
      } as never
    }
  },
  {
    name: 'store guidance',
    component: EcommerceStoreGuidanceView,
    prepare: pinia => {
      useEcommerceStoreGuidanceStore(pinia).current = {
        id: 1,
        store_type: longChinese,
        platform: 'taobao',
        style_preference: longChinese,
        plan: {
          home_layout: longChinese,
          color_scheme: longChinese,
          detail_structure: longChinese,
          navigation: longChinese
        },
        created_at: '2026-09-17T08:00:00+08:00'
      } as never
    }
  },
  {
    name: 'customer service',
    component: EcommerceCustomerServiceView,
    prepare: pinia => {
      useEcommerceCustomerServiceStore(pinia).replaceSession({
        id: 1,
        scenario_key: 'after_sales',
        scenario_label: longChinese,
        goal_criteria: [longChinese, longChinese],
        status: 'completed',
        end_suggested: true,
        turns: [
          {
            id: 1,
            turn_no: 1,
            customer_message: longChinese,
            student_reply: longChinese,
            analysis: {
              problem: longChinese,
              evidence: longChinese,
              suggestion: longChinese,
              criteria: {
                [longChinese]: true,
                [longChinese + '另一项']: false
              },
              goal_status: 'reached'
            },
            created_at: '2026-09-17T08:00:00+08:00'
          }
        ],
        summary: {
          overall_performance: longChinese,
          main_problems: longChinese,
          prioritized_improvements: longChinese,
          goal_completion: longChinese
        },
        confirmed_at: '2026-09-17T08:10:00+08:00',
        created_at: '2026-09-17T08:00:00+08:00',
        updated_at: '2026-09-17T08:10:00+08:00',
        completed_at: '2026-09-17T08:10:00+08:00'
      } as never)
    }
  },
  {
    name: 'courses',
    component: EcommerceCoursesView,
    prepare: async pinia => {
      const store = useCourseLearningStore(pinia)
      store.courses = [
        {
          id: 1,
          title: longChinese,
          summary: longChinese,
          teacher_name: longChinese,
          published_at: '2026-09-17T08:00:00+08:00',
          duration_seconds: 600,
          direction: 'ecommerce',
          status: 'published',
          tag_ids: [1, 2]
        }
      ] as never
      store.recommendations = []
      store.progressByCourse = {
        1: {
          course_id: 1,
          duration_seconds: 600,
          furthest_position_seconds: 480,
          resume_position_seconds: 480,
          progress_percent: 80,
          watched_seconds: 480,
          completed_at: '2026-09-17T08:10:00+08:00',
          last_viewed_at: '2026-09-17T08:10:00+08:00'
        }
      } as never
      await nextTick()
    }
  }
]

describe('ecommerce responsive CSS contracts', () => {
  // jsdom does not calculate layout; real overflow and overlap remain browser acceptance checks.
  it('declares explicit containment, collapse and wrapping contracts', () => {
    expect(cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-home')).toContain(
      'min-width: 0'
    )
    expect(cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-home')).toContain(
      'overflow-x: clip'
    )
    expect(cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-home')).toContain(
      'min-height: 100svh'
    )
    expect(
      cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-home__main')
    ).not.toContain('min-height')
    expect(
      cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-home__intro p')
    ).toContain('line-break: strict')
    expect(
      cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-home__intro p')
    ).toContain('text-wrap: pretty')
    expect(
      cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-home__intro p')
    ).toContain('word-break: keep-all')
    expect(
      cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-home__grid')
    ).toContain('repeat(auto-fit, minmax(250px, 1fr))')
    expect(
      cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-home__grid')
    ).toContain('gap: 10px')
    expect(
      cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-home__grid')
    ).not.toContain('background: var(--ark-line)')
    expect(
      cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-card')
    ).toContain('grid-template-columns: auto minmax(0, 1fr) auto')
    expect(
      cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-card')
    ).toContain('border: 1px solid var(--ark-line-strong)')
    expect(
      cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-card__body')
    ).toContain('min-width: 0')
    expect(
      cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-card__body strong')
    ).toContain('word-break: keep-all')
    expect(
      cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-card__body small')
    ).toContain('line-break: strict')
    expect(
      cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-card__body small')
    ).toContain('text-wrap: pretty')
    expect(
      cssRule(ecommerceTrainingHomeSource, '.ecommerce-training-card__body small')
    ).not.toContain('word-break: keep-all')
    expect(
      cssRule(
        mediaBlock(ecommerceTrainingHomeSource, 640),
        '.ecommerce-training-home__grid'
      )
    ).toContain('grid-template-columns: minmax(0, 1fr)')
    expect(
      cssRule(
        mediaBlock(ecommerceTrainingHomeSource, 640),
        '.ecommerce-training-home__main'
      )
    ).toContain('padding: 32px 14px 48px')

    const liveScriptMobile = mediaBlock(ecommerceLiveScriptSource, 900)
    const liveScriptTight = mediaBlock(ecommerceLiveScriptSource, 540)
    expect(cssRule(ecommerceLiveScriptSource, '.live-script-page')).toContain(
      'min-width: 0'
    )
    expect(cssRule(ecommerceLiveScriptSource, '.live-script-page')).toContain(
      'overflow-x: clip'
    )
    expect(cssRule(liveScriptMobile, '.workspace')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(ecommerceLiveScriptSource, '.version-meta')).toContain(
      'flex-wrap: wrap'
    )
    expect(cssRule(ecommerceLiveScriptSource, '.version-meta > *')).toContain(
      'min-width: 0'
    )
    expect(cssRule(ecommerceLiveScriptSource, '.version-meta > *')).toContain(
      'overflow-wrap: anywhere'
    )
    expect(cssRule(liveScriptTight, '.style-options')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(liveScriptTight, '.history-panel button')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(ecommerceLiveScriptSource, '.output-panel')).toContain(
      'min-height: clamp(180px, 24svh, 300px)'
    )

    const simulationMobile = mediaBlock(ecommerceSimulationSource, 900)
    const simulationTight = mediaBlock(ecommerceSimulationSource, 560)
    expect(cssRule(ecommerceSimulationSource, '.simulation-page')).toContain(
      'min-width: 0'
    )
    expect(cssRule(ecommerceSimulationSource, '.simulation-page')).toContain(
      'overflow-x: clip'
    )
    expect(cssRule(simulationMobile, '.workspace')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(simulationTight, '.scene-panel ul')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(simulationTight, '.scene-heading')).toContain(
      'flex-direction: column'
    )
    expect(cssRule(simulationTight, '.score-row')).toContain(
      'grid-template-columns: minmax(0, 1fr) auto'
    )
    expect(cssRule(ecommerceSimulationSource, '.training-panel')).toContain(
      'min-height: clamp(200px, 28svh, 340px)'
    )
    expect(
      cssRule(ecommerceSimulationSource, '.scene-panel button span')
    ).toContain('overflow-wrap: anywhere')

    const copyTrainingMobile = mediaBlock(ecommerceCopyTrainingSource, 760)
    const copyTrainingTight = mediaBlock(ecommerceCopyTrainingSource, 540)
    expect(cssRule(ecommerceCopyTrainingSource, '.copy-training-page')).toContain(
      'min-width: 0'
    )
    expect(cssRule(ecommerceCopyTrainingSource, '.copy-training-page')).toContain(
      'overflow-x: clip'
    )
    expect(cssRule(copyTrainingMobile, '.selection-form')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(copyTrainingMobile, '.comparison-grid')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(copyTrainingMobile, '.score-strip')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(copyTrainingTight, '.panel-heading')).toContain(
      'flex-wrap: wrap'
    )
    expect(cssRule(ecommerceCopyTrainingSource, '.case-copy')).toContain(
      'overflow-wrap: anywhere'
    )

    const storeGuidanceMobile = mediaBlock(ecommerceStoreGuidanceSource, 900)
    const storeGuidanceTight = mediaBlock(ecommerceStoreGuidanceSource, 640)
    expect(cssRule(ecommerceStoreGuidanceSource, '.store-guidance-page')).toContain(
      'min-width: 0'
    )
    expect(cssRule(ecommerceStoreGuidanceSource, '.store-guidance-page')).toContain(
      'overflow-x: clip'
    )
    expect(cssRule(storeGuidanceMobile, '.workspace')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(ecommerceStoreGuidanceSource, '.page-kicker')).toContain(
      'color: var(--ark-signal)'
    )
    expect(cssRule(ecommerceStoreGuidanceSource, '.output-panel')).toContain(
      'min-height: clamp(280px, 42svh, 400px)'
    )
    expect(cssRule(ecommerceStoreGuidanceSource, '.current-inputs')).toContain(
      'flex-wrap: wrap'
    )
    expect(cssRule(ecommerceStoreGuidanceSource, '.plan-sections p')).toContain(
      'overflow-wrap: anywhere'
    )
    expect(cssRule(storeGuidanceTight, '.history-panel button')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )

    const customerServiceTablet = mediaBlock(ecommerceCustomerServiceSource, 1120)
    const customerServiceMobile = mediaBlock(ecommerceCustomerServiceSource, 760)
    expect(cssRule(ecommerceCustomerServiceSource, '.customer-service-page')).toContain(
      'min-width: 0'
    )
    expect(cssRule(ecommerceCustomerServiceSource, '.customer-service-page')).toContain(
      'overflow-x: clip'
    )
    expect(cssRule(customerServiceTablet, '.scenario-grid')).toContain(
      'grid-template-columns: repeat(3, minmax(0, 1fr))'
    )
    expect(cssRule(customerServiceMobile, '.scenario-grid')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(customerServiceMobile, '.turn-analysis dl')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(customerServiceMobile, '.summary-grid')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(ecommerceCustomerServiceSource, '.page-kicker')).toContain(
      'color: var(--ark-signal)'
    )
    expect(cssRule(ecommerceCustomerServiceSource, '.page-heading h1')).toContain(
      'text-wrap: balance'
    )
    expect(
      cssRule(ecommerceCustomerServiceSource, '.page-heading > p:last-child')
    ).toContain('line-break: strict')
    expect(
      cssRule(ecommerceCustomerServiceSource, '.page-heading > p:last-child')
    ).toContain('text-wrap: pretty')
    expect(
      cssRule(ecommerceCustomerServiceSource, '.page-heading > p:last-child')
    ).toContain('word-break: keep-all')
    expect(
      cssRule(ecommerceCustomerServiceSource, '.page-heading__nowrap')
    ).toContain('white-space: nowrap')
    expect(cssRule(ecommerceCustomerServiceSource, '.message p')).toContain(
      'overflow-wrap: anywhere'
    )
    expect(cssRule(ecommerceCustomerServiceSource, '.goal-criteria')).toContain(
      'flex-wrap: wrap'
    )

    const coursesMobile = mediaBlock(courseLearningPanelSource, 760)
    expect(cssRule(courseLearningPanelSource, '.agri-courses-page')).toContain(
      'min-width: 0'
    )
    expect(cssRule(courseLearningPanelSource, '.agri-courses-page')).toContain(
      'overflow-x: clip'
    )
    expect(cssRule(coursesMobile, '.recommendation-list')).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(courseLearningPanelSource, '.recommendation-list')).toContain(
      'repeat(auto-fit, minmax(min(100%, 240px), 1fr))'
    )
    expect(courseLearningPanelSource).not.toContain(
      '.recommendation-item:nth-child(3n)'
    )
    expect(cssRule(courseLearningPanelSource, '.course-card')).toContain(
      'min-width: 0'
    )
    expect(cssRule(courseLearningPanelSource, '.course-card__summary')).toContain(
      'overflow-wrap: anywhere'
    )
    expect(cssRule(courseLearningPanelSource, '.course-card__summary')).toContain(
      'text-wrap: balance'
    )
    expect(cssRule(courseLearningPanelSource, '.course-card__summary')).toContain(
      'line-break: strict'
    )
    expect(cssRule(courseLearningPanelSource, '.course-card__summary')).toContain(
      'word-break: keep-all'
    )
    expect(
      cssRule(courseLearningPanelSource, '.agri-courses-heading__nowrap')
    ).toContain('white-space: nowrap')
    expect(cssRule(courseLearningPanelSource, '.agri-courses-heading p')).toContain(
      'line-break: strict'
    )
    expect(cssRule(courseLearningPanelSource, '.agri-courses-heading p')).toContain(
      'word-break: keep-all'
    )
    expect(
      cssRule(courseLearningPanelSource, '.section-heading span')
    ).toContain('color: var(--ark-paper)')
    expect(
      cssRule(courseLearningPanelSource, '.quiz-panel__head span')
    ).toContain('color: var(--ark-paper)')
    expect(cssRule(courseLearningPanelSource, '.course-card__index')).toContain(
      'color: var(--ark-paper)'
    )
    expect(cssRule(courseLearningPanelSource, '.course-card__meta dt')).toContain(
      'color: var(--ark-paper)'
    )
    expect(cssRule(courseLearningPanelSource, '.course-card__meta')).toContain(
      'flex-wrap: wrap'
    )
    expect(cssRule(courseLearningPanelSource, '.course-card__actions')).toContain(
      'flex-wrap: wrap'
    )
    expect(cssRule(courseLearningPanelSource, '.course-progress progress')).toContain(
      'border: 1px solid var(--ark-line-strong)'
    )
    expect(
      cssRule(courseLearningPanelSource, '.course-card__actions button:disabled')
    ).toContain('color: var(--ark-muted)')
    expect(cssRule(courseLearningPanelSource, '.course-card__actions small')).toContain(
      'flex: 1 0 100%'
    )
    expect(cssRule(courseLearningPanelSource, '.recommendation-item p')).toContain(
      'text-wrap: balance'
    )
    expect(cssRule(coursesMobile, '.course-card__head')).toContain(
      'flex-direction: column'
    )
    expect(cssRule(coursesMobile, '.quiz-submit')).toContain('width: 100%')
    expect(cssRule(courseLearningPanelSource, '.quiz-submit:disabled')).toContain(
      'background: var(--ark-surface-2)'
    )
    expect(cssRule(courseLearningPanelSource, '.quiz-submit:disabled')).toContain(
      'color: var(--ark-paper)'
    )
    expect(cssRule(courseLearningPanelSource, '.quiz-submit:disabled')).toContain(
      'opacity: 1'
    )

    const navEdge = mediaBlock(ecommerceTrainingNavSource, 900)
    const navMobile = mediaBlock(ecommerceTrainingNavSource, 640)
    expect(cssRule(ecommerceTrainingNavSource, '.ecommerce-training-nav')).toContain(
      'position: relative'
    )
    expect(
      cssRule(ecommerceTrainingNavSource, '.ecommerce-training-nav__inner')
    ).toContain('overflow-x: auto')
    expect(
      cssRule(ecommerceTrainingNavSource, '.ecommerce-training-nav__inner')
    ).toContain('scrollbar-width: thin')
    expect(
      cssRule(
        ecommerceTrainingNavSource,
        '.ecommerce-training-nav__inner::-webkit-scrollbar'
      )
    ).toContain('height: 6px')
    expect(cssRule(ecommerceTrainingNavSource, '.ecommerce-training-nav a')).toContain(
      'flex: 0 0 auto'
    )
    expect(cssRule(ecommerceTrainingNavSource, '.ecommerce-training-nav a')).toContain(
      'white-space: nowrap'
    )
    expect(
      cssRule(ecommerceTrainingNavSource, '.ecommerce-training-nav::before')
    ).toContain('linear-gradient(to right, var(--ark-surface-0), transparent)')
    expect(
      cssRule(ecommerceTrainingNavSource, '.ecommerce-training-nav::after')
    ).toContain('linear-gradient(to left, var(--ark-surface-0), transparent)')
    expect(cssRule(navEdge, '.ecommerce-training-nav::before')).toContain(
      'width: 18px'
    )
    expect(cssRule(navMobile, '.ecommerce-training-nav__inner')).toContain(
      'padding-inline: 24px'
    )
  })
})

describe.each(sessionCases)('$name session expiry', ({ path, component }) => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses the existing session-expired handler without exposing provider errors', async () => {
    const auth = useAuthStore()
    auth.sessionState = 'active'
    auth.user = {
      id: 1,
      username: 'student01',
      name: '林晓',
      role: 'student'
    }
    auth.defaultPath = '/student'

    const router = testRouter()
    await router.push(path)
    await router.isReady()

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        headers: new Headers({ 'Content-Type': 'application/json' }),
        json: async () => ({
          success: false,
          message: 'raw provider credential error',
          redirect: '/login'
        })
      })
    )

    const stopHandler = installSessionExpiredHandler(auth, router)
    let wrapper: ReturnType<typeof mount> | undefined
    try {
      wrapper = mount(component, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()
    } finally {
      stopHandler()
    }

    expect(auth.sessionState).toBe('anonymous')
    expect(auth.user).toBeNull()
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe(path)
    expect(wrapper?.text()).not.toContain('raw provider credential error')
  })
})

describe.each(widths)('ecommerce acceptance at %dpx', width => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async input => {
        const path = String(input)
        if (path.endsWith('/courses')) {
          return successResponse({ success: true, courses: [] })
        }
        if (path.endsWith('/recommendations')) {
          return successResponse({ success: true, courses: [] })
        }
        if (path.includes('/simulations/scenes')) {
          return successResponse({ success: true, scenes: [] })
        }
        if (path.includes('/simulations')) {
          return successResponse({ success: true, trainings: [] })
        }
        if (path.includes('/copy-training/catalog')) {
          return successResponse({
            success: true,
            catalog: {
              product_types: ['food'],
              scenes: ['social_commerce'],
              defect_categories: ['missing_action']
            }
          })
        }
        if (path.includes('/copy-training')) {
          return successResponse({ success: true, sessions: [] })
        }
        if (path.includes('/customer-service/scenarios')) {
          return successResponse({ success: true, scenarios: [] })
        }
        if (path.includes('/customer-service/sessions')) {
          return successResponse({ success: true, sessions: [] })
        }
        if (path.includes('/store-plans')) {
          return successResponse({ success: true, plans: [] })
        }
        if (path.includes('/live-scripts')) {
          return successResponse({ success: true, versions: [] })
        }
        throw new Error(`Unexpected API request: ${path}`)
      })
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it.each(responsiveCases)(
    'renders long Chinese content for $name without English AI errors',
    async ({ component, prepare }) => {
      vi.stubGlobal('innerWidth', width)
      const pinia = createPinia()
      setActivePinia(pinia)
      const wrapper = mount(component, {
        global: {
          plugins: [pinia, testRouter()]
        }
      })
      await flushPromises()
      await prepare(pinia)
      await nextTick()

      expect(wrapper.text()).toContain(longChinese)
      expect(wrapper.text()).not.toContain('AI service unavailable')
    }
  )
})
