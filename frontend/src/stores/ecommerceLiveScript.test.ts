import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type { LiveScriptVersion } from '@/api/types'

import { useEcommerceLiveScriptStore } from './ecommerceLiveScript'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function version(
  id: number,
  patch: Partial<LiveScriptVersion> = {}
): LiveScriptVersion {
  return {
    id,
    product_name: '荔枝干',
    selling_points: ['香甜', '耐储存'],
    price_text: '39.9 元',
    style: 'enthusiastic',
    script: {
      opening: '欢迎来到直播间',
      product_intro: '来自广东的香甜荔枝干',
      interaction: '喜欢的朋友扣一',
      closing: '现在下单更划算'
    },
    is_current: false,
    created_at: `2026-09-17T0${id}:00:00+00:00`,
    ...patch
  }
}

describe('ecommerceLiveScript store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('generates a version and keeps every successful result in history', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        version: version(1, { is_current: true })
      } as never)
      .mockResolvedValueOnce({
        success: true,
        version: version(2, {
          style: 'professional',
          is_current: true
        })
      } as never)
    const store = useEcommerceLiveScriptStore()
    store.form = {
      product_name: '荔枝干',
      selling_points: '香甜、耐储存',
      price_text: '39.9 元',
      style: 'enthusiastic'
    }

    expect(await store.generate()).toBe(true)
    store.form.style = 'professional'
    expect(await store.generate()).toBe(true)

    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      '/api/ecommerce-training/live-scripts',
      {
        method: 'POST',
        body: JSON.stringify(store.form)
      }
    )
    expect(store.current?.id).toBe(2)
    expect(store.current?.is_current).toBe(true)
    expect(store.history.map(item => item.id)).toEqual([2, 1])
    expect(store.history.map(item => item.is_current)).toEqual([true, false])
  })

  it('loads unordered module history and opens an original version', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        versions: [
          version(1, { style: 'humorous' }),
          version(3),
          version(2, { is_current: true })
        ]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        version: version(1, {
          style: 'humorous',
          selling_points: ['理气', '陈香']
        })
      } as never)
    const store = useEcommerceLiveScriptStore()

    await store.loadHistory()
    expect(store.current?.id).toBe(2)
    expect(store.history.map(item => item.id)).toEqual([3, 2, 1])

    await store.openVersion(1)
    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      '/api/ecommerce-training/live-scripts/1'
    )
    expect(store.current?.id).toBe(1)
    expect(store.current?.style).toBe('humorous')
    expect(store.current?.selling_points).toEqual(['理气', '陈香'])
  })

  it('recomputes current from server history and clears stale current', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        versions: [version(4), version(3)]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        versions: []
      } as never)
    const store = useEcommerceLiveScriptStore()
    store.current = version(99, { is_current: true })

    await store.loadHistory()
    expect(store.current).toBeNull()
    expect(store.history.map(item => item.id)).toEqual([4, 3])

    store.current = version(99, { is_current: true })
    await store.loadHistory()
    expect(store.current).toBeNull()
    expect(store.history).toEqual([])
  })

  it('keeps the form and exact AI message when generation fails', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('provider timeout', 503)
    )
    const store = useEcommerceLiveScriptStore()
    store.form = {
      product_name: '荔枝干',
      selling_points: '香甜、耐储存',
      price_text: '39.9 元',
      style: 'enthusiastic'
    }

    expect(await store.generate()).toBe(false)
    expect(store.form.product_name).toBe('荔枝干')
    expect(store.form.selling_points).toBe('香甜、耐储存')
    expect(store.form.price_text).toBe('39.9 元')
    expect(store.current).toBeNull()
    expect(store.history).toEqual([])
    expect(store.error).toBe('AI 服务暂时不可用')
  })

  it('keeps an existing current version when regeneration fails', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('provider timeout', 503)
    )
    const store = useEcommerceLiveScriptStore()
    const existing = version(7, { is_current: true })
    store.current = existing
    store.history = [existing]
    store.form = {
      product_name: '陈皮',
      selling_points: '陈香',
      price_text: '',
      style: 'professional'
    }

    expect(await store.generate()).toBe(false)
    expect(store.current).toEqual(existing)
    expect(store.history).toEqual([existing])
    expect(store.error).toBe('AI 服务暂时不可用')
  })

  it('submits without price text and stores the empty input', async () => {
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      version: version(5, {
        price_text: '',
        is_current: true
      })
    } as never)
    const store = useEcommerceLiveScriptStore()
    store.form = {
      product_name: '荔枝干',
      selling_points: '香甜、耐储存',
      price_text: '',
      style: 'enthusiastic'
    }

    expect(await store.generate()).toBe(true)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/ecommerce-training/live-scripts',
      {
        method: 'POST',
        body: JSON.stringify(store.form)
      }
    )
    expect(store.current?.price_text).toBe('')
  })

  it('does not call the AI when required inputs are empty', async () => {
    const store = useEcommerceLiveScriptStore()
    store.form.product_name = ' '
    store.form.selling_points = ''
    store.form.price_text = ''

    expect(await store.generate()).toBe(false)
    expect(mockedApiFetch).not.toHaveBeenCalled()
    expect(store.current).toBeNull()
  })
})
