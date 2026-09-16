import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type { SimulationScene, SimulationTraining } from '@/api/types'

import { useEcommerceSimulationStore } from './ecommerceSimulation'

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
  }
]

function training(
  patch: Partial<SimulationTraining> = {}
): SimulationTraining {
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
    completed_at: null,
    ...patch
  }
}

function completedTraining(): SimulationTraining {
  return training({
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
  })
}

describe('ecommerceSimulation store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('loads scenes in backend order and starts exactly one selected scene', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        scenes
      } as never)
      .mockResolvedValueOnce({
        success: true,
        training: training()
      } as never)
    const store = useEcommerceSimulationStore()

    await store.loadScenes()
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/ecommerce-training/simulations/scenes'
    )
    expect(store.scenes.map(scene => scene.key)).toEqual([
      'opening',
      'product_intro'
    ])
    expect(store.scenes[0].segments.map(segment => segment.key)).toEqual([
      'greeting',
      'hook',
      'audience_call'
    ])

    expect(await store.start('opening')).toBe(true)
    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      '/api/ecommerce-training/simulations',
      {
        method: 'POST',
        body: JSON.stringify({ scene_key: 'opening' })
      }
    )
    expect(store.current?.scene_key).toBe('opening')
    expect(store.current?.segments.map(segment => segment.key)).toEqual([
      'greeting',
      'hook',
      'audience_call'
    ])
  })

  it('saves each segment before enabling scoring', async () => {
    const store = useEcommerceSimulationStore()
    store.current = training()
    store.drafts = {
      greeting: '欢迎来到直播间',
      hook: '今天带来广东荔枝干',
      audience_call: ''
    }

    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        training: training({
          segments: [
            { key: 'greeting', label: '欢迎问候', text: '欢迎来到直播间' },
            { key: 'hook', label: '利益吸引', text: '' },
            { key: 'audience_call', label: '观众召集', text: '' }
          ]
        })
      } as never)
      .mockResolvedValueOnce({
        success: true,
        training: training({
          segments: [
            { key: 'greeting', label: '欢迎问候', text: '欢迎来到直播间' },
            {
              key: 'hook',
              label: '利益吸引',
              text: '今天带来广东荔枝干'
            },
            { key: 'audience_call', label: '观众召集', text: '' }
          ]
        })
      } as never)
      .mockResolvedValueOnce({
        success: true,
        training: training({
          segments: [
            { key: 'greeting', label: '欢迎问候', text: '欢迎来到直播间' },
            {
              key: 'hook',
              label: '利益吸引',
              text: '今天带来广东荔枝干'
            },
            {
              key: 'audience_call',
              label: '观众召集',
              text: '想要的扣一'
            }
          ]
        })
      } as never)

    expect(store.canScore).toBe(false)
    expect(await store.saveSegment('greeting', '欢迎来到直播间')).toBe(true)
    expect(store.canScore).toBe(false)
    expect(await store.saveSegment('hook', '今天带来广东荔枝干')).toBe(true)
    expect(store.canScore).toBe(false)
    expect(await store.saveSegment('audience_call', '想要的扣一')).toBe(true)
    expect(store.canScore).toBe(true)

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/ecommerce-training/simulations/1/segments/greeting',
      {
        method: 'PUT',
        body: JSON.stringify({ text: '欢迎来到直播间' })
      }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/ecommerce-training/simulations/1/segments/audience_call',
      {
        method: 'PUT',
        body: JSON.stringify({ text: '想要的扣一' })
      }
    )
  })

  it('uses the backend score and total without recalculating them', async () => {
    const scored = completedTraining()
    const store = useEcommerceSimulationStore()
    store.current = training({
      segments: scored.segments
    })
    store.drafts = Object.fromEntries(
      scored.segments.map(segment => [segment.key, segment.text])
    )
    store.savedSegments = {
      greeting: true,
      hook: true,
      audience_call: true
    }
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      training: scored
    } as never)

    expect(await store.score()).toBe(true)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/ecommerce-training/simulations/1/score',
      { method: 'POST' }
    )
    expect(store.current?.scores).toEqual(scored.scores)
    expect(store.current?.total_score).toBe(64)
    expect(store.current?.status).toBe('completed')
  })

  it('keeps drafts, saved state, and current training when scoring fails, then retries', async () => {
    const scored = completedTraining()
    const store = useEcommerceSimulationStore()
    store.current = training({ segments: scored.segments })
    store.drafts = Object.fromEntries(
      scored.segments.map(segment => [segment.key, segment.text])
    )
    store.savedSegments = {
      greeting: true,
      hook: true,
      audience_call: true
    }
    const original = store.current
    mockedApiFetch
      .mockRejectedValueOnce(new ApiError('provider timeout', 503))
      .mockResolvedValueOnce({
        success: true,
        training: scored
      } as never)

    expect(await store.score()).toBe(false)
    expect(store.error).toBe('AI 服务暂时不可用')
    expect(store.current).toEqual(original)
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
    expect(store.canScore).toBe(true)

    expect(await store.score()).toBe(true)
    expect(mockedApiFetch).toHaveBeenCalledTimes(2)
    expect(store.error).toBe('')
    expect(store.current?.total_score).toBe(64)
  })

  it('loads history and opens a historical training record', async () => {
    const scored = completedTraining()
    const store = useEcommerceSimulationStore()
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        trainings: [scored]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        training: scored
      } as never)

    await store.loadHistory()
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/ecommerce-training/simulations'
    )
    expect(store.history).toEqual([scored])

    expect(await store.openTraining(1)).toBe(true)
    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      '/api/ecommerce-training/simulations/1'
    )
    expect(store.current?.status).toBe('completed')
    expect(store.canScore).toBe(false)
    expect(store.drafts).toEqual({
      greeting: '欢迎来到直播间',
      hook: '今天带来广东荔枝干',
      audience_call: '想要的扣一'
    })
  })
})
