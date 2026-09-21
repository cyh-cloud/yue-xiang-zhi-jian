import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { ApiError, apiFetch } from '@/api/client'
import type {
  AdminAccount,
  AdminAccountCreatePayload,
  AdminAccountResponse,
  AdminAccountStatusPayload,
  AdminAccountsResponse,
  AdminAnnouncement,
  AdminAnnouncementCreatePayload,
  AdminAnnouncementResponse,
  AdminAnnouncementPublishResponse,
  AdminAnnouncementsResponse,
  AdminPointsPolicy,
  AdminPointsPolicyPayload,
  AdminPointsPolicyResponse,
  AdminPasswordResetResponse,
  AdminConsoleRole,
  AdminDashboardPayload,
  AdminDashboardSnapshot,
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

export type AdminModerationContentType =
  | 'course_video'
  | 'handcraft_teaching_video'

export type AdminModerationContentTypeFilter =
  | AdminModerationContentType
  | 'all'

export type AdminModerationVisibilityFilter = 'all' | 'visible' | 'hidden'

export type AdminCommentReportStatus = 'pending' | 'confirmed' | 'rejected'

export type AdminCommentReportStatusFilter = AdminCommentReportStatus | 'all'

export type AdminFeedbackStatus = 'pending' | 'processed' | 'closed'

export type AdminFeedbackStatusFilter = AdminFeedbackStatus | 'all'

export interface AdminModerationPerson {
  username: string
  name: string
}

export interface AdminModerationComment {
  comment_id: string
  content_type: AdminModerationContentType
  content_id: string
  author_id: number
  author: AdminModerationPerson
  parent_comment_id: string | null
  body: string
  is_teacher_reply: boolean
  is_visible: boolean
  created_at: string
  updated_at: string
}

export interface AdminCommentReport {
  report_id: string
  comment_id: string
  reporter_id: number
  reporter: AdminModerationPerson
  reason: string
  status: AdminCommentReportStatus
  resolver_id: number | null
  resolver: AdminModerationPerson
  result: string | null
  comment_is_visible: boolean | null
  created_at: string
  updated_at: string
  resolved_at: string | null
}

export interface AdminFeedbackRecord {
  feedback_id: string
  submitter_id: number
  submitter: AdminModerationPerson
  body: string
  status: AdminFeedbackStatus
  idempotency_key: string
  handler_id: number | null
  handler: AdminModerationPerson
  result: string | null
  created_at: string
  updated_at: string
}

export interface AdminModerationCommentQuery {
  content_type: AdminModerationContentTypeFilter
  content_id: string
  author_id: string
  keyword: string
  is_visible: AdminModerationVisibilityFilter
  created_from: string
  created_to: string
}

export interface AdminModerationReportQuery {
  status: AdminCommentReportStatusFilter
  comment_id: string
  reporter_id: string
  created_from: string
  created_to: string
}

export interface AdminModerationFeedbackQuery {
  status: AdminFeedbackStatusFilter
  submitter_id: string
  created_from: string
  created_to: string
}

export interface AdminModerationCommentsResponse {
  success: true
  items: AdminModerationComment[]
  count: number
}

export interface AdminCommentDeleteResponse {
  success: true
  comment_id: string
  is_visible: boolean
  changed: boolean
  updated_at: string
}

export interface AdminCommentReportsResponse {
  success: true
  items: AdminCommentReport[]
  count: number
}

export interface AdminResolvedCommentReport extends AdminCommentReport {
  changed: boolean
}

export interface AdminCommentReportResolveResponse {
  success: true
  report: AdminResolvedCommentReport
}

export interface AdminFeedbackListResponse {
  success: true
  items: AdminFeedbackRecord[]
  count: number
}

export interface AdminUpdatedFeedbackRecord extends AdminFeedbackRecord {
  changed: boolean
}

export interface AdminFeedbackUpdateResponse {
  success: true
  feedback: AdminUpdatedFeedbackRecord
}

// One page of every moderation queue. The backend caps `limit` at 200 and
// answers with the rows the page actually carries, so the console never
// claims a total it was not given.
const MODERATION_PAGE_SIZE = 20

function emptyReviewCounts(): AdminReviewCounts {
  return {
    course_video: 0,
    job_position: 0,
    handcraft_teaching_video: 0
  }
}

export const useAdminConsoleStore = defineStore('adminConsole', () => {
  const auth = useAuthStore()
  const dashboard = ref<AdminDashboardSnapshot | null>(null)
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
  const announcements = ref<AdminAnnouncement[]>([])
  const announcementsLoading = ref(false)
  const announcementsError = ref('')
  const announcementAccessDenied = ref(false)
  const announcementActionLoading = ref(false)
  const announcementFormError = ref('')
  const announcementFormErrorCode = ref('')
  const announcementPublishResult = ref<AdminAnnouncementPublishResponse | null>(
    null
  )
  const pointsPolicy = ref<AdminPointsPolicy | null>(null)
  const pointsPolicyLoading = ref(false)
  const pointsPolicyError = ref('')
  const pointsPolicyActionLoading = ref(false)
  const pointsPolicyFormError = ref('')
  const pointsPolicyFormErrorCode = ref('')

  const moderationComments = ref<AdminModerationComment[]>([])
  const moderationCommentCount = ref(0)
  const moderationCommentsLoading = ref(false)
  const moderationCommentsError = ref('')
  const moderationCommentActionLoading = ref(false)
  const moderationCommentQuery = ref<AdminModerationCommentQuery>({
    content_type: 'all',
    content_id: '',
    author_id: '',
    keyword: '',
    is_visible: 'all',
    created_from: '',
    created_to: ''
  })
  const moderationReports = ref<AdminCommentReport[]>([])
  const moderationReportCount = ref(0)
  const moderationReportsLoading = ref(false)
  const moderationReportsError = ref('')
  const moderationReportActionLoading = ref(false)
  const moderationReportQuery = ref<AdminModerationReportQuery>({
    status: 'all',
    comment_id: '',
    reporter_id: '',
    created_from: '',
    created_to: ''
  })
  const moderationFeedback = ref<AdminFeedbackRecord[]>([])
  const moderationFeedbackCount = ref(0)
  const moderationFeedbackLoading = ref(false)
  const moderationFeedbackError = ref('')
  const moderationFeedbackActionLoading = ref(false)
  const moderationFeedbackQuery = ref<AdminModerationFeedbackQuery>({
    status: 'all',
    submitter_id: '',
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

  async function loadDashboard(): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      // The role picks the endpoint, so an ordinary admin never asks the
      // server for the platform-wide metrics the permission matrix hides.
      const path =
        role.value === 'super_admin'
          ? '/api/admin/dashboard'
          : '/api/admin/content-dashboard'
      const response = await apiFetch<AdminDashboardPayload>(path)
      dashboard.value = response.dashboard
      return true
    } catch (caught) {
      captureError(caught, '看板加载失败')
      dashboard.value = null
      return false
    } finally {
      loading.value = false
    }
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
      // A 409 means another admin already moved the row: reload so the edit
      // form re-seeds its expected version from the server values, then keep
      // the conflict message visible next to the form.
      const conflictMessage = errorMessage(caught, '编辑奖品失败')
      await loadRewards()
      rewardFormError.value = conflictMessage
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
      // The 05 action also rewrites the linked redemption and, on cancel,
      // releases the stock reservation. The optimistic merge above cannot
      // carry redemption_status or updated_at, so re-read the queue and the
      // catalog to keep both tables authoritative.
      await loadFulfillments()
      await loadRewards()
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

  async function loadAnnouncements(): Promise<boolean> {
    announcementsLoading.value = true
    announcementsError.value = ''
    announcementAccessDenied.value = false
    try {
      const response = await apiFetch<AdminAnnouncementsResponse>(
        '/api/admin/announcements'
      )
      announcements.value = response.items
      return true
    } catch (caught) {
      announcementsError.value = errorMessage(caught, '公告列表加载失败')
      // A 403 means the role is outside the permission matrix, which is a
      // denial and not an empty history: the screen must say so instead of
      // rendering "no announcements yet".
      announcementAccessDenied.value =
        caught instanceof ApiError && caught.status === 403
      announcements.value = []
      return false
    } finally {
      announcementsLoading.value = false
    }
  }

  async function createAnnouncement(
    payload: AdminAnnouncementCreatePayload
  ): Promise<boolean> {
    announcementActionLoading.value = true
    announcementFormError.value = ''
    announcementFormErrorCode.value = ''
    try {
      const response = await apiFetch<AdminAnnouncementResponse>(
        '/api/admin/announcements',
        {
          method: 'POST',
          body: JSON.stringify(payload)
        }
      )
      announcements.value = [response.announcement, ...announcements.value]
      return true
    } catch (caught) {
      announcementFormError.value = errorMessage(caught, '创建公告失败')
      announcementFormErrorCode.value =
        caught instanceof ApiError && caught.code ? caught.code : ''
      return false
    } finally {
      announcementActionLoading.value = false
    }
  }

  async function publishAnnouncement(
    announcementId: string
  ): Promise<boolean> {
    announcementActionLoading.value = true
    announcementsError.value = ''
    announcementPublishResult.value = null
    try {
      const response = await apiFetch<AdminAnnouncementPublishResponse>(
        `/api/admin/announcements/${encodeURIComponent(announcementId)}/publish`,
        { method: 'POST' }
      )
      announcementPublishResult.value = response
      // The publish keeps its own delivery summary, so the list is re-read to
      // show the committed status without guessing it from the response.
      await loadAnnouncements()
      return true
    } catch (caught) {
      announcementsError.value = errorMessage(caught, '发布公告失败')
      return false
    } finally {
      announcementActionLoading.value = false
    }
  }

  function clearAnnouncementFormError() {
    announcementFormError.value = ''
    announcementFormErrorCode.value = ''
  }

  function clearAnnouncementsError() {
    announcementsError.value = ''
  }

  function clearAnnouncementPublishResult() {
    announcementPublishResult.value = null
  }

  async function loadPointsPolicy(): Promise<boolean> {
    pointsPolicyLoading.value = true
    pointsPolicyError.value = ''
    try {
      const response = await apiFetch<AdminPointsPolicyResponse>(
        '/api/admin/points-policy'
      )
      pointsPolicy.value = response.policy
      return true
    } catch (caught) {
      pointsPolicyError.value = errorMessage(caught, '积分规则加载失败')
      pointsPolicy.value = null
      return false
    } finally {
      pointsPolicyLoading.value = false
    }
  }

  async function savePointsPolicy(
    payload: AdminPointsPolicyPayload
  ): Promise<boolean> {
    pointsPolicyActionLoading.value = true
    pointsPolicyFormError.value = ''
    pointsPolicyFormErrorCode.value = ''
    try {
      const response = await apiFetch<AdminPointsPolicyResponse>(
        '/api/admin/points-policy',
        {
          method: 'PUT',
          body: JSON.stringify(payload)
        }
      )
      pointsPolicy.value = response.policy
      return true
    } catch (caught) {
      pointsPolicyFormError.value = errorMessage(caught, '保存积分规则失败')
      pointsPolicyFormErrorCode.value =
        caught instanceof ApiError && caught.code ? caught.code : ''
      // Only a version conflict invalidates the optimistic lock the form was
      // built on, so only that case reloads the row and re-seeds the controls.
      // A 400, 500, 503 or a dropped connection leaves the admin's typed
      // values alone: reloading would replace them with the last committed
      // policy and discard the edit behind a single banner.
      if (caught instanceof ApiError && caught.status === 409) {
        await loadPointsPolicy()
      }
      return false
    } finally {
      pointsPolicyActionLoading.value = false
    }
  }

  function clearPointsPolicyFormError() {
    pointsPolicyFormError.value = ''
    pointsPolicyFormErrorCode.value = ''
  }

  // The console owns the wording for the four codes the moderation module
  // raises, so a 404 and a rejected query string read as decisions rather
  // than as the backend's raw message text.
  const MODERATION_ERROR_CODES: Record<string, string> = {
    comment_not_found: '评论不存在或已被删除',
    comment_report_not_found: '举报不存在或已处理',
    feedback_not_found: '反馈不存在',
    moderation_filter_invalid: '筛选条件不正确，请检查后重试',
    moderation_validation_failed: '处理内容校验失败，请检查处理备注'
  }

  function moderationErrorMessage(caught: unknown, fallback: string): string {
    if (caught instanceof ApiError && caught.code) {
      const mapped = MODERATION_ERROR_CODES[caught.code]
      if (mapped) {
        return mapped
      }
    }
    return errorMessage(caught, fallback)
  }

  function moderationQueueQuery(
    params: Record<string, string>,
    offset: number,
    limit: number
  ): string {
    const search = new URLSearchParams()
    for (const [field, value] of Object.entries(params)) {
      if (value) {
        search.set(field, value)
      }
    }
    search.set('limit', String(limit))
    search.set('offset', String(offset))
    return `?${search.toString()}`
  }

  async function loadModerationComments(
    query: AdminModerationCommentQuery = moderationCommentQuery.value,
    offset = 0,
    limit = MODERATION_PAGE_SIZE
  ): Promise<boolean> {
    moderationCommentsLoading.value = true
    moderationCommentsError.value = ''
    moderationCommentQuery.value = query
    try {
      const response = await apiFetch<AdminModerationCommentsResponse>(
        `/api/admin/comments${moderationQueueQuery(
          {
            content_type:
              query.content_type === 'all' ? '' : query.content_type,
            content_id: query.content_id.trim(),
            author_id: query.author_id.trim(),
            keyword: query.keyword.trim(),
            is_visible:
              query.is_visible === 'all'
                ? ''
                : query.is_visible === 'visible'
                  ? '1'
                  : '0',
            created_from: query.created_from,
            created_to: query.created_to
          },
          offset,
          limit
        )}`
      )
      // `count` is how many rows this page carries, not how many rows the
      // filters match, so the console can only ever say "this page holds N".
      moderationComments.value = response.items
      moderationCommentCount.value = response.count
      return true
    } catch (caught) {
      moderationComments.value = []
      moderationCommentCount.value = 0
      moderationCommentsError.value = moderationErrorMessage(
        caught,
        '评论列表加载失败'
      )
      return false
    } finally {
      moderationCommentsLoading.value = false
    }
  }

  function applyHiddenComment(result: AdminCommentDeleteResponse): void {
    const index = moderationComments.value.findIndex(
      item => item.comment_id === result.comment_id
    )
    if (index === -1) return
    const current = moderationComments.value[index]
    if (!current) return
    // A repeat delete answers `changed: false` with the row untouched, so the
    // same merge renders the stored visibility instead of guessing one.
    moderationComments.value = [
      ...moderationComments.value.slice(0, index),
      {
        ...current,
        is_visible: result.is_visible,
        updated_at: result.updated_at
      },
      ...moderationComments.value.slice(index + 1)
    ]
  }

  async function deleteModerationComment(
    commentId: string
  ): Promise<AdminCommentDeleteResponse | null> {
    moderationCommentActionLoading.value = true
    moderationCommentsError.value = ''
    try {
      const response = await apiFetch<AdminCommentDeleteResponse>(
        `/api/admin/comments/${encodeURIComponent(commentId)}`,
        { method: 'DELETE' }
      )
      applyHiddenComment(response)
      return response
    } catch (caught) {
      moderationCommentsError.value = moderationErrorMessage(
        caught,
        '隐藏评论失败'
      )
      return null
    } finally {
      moderationCommentActionLoading.value = false
    }
  }

  async function loadModerationReports(
    query: AdminModerationReportQuery = moderationReportQuery.value,
    offset = 0,
    limit = MODERATION_PAGE_SIZE
  ): Promise<boolean> {
    moderationReportsLoading.value = true
    moderationReportsError.value = ''
    moderationReportQuery.value = query
    try {
      const response = await apiFetch<AdminCommentReportsResponse>(
        `/api/admin/reports${moderationQueueQuery(
          {
            status: query.status === 'all' ? '' : query.status,
            comment_id: query.comment_id.trim(),
            reporter_id: query.reporter_id.trim(),
            created_from: query.created_from,
            created_to: query.created_to
          },
          offset,
          limit
        )}`
      )
      moderationReports.value = response.items
      moderationReportCount.value = response.count
      return true
    } catch (caught) {
      moderationReports.value = []
      moderationReportCount.value = 0
      moderationReportsError.value = moderationErrorMessage(
        caught,
        '举报队列加载失败'
      )
      return false
    } finally {
      moderationReportsLoading.value = false
    }
  }

  function replaceModerationReport(report: AdminResolvedCommentReport): void {
    // The answer is read back from the table by the backend, so the row is
    // replaced with the stored decision rather than with what the operator
    // typed: a `changed: false` repeat shows the decision that is on file.
    moderationReports.value = moderationReports.value.map(item =>
      item.report_id === report.report_id
        ? {
            ...item,
            status: report.status,
            resolver_id: report.resolver_id,
            resolver: report.resolver,
            result: report.result,
            comment_is_visible: report.comment_is_visible,
            updated_at: report.updated_at,
            resolved_at: report.resolved_at
          }
        : item
    )
  }

  async function resolveModerationReport(
    reportId: string,
    confirmed: boolean,
    result: string
  ): Promise<AdminResolvedCommentReport | null> {
    moderationReportActionLoading.value = true
    moderationReportsError.value = ''
    try {
      const response = await apiFetch<AdminCommentReportResolveResponse>(
        `/api/admin/reports/${encodeURIComponent(reportId)}/resolve`,
        {
          method: 'POST',
          body: JSON.stringify({ confirmed, result })
        }
      )
      replaceModerationReport(response.report)
      return response.report
    } catch (caught) {
      moderationReportsError.value = moderationErrorMessage(
        caught,
        '处理举报失败'
      )
      return null
    } finally {
      moderationReportActionLoading.value = false
    }
  }

  async function loadModerationFeedback(
    query: AdminModerationFeedbackQuery = moderationFeedbackQuery.value,
    offset = 0,
    limit = MODERATION_PAGE_SIZE
  ): Promise<boolean> {
    moderationFeedbackLoading.value = true
    moderationFeedbackError.value = ''
    moderationFeedbackQuery.value = query
    try {
      const response = await apiFetch<AdminFeedbackListResponse>(
        `/api/admin/feedback${moderationQueueQuery(
          {
            status: query.status === 'all' ? '' : query.status,
            submitter_id: query.submitter_id.trim(),
            created_from: query.created_from,
            created_to: query.created_to
          },
          offset,
          limit
        )}`
      )
      moderationFeedback.value = response.items
      moderationFeedbackCount.value = response.count
      return true
    } catch (caught) {
      moderationFeedback.value = []
      moderationFeedbackCount.value = 0
      moderationFeedbackError.value = moderationErrorMessage(
        caught,
        '反馈队列加载失败'
      )
      return false
    } finally {
      moderationFeedbackLoading.value = false
    }
  }

  function replaceModerationFeedback(
    feedback: AdminUpdatedFeedbackRecord
  ): void {
    moderationFeedback.value = moderationFeedback.value.map(item =>
      item.feedback_id === feedback.feedback_id
        ? {
            ...item,
            status: feedback.status,
            handler_id: feedback.handler_id,
            handler: feedback.handler,
            result: feedback.result,
            updated_at: feedback.updated_at
          }
        : item
    )
  }

  async function updateModerationFeedback(
    feedbackId: string,
    status: AdminFeedbackStatus,
    result: string
  ): Promise<AdminUpdatedFeedbackRecord | null> {
    moderationFeedbackActionLoading.value = true
    moderationFeedbackError.value = ''
    try {
      const response = await apiFetch<AdminFeedbackUpdateResponse>(
        `/api/admin/feedback/${encodeURIComponent(feedbackId)}`,
        {
          method: 'PATCH',
          body: JSON.stringify({ status, result })
        }
      )
      replaceModerationFeedback(response.feedback)
      return response.feedback
    } catch (caught) {
      moderationFeedbackError.value = moderationErrorMessage(
        caught,
        '更新反馈状态失败'
      )
      return null
    } finally {
      moderationFeedbackActionLoading.value = false
    }
  }

  function clearModerationCommentsError() {
    moderationCommentsError.value = ''
  }

  function clearModerationReportsError() {
    moderationReportsError.value = ''
  }

  function clearModerationFeedbackError() {
    moderationFeedbackError.value = ''
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
    loadDashboard,
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
    clearRedemptionDetailError,
    announcements,
    announcementsLoading,
    announcementsError,
    announcementAccessDenied,
    announcementActionLoading,
    announcementFormError,
    announcementFormErrorCode,
    announcementPublishResult,
    loadAnnouncements,
    createAnnouncement,
    publishAnnouncement,
    clearAnnouncementFormError,
    clearAnnouncementsError,
    clearAnnouncementPublishResult,
    pointsPolicy,
    pointsPolicyLoading,
    pointsPolicyError,
    pointsPolicyActionLoading,
    pointsPolicyFormError,
    pointsPolicyFormErrorCode,
    loadPointsPolicy,
    savePointsPolicy,
    clearPointsPolicyFormError,
    moderationComments,
    moderationCommentCount,
    moderationCommentsLoading,
    moderationCommentsError,
    moderationCommentActionLoading,
    moderationReports,
    moderationReportCount,
    moderationReportsLoading,
    moderationReportsError,
    moderationReportActionLoading,
    moderationFeedback,
    moderationFeedbackCount,
    moderationFeedbackLoading,
    moderationFeedbackError,
    moderationFeedbackActionLoading,
    loadModerationComments,
    deleteModerationComment,
    clearModerationCommentsError,
    loadModerationReports,
    resolveModerationReport,
    clearModerationReportsError,
    loadModerationFeedback,
    updateModerationFeedback,
    clearModerationFeedbackError
  }
})
