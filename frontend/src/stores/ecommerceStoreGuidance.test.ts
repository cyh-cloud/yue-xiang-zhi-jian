import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type { StorePlan } from '@/api/types'

import { useEcommerceStoreGuidanceStore } from './ecommerceStoreGuidance'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function storePlan(
  id: number,
  patch: Partial<StorePlan> = {}
): StorePlan {
  return {
    id,
    store_type: '农产品旗舰店',
    platform: 'taobao',
    style_preference: '温暖可靠',
    plan: {
      home_layout: ['顶部活动区', '商品分组'],
      color_scheme: {
        primary: '#E43D30',
        accent: '#F7C948'
      },
      detail_structure: ['卖点', '参数', '售后'],
      navigation: ['首页', '新品', '优惠', '客服']
    },
    created_at: `2026-09-17T0${id}:00:00+00:00`,
    ...patch
  }
}

describe('ecommerceStoreGuidance store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('generates a plan and exposes the complete four-part result', async () => {
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      plan: storePlan(1)
    } as never)
    const store = useEcommerceStoreGuidanceStore()
    store.form = {
      store_type: '农产品旗舰店',
      platform: 'taobao',
      style_preference: '温暖可靠'
    }

    expect(await store.generate()).toBe(true)

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/ecommerce-training/store-plans',
      {
        method: 'POST',
        body: JSON.stringify(store.form)
      }
    )
    expect(store.current?.id).toBe(1)
    expect(store.current?.plan.home_layout).toEqual([
      '顶部活动区',
      '商品分组'
    ])
    expect(store.history.map(item => item.id)).toEqual([1])
    expect(store.error).toBe('')
  })

  it('loads history in newest-first order and opens a plan by id', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        plans: [
          storePlan(1, { platform: 'taobao' }),
          storePlan(3, { platform: 'douyin_shop' }),
          storePlan(2, { platform: 'pinduoduo' })
        ]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        plan: storePlan(1, {
          store_type: '陈皮专营店',
          platform: 'taobao',
          style_preference: '古朴'
        })
      } as never)
    const store = useEcommerceStoreGuidanceStore()

    expect(await store.loadHistory()).toBe(true)
    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      '/api/ecommerce-training/store-plans'
    )
    expect(store.history.map(item => item.id)).toEqual([3, 2, 1])

    expect(await store.openPlan(1)).toBe(true)
    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      '/api/ecommerce-training/store-plans/1'
    )
    expect(store.current?.store_type).toBe('陈皮专营店')
    expect(store.current?.style_preference).toBe('古朴')
  })

  it('rejects an unsupported platform before sending a request', async () => {
    const store = useEcommerceStoreGuidanceStore()
    store.form = {
      store_type: '农产品旗舰店',
      platform: 'unknown' as never,
      style_preference: '温暖可靠'
    }

    expect(await store.generate()).toBe(false)
    expect(mockedApiFetch).not.toHaveBeenCalled()
    expect(store.current).toBeNull()
    expect(store.history).toEqual([])
  })

  it('keeps the form empty of fabricated output after AI failure', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('provider timeout', 503)
    )
    const store = useEcommerceStoreGuidanceStore()
    store.form = {
      store_type: '农产品旗舰店',
      platform: 'taobao',
      style_preference: '温暖、可靠'
    }

    expect(await store.generate()).toBe(false)
    expect(store.form).toEqual({
      store_type: '农产品旗舰店',
      platform: 'taobao',
      style_preference: '温暖、可靠'
    })
    expect(store.current).toBeNull()
    expect(store.history).toEqual([])
    expect(store.error).toBe('AI 服务暂时不可用')
  })
})
