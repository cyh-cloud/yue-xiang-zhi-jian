import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, type Component } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { installSessionExpiredHandler } from '@/api/session-expiry'
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
    'keeps $name free of horizontal overflow and English AI errors',
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
      expect(wrapper.find('[data-test="horizontal-overflow"]').exists()).toBe(
        false
      )
      expect(wrapper.text()).not.toContain('AI service unavailable')
    }
  )
})
