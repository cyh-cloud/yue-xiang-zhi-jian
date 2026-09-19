import { defineStore } from 'pinia'
import { ref } from 'vue'

import { ApiError, apiFetch } from '@/api/client'
import type {
  LocalResourceCase,
  LocalResourceCaseDetail,
  LocalResourceNews,
  LocalResourcePolicy,
  NewsCategoryCode,
  PolicyCategoryCode,
  PolicyCategorySubscription,
  PolicySubscriptionState
} from '@/api/types'

const API_PREFIX = '/api/local-resources'

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : fallback
}

export const useLocalResourcesStore = defineStore('localResources', () => {
  const cases = ref<LocalResourceCase[]>([])
  const caseDetail = ref<LocalResourceCaseDetail | null>(null)
  const policies = ref<LocalResourcePolicy[]>([])
  const policyDetail = ref<LocalResourcePolicy | null>(null)
  const news = ref<LocalResourceNews[]>([])
  const newsDetail = ref<LocalResourceNews | null>(null)
  const subscriptions = ref<PolicySubscriptionState>({
    categories: [],
    recommended_category_codes: []
  })
  const policyViewEventId = ref<string | null>(null)
  const newsViewEventId = ref<string | null>(null)
  const loading = ref(false)
  const error = ref('')
  const viewNotice = ref('')

  async function loadCases(): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      const response = await apiFetch<{
        success: true
        cases: LocalResourceCase[]
      }>(`${API_PREFIX}/cases`)
      cases.value = response.cases
      return true
    } catch (caught) {
      error.value = errorMessage(caught, '案例列表加载失败')
      return false
    } finally {
      loading.value = false
    }
  }

  async function openCase(caseId: string): Promise<boolean> {
    if (caseDetail.value?.id !== caseId) {
      caseDetail.value = null
    }
    loading.value = true
    error.value = ''
    try {
      const response = await apiFetch<{
        success: true
        case: LocalResourceCaseDetail
      }>(`${API_PREFIX}/cases/${encodeURIComponent(caseId)}`)
      caseDetail.value = response.case
      return true
    } catch (caught) {
      error.value = errorMessage(caught, '案例详情加载失败')
      return false
    } finally {
      loading.value = false
    }
  }

  async function loadPolicies(
    category?: PolicyCategoryCode
  ): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      const suffix = category
        ? `?category=${encodeURIComponent(category)}`
        : ''
      const response = await apiFetch<{
        success: true
        policies: LocalResourcePolicy[]
      }>(`${API_PREFIX}/policies${suffix}`)
      policies.value = response.policies
      return true
    } catch (caught) {
      error.value = errorMessage(caught, '政策列表加载失败')
      return false
    } finally {
      loading.value = false
    }
  }

  async function openPolicy(policyId: string): Promise<boolean> {
    policyViewEventId.value = null
    if (policyDetail.value?.id !== policyId) {
      policyDetail.value = null
    }
    loading.value = true
    error.value = ''
    viewNotice.value = ''
    try {
      const response = await apiFetch<{
        success: true
        policy: LocalResourcePolicy
      }>(`${API_PREFIX}/policies/${encodeURIComponent(policyId)}`)
      policyDetail.value = response.policy
      return true
    } catch (caught) {
      error.value = errorMessage(caught, '政策详情加载失败')
      return false
    } finally {
      loading.value = false
    }
  }

  async function loadNews(category?: NewsCategoryCode): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      const suffix = category
        ? `?category=${encodeURIComponent(category)}`
        : ''
      const response = await apiFetch<{
        success: true
        news: LocalResourceNews[]
      }>(`${API_PREFIX}/news${suffix}`)
      news.value = response.news
      return true
    } catch (caught) {
      error.value = errorMessage(caught, '新闻列表加载失败')
      return false
    } finally {
      loading.value = false
    }
  }

  async function openNews(newsId: string): Promise<boolean> {
    newsViewEventId.value = null
    if (newsDetail.value?.id !== newsId) {
      newsDetail.value = null
    }
    loading.value = true
    error.value = ''
    viewNotice.value = ''
    try {
      const response = await apiFetch<{
        success: true
        news: LocalResourceNews
      }>(`${API_PREFIX}/news/${encodeURIComponent(newsId)}`)
      newsDetail.value = response.news
      return true
    } catch (caught) {
      error.value = errorMessage(caught, '新闻详情加载失败')
      return false
    } finally {
      loading.value = false
    }
  }

  async function loadSubscriptions(): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      const response = await apiFetch<{
        success: true
        subscriptions: PolicySubscriptionState
      }>(`${API_PREFIX}/policy-subscriptions`)
      subscriptions.value = response.subscriptions
      return true
    } catch (caught) {
      error.value = errorMessage(caught, '政策订阅加载失败')
      return false
    } finally {
      loading.value = false
    }
  }

  async function changePolicySubscription(
    category: PolicyCategoryCode,
    method: 'POST' | 'DELETE'
  ): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      await apiFetch<{
        success: true
        subscription: PolicyCategorySubscription
      }>(
        `${API_PREFIX}/policy-subscriptions/${encodeURIComponent(category)}`,
        { method }
      )
      return await loadSubscriptions()
    } catch (caught) {
      error.value = errorMessage(caught, '政策订阅更新失败')
      return false
    } finally {
      loading.value = false
    }
  }

  function subscribePolicyCategory(
    category: PolicyCategoryCode
  ): Promise<boolean> {
    return changePolicySubscription(category, 'POST')
  }

  function unsubscribePolicyCategory(
    category: PolicyCategoryCode
  ): Promise<boolean> {
    return changePolicySubscription(category, 'DELETE')
  }

  async function recordPolicyView(policyId: string): Promise<void> {
    const eventId = policyViewEventId.value ?? crypto.randomUUID()
    policyViewEventId.value = eventId
    try {
      await apiFetch(
        `${API_PREFIX}/policies/${encodeURIComponent(policyId)}/views`,
        {
          method: 'POST',
          body: JSON.stringify({ view_event_id: eventId })
        }
      )
      viewNotice.value = ''
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 404) {
        policyDetail.value = null
        error.value = '政策不存在'
        viewNotice.value = ''
        return
      }
      viewNotice.value = '浏览量暂未记录'
    }
  }

  async function recordNewsView(newsId: string): Promise<void> {
    const eventId = newsViewEventId.value ?? crypto.randomUUID()
    newsViewEventId.value = eventId
    try {
      await apiFetch(
        `${API_PREFIX}/news/${encodeURIComponent(newsId)}/views`,
        {
          method: 'POST',
          body: JSON.stringify({ view_event_id: eventId })
        }
      )
      viewNotice.value = ''
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 404) {
        newsDetail.value = null
        error.value = '新闻不存在'
        viewNotice.value = ''
        return
      }
      viewNotice.value = '浏览量暂未记录'
    }
  }

  return {
    cases,
    caseDetail,
    policies,
    policyDetail,
    news,
    newsDetail,
    subscriptions,
    policyViewEventId,
    newsViewEventId,
    loading,
    error,
    viewNotice,
    loadCases,
    openCase,
    loadPolicies,
    openPolicy,
    loadNews,
    openNews,
    loadSubscriptions,
    subscribePolicyCategory,
    unsubscribePolicyCategory,
    recordPolicyView,
    recordNewsView
  }
})
