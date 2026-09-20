import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { ApiError, apiFetch } from '@/api/client'
import type {
  AdminAccount,
  AdminAccountCreatePayload,
  AdminAccountResponse,
  AdminAccountStatusPayload,
  AdminAccountsResponse,
  AdminPasswordResetResponse,
  AdminConsoleRole,
  AdminDashboard,
  AdminManagedRole,
  AdminReviewActionResponse,
  AdminReviewContentType,
  AdminReviewCounts,
  AdminReviewItem,
  AdminReviewQueueResponse
} from '@/api/types'
import { useAuthStore } from '@/stores/auth'

function emptyReviewCounts(): AdminReviewCounts {
  return {
    course_video: 0,
    job_position: 0,
    handcraft_teaching_video: 0
  }
}

export const useAdminConsoleStore = defineStore('adminConsole', () => {
  const auth = useAuthStore()
  const dashboard = ref<AdminDashboard | null>(null)
  const loading = ref(false)
  const error = ref('')
  const reviewItems = ref<AdminReviewItem[]>([])
  const reviewCounts = ref<AdminReviewCounts>(emptyReviewCounts())
  const reviewLoading = ref(false)
  const reviewActionLoading = ref(false)
  const reviewError = ref('')
  const accounts = ref<AdminAccount[]>([])
  const accountsLoading = ref(false)
  const accountsError = ref('')
  const accountActionLoading = ref(false)
  const accountsQuery = ref<{
    role: AdminManagedRole | null
    keyword: string
  }>({ role: null, keyword: '' })

  const role = computed<AdminConsoleRole>(() =>
    auth.user?.role === 'super_admin' ? 'super_admin' : 'admin'
  )
  const canManagePlatform = computed(() => role.value === 'super_admin')

  function errorMessage(caught: unknown, fallback: string) {
    return (
      caught instanceof ApiError
        ? caught.message
        : caught instanceof Error
          ? caught.message
          : fallback
    )
  }

  function captureError(caught: unknown, fallback: string) {
    error.value = errorMessage(caught, fallback)
  }

  function clearError() {
    error.value = ''
  }

  async function loadReviewQueue(
    contentType: AdminReviewContentType | null = null
  ): Promise<boolean> {
    reviewLoading.value = true
    reviewError.value = ''
    try {
      const query = contentType
        ? `?content_type=${encodeURIComponent(contentType)}`
        : ''
      const response = await apiFetch<AdminReviewQueueResponse>(
        `/api/admin/review${query}`
      )
      reviewItems.value = response.items
      reviewCounts.value = response.counts
      return true
    } catch (caught) {
      reviewError.value = errorMessage(caught, '审核队列加载失败')
      return false
    } finally {
      reviewLoading.value = false
    }
  }

  async function approveReview(
    contentType: AdminReviewContentType,
    contentId: string,
    expectedVersion: number
  ): Promise<boolean> {
    reviewActionLoading.value = true
    reviewError.value = ''
    try {
      await apiFetch<AdminReviewActionResponse>(
        `/api/admin/review/${encodeURIComponent(contentType)}/${encodeURIComponent(contentId)}/approve`,
        {
          method: 'POST',
          body: JSON.stringify({ expected_version: expectedVersion })
        }
      )
      await loadReviewQueue()
      return true
    } catch (caught) {
      reviewError.value = errorMessage(caught, '审核通过失败')
      return false
    } finally {
      reviewActionLoading.value = false
    }
  }

  async function rejectReview(
    contentType: AdminReviewContentType,
    contentId: string,
    expectedVersion: number,
    opinion: string
  ): Promise<boolean> {
    reviewActionLoading.value = true
    reviewError.value = ''
    try {
      await apiFetch<AdminReviewActionResponse>(
        `/api/admin/review/${encodeURIComponent(contentType)}/${encodeURIComponent(contentId)}/reject`,
        {
          method: 'POST',
          body: JSON.stringify({
            expected_version: expectedVersion,
            opinion
          })
        }
      )
      await loadReviewQueue()
      return true
    } catch (caught) {
      reviewError.value = errorMessage(caught, '审核驳回失败')
      return false
    } finally {
      reviewActionLoading.value = false
    }
  }

  function clearReviewError() {
    reviewError.value = ''
  }

  async function loadAccounts(
    role: AdminManagedRole | null = null,
    keyword = ''
  ): Promise<boolean> {
    accountsLoading.value = true
    accountsError.value = ''
    accountsQuery.value = { role, keyword }
    try {
      const params = new URLSearchParams()
      if (role) {
        params.set('role', role)
      }
      if (keyword) {
        params.set('keyword', keyword)
      }
      const query = params.toString()
      const response = await apiFetch<AdminAccountsResponse>(
        `/api/admin/accounts${query ? `?${query}` : ''}`
      )
      accounts.value = response.accounts
      return true
    } catch (caught) {
      accountsError.value = errorMessage(caught, '账户列表加载失败')
      return false
    } finally {
      accountsLoading.value = false
    }
  }

  async function refreshAccounts(): Promise<boolean> {
    return loadAccounts(accountsQuery.value.role, accountsQuery.value.keyword)
  }

  async function createAccount(
    payload: AdminAccountCreatePayload
  ): Promise<boolean> {
    accountActionLoading.value = true
    accountsError.value = ''
    try {
      await apiFetch<AdminAccountResponse>('/api/admin/accounts', {
        method: 'POST',
        body: JSON.stringify(payload)
      })
      await refreshAccounts()
      return true
    } catch (caught) {
      accountsError.value = errorMessage(caught, '创建账户失败')
      return false
    } finally {
      accountActionLoading.value = false
    }
  }

  async function setAccountEnabled(
    userId: number,
    enabled: boolean
  ): Promise<boolean> {
    accountActionLoading.value = true
    accountsError.value = ''
    try {
      await apiFetch<AdminAccountResponse>(
        `/api/admin/accounts/${userId}/status`,
        {
          method: 'POST',
          body: JSON.stringify({ enabled } satisfies AdminAccountStatusPayload)
        }
      )
      await refreshAccounts()
      return true
    } catch (caught) {
      accountsError.value = errorMessage(caught, '更新账户状态失败')
      return false
    } finally {
      accountActionLoading.value = false
    }
  }

  async function resetPassword(userId: number): Promise<boolean> {
    accountActionLoading.value = true
    accountsError.value = ''
    try {
      await apiFetch<AdminPasswordResetResponse>(
        `/api/admin/accounts/${userId}/password-reset`,
        { method: 'POST' }
      )
      await refreshAccounts()
      return true
    } catch (caught) {
      accountsError.value = errorMessage(caught, '重置密码失败')
      return false
    } finally {
      accountActionLoading.value = false
    }
  }

  function clearAccountsError() {
    accountsError.value = ''
  }

  return {
    dashboard,
    loading,
    error,
    reviewItems,
    reviewCounts,
    reviewLoading,
    reviewActionLoading,
    reviewError,
    accounts,
    accountsLoading,
    accountsError,
    accountActionLoading,
    role,
    canManagePlatform,
    captureError,
    clearError,
    loadReviewQueue,
    approveReview,
    rejectReview,
    clearReviewError,
    loadAccounts,
    createAccount,
    setAccountEnabled,
    resetPassword,
    clearAccountsError
  }
})
