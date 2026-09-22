<script setup lang="ts">
import {
  Check,
  Database,
  Eye,
  Inbox,
  Pencil,
  RefreshCw,
  ShieldAlert,
  Trash2,
  Undo2,
  X
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import type {
  AdminReviewContentType,
  AdminReviewStatus
} from '@/api/types'
import type {
  AdminPresetCategory,
  AdminManagedContentCorrectionPayload,
  AdminManagedContentItem,
  AdminManagedVideoItem,
  AdminManagedContentType
} from '@/stores/adminConsole'
import { useAdminConsoleStore } from '@/stores/adminConsole'

// How a delete removes the row. The backend fixes the semantics per content
// type and the console has to say out loud which one the operator is about to
// run, because only one of them is reversible.
type DeleteMode = 'hard' | 'tombstone' | 'hide' | 'disable'

interface ContentTypeDefinition {
  id: AdminManagedContentType
  label: string
  itemNoun: string
  supportsCorrection: boolean
  supportsUnpublish: boolean
  deleteMode: DeleteMode
  deleteLabel: string
  bodyLabel: string
  // The management read surface returns the copy of policy, news and video
  // rows, while a course summary and a job description stay behind their own
  // editors, so those two forms start with an empty body and say why.
  bodyReturned: boolean
}

interface DetailEntry {
  label: string
  value: string
}

interface CorrectionFormState {
  title: string
  body: string
}

interface ContentCandidate {
  id: string
  label: string
  version: number | null
}

// The backend is the authority for which write each content type accepts, so
// the console mirrors its handler table: news and comments cannot be taken
// offline, comments and presets cannot be corrected, and a preset reaches the
// same logical disable through either path, which is why it only carries the
// one control instead of two identical ones.
const contentTypes: ReadonlyArray<ContentTypeDefinition> = [
  {
    id: 'policy',
    label: '政策',
    itemNoun: '政策',
    supportsCorrection: true,
    supportsUnpublish: true,
    deleteMode: 'hard',
    deleteLabel: '删除',
    bodyLabel: '正文',
    bodyReturned: true
  },
  {
    id: 'news',
    label: '新闻',
    itemNoun: '新闻',
    supportsCorrection: true,
    supportsUnpublish: false,
    deleteMode: 'hard',
    deleteLabel: '删除',
    bodyLabel: '正文',
    bodyReturned: true
  },
  {
    id: 'course',
    label: '课程',
    itemNoun: '课程',
    supportsCorrection: true,
    supportsUnpublish: true,
    deleteMode: 'tombstone',
    deleteLabel: '删除',
    bodyLabel: '课程简介',
    bodyReturned: false
  },
  {
    id: 'job',
    label: '职位',
    itemNoun: '职位',
    supportsCorrection: true,
    supportsUnpublish: true,
    deleteMode: 'tombstone',
    deleteLabel: '删除',
    bodyLabel: '职位描述',
    bodyReturned: false
  },
  {
    id: 'handcraft_video',
    label: '非遗视频',
    itemNoun: '视频',
    supportsCorrection: true,
    supportsUnpublish: true,
    deleteMode: 'tombstone',
    deleteLabel: '删除',
    bodyLabel: '标题',
    bodyReturned: true
  },
  {
    id: 'comment',
    label: '评论',
    itemNoun: '评论',
    supportsCorrection: false,
    supportsUnpublish: false,
    deleteMode: 'hide',
    deleteLabel: '隐藏',
    bodyLabel: '评论内容',
    bodyReturned: true
  },
  {
    id: 'preset',
    label: '预置技艺',
    itemNoun: '技艺',
    supportsCorrection: false,
    supportsUnpublish: false,
    deleteMode: 'disable',
    deleteLabel: '停用',
    bodyLabel: '技艺简介',
    bodyReturned: true
  }
]

const STATUS_LABELS: Record<string, string> = {
  active: '已发布',
  unpublished: '已下线',
  draft: '草稿',
  pending: '待审核',
  published: '已发布',
  offline: '已下线',
  approved: '已通过',
  rejected: '已驳回'
}

const CATEGORY_LABELS: Record<string, string> = {
  subsidy: '补贴扶持',
  ecommerce: '电商扶持',
  heritage: '非遗传承',
  training: '培训提升',
  certification: '认证认定',
  general: '综合政务',
  entrepreneurship: '创业支持',
  news: '新闻资讯',
  disaster_warning: '灾害预警',
  policy_update: '政策更新'
}

const DIRECTION_LABELS: Record<string, string> = {
  agriculture: '农业',
  ecommerce: '电商',
  handcraft: '非遗'
}

const reviewTypeOptions: ReadonlyArray<{
  value: AdminReviewContentType
  label: string
}> = [
  { value: 'course_video', label: '课程视频' },
  { value: 'job_position', label: '招聘职位' },
  { value: 'handcraft_teaching_video', label: '非遗教学视频' }
]

// The managed-preset projection is widening from the handcraft crafts alone
// to every preset family, so a preset row is read as a family plus a stable
// id rather than as a craft.
const presetFamilies: ReadonlyArray<AdminPresetCategory> = [
  'agri_products',
  'agri_calendar',
  'pest_knowledge',
  'handcraft_crafts',
  'success_cases',
  'assistant_knowledge'
]

const PRESET_FAMILY_LABELS: Record<AdminPresetCategory, string> = {
  agri_products: '农产品',
  agri_calendar: '农时月历',
  pest_knowledge: '病虫害',
  handcraft_crafts: '非遗技艺',
  success_cases: '成功案例',
  assistant_knowledge: '助手知识'
}

const store = useAdminConsoleStore()

// 复用 store 的 canManagePlatform，作为“是否超管”的单一来源，避免与壳层角色派生
// 分裂（行为不变：仍为 role === 'super_admin'）。
const canManage = computed(() => store.canManagePlatform)
const activeType = computed<AdminManagedContentType>(
  () => store.managedContentType
)
const activeDefinition = computed(
  () => contentTypes.find(item => item.id === activeType.value) ?? contentTypes[0]
)

const correctionId = ref<string | null>(null)
const correctionVersion = ref<number | null>(null)
const correctionLabel = ref('')
const correctionForm = ref<CorrectionFormState>({ title: '', body: '' })
const actionMessage = ref('')
const unpublishCandidate = ref<ContentCandidate | null>(null)
const deleteCandidate = ref<ContentCandidate | null>(null)
const reviewFilter = ref<'all' | AdminReviewContentType>('all')

const isCorrecting = computed(() => correctionId.value !== null)
const canSubmitCorrection = computed(() => {
  if (!isCorrecting.value) return false
  if (correctionForm.value.title.trim().length === 0) return false
  return (
    activeType.value === 'handcraft_video' ||
    correctionForm.value.body.trim().length > 0
  )
})

const filteredReviewItems = computed(() =>
  reviewFilter.value === 'all'
    ? store.reviewItems
    : store.reviewItems.filter(item => item.content_type === reviewFilter.value)
)
const pendingReviewTotal = computed(() =>
  reviewTypeOptions.reduce(
    (total, option) => total + store.reviewCounts[option.value],
    0
  )
)
const detailOpen = computed(
  () =>
    store.managedContentDetailLoading ||
    store.managedContentDetail !== null ||
    store.managedContentDetailError !== ''
)

// The video list projection is gaining its own `content_type` to match the
// detail projection. Until that lands, a row that carries none is the video
// row of the type that was just listed, so the console names it here instead
// of letting it fall through to the preset branch.
const listRows = computed<AdminManagedContentItem[]>(() =>
  store.managedContentItems.map(item => {
    // The tag is read as optional because the list projection is still
    // catching up with the detail projection.
    const raw = item as Partial<AdminManagedContentItem>
    if (raw.content_type) return item
    return {
      ...raw,
      content_type: 'handcraft_video'
    } as AdminManagedVideoItem
  })
)

function itemId(item: AdminManagedContentItem): string {
  switch (item.content_type) {
    case 'policy':
    case 'news':
      return item.id
    case 'course':
      return String(item.id)
    case 'job':
      return item.job_id
    case 'handcraft_video':
      return item.video_id
    case 'comment':
      return item.comment_id
    default:
      // A preset row is addressed by the stable id the projection encodes,
      // which carries its family prefix once the widened projection lands.
      return item.id ?? item.craft_key ?? ''
  }
}

function itemTitle(item: AdminManagedContentItem): string {
  switch (item.content_type) {
    case 'comment':
      return item.body
    case 'preset':
      // Every preset family spells its label differently, so the row keeps
      // whichever spelling the projection sent.
      return item.name ?? item.title ?? itemId(item)
    default:
      return item.title
  }
}

function presetFamilyOf(
  item: AdminManagedContentItem
): AdminPresetCategory | null {
  if (item.content_type !== 'preset') return null
  if (item.preset_category) return item.preset_category
  // Without a family tag the stable id still encodes one as its prefix, and a
  // row with neither is the handcraft craft the projection started from.
  const raw = item.id ?? item.craft_key ?? ''
  const encoded = presetFamilies.find(
    family => raw.startsWith(`${family}:`) || raw.startsWith(`${family}-`)
  )
  return encoded ?? 'handcraft_crafts'
}

function presetFamilyLabel(item: AdminManagedContentItem): string {
  const family = presetFamilyOf(item)
  return family === null ? '' : PRESET_FAMILY_LABELS[family]
}

function itemVersion(item: AdminManagedContentItem): string {
  // The comment projection carries no optimistic lock, so there is no version
  // to display or to send.
  return item.content_type === 'comment' ? '无版本' : `v${item.version}`
}

// A row is addressed by the id the route decodes, while the table shows the
// bare stable id a human reads.
function itemStableId(item: AdminManagedContentItem): string {
  return item.content_type === 'preset' && item.stable_id
    ? item.stable_id
    : itemId(item)
}

function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status
}

function categoryLabel(code: string): string {
  return CATEGORY_LABELS[code] ?? code
}

function directionLabel(direction: string): string {
  return DIRECTION_LABELS[direction] ?? direction
}

function itemStatus(item: AdminManagedContentItem): string {
  switch (item.content_type) {
    case 'news':
      // The news table carries no lifecycle column: a row only exists once
      // it is out, so the console reports that one fixed state.
      return '已发布'
    case 'job':
    case 'handcraft_video':
      return statusLabel(item.review_status)
    case 'comment':
      return item.is_visible ? '可见' : '已隐藏'
    case 'preset':
      return item.is_enabled ? '已启用' : '已停用'
    default:
      return statusLabel(item.status)
  }
}

function statusTone(item: AdminManagedContentItem): string {
  if (item.content_type === 'comment') {
    return item.is_visible ? 'is-active' : 'is-muted'
  }
  if (item.content_type === 'preset') {
    return item.is_enabled ? 'is-active' : 'is-muted'
  }
  if (item.content_type === 'news') {
    return 'is-active'
  }
  const status =
    item.content_type === 'job' || item.content_type === 'handcraft_video'
      ? item.review_status
      : item.status
  if (status === 'pending' || status === 'draft') return 'is-pending'
  if (status === 'active' || status === 'published' || status === 'approved') {
    return 'is-active'
  }
  return 'is-muted'
}

function reviewStatusLabel(status: AdminReviewStatus): string {
  return statusLabel(status)
}

function formatTime(value: string | null): string {
  if (!value) return '时间未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23'
    })
      .formatToParts(date)
      .filter(part => part.type !== 'literal')
      .map(part => [part.type, part.value])
  )
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`
}

function detailEntries(item: AdminManagedContentItem): DetailEntry[] {
  switch (item.content_type) {
    case 'policy':
      return [
        { label: '政策 ID', value: item.id },
        { label: '标题', value: item.title },
        { label: '分类', value: categoryLabel(item.category_code) },
        { label: '状态', value: statusLabel(item.status) },
        { label: '浏览量', value: String(item.view_count) },
        { label: '版本', value: `v${item.version}` },
        { label: '发布时间', value: formatTime(item.published_at) },
        { label: '更新时间', value: formatTime(item.updated_at) },
        { label: '正文', value: item.content }
      ]
    case 'news':
      return [
        // The news table carries no lifecycle column, so the detail reports
        // the one fixed state the row has instead of inventing a status.
        {
          label: '新闻 ID',
          value: item.id
        },
        { label: '标题', value: item.title },
        { label: '分类', value: categoryLabel(item.category_code) },
        { label: '浏览量', value: String(item.view_count) },
        { label: '版本', value: `v${item.version}` },
        { label: '发布时间', value: formatTime(item.published_at) },
        { label: '更新时间', value: formatTime(item.updated_at) },
        { label: '正文', value: item.content }
      ]
    case 'course':
      return [
        { label: '课程 ID', value: String(item.id) },
        { label: '标题', value: item.title },
        { label: '方向', value: directionLabel(item.direction) },
        { label: '状态', value: statusLabel(item.status) },
        { label: '主讲教师', value: item.teacher_name || '未指定' },
        { label: '版本', value: `v${item.version}` },
        { label: '发布时间', value: formatTime(item.published_at) },
        { label: '更新时间', value: formatTime(item.updated_at) }
      ]
    case 'job':
      return [
        { label: '职位 ID', value: item.job_id },
        { label: '标题', value: item.title },
        { label: '企业 ID', value: String(item.enterprise_id) },
        { label: '审核状态', value: statusLabel(item.review_status) },
        { label: '版本', value: `v${item.version}` },
        { label: '发布时间', value: formatTime(item.published_at) },
        { label: '更新时间', value: formatTime(item.updated_at) }
      ]
    case 'handcraft_video':
      return [
        { label: '视频 ID', value: item.video_id },
        { label: '标题', value: item.title },
        { label: '技艺键', value: item.craft_key },
        { label: '审核状态', value: statusLabel(item.review_status) },
        { label: '版本', value: `v${item.version}` },
        { label: '发布时间', value: formatTime(item.published_at) },
        { label: '更新时间', value: formatTime(item.updated_at) }
      ]
    case 'comment':
      return [
        { label: '评论 ID', value: item.comment_id },
        { label: '评论内容', value: item.body },
        { label: '目标类型', value: item.target_content_type },
        { label: '目标内容', value: item.target_content_id },
        { label: '作者 ID', value: String(item.author_id) },
        { label: '可见性', value: item.is_visible ? '可见' : '已隐藏' },
        { label: '创建时间', value: formatTime(item.created_at) },
        { label: '更新时间', value: formatTime(item.updated_at) }
      ]
    default:
      return [
        { label: '预置家族', value: presetFamilyLabel(item) },
        { label: '稳定 ID', value: itemStableId(item) },
        { label: '名称', value: itemTitle(item) },
        { label: '状态', value: item.is_enabled ? '已启用' : '已停用' },
        { label: '版本', value: `v${item.version}` },
        { label: '更新时间', value: formatTime(item.updated_at) }
      ]
  }
}

function unpublishNotice(): string {
  return (
    '这是<strong>可逆下线</strong>：内容会立即停止对学员端、教师端等用户端可见，' +
    '但不会被标记删除或墓碑，之后可以重新发布恢复。下线同样受版本号保护。'
  )
}

function deleteNotice(mode: DeleteMode): string {
  switch (mode) {
    case 'hard':
      return (
        '这是<strong>不可逆的硬删除</strong>：内容及其平台记录会被永久移除，' +
        '无法恢复。删除同样受版本号保护。'
      )
    case 'tombstone':
      return (
        '这是<strong>不可逆的墓碑删除</strong>：内容会立即从各端与审核队列消失，' +
        '历史学习进度与职业申请会被保留，条目本身无法恢复。删除同样受版本号保护。'
      )
    case 'hide':
      return (
        '这是<strong>隐藏评论</strong>：评论会立即对所有用户端不可见，' +
        '后台记录保留，但无法恢复为可见。'
      )
    default:
      return (
        '这是<strong>逻辑停用</strong>：条目会立即停止对用户端可见，' +
        '但<strong>稳定 ID 会被保留</strong>，管理员在后台仍可看到并再次启用。' +
        '停用同样受版本号保护。'
      )
  }
}

function deleteDialogTitle(mode: DeleteMode): string {
  const noun = activeDefinition.value.itemNoun
  if (mode === 'hide') return '隐藏评论'
  if (mode === 'disable') return `停用${noun}`
  return `删除${noun}`
}

function deleteConfirmLabel(mode: DeleteMode): string {
  if (mode === 'hide') return '确认隐藏'
  if (mode === 'disable') return '确认停用'
  return '确认删除'
}

function deleteSuccessMessage(mode: DeleteMode, label: string): string {
  const noun = activeDefinition.value.itemNoun
  switch (mode) {
    case 'hard':
      return `已永久删除${noun}「${label}」，内容无法恢复`
    case 'tombstone':
      return `已删除${noun}「${label}」，条目已退出各端与审核队列，历史记录保留且不可恢复`
    case 'hide':
      return `已隐藏评论「${label}」，评论对所有用户端不再可见`
    default:
      return `已停用${noun}「${label}」，稳定 ID 仍保留，可再次启用`
  }
}

function selectType(id: AdminManagedContentType): void {
  if (id === activeType.value) return
  actionMessage.value = ''
  resetCorrection()
  closeDialogs()
  closeDetail()
  store.clearManagedContentError()
  store.clearManagedContentFormError()
  void store.loadManagedContent(id)
}

function startCorrection(item: AdminManagedContentItem): void {
  store.clearManagedContentFormError()
  store.clearManagedContentError()
  actionMessage.value = ''
  closeDetail()
  correctionId.value = itemId(item)
  correctionVersion.value =
    item.content_type === 'comment' ? null : item.version
  correctionLabel.value = `${itemTitle(item)}（${itemId(item)}）`
  const next: CorrectionFormState = { title: '', body: '' }
  switch (item.content_type) {
    case 'comment':
    case 'preset':
      break
    case 'handcraft_video':
      next.title = item.title
      break
    default:
      next.title = item.title
      next.body =
        item.content_type === 'course'
          ? ''
          : item.content_type === 'job'
            ? ''
            : item.content
  }
  correctionForm.value = next
}

function resetCorrection(): void {
  correctionId.value = null
  correctionVersion.value = null
  correctionLabel.value = ''
  correctionForm.value = { title: '', body: '' }
}

function correctionPayload(): AdminManagedContentCorrectionPayload {
  const title = correctionForm.value.title.trim()
  const body = correctionForm.value.body.trim()
  switch (activeType.value) {
    case 'course':
      return { title, summary: body }
    case 'job':
      return { title, description: body }
    case 'handcraft_video':
      return { title }
    default:
      return { title, content: body }
  }
}

async function submitCorrection(): Promise<void> {
  const id = correctionId.value
  const version = correctionVersion.value
  if (id === null || version === null) return
  const payload = correctionPayload()
  if (payload.title.length === 0) return
  const saved = await store.correctManagedContent(
    activeType.value,
    id,
    version,
    payload
  )
  if (saved === null) return
  actionMessage.value = `已保存${activeDefinition.value.itemNoun}纠错「${correctionLabel.value}」`
  resetCorrection()
}

// After a 409 the store has already reloaded the list, so the form re-seeds
// its expected version from the refreshed row and keeps the typed values. A
// row that vanished from the list closes the form instead.
async function resyncCorrection(): Promise<void> {
  const id = correctionId.value
  if (id === null) return
  const done = await store.loadManagedContent(activeType.value)
  if (!done) return
  const fresh = store.managedContentItems.find(item => itemId(item) === id)
  if (fresh) {
    correctionVersion.value =
      fresh.content_type === 'comment' ? null : fresh.version
    // The operator has now adopted the server's version, so the conflict
    // banner that asked for this reload is no longer the current state.
    store.clearManagedContentFormError()
    return
  }
  resetCorrection()
}

function openDetail(item: AdminManagedContentItem): void {
  actionMessage.value = ''
  void store.loadManagedContentDetail(activeType.value, itemId(item))
}

function closeDetail(): void {
  store.clearManagedContentDetail()
}

function openUnpublish(item: AdminManagedContentItem): void {
  actionMessage.value = ''
  store.clearManagedContentError()
  store.clearManagedContentFormError()
  closeDetail()
  unpublishCandidate.value = {
    id: itemId(item),
    label: itemTitle(item),
    version: item.content_type === 'comment' ? null : item.version
  }
}

function openDelete(item: AdminManagedContentItem): void {
  actionMessage.value = ''
  store.clearManagedContentError()
  store.clearManagedContentFormError()
  closeDetail()
  deleteCandidate.value = {
    id: itemId(item),
    label: itemTitle(item),
    version: item.content_type === 'comment' ? null : item.version
  }
}

function closeDialogs(): void {
  unpublishCandidate.value = null
  deleteCandidate.value = null
}

async function confirmUnpublish(): Promise<void> {
  const candidate = unpublishCandidate.value
  if (candidate === null || candidate.version === null) return
  const done = await store.unpublishManagedContent(
    activeType.value,
    candidate.id,
    candidate.version
  )
  // The dialog closes either way: a rejected action leaves the row in the list
  // with the server's version, so a stale confirmation would only invite a
  // second failing submit.
  closeDialogs()
  if (done === null) return
  actionMessage.value = `已下线${activeDefinition.value.itemNoun}「${candidate.label}」，该内容已停止对用户端可见，之后可以重新发布`
}

async function confirmDelete(): Promise<void> {
  const candidate = deleteCandidate.value
  if (candidate === null) return
  const mode = activeDefinition.value.deleteMode
  const done = await store.deleteManagedContent(
    activeType.value,
    candidate.id,
    candidate.version ?? undefined
  )
  closeDialogs()
  if (done === null) return
  actionMessage.value = deleteSuccessMessage(mode, candidate.label)
}

onMounted(() => {
  if (canManage.value) {
    void store.loadManagedContent(store.managedContentType)
    return
  }
  // The ordinary admin never asks for /api/admin/content/*: the backend
  // answers those with a 403, so the read-only view reads the shared review
  // queue and shows the supervision context that queue carries.
  void store.loadReviewQueue()
})
</script>

<template>
  <section class="admin-content" data-test="admin-content">
    <header class="content-header">
      <div class="content-header__identity">
        <Database :size="26" aria-hidden="true" />
        <div>
          <h1>全平台数据管理</h1>
          <p v-if="canManage">
            政策、新闻、课程、职位、非遗视频、评论与预置技艺七类内容在此纠错、下线与删除。
            下线可恢复，删除不可逆：课程、职位与非遗视频是墓碑，评论是隐藏，预置技艺是逻辑停用，
            新闻与政策是硬删。
          </p>
          <p v-else>
            这是只读审查视图：呈现审核状态与监管上下文。纠错、下线与删除属于超级管理员权限，
            此角色不可使用，页面不会请求内容管理接口。
          </p>
        </div>
      </div>
      <dl v-if="canManage" class="content-header__summary">
        <div>
          <dt>当前类型</dt>
          <dd data-test="content-active-type">{{ activeDefinition.label }}</dd>
        </div>
        <div>
          <dt>本类条目</dt>
          <dd class="ark-data" data-test="content-count">
            {{ store.managedContentCount }}
          </dd>
        </div>
      </dl>
      <dl v-else class="content-header__summary">
        <div>
          <dt>待处理</dt>
          <dd class="ark-data" data-test="content-readonly-pending">
            {{ pendingReviewTotal }}
          </dd>
        </div>
        <div>
          <dt>当前显示</dt>
          <dd class="ark-data" data-test="content-readonly-visible">
            {{ filteredReviewItems.length }}
          </dd>
        </div>
      </dl>
    </header>

    <template v-if="canManage">
      <div
        class="content-tabs"
        role="tablist"
        aria-label="内容类型"
        data-test="content-tabs"
      >
        <button
          v-for="type in contentTypes"
          :key="type.id"
          type="button"
          role="tab"
          :data-test="`content-type-${type.id}`"
          :class="{ 'is-active': activeType === type.id }"
          :aria-selected="activeType === type.id"
          @click="selectType(type.id)"
        >
          <span>{{ type.label }}</span>
        </button>
      </div>

      <p
        v-if="actionMessage"
        class="content-message"
        data-test="content-message"
        role="status"
      >
        <Check :size="17" aria-hidden="true" />
        {{ actionMessage }}
      </p>

      <div
        v-if="store.managedContentError"
        class="content-error"
        data-test="content-error"
        role="alert"
      >
        <ShieldAlert :size="18" aria-hidden="true" />
        <span>{{ store.managedContentError }}</span>
        <button
          type="button"
          data-test="content-retry"
          :disabled="store.managedContentLoading"
          @click="store.loadManagedContent(activeType)"
        >
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </div>

      <section
        class="content-registry"
        aria-labelledby="content-registry-title"
      >
        <header class="content-registry__heading">
          <h2 id="content-registry-title">{{ activeDefinition.label }}列表</h2>
          <span class="ark-data" data-test="content-registry-count">
            {{ store.managedContentCount }} 条
          </span>
        </header>

        <div
          v-if="
            store.managedContentLoading && store.managedContentItems.length === 0
          "
          class="content-state"
          data-test="content-loading"
          role="status"
        >
          <RefreshCw class="spinning" :size="20" aria-hidden="true" />
          正在加载{{ activeDefinition.label }}列表
        </div>

        <div
          v-else-if="listRows.length === 0 && !store.managedContentError"
          class="content-state content-state--empty"
          data-test="content-empty"
        >
          <Inbox :size="24" aria-hidden="true" />
          <span>暂无{{ activeDefinition.label }}内容</span>
        </div>

        <div v-else class="content-table-wrap">
          <table class="content-table">
            <thead>
              <tr>
                <th scope="col">内容</th>
                <th scope="col">状态</th>
                <th scope="col">版本</th>
                <th scope="col">更新时间</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in listRows"
                :key="itemId(item)"
                data-test="content-row"
                :data-content-id="itemId(item)"
              >
                <td data-label="内容">
                  <div class="content-table__title">
                    <strong>{{ itemTitle(item) }}</strong>
                    <span
                      v-if="presetFamilyOf(item)"
                      class="content-table__family"
                      data-test="content-preset-family"
                    >
                      家族 {{ presetFamilyLabel(item) }}
                    </span>
                    <span class="ark-data">ID {{ itemStableId(item) }}</span>
                  </div>
                </td>
                <td data-label="状态">
                  <span
                    class="content-status"
                    :class="statusTone(item)"
                    data-test="content-status"
                  >
                    {{ itemStatus(item) }}
                  </span>
                </td>
                <td data-label="版本">
                  <span class="ark-data" data-test="content-version">
                    {{ itemVersion(item) }}
                  </span>
                </td>
                <td data-label="更新时间">
                  <time class="ark-data" :datetime="item.updated_at">
                    {{ formatTime(item.updated_at) }}
                  </time>
                </td>
                <td data-label="操作">
                  <div class="content-actions">
                    <button
                      type="button"
                      :data-test="`content-detail-${itemId(item)}`"
                      :aria-label="`查看${activeDefinition.itemNoun}详情`"
                      :title="`查看${activeDefinition.itemNoun}详情`"
                      @click="openDetail(item)"
                    >
                      <Eye :size="16" aria-hidden="true" />
                      详情
                    </button>
                    <button
                      v-if="activeDefinition.supportsCorrection"
                      type="button"
                      :data-test="`content-correct-${itemId(item)}`"
                      :title="`纠错${activeDefinition.itemNoun}`"
                      :disabled="store.managedContentActionLoading"
                      @click="startCorrection(item)"
                    >
                      <Pencil :size="16" aria-hidden="true" />
                      纠错
                    </button>
                    <button
                      v-if="activeDefinition.supportsUnpublish"
                      type="button"
                      :data-test="`content-unpublish-${itemId(item)}`"
                      :title="`可逆下线${activeDefinition.itemNoun}`"
                      :disabled="store.managedContentActionLoading"
                      @click="openUnpublish(item)"
                    >
                      <Undo2 :size="16" aria-hidden="true" />
                      下线
                    </button>
                    <button
                      type="button"
                      :data-test="`content-delete-${itemId(item)}`"
                      :title="`${activeDefinition.deleteLabel}${activeDefinition.itemNoun}`"
                      :disabled="store.managedContentActionLoading"
                      @click="openDelete(item)"
                    >
                      <Trash2 :size="16" aria-hidden="true" />
                      {{ activeDefinition.deleteLabel }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section
        class="content-form"
        aria-labelledby="content-form-title"
      >
        <header class="content-form__heading">
          <Pencil :size="20" aria-hidden="true" />
          <h2 id="content-form-title">
            {{
              activeDefinition.supportsCorrection
                ? `纠错${activeDefinition.itemNoun}`
                : `${activeDefinition.itemNoun}不可纠错`
            }}
          </h2>
          <button
            v-if="isCorrecting"
            type="button"
            data-test="content-correct-cancel"
            @click="resetCorrection"
          >
            取消
          </button>
        </header>

        <p
          v-if="!activeDefinition.supportsCorrection"
          class="content-form__note"
          data-test="content-correct-unsupported"
        >
          评论与预置技艺不开放纠错：评论区只有隐藏，预置技艺的编辑在「预置内容」页进行。
        </p>

        <form
          v-else
          class="content-form__grid"
          data-test="content-correct"
          @submit.prevent="submitCorrection"
        >
          <div class="content-field">
            <label>
              <span>标题</span>
              <input
                v-model="correctionForm.title"
                type="text"
                maxlength="200"
                autocomplete="off"
                :disabled="!isCorrecting"
                data-test="content-correct-title"
              />
            </label>
            <small v-if="!isCorrecting">
              在列表中点击「纠错」后填写。纠错只修改文案，不会重新发布，也不会改变审核或发布状态。
            </small>
            <small v-else>最长 200 个字符，不能为空。</small>
          </div>

          <div
            v-if="activeType !== 'handcraft_video'"
            class="content-field content-field--wide"
          >
            <label>
              <span>{{ activeDefinition.bodyLabel }}</span>
              <textarea
                v-model="correctionForm.body"
                rows="8"
                maxlength="20000"
                :disabled="!isCorrecting"
                data-test="content-correct-body"
              />
            </label>
            <small v-if="!activeDefinition.bodyReturned">
              管理接口不返回{{ activeDefinition.bodyLabel }}，纠错时请填写完整内容后保存。
            </small>
          </div>

          <div class="content-form__actions">
            <button
              type="submit"
              class="content-submit"
              data-test="content-correct-submit"
              :disabled="!canSubmitCorrection || store.managedContentActionLoading"
            >
              {{ store.managedContentActionLoading ? '正在保存' : '保存纠错' }}
            </button>
          </div>
        </form>

        <p
          v-if="store.managedContentFormError"
          class="content-form__error"
          data-test="content-form-error"
          role="alert"
        >
          <ShieldAlert :size="18" aria-hidden="true" />
          <span>{{ store.managedContentFormError }}</span>
          <span
            v-if="store.managedContentFormErrorCode"
            class="content-form__code"
            data-test="content-form-error-code"
          >
            {{ store.managedContentFormErrorCode }}
          </span>
          <button
            type="button"
            data-test="content-form-resync"
            @click="resyncCorrection"
          >
            <RefreshCw :size="16" aria-hidden="true" />
            重新加载
          </button>
        </p>
      </section>

      <div
        v-if="detailOpen"
        class="content-dialog-backdrop"
        data-test="content-detail-dialog"
        @click.self="closeDetail"
      >
        <section
          class="content-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="content-detail-title"
        >
          <header>
            <h2 id="content-detail-title">
              {{ activeDefinition.itemNoun }}详情
            </h2>
            <button
              type="button"
              aria-label="关闭详情对话框"
              title="关闭"
              data-test="content-detail-close"
              @click="closeDetail"
            >
              <X :size="18" aria-hidden="true" />
            </button>
          </header>

          <div
            v-if="
              store.managedContentDetailLoading &&
              store.managedContentDetail === null
            "
            class="content-state"
            data-test="content-detail-loading"
            role="status"
          >
            <RefreshCw class="spinning" :size="20" aria-hidden="true" />
            正在加载详情
          </div>

          <div
            v-else-if="store.managedContentDetailError"
            class="content-dialog__error"
            data-test="content-detail-error"
            role="alert"
          >
            <ShieldAlert :size="18" aria-hidden="true" />
            <span>{{ store.managedContentDetailError }}</span>
          </div>

          <dl
            v-else-if="store.managedContentDetail"
            class="content-detail__grid"
          >
            <div
              v-for="entry in detailEntries(store.managedContentDetail)"
              :key="entry.label"
            >
              <dt>{{ entry.label }}</dt>
              <dd data-test="content-detail-value">{{ entry.value }}</dd>
            </div>
          </dl>

          <div class="content-dialog__actions">
            <button type="button" @click="closeDetail">关闭</button>
          </div>
        </section>
      </div>

      <div
        v-if="unpublishCandidate"
        class="content-dialog-backdrop"
        data-test="content-unpublish-dialog"
        @click.self="closeDialogs"
      >
        <section
          class="content-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="content-unpublish-title"
        >
          <header>
            <h2 id="content-unpublish-title">
              下线{{ activeDefinition.itemNoun }}
            </h2>
            <button
              type="button"
              aria-label="关闭下线确认对话框"
              title="关闭"
              :disabled="store.managedContentActionLoading"
              @click="closeDialogs"
            >
              <X :size="18" aria-hidden="true" />
            </button>
          </header>
          <p data-test="content-unpublish-notice" v-html="unpublishNotice()" />
          <p class="content-dialog__quote">
            {{ unpublishCandidate.label }}
            <span class="content-mono">{{ unpublishCandidate.id }}</span>
          </p>
          <div class="content-dialog__actions">
            <button
              type="button"
              data-test="content-confirm-unpublish"
              :disabled="store.managedContentActionLoading"
              @click="confirmUnpublish"
            >
              <Undo2 :size="16" aria-hidden="true" />
              {{
                store.managedContentActionLoading ? '正在处理' : '确认下线'
              }}
            </button>
            <button
              type="button"
              :disabled="store.managedContentActionLoading"
              @click="closeDialogs"
            >
              取消
            </button>
          </div>
        </section>
      </div>

      <div
        v-if="deleteCandidate"
        class="content-dialog-backdrop"
        data-test="content-delete-dialog"
        @click.self="closeDialogs"
      >
        <section
          class="content-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="content-delete-title"
        >
          <header>
            <h2 id="content-delete-title">
              {{ deleteDialogTitle(activeDefinition.deleteMode) }}
            </h2>
            <button
              type="button"
              aria-label="关闭删除确认对话框"
              title="关闭"
              :disabled="store.managedContentActionLoading"
              @click="closeDialogs"
            >
              <X :size="18" aria-hidden="true" />
            </button>
          </header>
          <p
            data-test="content-delete-notice"
            v-html="deleteNotice(activeDefinition.deleteMode)"
          />
          <p class="content-dialog__quote">
            {{ deleteCandidate.label }}
            <span class="content-mono">{{ deleteCandidate.id }}</span>
          </p>
          <div class="content-dialog__actions">
            <button
              type="button"
              data-test="content-confirm-delete"
              :disabled="store.managedContentActionLoading"
              @click="confirmDelete"
            >
              <Trash2 :size="16" aria-hidden="true" />
              {{
                store.managedContentActionLoading
                  ? '正在处理'
                  : deleteConfirmLabel(activeDefinition.deleteMode)
              }}
            </button>
            <button
              type="button"
              :disabled="store.managedContentActionLoading"
              @click="closeDialogs"
            >
              取消
            </button>
          </div>
        </section>
      </div>
    </template>

    <div v-else class="content-readonly" data-test="content-readonly">
      <p class="content-readonly__notice">
        以下数据来自内容审核队列，呈现审核状态与监管上下文：待审核条目、提交者与处理时间。
        纠错、下线与删除等生产编辑控件对此角色不开放。
      </p>

      <div
        class="content-readonly__filters"
        role="group"
        aria-label="按审核类型筛选"
        data-test="content-readonly-filters"
      >
        <button
          type="button"
          data-test="content-readonly-filter-all"
          :class="{ 'is-active': reviewFilter === 'all' }"
          :aria-pressed="reviewFilter === 'all'"
          @click="reviewFilter = 'all'"
        >
          <span>全部</span>
          <strong class="ark-data">{{ pendingReviewTotal }}</strong>
        </button>
        <button
          v-for="option in reviewTypeOptions"
          :key="option.value"
          type="button"
          :data-test="`content-readonly-filter-${option.value}`"
          :class="{ 'is-active': reviewFilter === option.value }"
          :aria-pressed="reviewFilter === option.value"
          @click="reviewFilter = option.value"
        >
          <span>{{ option.label }}</span>
          <strong class="ark-data">{{ store.reviewCounts[option.value] }}</strong>
        </button>
      </div>

      <div
        v-if="store.reviewError"
        class="content-error"
        data-test="content-readonly-error"
        role="alert"
      >
        <ShieldAlert :size="18" aria-hidden="true" />
        <span>{{ store.reviewError }}</span>
        <button
          type="button"
          data-test="content-readonly-retry"
          :disabled="store.reviewLoading"
          @click="store.loadReviewQueue()"
        >
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </div>

      <section
        class="content-registry"
        aria-labelledby="content-readonly-title"
      >
        <header class="content-registry__heading">
          <h2 id="content-readonly-title">审核队列</h2>
          <span class="ark-data">{{ filteredReviewItems.length }} 条</span>
        </header>

        <div
          v-if="store.reviewLoading && store.reviewItems.length === 0"
          class="content-state"
          data-test="content-readonly-loading"
          role="status"
        >
          <RefreshCw class="spinning" :size="20" aria-hidden="true" />
          正在加载审核队列
        </div>

        <div
          v-else-if="filteredReviewItems.length === 0"
          class="content-state content-state--empty"
          data-test="content-readonly-empty"
        >
          <Inbox :size="24" aria-hidden="true" />
          <span>暂无审核内容</span>
        </div>

        <div v-else class="content-table-wrap">
          <table class="content-table">
            <thead>
              <tr>
                <th scope="col">内容</th>
                <th scope="col">类型</th>
                <th scope="col">状态</th>
                <th scope="col">提交者</th>
                <th scope="col">更新时间</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in filteredReviewItems"
                :key="`${item.content_type}:${item.content_id}`"
                data-test="content-readonly-row"
                :data-content-type="item.content_type"
                :data-content-id="item.content_id"
              >
                <td data-label="内容">
                  <div class="content-table__title">
                    <strong>{{ item.title || item.content_id }}</strong>
                    <span class="ark-data">ID {{ item.content_id }}</span>
                  </div>
                </td>
                <td data-label="类型">
                  {{
                    reviewTypeOptions.find(option => option.value === item.content_type)
                      ?.label ?? item.content_type
                  }}
                </td>
                <td data-label="状态">
                  <span
                    class="content-status"
                    :class="`is-${item.review_status}`"
                    data-test="content-readonly-status"
                  >
                    {{ reviewStatusLabel(item.review_status) }}
                  </span>
                </td>
                <td data-label="提交者">
                  {{
                    item.submitter_name ||
                    item.owner_name ||
                    (item.submitter_id === null
                      ? '未知提交者'
                      : `用户 #${item.submitter_id}`)
                  }}
                </td>
                <td data-label="更新时间">
                  <time class="ark-data" :datetime="item.updated_at || undefined">
                    {{ formatTime(item.updated_at) }}
                  </time>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.admin-content {
  min-width: 0;
  color: var(--ark-paper);
}

.content-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 0.42fr);
  min-width: 0;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.content-header__identity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 16px;
  padding: 28px 26px;
}

.content-header__identity > svg {
  flex: 0 0 auto;
  margin-top: 4px;
  color: var(--ark-signal);
}

.content-header__identity > div {
  min-width: 0;
}

.content-header__identity h1 {
  margin: 0;
  font-size: 2.35rem;
  line-height: 1;
  text-wrap: balance;
}

.content-header__identity p {
  max-width: 62ch;
  margin: 13px 0 0;
  color: var(--ark-muted);
  font-size: 0.86rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.content-header__summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin: 0;
  border-left: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.content-header__summary div {
  display: grid;
  min-width: 0;
  align-content: center;
  padding: 20px 16px;
  background: var(--ark-surface-1);
}

.content-header__summary dt {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.content-header__summary dd {
  margin: 5px 0 0;
  color: var(--ark-signal);
  font-size: 1.8rem;
  line-height: 1;
}

.content-tabs,
.content-readonly__filters {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.content-tabs button,
.content-readonly__filters button {
  display: flex;
  min-width: 0;
  min-height: 56px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 10px 8px;
  border: 0;
  background: var(--ark-surface-0);
  color: var(--ark-muted);
}

.content-readonly__filters button {
  justify-content: space-between;
  padding: 10px 14px;
  text-align: left;
}

.content-tabs button:hover,
.content-tabs button:focus-visible,
.content-readonly__filters button:hover,
.content-readonly__filters button:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.content-tabs button.is-active,
.content-readonly__filters button.is-active {
  box-shadow: inset 0 -2px 0 var(--ark-signal);
  color: var(--ark-signal);
}

.content-tabs button span,
.content-readonly__filters button span {
  min-width: 0;
  font-size: 0.86rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.content-readonly__filters button strong {
  color: inherit;
  font-size: 1.2rem;
}

.content-message,
.content-error {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.content-message {
  color: var(--ark-state);
}

.content-message svg,
.content-error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.content-message,
.content-error span {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.content-error button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  min-height: 38px;
  margin-left: auto;
  padding: 0 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.content-readonly__notice {
  max-width: 78ch;
  margin: 18px 0 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.content-registry {
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.content-registry__heading {
  display: flex;
  min-height: 62px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.content-registry__heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.content-registry__heading span {
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.content-state {
  display: flex;
  min-height: 190px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--ark-muted);
  text-align: center;
}

.content-state--empty {
  flex-direction: column;
}

/* The table owns its own horizontal scroll so a wide row never widens the
   page shell at 320px. */
.content-table-wrap {
  min-width: 0;
  overflow-x: auto;
}

.content-table {
  width: 100%;
  min-width: 760px;
  table-layout: fixed;
  border-collapse: collapse;
}

.content-table th,
.content-table td {
  min-width: 0;
  padding: 14px 11px;
  border-bottom: 1px solid var(--ark-line);
  text-align: left;
  vertical-align: top;
}

.content-table th {
  color: var(--ark-muted);
  font-size: 0.7rem;
  font-weight: 500;
  white-space: nowrap;
}

.content-table td {
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.content-table th:nth-child(1) {
  width: 26%;
}

.content-table th:nth-child(2) {
  width: 13%;
}

.content-table th:nth-child(3) {
  width: 11%;
}

.content-table th:nth-child(4) {
  width: 16%;
}

.content-table th:nth-child(5) {
  width: 22%;
}

.content-table th:nth-child(6) {
  width: 12%;
}

.content-table tbody tr:last-child td {
  border-bottom: 0;
}

.content-table__title {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.content-table__title strong {
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.content-table__title span,
.content-table time {
  color: var(--ark-muted);
  font-size: 0.7rem;
}

/* A preset row names the family it belongs to, so the table never reads as
   if every preset were a handcraft craft. */
.content-table__family {
  color: var(--ark-signal);
  font-size: 0.7rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.content-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.content-status::before {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  background: currentColor;
  content: "";
}

.content-status.is-active,
.content-status.is-approved {
  color: var(--ark-state);
}

.content-status.is-pending {
  color: var(--ark-signal);
}

.content-status.is-muted,
.content-status.is-rejected,
.content-status.is-offline,
.content-status.is-unpublished {
  color: var(--ark-muted);
}

.content-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.content-actions button {
  display: inline-flex;
  min-height: 38px;
  flex: 1 1 68px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.content-actions button:first-child {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.content-actions button:hover:not(:disabled),
.content-error button:hover:not(:disabled) {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.content-form {
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.content-form__heading {
  display: flex;
  min-height: 62px;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.content-form__heading > svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.content-form__heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.content-form__heading button {
  display: inline-flex;
  min-height: 38px;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.content-form__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1px;
  min-width: 0;
  background: var(--ark-line);
}

.content-field {
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 12px 14px;
  background: var(--ark-surface-0);
  align-content: start;
}

.content-field > label {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.content-field label > span {
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.content-field small {
  color: var(--ark-muted);
  font-size: 0.68rem;
  line-height: 1.5;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.content-field--wide {
  grid-column: span 2;
}

.content-field input,
.content-field textarea {
  width: 100%;
  min-width: 0;
  min-height: 38px;
  padding: 8px 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.content-field textarea {
  resize: vertical;
}

.content-field input:hover,
.content-field textarea:hover {
  border-color: var(--ark-signal);
}

.content-field input:disabled,
.content-field textarea:disabled {
  background: var(--ark-surface-1);
  color: var(--ark-muted);
}

.content-form__note {
  margin: 0;
  padding: 16px 18px;
  color: var(--ark-muted);
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.content-form__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  grid-column: 1 / -1;
  padding: 14px;
  background: var(--ark-surface-0);
}

.content-form__actions button {
  display: inline-flex;
  min-height: 38px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 14px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.content-submit {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.content-form__error {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 10px;
  margin: 0;
  padding: 12px 14px;
  border-top: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.content-form__error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
  color: var(--ark-signal);
}

.content-form__error > span {
  min-width: 0;
}

.content-form__code {
  flex: 0 0 auto;
  padding: 2px 7px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.content-form__error button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  min-height: 34px;
  margin-left: auto;
  padding: 0 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.content-dialog-backdrop {
  position: fixed;
  z-index: 40;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: color-mix(in srgb, var(--ark-paper) 72%, transparent);
}

.content-dialog {
  width: min(100%, 560px);
  max-height: calc(100svh - 40px);
  overflow-y: auto;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
}

.content-dialog header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.content-dialog h2 {
  margin: 0;
  font-size: 1.15rem;
}

.content-dialog header button {
  display: inline-grid;
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: transparent;
  color: var(--ark-paper);
}

.content-dialog > p {
  margin: 0;
  padding: 18px 18px 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.content-dialog > p strong {
  color: var(--ark-paper);
}

.content-dialog__quote {
  display: grid;
  gap: 4px;
  color: var(--ark-paper);
  font-size: 0.86rem;
}

.content-dialog__error {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin: 0;
  padding: 18px 18px 0;
  color: var(--ark-paper);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.content-dialog__error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
  color: var(--ark-signal);
}

.content-detail__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1px;
  margin: 0;
  background: var(--ark-line);
}

.content-detail__grid > div {
  display: grid;
  gap: 5px;
  min-width: 0;
  padding: 12px 14px;
  background: var(--ark-surface-0);
  align-content: start;
}

.content-detail__grid dt {
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.content-detail__grid dd {
  margin: 0;
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
  white-space: pre-wrap;
}

.content-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 18px;
}

.content-dialog__actions button {
  display: inline-flex;
  min-width: 108px;
  min-height: 38px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.content-dialog__actions button:first-child {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.content-mono {
  font-family: ui-monospace, "SFMono-Regular", "Cascadia Mono", Consolas, monospace;
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.admin-content :is(button, input, textarea):focus-visible {
  outline: 2px solid var(--ark-focus);
  outline-offset: 3px;
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1080px) {
  .content-header {
    grid-template-columns: minmax(0, 1fr);
  }

  .content-header__summary {
    border-top: 1px solid var(--ark-line-strong);
    border-left: 0;
  }

  .content-tabs,
  .content-readonly__filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .content-field--wide {
    grid-column: 1 / -1;
  }
}

@media (max-width: 640px) {
  .content-header__identity {
    padding: 21px 16px;
  }

  .content-header__identity h1 {
    font-size: 2rem;
  }

  .content-tabs,
  .content-readonly__filters {
    grid-template-columns: minmax(0, 1fr);
  }

  .content-form__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .content-field--wide {
    grid-column: 1 / -1;
  }

  .content-dialog-backdrop {
    padding: 10px;
  }

  .content-dialog__actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }

  .content-dialog__actions button {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
