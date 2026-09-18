import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'
import type {
  GovernmentDashboard,
  GovernmentNews,
  GovernmentPolicy
} from '@/api/types'

import { useGovernmentConsoleStore } from './governmentConsole'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const policyFixture = {
  id: 'policy-1',
  title: '创业补贴',
  content: '正文',
  category_code: 'entrepreneurship',
  category_label: '创业支持',
  status: 'active',
  view_count: 9,
  version: 1,
  published_at: '2026-09-18T09:00:00+08:00',
  updated_at: '2026-09-18T09:00:00+08:00'
} satisfies GovernmentPolicy

const newsFixture = {
  id: 'news-1',
  title: '暴雨预警',
  content: '请提前防范',
  category_code: 'disaster_warning',
  category_label: '灾害预警',
  view_count: 7,
  version: 1,
  published_at: '2026-09-18T10:00:00+08:00',
  updated_at: '2026-09-18T10:00:00+08:00'
} satisfies GovernmentNews

const dashboardFixture = {
  employment: {
    active_job_count: null,
    cumulative_application_count: null,
    available: false
  },
  policy: {
    active_count: 1,
    unpublished_count: 1,
    total_count: 2,
    view_count: 9
  },
  news: { total_count: 3, view_count: 7 }
} satisfies GovernmentDashboard

describe('governmentConsole store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('loads policies and news from their route payloads', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        policies: [policyFixture]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        news: [newsFixture]
      } as never)
    const store = useGovernmentConsoleStore()

    await store.loadPolicies()
    await store.loadNews()

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/government/policies'
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/government/news'
    )
    expect(store.policies).toEqual([policyFixture])
    expect(store.news).toEqual([newsFixture])
    expect(store.loading).toBe(false)
    expect(store.error).toBe('')
  })

  it('publishes a policy and refreshes the list', async () => {
    const payload = {
      request_id: crypto.randomUUID(),
      title: '创业补贴',
      content: '正文',
      category_code: 'entrepreneurship' as const
    }
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, policy: policyFixture } as never)
      .mockResolvedValueOnce({
        success: true,
        policies: [policyFixture]
      } as never)

    const store = useGovernmentConsoleStore()
    await store.publishPolicy(payload)

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/government/policies',
      { method: 'POST', body: JSON.stringify(payload) }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/government/policies'
    )
    expect(store.policies).toEqual([policyFixture])
  })

  it('unpublishes and relists a policy with expected versions', async () => {
    const unpublishedPolicy = {
      ...policyFixture,
      status: 'unpublished',
      version: 2
    } satisfies GovernmentPolicy
    const relistedPolicy = {
      ...policyFixture,
      version: 3
    } satisfies GovernmentPolicy
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        policy: unpublishedPolicy
      } as never)
      .mockResolvedValueOnce({
        success: true,
        policies: [unpublishedPolicy]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        policy: relistedPolicy
      } as never)
      .mockResolvedValueOnce({
        success: true,
        policies: [relistedPolicy]
      } as never)
    const store = useGovernmentConsoleStore()

    await store.unpublishPolicy(policyFixture.id, policyFixture.version)
    await store.relistPolicy(unpublishedPolicy.id, unpublishedPolicy.version)

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/government/policies/policy-1/unpublish',
      {
        method: 'POST',
        body: JSON.stringify({ expected_version: 1 })
      }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/government/policies'
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/government/policies/policy-1/relist',
      {
        method: 'POST',
        body: JSON.stringify({ expected_version: 2 })
      }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      4,
      '/api/government/policies'
    )
    expect(store.policies).toEqual([relistedPolicy])
  })

  it('deletes a policy with its expected version and refreshes the list', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({ success: true } as never)
      .mockResolvedValueOnce({ success: true, policies: [] } as never)
    const store = useGovernmentConsoleStore()

    await store.deletePolicy(policyFixture.id, policyFixture.version)

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/government/policies/policy-1',
      {
        method: 'DELETE',
        body: JSON.stringify({ expected_version: 1 })
      }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/government/policies'
    )
    expect(store.policies).toEqual([])
  })

  it('publishes and deletes news while refreshing the list', async () => {
    const payload = {
      request_id: crypto.randomUUID(),
      title: '暴雨预警',
      content: '请提前防范',
      category_code: 'disaster_warning' as const
    }
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, news: newsFixture } as never)
      .mockResolvedValueOnce({
        success: true,
        news: [newsFixture]
      } as never)
      .mockResolvedValueOnce({ success: true } as never)
      .mockResolvedValueOnce({ success: true, news: [] } as never)
    const store = useGovernmentConsoleStore()

    await store.publishNews(payload)
    expect(store.news).toEqual([newsFixture])
    await store.deleteNews(newsFixture.id, newsFixture.version)

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/government/news',
      { method: 'POST', body: JSON.stringify(payload) }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/government/news'
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/government/news/news-1',
      {
        method: 'DELETE',
        body: JSON.stringify({ expected_version: 1 })
      }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      4,
      '/api/government/news'
    )
    expect(store.news).toEqual([])
  })

  it('loads dashboard without adding user or training keys', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      dashboard: dashboardFixture
    } as never)

    const store = useGovernmentConsoleStore()
    await store.loadDashboard()

    expect(mockedApiFetch).toHaveBeenCalledWith('/api/government/dashboard')
    expect(Object.keys(store.dashboard!)).toEqual([
      'employment',
      'policy',
      'news'
    ])
    expect(store.dashboard).toEqual(dashboardFixture)
  })

  it('exposes API failures through error and clears loading', async () => {
    mockedApiFetch.mockRejectedValueOnce(new Error('政策列表暂不可用'))
    const store = useGovernmentConsoleStore()

    await store.loadPolicies()

    expect(store.error).toBe('政策列表暂不可用')
    expect(store.loading).toBe(false)
  })
})
