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
  AdminReviewQueueResponse,
  AdminFulfillment,
  AdminFulfillmentActionResponse,
  AdminFulfillmentActionResult,
  AdminFulfillmentsResponse,
  AdminRedemption,
  AdminRedemptionDetail,
  AdminRedemptionDetailResponse,
  AdminRedemptionsResponse,
  AdminReward,
  AdminRewardCreatePayload,
  AdminRewardOnlinePayload,
  AdminRewardQueueQuery,
  AdminRewardResponse,
  AdminRewardUpdatePayload,
  AdminRewardsResponse
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
  const rewards = ref<AdminReward[]>([])
  const rewardsLoading = ref(false)
  const rewardsError = ref('')
  const rewardActionLoading = ref(false)
  const rewardFormError = ref('')
  const fulfillments = ref<AdminFulfillment[]>([])
  const fulfillmentsLoading = ref(false)
  const fulfillmentsError = ref('')
  const fulfillmentActionLoading = ref(false)
  const redemptions = ref<AdminRedemption[]>([])
  const redemptionsLoading = ref(false)
  const redemptionsError = ref('')
  const redemptionDetail = ref<AdminRedemptionDetail | null>(null)
  const redemptionDetailLoading = ref(false)
  const redemptionDetailError = ref('')
  const fulfillmentQuery = ref<AdminRewardQueueQuery>({
    user: '',
    reward: '',
    status: 'all',
    fulfillment_status: 'all',
    created_from: '',
    created_to: ''
  })
  const redemptionQuery = ref<AdminRewardQueueQuery>({
    user: '',
    reward: '',
    status: 'all',
    fulfillment_status: 'all',
    created_from: '',
    created_to: ''
  })

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

  function queueQuery(query: AdminRewardQueueQuery): string {
    const params = new URLSearchParams()
    if (query.user) {
      params.set('user', query.user)
    }
    if (query.reward) {
      params.set('reward', query.reward)
    }
    if (query.status !== 'all') {
      params.set('status', query.status)
    }
    if (query.fulfillment_status !== 'all') {
      params.set('fulfillment_status', query.fulfillment_status)
    }
    if (query.created_from) {
      params.set('created_from', query.created_from)
    }
    if (query.created_to) {
      params.set('created_to', query.created_to)
    }
    const serialized = params.toString()
    return serialized ? `?${serialized}` : ''
  }

  async function loadRewards(): Promise<boolean> {
    rewardsLoading.value = true
    rewardsError.value = ''
    try {
      const response = await apiFetch<AdminRewardsResponse>('/api/admin/rewards')
      rewards.value = response.items
      return true
    } catch (caught) {
      rewardsError.value = errorMessage(caught, '奖品目录加载失败')
      return false
    } finally {
      rewardsLoading.value = false
    }
  }

  async function createReward(
    payload: AdminRewardCreatePayload
  ): Promise<boolean> {
    rewardActionLoading.value = true
    rewardFormError.value = ''
    try {
      await apiFetch<AdminRewardResponse>('/api/admin/rewards', {
        method: 'POST',
        body: JSON.stringify(payload)
      })
      await loadRewards()
      return true
    } catch (caught) {
      rewardFormError.value = errorMessage(caught, '创建奖品失败')
      return false
    } finally {
      rewardActionLoading.value = false
    }
  }

  async function updateReward(
    rewardId: string,
    payload: AdminRewardUpdatePayload
  ): Promise<boolean> {
    rewardActionLoading.value = true
    rewardFormError.value = ''
    try {
      await apiFetch<AdminRewardResponse>(
        `/api/admin/rewards/${encodeURIComponent(rewardId)}`,
        {
          method: 'PUT',
          body: JSON.stringify(payload)
        }
      )
      await loadRewards()
      return true
    } catch (caught) {
      rewardFormError.value = errorMessage(caught, '编辑奖品失败')
      return false
    } finally {
      rewardActionLoading.value = false
    }
  }

  async function setRewardOnline(
    rewardId: string,
    expectedVersion: number,
    online: boolean
  ): Promise<boolean> {
    rewardActionLoading.value = true
    rewardsError.value = ''
    try {
      const body = {
        expected_version: expectedVersion,
        online
      } satisfies AdminRewardOnlinePayload
      await apiFetch<AdminRewardResponse>(
        `/api/admin/rewards/${encodeURIComponent(rewardId)}/online`,
        {
          method: 'POST',
          body: JSON.stringify(body)
        }
      )
      await loadRewards()
      return true
    } catch (caught) {
      // A 409 means another admin already moved the row: reload so the
      // table shows the server values, then keep the conflict message.
      const conflictMessage = errorMessage(caught, '更新上架状态失败')
      await loadRewards()
      rewardsError.value = conflictMessage
      return false
    } finally {
      rewardActionLoading.value = false
    }
  }

  async function loadFulfillments(
    query: AdminRewardQueueQuery = fulfillmentQuery.value
  ): Promise<boolean> {
    fulfillmentsLoading.value = true
    fulfillmentsError.value = ''
    fulfillmentQuery.value = query
    try {
      const response = await apiFetch<AdminFulfillmentsResponse>(
        `/api/admin/fulfillments${queueQuery(query)}`
      )
      fulfillments.value = response.items
      return true
    } catch (caught) {
      fulfillmentsError.value = errorMessage(caught, '履约队列加载失败')
      return false
    } finally {
      fulfillmentsLoading.value = false
    }
  }

  function replaceFulfillment(result: AdminFulfillmentActionResult): void {
    const index = fulfillments.value.findIndex(
      item => item.id === result.fulfillment_id
    )
    if (index === -1) return
    const current = fulfillments.value[index]
    if (!current) return
    fulfillments.value = [
      ...fulfillments.value.slice(0, index),
      {
        ...current,
        status: result.status,
        issued_at: result.issued_at,
        verified_at: result.verified_at,
        canceled_at: result.canceled_at,
        restored_points: result.restored_points
      },
      ...fulfillments.value.slice(index + 1)
    ]
  }

  async function applyFulfillmentAction(
    fulfillmentId: number,
    action: 'issue' | 'cancel' | 'verify'
  ): Promise<boolean> {
    fulfillmentActionLoading.value = true
    fulfillmentsError.value = ''
    try {
      const response = await apiFetch<AdminFulfillmentActionResponse>(
        `/api/admin/fulfillments/${fulfillmentId}/${action}`,
        { method: 'POST' }
      )
      replaceFulfillment(response.fulfillment)
      if (redemptionDetail.value !== null) {
        await loadRedemptionDetail(redemptionDetail.value.id)
      }
      return true
    } catch (caught) {
      const labels: Record<typeof action, string> = {
        issue: '发放奖品失败',
        cancel: '取消履约失败',
        verify: '核销履约失败'
      }
      fulfillmentsError.value = errorMessage(caught, labels[action])
      return false
    } finally {
      fulfillmentActionLoading.value = false
    }
  }

  function issueFulfillment(fulfillmentId: number): Promise<boolean> {
    return applyFulfillmentAction(fulfillmentId, 'issue')
  }

  function cancelFulfillment(fulfillmentId: number): Promise<boolean> {
    return applyFulfillmentAction(fulfillmentId, 'cancel')
  }

  function verifyFulfillment(fulfillmentId: number): Promise<boolean> {
    return applyFulfillmentAction(fulfillmentId, 'verify')
  }

  async function loadRedemptions(
    query: AdminRewardQueueQuery = redemptionQuery.value
  ): Promise<boolean> {
    redemptionsLoading.value = true
    redemptionsError.value = ''
    redemptionQuery.value = query
    try {
      const response = await apiFetch<AdminRedemptionsResponse>(
        `/api/admin/redemptions${queueQuery(query)}`
      )
      redemptions.value = response.items
      return true
    } catch (caught) {
      redemptionsError.value = errorMessage(caught, '兑换记录加载失败')
      return false
    } finally {
      redemptionsLoading.value = false
    }
  }

  async function loadRedemptionDetail(
    redemptionId: number
  ): Promise<boolean> {
    redemptionDetailLoading.value = true
    redemptionDetailError.value = ''
    try {
      const response = await apiFetch<AdminRedemptionDetailResponse>(
        `/api/admin/redemptions/${redemptionId}`
      )
      redemptionDetail.value = response
      return true
    } catch (caught) {
      redemptionDetailError.value = errorMessage(caught, '兑换详情加载失败')
      return false
    } finally {
      redemptionDetailLoading.value = false
    }
  }

  function clearRewardFormError() {
    rewardFormError.value = ''
  }

  function clearRewardsError() {
    rewardsError.value = ''
  }

  function clearFulfillmentsError() {
    fulfillmentsError.value = ''
  }

  function clearRedemptionsError() {
    redemptionsError.value = ''
  }

  function clearRedemptionDetailError() {
    redemptionDetailError.value = ''
  }

  function clearRedemptionDetail() {
    redemptionDetail.value = null
    redemptionDetailError.value = ''
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
    clearAccountsError,
    rewards,
    rewardsLoading,
    rewardsError,
    rewardActionLoading,
    rewardFormError,
    fulfillments,
    fulfillmentsLoading,
    fulfillmentsError,
    fulfillmentActionLoading,
    redemptions,
    redemptionsLoading,
    redemptionsError,
    redemptionDetail,
    redemptionDetailLoading,
    redemptionDetailError,
    loadRewards,
    createReward,
    updateReward,
    setRewardOnline,
    clearRewardFormError,
    clearRewardsError,
    loadFulfillments,
    issueFulfillment,
    cancelFulfillment,
    verifyFulfillment,
    clearFulfillmentsError,
    loadRedemptions,
    loadRedemptionDetail,
    clearRedemptionDetail,
    clearRedemptionsError,
    clearRedemptionDetailError
  }
})
