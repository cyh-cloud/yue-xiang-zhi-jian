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

// 后端只接受带时区的 ISO 8601 时间戳，`type="date"` 的裸值需加宽为平台当日边界。
// 若某个值已经带上时间分量（即此前已加宽过），则原样透传，保证加宽幂等——
// 否则经 store 默认参数 query 回灌的 ISO 串会被再次拼成
// `...T00:00:00+08:00T00:00:00+08:00`。
export function widenModerationDay(filters: {
  created_from: string
  created_to: string
}): { created_from: string; created_to: string } {
  const widen = (value: string, endOfDay: boolean): string => {
    if (!value) return ''
    if (value.includes('T')) return value
    return endOfDay ? `${value}T23:59:59+08:00` : `${value}T00:00:00+08:00`
  }
  return {
    created_from: widen(filters.created_from, false),
    created_to: widen(filters.created_to, true)
  }
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

export type AdminPresetCategory =
  | 'agri_products'
  | 'agri_calendar'
  | 'pest_knowledge'
  | 'handcraft_crafts'
  | 'success_cases'
  | 'assistant_knowledge'

export interface AdminAgriProductPreset {
  product_key: string
  name: string
  sort_order: number
  is_enabled: boolean
  version: number
  created_at: string
  updated_at: string
}

export interface AdminAgriCalendarPreset {
  item_id: string
  product_key: string
  month: number
  tasks: string[]
  management: string[]
  solar_terms: string[]
  reminder: string
  sort_order: number
  is_enabled: boolean
  version: number
  created_at: string
  updated_at: string
}

export interface AdminPestKnowledgePreset {
  item_id: string
  sort_order: number
  pest_name: string
  product_names: string[]
  symptoms: string[]
  aliases: string[]
  answer: string
  is_enabled: boolean
  version: number
  created_at: string
  updated_at: string
}

export interface AdminCraftPresetStep {
  step_no: number
  step_key: string
  title: string
  description: string
  tips: string[]
}

export interface AdminCraftMaterialGuide {
  name: string
  reference_price: string
  purchase_channel: string
  precautions: string
  taobao_keyword: string
}

export interface AdminHandcraftCraftPreset {
  craft_key: string
  name: string
  introduction: string
  steps: AdminCraftPresetStep[]
  material_guide: AdminCraftMaterialGuide[]
  is_demo: boolean
  source_available: boolean
  available: boolean
  sort_order: number
  is_enabled: boolean
  version: number
  created_at: string
  updated_at: string
}

// The 06 read shape names the stable id `id`, while the console write paths
// call the same value `case_id`, so both spellings are kept apart here.
export interface AdminSuccessCasePreset {
  id: string
  title: string
  summary: string
  background: string
  journey: string
  lessons: string
  published_at: string
  updated_at: string
  is_demo: boolean
  sort_order: number
  is_enabled: boolean
  source_available: boolean
  version: number
}

export interface AdminAssistantKnowledgePreset {
  knowledge_id: string
  title: string
  body: string
  feature_key: string
  jump_target: string
  is_enabled: boolean
  sort_order: number
  version: number
  created_at: string
  updated_at: string
}

export type AdminPresetItem =
  | AdminAgriProductPreset
  | AdminAgriCalendarPreset
  | AdminPestKnowledgePreset
  | AdminHandcraftCraftPreset
  | AdminSuccessCasePreset
  | AdminAssistantKnowledgePreset

export interface AdminAgriProductPresetPayload {
  product_key?: string
  name: string
  sort_order?: number
  is_enabled?: boolean
  expected_version?: number
}

export interface AdminAgriCalendarPresetPayload {
  product_key?: string
  month?: number
  tasks: string[]
  management: string[]
  solar_terms: string[]
  reminder: string
  sort_order?: number
  is_enabled?: boolean
  expected_version?: number
}

export interface AdminPestKnowledgePresetPayload {
  item_id?: string
  sort_order?: number
  pest_name: string
  product_names: string[]
  symptoms: string[]
  aliases: string[]
  answer: string
  is_enabled?: boolean
  expected_version?: number
}

export interface AdminHandcraftCraftPresetPayload {
  craft_key?: string
  name: string
  introduction: string
  steps: AdminCraftPresetStep[]
  material_guide: AdminCraftMaterialGuide[]
  source_available?: boolean
  sort_order?: number
  is_enabled?: boolean
  expected_version?: number
}

export interface AdminSuccessCasePresetPayload {
  case_id?: string
  title: string
  summary: string
  background: string
  journey: string
  lessons: string
  sort_order?: number
  published_at: string
  is_enabled?: boolean
  expected_version?: number
}

export interface AdminAssistantKnowledgePresetPayload {
  knowledge_id?: string
  title: string
  body: string
  feature_key: string
  jump_target?: string
  sort_order?: number
  is_enabled?: boolean
  expected_version?: number
}

export type AdminPresetPayload =
  | AdminAgriProductPresetPayload
  | AdminAgriCalendarPresetPayload
  | AdminPestKnowledgePresetPayload
  | AdminHandcraftCraftPresetPayload
  | AdminSuccessCasePresetPayload
  | AdminAssistantKnowledgePresetPayload

export interface AdminPresetListResponse {
  success: true
  items: AdminPresetItem[]
  count: number
}

export interface AdminPresetItemResponse {
  success: true
  item: AdminPresetItem
}

// --- managed content (Task 25) ----------------------------------------------

export type AdminManagedContentType =
  | 'policy'
  | 'news'
  | 'course'
  | 'job'
  | 'handcraft_video'
  | 'comment'
  | 'preset'

export interface AdminManagedPolicyItem {
  content_type: 'policy'
  id: string
  title: string
  content: string
  category_code: string
  status: string
  view_count: number
  version: number
  published_at: string | null
  updated_at: string
}

export interface AdminManagedNewsItem {
  content_type: 'news'
  id: string
  title: string
  content: string
  category_code: string
  view_count: number
  version: number
  published_at: string | null
  updated_at: string
}

export interface AdminManagedCourseItem {
  content_type: 'course'
  id: number
  title: string
  direction: string
  status: string
  teacher_id: number | null
  teacher_name: string
  version: number
  published_at: string | null
  deleted_at: string | null
  updated_at: string
}

export interface AdminManagedJobItem {
  content_type: 'job'
  job_id: string
  title: string
  enterprise_id: number
  review_status: string
  version: number
  published_at: string | null
  deleted_at: string | null
  updated_at: string
}

export interface AdminManagedVideoItem {
  content_type: 'handcraft_video'
  video_id: string
  craft_key: string
  title: string
  review_status: string
  version: number
  published_at: string | null
  deleted_at: string | null
  updated_at: string
}

export interface AdminManagedCommentItem {
  content_type: 'comment'
  comment_id: string
  target_content_type: string
  target_content_id: string
  author_id: number
  body: string
  is_visible: boolean
  created_at: string
  updated_at: string
}

export interface AdminManagedPresetItem {
  content_type: 'preset'
  // The managed-preset projection is widening from the handcraft crafts alone
  // to all six preset families, so a row names its family and carries a stable
  // id instead of the craft-only spellings. The craft-only fields stay
  // optional until the widened projection lands.
  preset_category?: AdminPresetCategory
  id?: string
  // The union projection keeps the family-encoded id and the bare stable id
  // side by side, so the table can show the id a human reads and still
  // address the row by the one the route decodes.
  stable_id?: string
  sort_order?: number
  craft_key?: string
  name?: string
  title?: string
  is_enabled: boolean
  version: number
  updated_at: string
}

export type AdminManagedContentItem =
  | AdminManagedPolicyItem
  | AdminManagedNewsItem
  | AdminManagedCourseItem
  | AdminManagedJobItem
  | AdminManagedVideoItem
  | AdminManagedCommentItem
  | AdminManagedPresetItem

// A correction only rewrites the copy of a row: policy and news name the body
// `content`, a course a `summary`, a job a `description`, and a video carries
// a title alone, so every spelling stays optional on the way out.
export interface AdminManagedContentCorrectionPayload {
  title: string
  content?: string
  summary?: string
  description?: string
}

export interface AdminManagedContentListResponse {
  success: true
  items: AdminManagedContentItem[]
  count: number
}

export interface AdminManagedContentItemResponse {
  success: true
  item: AdminManagedContentItem
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

  // One category of presets is open at a time, so a single row set covers all
  // six: the backend lists the whole table without paging, and every write
  // answers with the stored row so the console can refresh what it shows.
  const presetCategory = ref<AdminPresetCategory>('agri_products')
  const presetItems = ref<AdminPresetItem[]>([])
  const presetCount = ref(0)
  const presetsLoading = ref(false)
  const presetsError = ref('')
  const presetActionLoading = ref(false)
  const presetFormError = ref('')
  const presetFormErrorCode = ref('')

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

  // The preset module reports a validation failure against the field that
  // failed and a conflict against the stable id that already exists, so the
  // console maps those codes to a sentence the operator can act on and lets
  // the backend's own message through for everything else.
  const PRESET_ERROR_CODES: Record<string, string> = {
    agri_product_preset_conflict: '农产品稳定 ID 已存在，请更换后重试',
    agri_calendar_preset_conflict: '该农产品当月农时已存在，请改月或改用既有条目',
    pest_knowledge_preset_conflict: '病虫害条目 ID 已存在，请更换后重试',
    craft_preset_conflict: '技艺键已存在，请更换后重试',
    case_preset_conflict: '案例 ID 已存在，请更换后重试',
    knowledge_preset_conflict: '知识条目 ID 已存在，请更换后重试',
    agri_product_preset_not_found: '农产品条目不存在或已被其他管理员删除',
    agri_calendar_preset_not_found: '农时条目不存在或已被其他管理员删除',
    pest_knowledge_preset_not_found: '病虫害条目不存在或已被其他管理员删除',
    craft_preset_not_found: '技艺内容不存在或已被其他管理员删除',
    case_preset_not_found: '成功案例不存在或已被其他管理员删除',
    knowledge_preset_not_found: '知识条目不存在或已被其他管理员删除',
    agri_product_preset_version_conflict:
      '农产品已被其他管理员修改，列表已刷新，请确认最新内容后重新保存',
    agri_calendar_preset_version_conflict:
      '农时条目已被其他管理员修改，列表已刷新，请确认最新内容后重新保存',
    pest_knowledge_preset_version_conflict:
      '病虫害条目已被其他管理员修改，列表已刷新，请确认最新内容后重新保存',
    craft_preset_version_conflict:
      '技艺内容已被其他管理员修改，列表已刷新，请确认最新内容后重新保存',
    case_preset_version_conflict:
      '成功案例已被其他管理员修改，列表已刷新，请确认最新内容后重新保存',
    knowledge_preset_version_conflict:
      '知识条目已被其他管理员修改，列表已刷新，请确认最新内容后重新保存',
    demo_case_not_editable:
      '演示案例由平台种子维护，每次启动都会被还原；请新建案例后再编辑或停用',
    product_key_mismatch: '农产品稳定 ID 与请求路径不一致，不可修改',
    item_id_mismatch: '条目稳定 ID 与请求路径不一致，不可修改',
    craft_key_mismatch: '技艺键与请求路径不一致，不可修改',
    case_id_mismatch: '案例稳定 ID 与请求路径不一致，不可修改',
    knowledge_id_mismatch: '知识条目稳定 ID 与请求路径不一致，不可修改',
    month_mismatch: '月份与既有农时条目不一致，不可修改'
  }

  function presetErrorMessage(caught: unknown, fallback: string): string {
    if (caught instanceof ApiError && caught.code) {
      const mapped = PRESET_ERROR_CODES[caught.code]
      if (mapped) {
        return mapped
      }
    }
    return errorMessage(caught, fallback)
  }

  function presetErrorCode(caught: unknown): string {
    return caught instanceof ApiError && caught.code ? caught.code : ''
  }

  async function loadPresets(
    category: AdminPresetCategory
  ): Promise<boolean> {
    presetsLoading.value = true
    presetsError.value = ''
    presetCategory.value = category
    try {
      const response = await apiFetch<AdminPresetListResponse>(
        `/api/admin/presets/${category}`
      )
      presetItems.value = response.items
      presetCount.value = response.count
      return true
    } catch (caught) {
      presetItems.value = []
      presetCount.value = 0
      presetsError.value = presetErrorMessage(caught, '预置内容加载失败')
      return false
    } finally {
      presetsLoading.value = false
    }
  }

  async function createPreset(
    category: AdminPresetCategory,
    payload: AdminPresetPayload
  ): Promise<AdminPresetItem | null> {
    presetActionLoading.value = true
    presetFormError.value = ''
    presetFormErrorCode.value = ''
    try {
      const response = await apiFetch<AdminPresetItemResponse>(
        `/api/admin/presets/${category}`,
        {
          method: 'POST',
          body: JSON.stringify(payload)
        }
      )
      await loadPresets(category)
      return response.item
    } catch (caught) {
      presetFormError.value = presetErrorMessage(caught, '创建预置内容失败')
      presetFormErrorCode.value = presetErrorCode(caught)
      return null
    } finally {
      presetActionLoading.value = false
    }
  }

  async function updatePreset(
    category: AdminPresetCategory,
    itemId: string,
    payload: AdminPresetPayload
  ): Promise<AdminPresetItem | null> {
    presetActionLoading.value = true
    presetFormError.value = ''
    presetFormErrorCode.value = ''
    try {
      const response = await apiFetch<AdminPresetItemResponse>(
        `/api/admin/presets/${category}/${encodeURIComponent(itemId)}`,
        {
          method: 'PUT',
          body: JSON.stringify(payload)
        }
      )
      await loadPresets(category)
      return response.item
    } catch (caught) {
      // A 409 means another admin already moved the row: reload so the edit
      // form can re-seed its expected version from the server values, then
      // keep the conflict text next to the form.
      presetFormError.value = presetErrorMessage(caught, '保存预置内容失败')
      presetFormErrorCode.value = presetErrorCode(caught)
      if (caught instanceof ApiError && caught.status === 409) {
        await loadPresets(category)
      }
      return null
    } finally {
      presetActionLoading.value = false
    }
  }

  async function disablePreset(
    category: AdminPresetCategory,
    itemId: string,
    expectedVersion: number
  ): Promise<AdminPresetItem | null> {
    presetActionLoading.value = true
    presetsError.value = ''
    try {
      const search = new URLSearchParams({
        expected_version: String(expectedVersion)
      })
      const response = await apiFetch<AdminPresetItemResponse>(
        `/api/admin/presets/${category}/${encodeURIComponent(itemId)}?${search.toString()}`,
        { method: 'DELETE' }
      )
      await loadPresets(category)
      return response.item
    } catch (caught) {
      presetsError.value = presetErrorMessage(caught, '停用预置内容失败')
      if (caught instanceof ApiError && caught.status === 409) {
        await loadPresets(category)
      }
      return null
    } finally {
      presetActionLoading.value = false
    }
  }

  function clearPresetsError() {
    presetsError.value = ''
  }

  function clearPresetFormError() {
    presetFormError.value = ''
    presetFormErrorCode.value = ''
  }

  // Cross-platform data management is a super-admin surface: one content type
  // is open at a time, the backend lists the whole table without paging, and
  // every write answers with the stored row so the console re-reads the list
  // instead of guessing the committed version.
  const managedContentType = ref<AdminManagedContentType>('policy')
  const managedContentItems = ref<AdminManagedContentItem[]>([])
  const managedContentCount = ref(0)
  const managedContentLoading = ref(false)
  const managedContentError = ref('')
  const managedContentActionLoading = ref(false)
  const managedContentFormError = ref('')
  const managedContentFormErrorCode = ref('')
  const managedContentDetail = ref<AdminManagedContentItem | null>(null)
  const managedContentDetailLoading = ref(false)
  const managedContentDetailError = ref('')

  // The data-management module reports a version conflict per content type and
  // a state conflict for the rows whose current status blocks the action, so
  // the console maps those codes to a sentence the operator can act on and
  // lets the backend's own message through for everything else.
  const MANAGED_CONTENT_ERROR_CODES: Record<string, string> = {
    content_type_invalid: '内容类型不正确，请刷新页面后重试',
    content_correct_unsupported: '该内容类型不支持纠错',
    content_unpublish_unsupported: '该内容类型不支持下线',
    content_not_found: '内容不存在或已被其他管理员删除',
    policy_not_found: '政策不存在或已被其他管理员删除',
    news_not_found: '新闻不存在或已被其他管理员删除',
    course_not_found: '课程不存在或已被其他管理员删除',
    job_not_found: '职位不存在或已被其他管理员删除',
    video_not_found: '视频不存在或已被其他管理员删除',
    comment_not_found: '评论不存在或已被其他管理员删除',
    preset_not_found: '预置内容不存在或已被其他管理员删除',
    craft_preset_not_found: '预置技艺不存在或已被其他管理员删除',
    comment_already_hidden: '评论已被隐藏，列表已刷新',
    policy_version_conflict:
      '政策已被其他管理员修改，列表已刷新，请确认最新内容后重试',
    news_version_conflict:
      '新闻已被其他管理员修改，列表已刷新，请确认最新内容后重试',
    course_version_conflict:
      '课程已被其他管理员修改，列表已刷新，请确认最新内容后重试',
    job_version_conflict:
      '职位已被其他管理员修改，列表已刷新，请确认最新内容后重试',
    video_version_conflict:
      '视频已被其他管理员修改，列表已刷新，请确认最新内容后重试',
    craft_preset_version_conflict:
      '预置技艺已被其他管理员修改，列表已刷新，请确认最新内容后重试',
    policy_state_conflict: '政策当前状态不允许下线，列表已刷新',
    course_state_conflict: '课程当前状态不允许下线，列表已刷新',
    job_state_conflict: '职位当前状态不允许下线，列表已刷新',
    video_state_conflict: '视频当前状态不允许下线，列表已刷新'
  }

  function managedContentErrorMessage(
    caught: unknown,
    fallback: string
  ): string {
    if (caught instanceof ApiError && caught.code) {
      const mapped = MANAGED_CONTENT_ERROR_CODES[caught.code]
      if (mapped) {
        return mapped
      }
    }
    return errorMessage(caught, fallback)
  }

  function managedContentErrorCode(caught: unknown): string {
    return caught instanceof ApiError && caught.code ? caught.code : ''
  }

  async function loadManagedContent(
    contentType: AdminManagedContentType
  ): Promise<boolean> {
    managedContentLoading.value = true
    managedContentError.value = ''
    managedContentType.value = contentType
    try {
      const response = await apiFetch<AdminManagedContentListResponse>(
        `/api/admin/content/${contentType}`
      )
      managedContentItems.value = response.items
      managedContentCount.value = response.count
      return true
    } catch (caught) {
      managedContentItems.value = []
      managedContentCount.value = 0
      managedContentError.value = managedContentErrorMessage(
        caught,
        '内容列表加载失败'
      )
      return false
    } finally {
      managedContentLoading.value = false
    }
  }

  async function loadManagedContentDetail(
    contentType: AdminManagedContentType,
    contentId: string
  ): Promise<boolean> {
    managedContentDetailLoading.value = true
    managedContentDetailError.value = ''
    try {
      const response = await apiFetch<AdminManagedContentItemResponse>(
        `/api/admin/content/${encodeURIComponent(contentType)}/${encodeURIComponent(contentId)}`
      )
      managedContentDetail.value = response.item
      return true
    } catch (caught) {
      managedContentDetail.value = null
      managedContentDetailError.value = managedContentErrorMessage(
        caught,
        '内容详情加载失败'
      )
      return false
    } finally {
      managedContentDetailLoading.value = false
    }
  }

  async function correctManagedContent(
    contentType: AdminManagedContentType,
    contentId: string,
    expectedVersion: number,
    payload: AdminManagedContentCorrectionPayload
  ): Promise<AdminManagedContentItem | null> {
    managedContentActionLoading.value = true
    managedContentFormError.value = ''
    managedContentFormErrorCode.value = ''
    try {
      const response = await apiFetch<AdminManagedContentItemResponse>(
        `/api/admin/content/${contentType}/${encodeURIComponent(contentId)}`,
        {
          method: 'PUT',
          body: JSON.stringify({
            ...payload,
            expected_version: expectedVersion
          })
        }
      )
      // A correction bumps the row's version, so the table is re-read to show
      // the stored version instead of the one that was sent.
      await loadManagedContent(contentType)
      return response.item
    } catch (caught) {
      // A 409 means another admin already moved the row: reload so the form
      // can re-seed its expected version from the server values, then keep
      // the conflict text next to the form.
      if (caught instanceof ApiError && caught.status === 409) {
        await loadManagedContent(contentType)
      }
      managedContentFormError.value = managedContentErrorMessage(
        caught,
        '保存纠错失败'
      )
      managedContentFormErrorCode.value = managedContentErrorCode(caught)
      return null
    } finally {
      managedContentActionLoading.value = false
    }
  }

  async function unpublishManagedContent(
    contentType: AdminManagedContentType,
    contentId: string,
    expectedVersion: number
  ): Promise<AdminManagedContentItem | null> {
    managedContentActionLoading.value = true
    managedContentError.value = ''
    try {
      const response = await apiFetch<AdminManagedContentItemResponse>(
        `/api/admin/content/${contentType}/${encodeURIComponent(contentId)}/unpublish`,
        {
          method: 'POST',
          body: JSON.stringify({ expected_version: expectedVersion })
        }
      )
      await loadManagedContent(contentType)
      return response.item
    } catch (caught) {
      // The reload clears the banner, so the message is captured first and
      // written back afterwards.
      const message = managedContentErrorMessage(caught, '下线内容失败')
      if (caught instanceof ApiError && caught.status === 409) {
        await loadManagedContent(contentType)
      }
      managedContentError.value = message
      return null
    } finally {
      managedContentActionLoading.value = false
    }
  }

  async function deleteManagedContent(
    contentType: AdminManagedContentType,
    contentId: string,
    expectedVersion?: number
  ): Promise<AdminManagedContentItem | null> {
    managedContentActionLoading.value = true
    managedContentError.value = ''
    try {
      // The comment projection carries no optimistic lock, so a version is
      // only sent for the types that own one.
      const body =
        expectedVersion === undefined
          ? {}
          : { expected_version: expectedVersion }
      const response = await apiFetch<AdminManagedContentItemResponse>(
        `/api/admin/content/${contentType}/${encodeURIComponent(contentId)}`,
        {
          method: 'DELETE',
          body: JSON.stringify(body)
        }
      )
      await loadManagedContent(contentType)
      return response.item
    } catch (caught) {
      // The reload clears the banner, so the message is captured first and
      // written back afterwards.
      const message = managedContentErrorMessage(caught, '删除内容失败')
      if (caught instanceof ApiError && caught.status === 409) {
        await loadManagedContent(contentType)
      }
      managedContentError.value = message
      return null
    } finally {
      managedContentActionLoading.value = false
    }
  }

  function clearManagedContentError() {
    managedContentError.value = ''
  }

  function clearManagedContentFormError() {
    managedContentFormError.value = ''
    managedContentFormErrorCode.value = ''
  }

  function clearManagedContentDetail() {
    managedContentDetail.value = null
    managedContentDetailError.value = ''
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
    clearModerationFeedbackError,
    presetCategory,
    presetItems,
    presetCount,
    presetsLoading,
    presetsError,
    presetActionLoading,
    presetFormError,
    presetFormErrorCode,
    loadPresets,
    createPreset,
    updatePreset,
    disablePreset,
    clearPresetsError,
    clearPresetFormError,
    managedContentType,
    managedContentItems,
    managedContentCount,
    managedContentLoading,
    managedContentError,
    managedContentActionLoading,
    managedContentFormError,
    managedContentFormErrorCode,
    managedContentDetail,
    managedContentDetailLoading,
    managedContentDetailError,
    loadManagedContent,
    loadManagedContentDetail,
    correctManagedContent,
    unpublishManagedContent,
    deleteManagedContent,
    clearManagedContentError,
    clearManagedContentFormError,
    clearManagedContentDetail
  }
})
