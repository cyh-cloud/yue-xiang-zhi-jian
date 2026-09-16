import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError, apiFetch } from '@/api/client'
import type { SimulationScene, SimulationTraining } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import EcommerceTrainingNav from '@/components/EcommerceTrainingNav.vue'
import { useEcommerceSimulationStore } from '@/stores/ecommerceSimulation'

import EcommerceSimulationView from './EcommerceSimulationView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const scenes: SimulationScene[] = [
  {
    key: 'opening',
    label: '开场白',
    segments: [
      { key: 'greeting', label: '欢迎问候' },
      { key: 'hook', label: '利益吸引' },
      { key: 'audience_call', label: '观众召集' }
    ]
  },
  {
    key: 'product_intro',
    label: '产品介绍',
    segments: [
      { key: 'feature', label: '核心卖点' },
      { key: 'proof', label: '信任证明' }
    ]
  },
  {
    key: 'interaction',
    label: '互动引导',
    segments: [{ key: 'question', label: '提问互动' }]
  },
  {
    key: 'closing',
    label: '促单话术',
    segments: [{ key: 'offer', label: '优惠促单' }]
  },
  {
    key: 'objection',
    label: '异议处理',
    segments: [{ key: 'response', label: '异议回应' }]
  }
]

function draftTraining(): SimulationTraining {
  return {
    id: 1,
    scene_key: 'opening',
    scene_label: '开场白',
    segments: [
      { key: 'greeting', label: '欢迎问候', text: '' },
      { key: 'hook', label: '利益吸引', text: '' },
      { key: 'audience_call', label: '观众召集', text: '' }
    ],
    status: 'draft',
    scores: null,
    suggestions: null,
    total_score: null,
    created_at: '2026-09-17T01:00:00+00:00',
    updated_at: '2026-09-17T01:00:00+00:00',
    completed_at: null
  }
}

function completedTraining(): SimulationTraining {
  return {
    ...draftTraining(),
    status: 'completed',
    segments: [
      { key: 'greeting', label: '欢迎问候', text: '欢迎来到直播间' },
      { key: 'hook', label: '利益吸引', text: '今天带来广东荔枝干' },
      { key: 'audience_call', label: '观众召集', text: '想要的扣一' }
    ],
    scores: {
      pacing: 80,
      emotion: 70,
      interaction: 90,
      selling_point: 60
    },
    suggestions: {
      pacing: '适当停顿',
      emotion: '增强感染力',
      interaction: '增加提问',
      selling_point: '突出产地优势'
    },
    total_score: 64,
    completed_at: '2026-09-17T01:10:00+00:00'
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
  const wrapper = mount(EcommerceSimulationView, {
    global: {
      plugins: [pinia, createTestRouter()]
    }
  })
  return { pinia, wrapper }
}

function installApiHarness(
  training: () => SimulationTraining = draftTraining
) {
  let saved = training()

  mockedApiFetch.mockImplementation(async (url, options) => {
    if (url === '/api/ecommerce-training/simulations/scenes') {
      return { success: true, scenes } as never
    }
    if (url === '/api/ecommerce-training/simulations') {
      if (options?.method === 'POST') {
        saved = training()
        return { success: true, training: saved } as never
      }
      return { success: true, trainings: [] } as never
    }
    if (typeof url === 'string' && url.endsWith('/score')) {
      saved = completedTraining()
      return { success: true, training: saved } as never
    }
    if (typeof url === 'string' && url.includes('/segments/')) {
      const parts = url.split('/')
      const segmentKey = parts[parts.length - 1] ?? ''
      const body = JSON.parse(String(options?.body)) as { text: string }
      saved = {
        ...saved,
        segments: saved.segments.map(segment =>
          segment.key === segmentKey
            ? { ...segment, text: body.text }
            : segment
        )
      }
      return { success: true, training: saved } as never
    }
    if (typeof url === 'string' && /\/simulations\/\d+$/.test(url)) {
      return { success: true, training: saved } as never
    }
    throw new Error(`Unexpected API call: ${url}`)
  })
}

async function completeOpeningTraining(
  wrapper: ReturnType<typeof mountView>['wrapper']
) {
  await wrapper.get('[data-test="simulation-scene-opening"]').trigger('click')
  await flushPromises()

  const values = [
    ['greeting', '欢迎来到直播间'],
    ['hook', '今天带来广东荔枝干'],
    ['audience_call', '想要的扣一']
  ] as const
  for (const [key, value] of values) {
    await wrapper
      .get(`[data-test="simulation-segment-${key}"] textarea`)
      .setValue(value)
    await wrapper
      .get(`[data-test="simulation-save-${key}"]`)
      .trigger('click')
    await flushPromises()
  }
}

describe('EcommerceSimulationView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    installApiHarness()
  })

  it('renders five scene choices and one active scene with ordered segments', async () => {
    const { wrapper } = mountView()
    await flushPromises()

    expect(wrapper.findComponent(AppHeader).exists()).toBe(true)
    expect(wrapper.findComponent(EcommerceTrainingNav).exists()).toBe(true)
    expect(wrapper.findAll('[data-test="simulation-scene-option"]')).toHaveLength(
      5
    )

    await wrapper.get('[data-test="simulation-scene-opening"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="simulation-active-scene"]').text()).toContain(
      '开场白'
    )
    expect(
      wrapper
        .findAll('[data-test="simulation-segment"]')
        .map(segment => segment.get('h3').text())
    ).toEqual(['欢迎问候', '利益吸引', '观众召集'])
    expect(wrapper.findAll('textarea')).toHaveLength(3)
    expect(wrapper.findAll('[data-test^="simulation-save-"]')).toHaveLength(3)
  })

  it('requires every textarea to be saved before scoring is enabled', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()

    await completeOpeningTraining(wrapper)

    const store = useEcommerceSimulationStore(pinia)
    expect(store.canScore).toBe(true)
    expect(
      wrapper.get('[data-test="simulation-score"]').attributes()
    ).not.toHaveProperty('disabled')
  })

  it('renders four labeled dimensions and the backend total score', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    await completeOpeningTraining(wrapper)

    await wrapper.get('[data-test="simulation-score"]').trigger('click')
    await flushPromises()

    const store = useEcommerceSimulationStore(pinia)
    expect(store.current?.total_score).toBe(64)
    expect(
      wrapper
        .findAll('[data-test="simulation-score-row"]')
        .map(row => row.get('[data-test="simulation-score-label"]').text())
    ).toEqual(['语速节奏', '情绪感染力', '互动引导', '卖点突出'])
    expect(
      wrapper
        .findAll('[data-test="simulation-score-value"]')
        .map(value => value.text())
    ).toEqual(['80', '70', '90', '60'])
    expect(wrapper.get('[data-test="simulation-total-score"]').text()).toContain(
      '64'
    )
    expect(wrapper.get('[data-test="simulation-total-score"]').text()).not.toContain(
      '75'
    )
  })

  it('preserves drafts and saved segments on failure and allows retry', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    await completeOpeningTraining(wrapper)

    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('provider timeout', 503)
    )
    await wrapper.get('[data-test="simulation-score"]').trigger('click')
    await flushPromises()

    const store = useEcommerceSimulationStore(pinia)
    expect(wrapper.get('[aria-live="assertive"]').text()).toBe(
      'AI 服务暂时不可用'
    )
    expect(store.current?.status).toBe('draft')
    expect(store.drafts).toEqual({
      greeting: '欢迎来到直播间',
      hook: '今天带来广东荔枝干',
      audience_call: '想要的扣一'
    })
    expect(store.savedSegments).toEqual({
      greeting: true,
      hook: true,
      audience_call: true
    })
    expect(
      wrapper.get('[data-test="simulation-score"]').attributes()
    ).not.toHaveProperty('disabled')

    await wrapper.get('[data-test="simulation-score"]').trigger('click')
    await flushPromises()

    expect(store.current?.status).toBe('completed')
    expect(wrapper.get('[data-test="simulation-total-score"]').text()).toContain(
      '64'
    )
    expect(wrapper.text()).not.toMatch(/SSE|流式|本地兜底/i)
  })

  it('loads history and opens a completed training record', async () => {
    const scored = completedTraining()
    installApiHarness(() => scored)
    mockedApiFetch.mockImplementation(async (url, options) => {
      if (url === '/api/ecommerce-training/simulations/scenes') {
        return { success: true, scenes } as never
      }
      if (url === '/api/ecommerce-training/simulations') {
        return { success: true, trainings: [scored] } as never
      }
      if (url === '/api/ecommerce-training/simulations/1') {
        return { success: true, training: scored } as never
      }
      throw new Error(`Unexpected API call: ${url} ${options?.method ?? ''}`)
    })
    const { pinia, wrapper } = mountView()
    await flushPromises()

    expect(wrapper.get('[data-test="simulation-history"]').text()).toContain(
      '开场白'
    )
    await wrapper
      .get('[data-test="simulation-history-item-1"]')
      .trigger('click')
    await flushPromises()

    const store = useEcommerceSimulationStore(pinia)
    expect(store.current?.id).toBe(1)
    expect(wrapper.get('[data-test="simulation-total-score"]').text()).toContain(
      '64'
    )
  })
})
