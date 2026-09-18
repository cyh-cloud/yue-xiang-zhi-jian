import { defineStore } from 'pinia'
import { ref } from 'vue'

import { ApiError, apiFetch } from '@/api/client'
import type {
  GovernmentDashboard,
  GovernmentNews,
  GovernmentPolicy
} from '@/api/types'

interface PublishPolicyPayload {
  request_id: string
  title: string
  content: string
  category_code: GovernmentPolicy['category_code']
}

interface PublishNewsPayload {
  request_id: string
  title: string
  content: string
  category_code: GovernmentNews['category_code']
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : fallback
}

export const useGovernmentConsoleStore = defineStore('governmentConsole', () => {
  const policies = ref<GovernmentPolicy[]>([])
  const news = ref<GovernmentNews[]>([])
  const dashboard = ref<GovernmentDashboard | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function loadPolicies(): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      const response = await apiFetch<{
        success: true
        policies: GovernmentPolicy[]
      }>('/api/government/policies')
      policies.value = response.policies
      return true
    } catch (caught) {
      error.value = errorMessage(caught, '政策列表加载失败')
      return false
    } finally {
      loading.value = false
    }
  }

  async function publishPolicy(payload: PublishPolicyPayload): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      await apiFetch<{ success: true; policy: GovernmentPolicy }>(
        '/api/government/policies',
        { method: 'POST', body: JSON.stringify(payload) }
      )
    } catch (caught) {
      error.value = errorMessage(caught, '政策发布失败')
      return false
    } finally {
      loading.value = false
    }
    return loadPolicies()
  }

  async function unpublishPolicy(
    policyId: string,
    expectedVersion: number
  ): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      await apiFetch<{ success: true; policy: GovernmentPolicy }>(
        `/api/government/policies/${policyId}/unpublish`,
        {
          method: 'POST',
          body: JSON.stringify({ expected_version: expectedVersion })
        }
      )
    } catch (caught) {
      error.value = errorMessage(caught, '政策下架失败')
      return false
    } finally {
      loading.value = false
    }
    return loadPolicies()
  }

  async function relistPolicy(
    policyId: string,
    expectedVersion: number
  ): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      await apiFetch<{ success: true; policy: GovernmentPolicy }>(
        `/api/government/policies/${policyId}/relist`,
        {
          method: 'POST',
          body: JSON.stringify({ expected_version: expectedVersion })
        }
      )
    } catch (caught) {
      error.value = errorMessage(caught, '政策重新上架失败')
      return false
    } finally {
      loading.value = false
    }
    return loadPolicies()
  }

  async function deletePolicy(
    policyId: string,
    expectedVersion: number
  ): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      await apiFetch<{ success: true }>(
        `/api/government/policies/${policyId}`,
        {
          method: 'DELETE',
          body: JSON.stringify({ expected_version: expectedVersion })
        }
      )
    } catch (caught) {
      error.value = errorMessage(caught, '政策删除失败')
      return false
    } finally {
      loading.value = false
    }
    return loadPolicies()
  }

  async function loadNews(): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      const response = await apiFetch<{
        success: true
        news: GovernmentNews[]
      }>('/api/government/news')
      news.value = response.news
      return true
    } catch (caught) {
      error.value = errorMessage(caught, '新闻列表加载失败')
      return false
    } finally {
      loading.value = false
    }
  }

  async function publishNews(payload: PublishNewsPayload): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      await apiFetch<{ success: true; news: GovernmentNews }>(
        '/api/government/news',
        { method: 'POST', body: JSON.stringify(payload) }
      )
    } catch (caught) {
      error.value = errorMessage(caught, '新闻发布失败')
      return false
    } finally {
      loading.value = false
    }
    return loadNews()
  }

  async function deleteNews(
    newsId: string,
    expectedVersion: number
  ): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      await apiFetch<{ success: true }>(
        `/api/government/news/${newsId}`,
        {
          method: 'DELETE',
          body: JSON.stringify({ expected_version: expectedVersion })
        }
      )
    } catch (caught) {
      error.value = errorMessage(caught, '新闻删除失败')
      return false
    } finally {
      loading.value = false
    }
    return loadNews()
  }

  async function loadDashboard(): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      const response = await apiFetch<{
        success: true
        dashboard: GovernmentDashboard
      }>('/api/government/dashboard')
      dashboard.value = response.dashboard
      return true
    } catch (caught) {
      error.value = errorMessage(caught, '数据看板加载失败')
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    policies,
    news,
    dashboard,
    loading,
    error,
    loadPolicies,
    publishPolicy,
    unpublishPolicy,
    relistPolicy,
    deletePolicy,
    loadNews,
    publishNews,
    deleteNews,
    loadDashboard
  }
})
