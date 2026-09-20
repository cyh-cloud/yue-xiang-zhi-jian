<script setup lang="ts">
import {
  AlertTriangle,
  Check,
  Inbox,
  Megaphone,
  Plus,
  RefreshCw,
  Send,
  ShieldAlert,
  X
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import type {
  AdminAnnouncement,
  AdminAnnouncementStatus,
  AdminAnnouncementTargetRole
} from '@/api/types'
import { useAdminConsoleStore } from '@/stores/adminConsole'

type AnnouncementFilter = 'all' | AdminAnnouncementStatus

const filterOptions: ReadonlyArray<{
  value: AnnouncementFilter
  label: string
}> = [
  { value: 'all', label: '全部' },
  { value: 'draft', label: '草稿' },
  { value: 'published', label: '已发布' }
]

const targetRoleOptions: ReadonlyArray<{
  value: AdminAnnouncementTargetRole
  label: string
}> = [
  { value: 'student', label: '学员' },
  { value: 'teacher', label: '教师' },
  { value: 'enterprise', label: '企业' },
  { value: 'government', label: '政府' },
  { value: 'admin', label: '普通管理员' },
  { value: 'super_admin', label: '超级管理员' }
]

const roleLabels: Record<AdminAnnouncementTargetRole, string> = {
  student: '学员',
  teacher: '教师',
  enterprise: '企业',
  government: '政府',
  admin: '普通管理员',
  super_admin: '超级管理员'
}

const statusLabels: Record<AdminAnnouncementStatus, string> = {
  draft: '草稿',
  published: '已发布'
}

const TITLE_MAX_LENGTH = 60
const BODY_MAX_LENGTH = 2000
const BODY_PREVIEW_LENGTH = 90

const store = useAdminConsoleStore()
const filter = ref<AnnouncementFilter>('all')
const createOpen = ref(false)
const publishCandidate = ref<AdminAnnouncement | null>(null)
const formError = ref('')
const form = ref<{
  title: string
  body: string
  target_roles: AdminAnnouncementTargetRole[]
}>({ title: '', body: '', target_roles: ['student'] })

const filteredAnnouncements = computed(() =>
  filter.value === 'all'
    ? store.announcements
    : store.announcements.filter(
        announcement => announcement.status === filter.value
      )
)

const draftCount = computed(
  () => store.announcements.filter(item => item.status === 'draft').length
)

const publishedCount = computed(
  () => store.announcements.filter(item => item.status === 'published').length
)

const publishResult = computed(() => store.announcementPublishResult)

const publishFailed = computed(
  () => (publishResult.value?.delivery.failed ?? 0) > 0
)

function roleLabel(role: AdminAnnouncementTargetRole): string {
  return roleLabels[role] ?? role
}

function targetRoleText(roles: AdminAnnouncementTargetRole[]): string {
  if (roles.length === 0) return '未设置'
  return roles.map(roleLabel).join('、')
}

function bodyPreview(body: string): string {
  const normalized = body.trim()
  if (normalized.length <= BODY_PREVIEW_LENGTH) return normalized
  return `${normalized.slice(0, BODY_PREVIEW_LENGTH)}…`
}

function formatTime(value: string | null, emptyLabel: string): string {
  if (!value) return emptyLabel
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

function toggleCreateForm(): void {
  createOpen.value = !createOpen.value
  formError.value = ''
  store.clearAnnouncementFormError()
}

function toggleRole(role: AdminAnnouncementTargetRole): void {
  formError.value = ''
  const selected = form.value.target_roles.includes(role)
  form.value = {
    ...form.value,
    target_roles: selected
      ? form.value.target_roles.filter(item => item !== role)
      : [...form.value.target_roles, role]
  }
}

function resetForm(): void {
  form.value = { title: '', body: '', target_roles: ['student'] }
}

function validateForm(): string {
  const title = form.value.title.trim()
  const body = form.value.body.trim()
  if (title.length === 0) return '公告标题不能为空'
  if (title.length > TITLE_MAX_LENGTH) {
    return `公告标题长度不能超过 ${TITLE_MAX_LENGTH} 个字符`
  }
  if (body.length === 0) return '公告正文不能为空'
  if (body.length > BODY_MAX_LENGTH) {
    return `公告正文长度不能超过 ${BODY_MAX_LENGTH} 个字符`
  }
  if (form.value.target_roles.length === 0) return '请至少选择一个目标角色'
  return ''
}

async function submitAnnouncement(): Promise<void> {
  const message = validateForm()
  formError.value = message
  if (message) return
  const done = await store.createAnnouncement({
    title: form.value.title.trim(),
    body: form.value.body.trim(),
    target_roles: form.value.target_roles
  })
  if (done) {
    resetForm()
  }
}

function openPublish(announcement: AdminAnnouncement): void {
  store.clearAnnouncementPublishResult()
  store.clearAnnouncementsError()
  publishCandidate.value = announcement
}

function closePublish(): void {
  publishCandidate.value = null
}

async function confirmPublish(): Promise<void> {
  const announcement = publishCandidate.value
  if (announcement === null) return
  const done = await store.publishAnnouncement(announcement.announcement_id)
  if (done) {
    closePublish()
  }
}

async function retryPublish(): Promise<void> {
  const announcement = publishResult.value?.announcement
  if (announcement === undefined) return
  await store.publishAnnouncement(announcement.announcement_id)
}

onMounted(() => {
  void store.loadAnnouncements()
})
</script>

<template>
  <section class="admin-announcements" data-test="admin-announcements">
    <header class="announcements-header">
      <div class="announcements-header__identity">
        <Megaphone :size="26" aria-hidden="true" />
        <div>
          <h1>系统公告</h1>
          <p>面向指定角色群发的平台公告，发布后历史保留。</p>
        </div>
      </div>
      <dl class="announcements-header__summary">
        <div>
          <dt>草稿</dt>
          <dd class="ark-data">{{ draftCount }}</dd>
        </div>
        <div>
          <dt>已发布</dt>
          <dd class="ark-data">{{ publishedCount }}</dd>
        </div>
      </dl>
    </header>

    <div class="announcements-toolbar">
      <div
        class="announcements-filter"
        role="group"
        aria-label="按状态筛选公告"
        data-test="announcement-filter"
      >
        <button
          v-for="option in filterOptions"
          :key="option.value"
          type="button"
          :data-test="`announcement-filter-${option.value}`"
          :class="{ 'is-active': filter === option.value }"
          :aria-pressed="filter === option.value"
          @click="filter = option.value"
        >
          <span>{{ option.label }}</span>
        </button>
      </div>
      <button
        type="button"
        class="announcements-refresh"
        data-test="announcements-refresh"
        aria-label="重新加载公告列表"
        title="重新加载公告列表"
        :disabled="store.announcementsLoading"
        @click="store.loadAnnouncements()"
      >
        <RefreshCw :size="16" aria-hidden="true" />
      </button>
    </div>

    <div
      v-if="store.announcementAccessDenied"
      class="announcements-denied"
      data-test="announcement-denied"
      role="alert"
    >
      <ShieldAlert :size="18" aria-hidden="true" />
      <div>
        <strong>无权限查看系统公告</strong>
        <span>当前角色不在公告权限矩阵内，未读取任何公告数据。</span>
      </div>
    </div>

    <div
      v-else-if="store.announcementsError"
      class="announcements-error"
      data-test="announcement-error"
      role="alert"
    >
      <ShieldAlert :size="18" aria-hidden="true" />
      <span>{{ store.announcementsError }}</span>
      <button
        type="button"
        data-test="announcement-retry"
        :disabled="store.announcementsLoading"
        @click="store.loadAnnouncements()"
      >
        <RefreshCw :size="16" aria-hidden="true" />
        重新加载
      </button>
    </div>

    <div
      v-if="
        publishResult !== null &&
        !store.announcementAccessDenied &&
        !store.announcementsError
      "
      class="announcements-outcome"
      :class="{
        'announcements-outcome--failed': publishFailed
      }"
      data-test="announcement-publish-outcome"
      role="status"
    >
      <AlertTriangle v-if="publishFailed" :size="18" aria-hidden="true" />
      <Check v-else :size="18" aria-hidden="true" />
      <span>
        {{
          publishFailed
            ? `通知未送达，已记录为可重试状态：${publishResult?.delivery.failed ?? 0} 次失败。`
            : publishResult?.changed
              ? `已发布并送达 ${publishResult?.delivery.recipient_count ?? 0} 个账户。`
              : '该公告已发布，本次未产生新的用户通知。'
        }}
      </span>
      <button
        v-if="publishFailed"
        type="button"
        data-test="announcement-publish-retry"
        :disabled="store.announcementActionLoading"
        @click="retryPublish"
      >
        <RefreshCw :size="16" aria-hidden="true" />
        重试发布
      </button>
    </div>

    <section class="announcements-create" aria-labelledby="announcements-create-title">
      <header class="announcements-create__heading">
        <Plus :size="20" aria-hidden="true" />
        <h2 id="announcements-create-title">新建公告</h2>
        <span>公告经 02 消息通道群发，不写入第二套通知。</span>
      </header>
      <button
        v-if="!createOpen"
        type="button"
        class="announcements-create__trigger"
        data-test="announcement-create"
        :aria-expanded="createOpen"
        @click="toggleCreateForm"
      >
        <Plus :size="16" aria-hidden="true" />
        新建公告
      </button>
      <form
        v-else
        class="announcements-create__form"
        data-test="announcement-create-form"
        @submit.prevent="submitAnnouncement"
      >
        <label class="announcements-field">
          <span>公告标题</span>
          <input
            v-model="form.title"
            type="text"
            data-test="announcement-title"
            maxlength="60"
            autocomplete="off"
          />
          <em class="announcements-field__count ark-data">
            {{ form.title.length }} / {{ TITLE_MAX_LENGTH }}
          </em>
        </label>
        <div class="announcements-field announcements-field--roles">
          <span>目标角色</span>
          <div
            class="announcements-roles"
            role="group"
            aria-label="选择目标角色"
            data-test="announcement-roles"
          >
            <label
              v-for="option in targetRoleOptions"
              :key="option.value"
              class="announcements-role"
            >
              <input
                type="checkbox"
                :data-test="`announcement-role-${option.value}`"
                :checked="form.target_roles.includes(option.value)"
                @change="toggleRole(option.value)"
              />
              <span>{{ option.label }}</span>
            </label>
          </div>
        </div>
        <label class="announcements-field announcements-field--wide">
          <span>公告正文</span>
          <textarea
            v-model="form.body"
            data-test="announcement-body"
            maxlength="2000"
            rows="6"
          />
          <em class="announcements-field__count ark-data">
            {{ form.body.length }} / {{ BODY_MAX_LENGTH }}
          </em>
        </label>
        <button
          type="submit"
          class="announcements-submit"
          data-test="announcement-submit"
          :disabled="store.announcementActionLoading"
        >
          <Send :size="16" aria-hidden="true" />
          {{ store.announcementActionLoading ? '正在创建' : '创建公告' }}
        </button>
      </form>
      <p
        v-if="formError"
        class="announcements-form__error"
        data-test="announcement-form-error"
        role="alert"
      >
        <AlertTriangle :size="16" aria-hidden="true" />
        {{ formError }}
      </p>
      <p
        v-if="store.announcementFormError"
        class="announcements-form__error"
        data-test="announcement-server-error"
        role="alert"
      >
        <ShieldAlert :size="16" aria-hidden="true" />
        {{ store.announcementFormError }}
        <span
          v-if="store.announcementFormErrorCode"
          class="announcements-form__code ark-data"
          data-test="announcement-server-error-code"
        >
          {{ store.announcementFormErrorCode }}
        </span>
      </p>
    </section>

    <section class="announcements-registry" aria-labelledby="announcements-registry-title">
      <header class="announcements-registry__heading">
        <h2 id="announcements-registry-title">公告列表</h2>
        <span class="ark-data">{{ filteredAnnouncements.length }} 条</span>
      </header>

      <div
        v-if="store.announcementsLoading && store.announcements.length === 0"
        class="announcements-state"
        data-test="announcement-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="20" aria-hidden="true" />
        正在加载公告列表
      </div>

      <div
        v-else-if="
          !store.announcementAccessDenied && filteredAnnouncements.length === 0
        "
        class="announcements-state announcements-state--empty"
        data-test="announcement-empty"
      >
        <Inbox :size="24" aria-hidden="true" />
        <span>暂无公告</span>
      </div>

      <ul
        v-else-if="!store.announcementAccessDenied"
        class="announcements-list"
        data-test="announcement-list"
      >
        <li
          v-for="announcement in filteredAnnouncements"
          :key="announcement.announcement_id"
          class="announcements-item"
          data-test="announcement-row"
          :data-announcement-id="announcement.announcement_id"
          :data-status="announcement.status"
        >
          <div class="announcements-item__head">
            <h3>{{ announcement.title }}</h3>
            <span
              class="announcements-item__status"
              :class="`is-${announcement.status}`"
              data-test="announcement-status"
            >
              {{ statusLabels[announcement.status] }}
            </span>
          </div>
          <p class="announcements-item__body">
            {{ bodyPreview(announcement.body) }}
          </p>
          <dl class="announcements-item__meta">
            <div>
              <dt>目标角色</dt>
              <dd>{{ targetRoleText(announcement.target_roles) }}</dd>
            </div>
            <div>
              <dt>创建时间</dt>
              <dd class="ark-data">
                {{ formatTime(announcement.created_at, '时间未知') }}
              </dd>
            </div>
            <div>
              <dt>发布时间</dt>
              <dd class="ark-data">
                {{ formatTime(announcement.published_at, '未发布') }}
              </dd>
            </div>
          </dl>
          <div class="announcements-item__actions">
            <button
              v-if="announcement.status === 'draft'"
              type="button"
              data-test="announcement-publish"
              :aria-label="`发布公告：${announcement.title}`"
              :title="`发布公告：${announcement.title}`"
              :disabled="store.announcementActionLoading"
              @click="openPublish(announcement)"
            >
              <Send :size="16" aria-hidden="true" />
              发布
            </button>
            <span v-else class="announcements-item__done">已发布</span>
          </div>
        </li>
      </ul>
    </section>

    <div
      v-if="publishCandidate"
      class="announcements-dialog-backdrop"
      data-test="announcement-publish-dialog"
      @click.self="closePublish"
    >
      <section
        class="announcements-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="announcements-publish-title"
      >
        <header>
          <h2 id="announcements-publish-title">确认发布公告</h2>
          <button
            type="button"
            aria-label="关闭发布公告对话框"
            title="关闭"
            :disabled="store.announcementActionLoading"
            @click="closePublish"
          >
            <X :size="18" aria-hidden="true" />
          </button>
        </header>
        <p>
          「{{ publishCandidate.title }}」发布后将经 02
          消息通道群发给目标角色，重复发布不会产生第二份通知。
        </p>
        <dl class="announcements-dialog__meta">
          <div>
            <dt>目标角色</dt>
            <dd>{{ targetRoleText(publishCandidate.target_roles) }}</dd>
          </div>
        </dl>
        <div class="announcements-dialog__actions">
          <button
            type="button"
            data-test="announcement-publish-confirm"
            :disabled="store.announcementActionLoading"
            @click="confirmPublish"
          >
            <Send :size="16" aria-hidden="true" />
            {{ store.announcementActionLoading ? '正在发布' : '确认发布' }}
          </button>
          <button
            type="button"
            data-test="announcement-publish-cancel"
            :disabled="store.announcementActionLoading"
            @click="closePublish"
          >
            取消
          </button>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.admin-announcements {
  min-width: 0;
  color: var(--ark-paper);
}

.announcements-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.62fr);
  min-width: 0;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.announcements-header__identity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 16px;
  padding: 28px 26px;
}

.announcements-header__identity > svg {
  flex: 0 0 auto;
  margin-top: 4px;
  color: var(--ark-signal);
}

.announcements-header__identity > div {
  min-width: 0;
}

.announcements-header__identity h1 {
  margin: 0;
  font-size: 2.35rem;
  line-height: 1;
  text-wrap: balance;
}

.announcements-header__identity p {
  max-width: 62ch;
  margin: 13px 0 0;
  color: var(--ark-muted);
  font-size: 0.86rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.announcements-header__summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin: 0;
  border-left: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.announcements-header__summary div {
  display: grid;
  min-width: 0;
  min-height: 76px;
  align-content: center;
  padding: 18px 20px;
  background: var(--ark-surface-1);
}

.announcements-header__summary dt {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.announcements-header__summary dd {
  margin: 5px 0 0;
  color: var(--ark-signal);
  font-size: 1.7rem;
  line-height: 1;
}

.announcements-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 52px;
  min-width: 0;
  align-items: stretch;
  gap: 10px;
  margin-top: 18px;
}

.announcements-filter {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.announcements-filter button {
  display: flex;
  min-width: 0;
  min-height: 52px;
  align-items: center;
  justify-content: center;
  padding: 10px 12px;
  border: 0;
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  text-align: center;
}

.announcements-filter button:hover,
.announcements-filter button:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.announcements-filter button.is-active {
  box-shadow: inset 0 -2px 0 var(--ark-signal);
  color: var(--ark-signal);
}

.announcements-filter button span {
  min-width: 0;
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.announcements-refresh {
  display: inline-grid;
  place-items: center;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.announcements-refresh:hover:not(:disabled) {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.announcements-denied,
.announcements-error,
.announcements-outcome {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.announcements-denied > svg,
.announcements-error > svg,
.announcements-outcome > svg {
  flex: 0 0 auto;
  margin-top: 2px;
  color: var(--ark-signal);
}

.announcements-denied > div {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.announcements-denied strong {
  font-size: 0.9rem;
}

.announcements-denied span,
.announcements-error span,
.announcements-outcome span {
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.announcements-outcome {
  color: var(--ark-state);
}

.announcements-outcome--failed {
  color: var(--ark-signal);
}

.announcements-error button,
.announcements-outcome button {
  display: inline-flex;
  min-height: 38px;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  margin-left: auto;
  padding: 0 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.announcements-error button:hover:not(:disabled),
.announcements-outcome button:hover:not(:disabled) {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.announcements-create,
.announcements-registry {
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.announcements-create__heading,
.announcements-registry__heading {
  display: flex;
  min-width: 0;
  min-height: 62px;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.announcements-create__heading > svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.announcements-create__heading h2,
.announcements-registry__heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.announcements-create__heading span {
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.75rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.announcements-registry__heading span {
  margin-left: auto;
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.announcements-create__trigger {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  gap: 7px;
  margin: 18px;
  padding: 0 14px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-signal);
}

.announcements-create__trigger:hover {
  background: var(--ark-surface-1);
}

.announcements-create__form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  min-width: 0;
  padding: 18px;
}

.announcements-field {
  display: grid;
  gap: 7px;
  min-width: 0;
  align-content: start;
}

.announcements-field--wide {
  grid-column: 1 / -1;
}

.announcements-field > span {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.announcements-field input,
.announcements-field textarea {
  width: 100%;
  min-width: 0;
  min-height: 44px;
  padding: 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.announcements-field textarea {
  min-height: 132px;
  resize: vertical;
}

.announcements-field input:hover,
.announcements-field textarea:hover {
  border-color: var(--ark-signal);
}

.announcements-field__count {
  color: var(--ark-muted);
  font-size: 0.72rem;
  font-style: normal;
}

.announcements-field--roles {
  grid-column: 1 / -1;
}

.announcements-roles {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.announcements-role {
  display: flex;
  min-width: 0;
  min-height: 46px;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--ark-surface-0);
}

.announcements-role input {
  flex: 0 0 auto;
}

.announcements-role span {
  min-width: 0;
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.announcements-submit {
  display: inline-flex;
  min-width: 140px;
  min-height: 44px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 16px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-signal);
}

.announcements-submit:hover:not(:disabled) {
  background: var(--ark-surface-1);
}

.announcements-form__error {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 8px;
  margin: 0 18px 18px;
  padding: 11px 13px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.announcements-form__error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
  color: var(--ark-signal);
}

.announcements-form__code {
  flex: 0 0 auto;
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.announcements-state {
  display: flex;
  min-width: 0;
  min-height: 190px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--ark-muted);
  text-align: center;
}

.announcements-state--empty {
  flex-direction: column;
}

.announcements-list {
  display: grid;
  gap: 1px;
  min-width: 0;
  margin: 0;
  padding: 0;
  list-style: none;
  background: var(--ark-line);
}

.announcements-item {
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 16px 18px;
  background: var(--ark-surface-0);
}

.announcements-item__head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 76px;
  min-width: 0;
  align-items: baseline;
  gap: 10px;
}

.announcements-item__head h3 {
  min-width: 0;
  margin: 0;
  font-size: 0.98rem;
  line-height: 1.4;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.announcements-item__status {
  padding: 3px 9px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  color: var(--ark-muted);
  font-size: 0.72rem;
  text-align: center;
}

.announcements-item__status.is-published {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.announcements-item__body {
  min-width: 0;
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-height: 1.6;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.announcements-item__meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin: 0;
  border: 1px solid var(--ark-line);
  background: var(--ark-line);
}

.announcements-item__meta div {
  display: grid;
  gap: 4px;
  min-width: 0;
  padding: 10px 12px;
  background: var(--ark-surface-1);
}

.announcements-item__meta dt {
  color: var(--ark-muted);
  font-size: 0.7rem;
}

.announcements-item__meta dd {
  min-width: 0;
  margin: 0;
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.announcements-item__actions {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 8px;
}

.announcements-item__actions button,
.announcements-item__done {
  display: inline-flex;
  min-height: 38px;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font-size: 0.8rem;
}

.announcements-item__actions button {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.announcements-item__actions button:hover:not(:disabled) {
  background: var(--ark-surface-1);
}

.announcements-item__done {
  color: var(--ark-muted);
}

.announcements-dialog-backdrop {
  position: fixed;
  z-index: 40;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgb(5 6 7 / 0.72);
}

.announcements-dialog {
  width: min(100%, 560px);
  max-height: calc(100svh - 40px);
  overflow-y: auto;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  box-shadow: 12px 14px 40px rgb(0 0 0 / 0.28);
}

.announcements-dialog header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.announcements-dialog h2 {
  margin: 0;
  font-size: 1.15rem;
}

.announcements-dialog header button {
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

.announcements-dialog > p {
  margin: 0;
  padding: 18px 18px 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.announcements-dialog__meta {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 14px 18px 0;
}

.announcements-dialog__meta dt {
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.announcements-dialog__meta dd {
  margin: 0;
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.announcements-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 18px;
}

.announcements-dialog__actions button {
  display: inline-flex;
  min-width: 116px;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.announcements-dialog__actions button:first-child {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.admin-announcements :is(button, input, textarea):focus-visible {
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

@media (max-width: 900px) {
  .announcements-header {
    grid-template-columns: minmax(0, 1fr);
  }

  .announcements-header__summary {
    border-top: 1px solid var(--ark-line-strong);
    border-left: 0;
  }

  .announcements-header__identity {
    padding: 24px 20px;
  }
}

@media (max-width: 560px) {
  .announcements-header__identity {
    padding: 21px 16px;
  }

  .announcements-header__identity h1 {
    font-size: 2rem;
  }

  .announcements-toolbar {
    padding-block: 4px;
  }

  .announcements-create__form {
    grid-template-columns: minmax(0, 1fr);
  }

  .announcements-roles {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .announcements-item__meta {
    grid-template-columns: minmax(0, 1fr);
  }

  .announcements-submit {
    width: 100%;
  }

  .announcements-item {
    padding: 14px;
  }

  .announcements-dialog-backdrop {
    padding: 10px;
  }

  .announcements-dialog__actions {
    grid-template-columns: minmax(0, 1fr);
    display: grid;
  }

  .announcements-dialog__actions button {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
