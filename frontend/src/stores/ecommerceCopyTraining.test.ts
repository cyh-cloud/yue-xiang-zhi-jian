import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type { CopyTrainingSession } from '@/api/types'

import { useEcommerceCopyTrainingStore } from './ecommerceCopyTraining'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)
const AI_UNAVAILABLE_MESSAGE = 'AI 服务暂时不可用'

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

function critiqueReady(): CopyTrainingSession {
  return session('critique_ready', {
    case: {
      copy_text: '荔枝干好吃，快来买。',
      is_teaching_case: true,
      defect_categories: ['missing_key_information', 'missing_action']
    },
    learner_critique: '缺少规格和行动指令',
    reference: {
      reference_critique: '没有说明规格、价格和购买方式。',
      consistency_score: 67,
      reason: '评判方向与参考一致，但覆盖的问题不完整。'
    }
  })
}

function copyReady(): CopyTrainingSession {
  const critiqued = critiqueReady()
  return session('copy_ready', {
    case: critiqued.case,
    learner_critique: critiqued.learner_critique,
    reference: critiqued.reference,
    optimized_prompt: '补充规格、价格和行动指令',
    revised_copy: '广东荔枝干 250g，限时 39.9 元，点击下单。'
  })
}

function completed(): CopyTrainingSession {
  const revised = copyReady()
  return session('completed', {
    case: revised.case,
    learner_critique: revised.learner_critique,
    reference: revised.reference,
    optimized_prompt: revised.optimized_prompt,
    revised_copy: revised.revised_copy,
    optimization: {
      differences: ['补充了 250g 规格', '增加了明确下单指令'],
      optimization_score: 88,
      evidence: '新旧文案均包含可见规格和行动信息，优化项可验证。'
    },
    completed_at: '2026-09-17T01:10:00+00:00'
  })
}

describe('ecommerceCopyTraining store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('loads the catalog and exposes backend history through the history getter', async () => {
    const historical = completed()
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, catalog } as never)
      .mockResolvedValueOnce({
        success: true,
        sessions: [historical]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        session: historical
      } as never)
    const store = useEcommerceCopyTrainingStore()

    expect(await store.loadCatalog()).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/ecommerce-training/copy-training/catalog'
    )
    expect(store.catalog.product_types).toEqual(catalog.product_types)
    expect(store.productType).toBe('food')
    expect(store.scene).toBe('social_commerce')

    expect(await store.loadHistory()).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/ecommerce-training/copy-training'
    )
    expect(store.history).toEqual([historical])

    expect(await store.openSession(1)).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/ecommerce-training/copy-training/1'
    )
    expect(store.current).toEqual(historical)
  })

  it('runs all five stages and preserves authoritative backend scores and evidence', async () => {
    const caseReady = session('case_ready')
    const critiqued = critiqueReady()
    const revised = copyReady()
    const optimized = completed()
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, session: caseReady } as never)
      .mockResolvedValueOnce({ success: true, session: critiqued } as never)
      .mockResolvedValueOnce({ success: true, session: revised } as never)
      .mockResolvedValueOnce({ success: true, session: optimized } as never)
    const store = useEcommerceCopyTrainingStore()

    expect(
      await store.create('food', 'social_commerce')
    ).toBe(true)
    expect(store.current?.status).toBe('case_ready')
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/ecommerce-training/copy-training',
      {
        method: 'POST',
        body: JSON.stringify({
          product_type: 'food',
          scene: 'social_commerce'
        })
      }
    )

    expect(
      await store.submitCritique('缺少规格和行动指令')
    ).toBe(true)
    expect(store.current?.status).toBe('critique_ready')
    expect(store.current?.reference?.consistency_score).toBe(67)
    expect(store.current?.reference?.reason).toBe(
      critiqued.reference?.reason
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/ecommerce-training/copy-training/1/critique',
      {
        method: 'POST',
        body: JSON.stringify({ critique: '缺少规格和行动指令' })
      }
    )

    expect(
      await store.generateCopy('补充规格、价格和行动指令')
    ).toBe(true)
    expect(store.current?.status).toBe('copy_ready')
    expect(store.current?.revised_copy).toContain('250g')
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/ecommerce-training/copy-training/1/copy',
      {
        method: 'POST',
        body: JSON.stringify({
          optimized_prompt: '补充规格、价格和行动指令'
        })
      }
    )

    expect(await store.generateOptimization()).toBe(true)
    expect(store.current?.status).toBe('completed')
    expect(store.current?.optimization?.optimization_score).toBe(88)
    expect(store.current?.optimization?.evidence).toContain('可验证')
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      4,
      '/api/ecommerce-training/copy-training/1/optimization',
      { method: 'POST' }
    )
    expect(store.history[0]).toEqual(optimized)
  })

  it('rejects skipped stages without calling the API', async () => {
    const store = useEcommerceCopyTrainingStore()

    expect(await store.submitCritique('缺少行动指令')).toBe(false)
    expect(await store.generateCopy('补充行动指令')).toBe(false)
    expect(await store.generateOptimization()).toBe(false)
    expect(mockedApiFetch).not.toHaveBeenCalled()

    store.current = session('case_ready')
    expect(await store.generateCopy('补充行动指令')).toBe(false)
    expect(await store.generateOptimization()).toBe(false)
    expect(mockedApiFetch).not.toHaveBeenCalled()

    store.current = critiqueReady()
    expect(await store.generateOptimization()).toBe(false)
    expect(mockedApiFetch).not.toHaveBeenCalled()
  })

  it('keeps selection and all prior fields when case generation fails', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('provider timeout', 503)
    )
    const store = useEcommerceCopyTrainingStore()
    store.catalog = catalog
    store.productType = 'craft'
    store.scene = 'product_page'

    expect(await store.create('craft', 'product_page')).toBe(false)
    expect(store.error).toBe(AI_UNAVAILABLE_MESSAGE)
    expect(store.catalog).toEqual(catalog)
    expect(store.productType).toBe('craft')
    expect(store.scene).toBe('product_page')
    expect(store.current).toBeNull()
    expect(store.history).toEqual([])
  })

  it('keeps the case, critique draft, and history when reference critique fails', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('provider timeout', 503)
    )
    const before = session('case_ready')
    const store = useEcommerceCopyTrainingStore()
    store.current = before
    store.sessionHistory = [before]

    expect(
      await store.submitCritique('缺少规格和行动指令')
    ).toBe(false)
    expect(store.error).toBe(AI_UNAVAILABLE_MESSAGE)
    expect(store.current).toEqual(before)
    expect(store.history).toEqual([before])
    expect(store.critiqueDraft).toBe('缺少规格和行动指令')
    expect(store.current?.reference).toBeNull()
  })

  it('keeps the critique, prompt, and history when revised-copy generation fails', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('provider timeout', 503)
    )
    const before = critiqueReady()
    const store = useEcommerceCopyTrainingStore()
    store.current = before
    store.sessionHistory = [before]

    expect(
      await store.generateCopy('补充规格、价格和行动指令')
    ).toBe(false)
    expect(store.error).toBe(AI_UNAVAILABLE_MESSAGE)
    expect(store.current).toEqual(before)
    expect(store.history).toEqual([before])
    expect(store.optimizedPrompt).toBe('补充规格、价格和行动指令')
    expect(store.current?.revised_copy).toBeNull()
  })

  it('keeps the optimized prompt, revised copy, and history when optimization fails', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('provider timeout', 503)
    )
    const before = copyReady()
    const store = useEcommerceCopyTrainingStore()
    store.current = before
    store.sessionHistory = [before]
    store.optimizedPrompt = before.optimized_prompt ?? ''

    expect(await store.generateOptimization()).toBe(false)
    expect(store.error).toBe(AI_UNAVAILABLE_MESSAGE)
    expect(store.current).toEqual(before)
    expect(store.history).toEqual([before])
    expect(store.optimizedPrompt).toBe('补充规格、价格和行动指令')
    expect(store.current?.revised_copy).toContain('250g')
    expect(store.current?.optimization).toBeNull()
  })

  it('does not call AI for blank step input', async () => {
    const store = useEcommerceCopyTrainingStore()
    store.current = session('case_ready')

    expect(await store.submitCritique('   ')).toBe(false)
    expect(store.error).toBe('请填写学员评判')
    store.current = critiqueReady()
    expect(await store.generateCopy('   ')).toBe(false)
    expect(mockedApiFetch).not.toHaveBeenCalled()
    expect(store.error).toBe('请填写优化提示词')
  })
})
