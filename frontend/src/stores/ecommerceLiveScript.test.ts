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

  it('loads module history and opens an original version', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        versions: [
          version(2, { is_current: true }),
          version(1, { style: 'humorous' })
        ]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        version: version(1, { style: 'humorous' })
      } as never)
    const store = useEcommerceLiveScriptStore()

    await store.loadHistory()
    expect(store.current?.id).toBe(2)

    await store.openVersion(1)
    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      '/api/ecommerce-training/live-scripts/1'
    )
    expect(store.current?.id).toBe(1)
    expect(store.current?.style).toBe('humorous')
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
