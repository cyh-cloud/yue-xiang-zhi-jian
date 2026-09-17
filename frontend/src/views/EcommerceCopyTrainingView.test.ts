import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type { CopyTrainingSession } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import EcommerceTrainingNav from '@/components/EcommerceTrainingNav.vue'
import { useEcommerceCopyTrainingStore } from '@/stores/ecommerceCopyTraining'

import EcommerceCopyTrainingView from './EcommerceCopyTrainingView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const catalog = {
  product_types: ['food', 'craft', 'agricultural_product'],
  scenes: ['social_commerce', 'product_page', 'live_room'],
  defect_categories: [
    'missing_key_information',
    'missing_action'
  ]
}

function session(
  status: CopyTrainingSession['status'],
  patch: Partial<CopyTrainingSession> = {}
): CopyTrainingSession {
  return {
    id: 1,
    product_type: 'food',
    scene: 'social_commerce',
    status,
    case: {
      copy_text: '荔枝干好吃，快来买。',
      is_teaching_case: true
    },
    learner_critique: null,
    reference: null,
    optimized_prompt: null,
    revised_copy: null,
    optimization: null,
    created_at: '2026-09-17T01:00:00+00:00',
    updated_at: '2026-09-17T01:00:00+00:00',
    completed_at: null,
    ...patch
  }
}

function createTestRouter() {
  const paths = [
    '/',
    '/login',
    '/register',
    '/student/ecommerce-training',
    '/student/ecommerce-training/live-script',
    '/student/ecommerce-training/simulation',
    '/student/ecommerce-training/copy-training',
    '/student/ecommerce-training/store-guidance',
    '/student/ecommerce-training/customer-service',
    '/student/ecommerce-training/courses'
  ]

  return createRouter({
    history: createMemoryHistory(),
    routes: paths.map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}

function mountView() {
  const pinia = createPinia()
  const wrapper = mount(EcommerceCopyTrainingView, {
    global: {
      plugins: [pinia, createTestRouter()]
    }
  })
  return { pinia, wrapper }
}

function installApiHarness() {
  let current: CopyTrainingSession | null = null

  mockedApiFetch.mockImplementation(async (url, options) => {
    if (url === '/api/ecommerce-training/copy-training/catalog') {
      return { success: true, catalog } as never
    }
    if (
      url === '/api/ecommerce-training/copy-training' &&
      options?.method === 'POST'
    ) {
      current = session('case_ready')
      return { success: true, session: current } as never
    }
    if (
      url === '/api/ecommerce-training/copy-training' &&
      options?.method !== 'POST'
    ) {
      return {
        success: true,
        sessions: current ? [current] : []
      } as never
    }
    if (url === '/api/ecommerce-training/copy-training/1/critique') {
      current = session('critique_ready', {
        case: {
          copy_text: '荔枝干好吃，快来买。',
          is_teaching_case: true,
          defect_categories: [
            'missing_key_information',
            'missing_action'
          ]
        },
        learner_critique: '缺少规格和行动指令',
        reference: {
          reference_critique: '没有说明规格、价格和购买方式。',
          consistency_score: 67,
          reason: '评判方向与参考一致，但覆盖的问题不完整。'
        }
      })
      return { success: true, session: current } as never
    }
    if (url === '/api/ecommerce-training/copy-training/1/copy') {
      current = session('copy_ready', {
        case: {
          copy_text: '荔枝干好吃，快来买。',
          is_teaching_case: true,
          defect_categories: [
            'missing_key_information',
            'missing_action'
          ]
        },
        learner_critique: '缺少规格和行动指令',
        reference: {
          reference_critique: '没有说明规格、价格和购买方式。',
          consistency_score: 67,
          reason: '评判方向与参考一致，但覆盖的问题不完整。'
        },
        optimized_prompt: '补充规格、价格和行动指令',
        revised_copy: '广东荔枝干 250g，限时 39.9 元，点击下单。'
      })
      return { success: true, session: current } as never
    }
    if (url === '/api/ecommerce-training/copy-training/1/optimization') {
      current = session('completed', {
        case: {
          copy_text: '荔枝干好吃，快来买。',
          is_teaching_case: true,
          defect_categories: [
            'missing_key_information',
            'missing_action'
          ]
        },
        learner_critique: '缺少规格和行动指令',
        reference: {
          reference_critique: '没有说明规格、价格和购买方式。',
          consistency_score: 67,
          reason: '评判方向与参考一致，但覆盖的问题不完整。'
        },
        optimized_prompt: '补充规格、价格和行动指令',
        revised_copy: '广东荔枝干 250g，限时 39.9 元，点击下单。',
        optimization: {
          differences: ['补充了 250g 规格', '增加了明确下单指令'],
          optimization_score: 88,
          evidence: '新旧文案均包含可见规格和行动信息，优化项可验证。'
        },
        completed_at: '2026-09-17T01:10:00+00:00'
      })
      return { success: true, session: current } as never
    }
    if (url === '/api/ecommerce-training/copy-training/1') {
      return { success: true, session: current } as never
    }
    throw new Error(`Unexpected API call: ${url}`)
  })
}

describe('EcommerceCopyTrainingView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    installApiHarness()
  })

  it('renders the five visible stages and keeps revised-copy generation inside stage five', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()

    expect(wrapper.findComponent(AppHeader).exists()).toBe(true)
    expect(wrapper.findComponent(EcommerceTrainingNav).exists()).toBe(true)
    expect(
      wrapper.get('[data-test="copy-training-stage-selection"]').text()
    ).toContain('选择商品与场景')
    expect(
      wrapper
        .findAll('[data-test="copy-training-product-type"] option')
        .map(option => option.attributes('value'))
    ).toEqual(catalog.product_types)
    expect(
      wrapper
        .findAll('[data-test="copy-training-scene"] option')
        .map(option => option.attributes('value'))
    ).toEqual(catalog.scenes)
    expect(wrapper.text()).not.toContain('生成成品文案')

    await wrapper.get('[data-test="copy-training-start"]').trigger('click')
    await flushPromises()

    expect(
      wrapper.get('[data-test="copy-training-stage-case"]').text()
    ).toContain('教学案例')
    expect(
      wrapper.get('[data-test="copy-training-case-copy"]').text()
    ).toContain('荔枝干好吃')
    expect(
      wrapper.get('[data-test="copy-training-stage-critique"]').text()
    ).toContain('学员评判')
    expect(
      wrapper.find('[data-test="copy-training-stage-comparison"]').exists()
    ).toBe(false)
    expect(
      wrapper.find('[data-test="copy-training-stage-optimization"]').exists()
    ).toBe(false)

    await wrapper
      .get('[data-test="copy-training-critique"]')
      .setValue('缺少规格和行动指令')
    await wrapper
      .get('[data-test="copy-training-submit-critique"]')
      .trigger('click')
    await flushPromises()

    const comparison = wrapper.get(
      '[data-test="copy-training-comparison"]'
    )
    expect(comparison.text()).toContain('学员评判')
    expect(comparison.text()).toContain('缺少规格和行动指令')
    expect(comparison.text()).toContain('参考评判')
    expect(comparison.text()).toContain('没有说明规格、价格和购买方式。')
    expect(
      wrapper.get('[data-test="copy-training-consistency-score"]').text()
    ).toContain('67')
    expect(
      wrapper.get('[data-test="copy-training-consistency-reason"]').text()
    ).toContain('评判方向与参考一致')

    const optimizationStage = wrapper.get(
      '[data-test="copy-training-stage-optimization"]'
    )
    expect(optimizationStage.text()).toContain('优化提示词')
    expect(
      wrapper.get('[data-test="copy-training-generate-revised"]').attributes()
    ).toHaveProperty('disabled')
    expect(
      mockedApiFetch.mock.calls.some(
        ([url]) =>
          url === '/api/ecommerce-training/copy-training/1/copy'
      )
    ).toBe(false)

    await wrapper
      .get('[data-test="copy-training-optimized-prompt"]')
      .setValue('补充规格、价格和行动指令')
    await wrapper
      .get('[data-test="copy-training-generate-revised"]')
      .trigger('click')
    await flushPromises()

    expect(
      wrapper.get('[data-test="copy-training-old-copy"]').text()
    ).toContain('荔枝干好吃')
    expect(
      wrapper.get('[data-test="copy-training-new-copy"]').text()
    ).toContain('250g')
    expect(
      wrapper.find('[data-test="copy-training-optimization-result"]').exists()
    ).toBe(false)

    await wrapper
      .get('[data-test="copy-training-generate-optimization"]')
      .trigger('click')
    await flushPromises()

    expect(
      wrapper.get('[data-test="copy-training-optimization-score"]').text()
    ).toContain('88')
    expect(
      wrapper.get('[data-test="copy-training-differences"]').text()
    ).toContain('明确下单指令')
    expect(
      wrapper.get('[data-test="copy-training-optimization-evidence"]').text()
    ).toContain('可验证')

    const store = useEcommerceCopyTrainingStore(pinia)
    expect(store.current?.status).toBe('completed')
    expect(store.current?.reference?.consistency_score).toBe(67)
    expect(store.current?.optimization?.optimization_score).toBe(88)
    expect(wrapper.text()).not.toMatch(/SSE|流式|本地兜底/i)
  })

  it('shows the exact AI failure and preserves the current stage and input', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()

    await wrapper.get('[data-test="copy-training-start"]').trigger('click')
    await flushPromises()
    await wrapper
      .get('[data-test="copy-training-critique"]')
      .setValue('缺少规格和行动指令')

    mockedApiFetch.mockRejectedValueOnce(
      new Error('provider timeout') as never
    )
    await wrapper
      .get('[data-test="copy-training-submit-critique"]')
      .trigger('click')
    await flushPromises()

    const store = useEcommerceCopyTrainingStore(pinia)
    expect(wrapper.get('[aria-live="assertive"]').text()).toBe(
      'AI 服务暂时不可用'
    )
    expect(store.current?.status).toBe('case_ready')
    expect(
      wrapper.get('[data-test="copy-training-case-copy"]').text()
    ).toContain('荔枝干好吃')
    expect(
      wrapper.get<HTMLTextAreaElement>(
        '[data-test="copy-training-critique"]'
      ).element.value
    ).toBe('缺少规格和行动指令')
    expect(
      wrapper.find('[data-test="copy-training-stage-comparison"]').exists()
    ).toBe(false)
    expect(store.current?.reference).toBeNull()
  })
})
