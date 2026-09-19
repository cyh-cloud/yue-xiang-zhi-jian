import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'

import { useLocalResourcesStore } from './localResources'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return { ...actual, apiFetch: vi.fn() }
})

const mockedApiFetch = vi.mocked(apiFetch)

describe('localResources store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('loads cases, policies, news and subscriptions', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, cases: [] } as never)
      .mockResolvedValueOnce({ success: true, policies: [] } as never)
      .mockResolvedValueOnce({ success: true, news: [] } as never)
      .mockResolvedValueOnce({
        success: true,
        subscriptions: {
          categories: [],
          recommended_category_codes: []
        }
      } as never)

    const store = useLocalResourcesStore()
    await store.loadCases()
    await store.loadPolicies()
    await store.loadNews()
    await store.loadSubscriptions()

    expect(mockedApiFetch.mock.calls.map(call => call[0])).toEqual([
      '/api/local-resources/cases',
      '/api/local-resources/policies',
      '/api/local-resources/news',
      '/api/local-resources/policy-subscriptions'
    ])
  })

  it('reuses one event id across retries and keeps content on unavailable', async () => {
    vi.spyOn(crypto, 'randomUUID').mockReturnValue(
      '00000000-0000-4000-8000-000000000001'
    )
    mockedApiFetch
      .mockRejectedValueOnce(new ApiError('unavailable', 503))
      .mockResolvedValueOnce({ success: true, view_count: 1 } as never)
    const store = useLocalResourcesStore()
    store.policyDetail = {
      id: 'policy-1',
      title: '政策',
      content: '正文',
      category_code: 'general',
      category_label: '综合',
      published_at: '2026-09-19T10:00:00+08:00',
      updated_at: '2026-09-19T10:00:00+08:00',
      version: 1
    }

    await store.recordPolicyView('policy-1')
    await store.recordPolicyView('policy-1')

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/local-resources/policies/policy-1/views',
      expect.objectContaining({ method: 'POST' })
    )
    expect(mockedApiFetch.mock.calls[0][1]?.body).toBe(
      mockedApiFetch.mock.calls[1][1]?.body
    )
    expect(store.policyDetail.content).toBe('正文')
    expect(store.viewNotice).toBe('')
  })

  it('clears stale detail when a concurrent delete returns 404', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('政策不存在', 404)
    )
    const store = useLocalResourcesStore()
    store.policyDetail = {
      id: 'policy-1',
      title: '政策',
      content: '正文',
      category_code: 'general',
      category_label: '综合',
      published_at: '2026-09-19T10:00:00+08:00',
      updated_at: '2026-09-19T10:00:00+08:00',
      version: 1
    }

    await store.recordPolicyView('policy-1')

    expect(store.policyDetail).toBeNull()
    expect(store.error).toBe('政策不存在')
    expect(store.viewNotice).toBe('')
  })

  it('resets the policy event id for a new open', async () => {
    vi.spyOn(crypto, 'randomUUID')
      .mockReturnValueOnce(
        'event-1' as ReturnType<typeof crypto.randomUUID>
      )
      .mockReturnValueOnce(
        'event-2' as ReturnType<typeof crypto.randomUUID>
      )
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        policy: {
          id: 'policy-1',
          title: '政策一',
          content: '正文一',
          category_code: 'general',
          category_label: '综合',
          published_at: '2026-09-19T10:00:00+08:00',
          updated_at: '2026-09-19T10:00:00+08:00',
          version: 1
        }
      } as never)
      .mockResolvedValueOnce({ success: true, view_count: 1 } as never)
      .mockResolvedValueOnce({
        success: true,
        policy: {
          id: 'policy-2',
          title: '政策二',
          content: '正文二',
          category_code: 'general',
          category_label: '综合',
          published_at: '2026-09-19T11:00:00+08:00',
          updated_at: '2026-09-19T11:00:00+08:00',
          version: 1
        }
      } as never)
      .mockResolvedValueOnce({ success: true, view_count: 1 } as never)
    const store = useLocalResourcesStore()

    await store.openPolicy('policy-1')
    await store.recordPolicyView('policy-1')
    await store.openPolicy('policy-2')
    await store.recordPolicyView('policy-2')

    expect(String(mockedApiFetch.mock.calls[1][1]?.body)).toContain('event-1')
    expect(String(mockedApiFetch.mock.calls[3][1]?.body)).toContain('event-2')
  })

  it('reuses news event ids on retry and clears detail on 404', async () => {
    vi.spyOn(crypto, 'randomUUID').mockReturnValue(
      'news-event-1' as ReturnType<typeof crypto.randomUUID>
    )
    mockedApiFetch
      .mockRejectedValueOnce(new ApiError('unavailable', 503))
      .mockResolvedValueOnce({ success: true, view_count: 1 } as never)
      .mockRejectedValueOnce(new ApiError('新闻不存在', 404))
    const store = useLocalResourcesStore()
    store.newsDetail = {
      id: 'news-1',
      title: '新闻',
      content: '正文',
      category_code: 'news',
      category_label: '新闻',
      published_at: '2026-09-19T10:00:00+08:00',
      updated_at: '2026-09-19T10:00:00+08:00',
      version: 1
    }

    await store.recordNewsView('news-1')
    await store.recordNewsView('news-1')
    expect(mockedApiFetch.mock.calls[0][1]?.body).toBe(
      mockedApiFetch.mock.calls[1][1]?.body
    )
    await store.recordNewsView('news-1')

    expect(store.newsDetail).toBeNull()
    expect(store.error).toBe('新闻不存在')
  })

  it('subscribes and unsubscribes idempotently through exact routes', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, subscription: {} } as never)
      .mockResolvedValueOnce({
        success: true,
        subscriptions: {
          categories: [],
          recommended_category_codes: []
        }
      } as never)
      .mockResolvedValueOnce({ success: true, subscription: {} } as never)
      .mockResolvedValueOnce({
        success: true,
        subscriptions: {
          categories: [],
          recommended_category_codes: []
        }
      } as never)
    const store = useLocalResourcesStore()

    await store.subscribePolicyCategory('ecommerce')
    await store.unsubscribePolicyCategory('ecommerce')

    expect(mockedApiFetch.mock.calls[0]).toEqual([
      '/api/local-resources/policy-subscriptions/ecommerce',
      { method: 'POST' }
    ])
    expect(mockedApiFetch.mock.calls[2]).toEqual([
      '/api/local-resources/policy-subscriptions/ecommerce',
      { method: 'DELETE' }
    ])
  })
})
