<script setup lang="ts">
import {
  EyeOff,
  FileVideo,
  Link2,
  Pencil,
  RefreshCw,
  RotateCcw,
  Save,
  Send,
  Upload,
  X
} from 'lucide-vue-next'
import { computed, reactive, ref } from 'vue'

import type {
  CourseDirection,
  TeacherCourse,
  TeacherCourseFilterStatus,
  TeacherCoursePayload,
  TeacherCourseStatus,
  TeacherMediaSourceType
} from '@/api/types'
import { useTeacherConsoleStore } from '@/stores/teacherConsole'

import TeacherQuizEditor from './TeacherQuizEditor.vue'

const props = defineProps<{
  courses?: TeacherCourse[]
}>()

const store = useTeacherConsoleStore()
const MAX_VIDEO_BYTES = 500 * 1024 * 1024
const VIDEO_ACCEPT = 'video/mp4,video/webm,.mp4,.webm'

const directionOptions: Array<{
  value: CourseDirection
  label: string
}> = [
  { value: 'agriculture', label: '农业' },
  { value: 'ecommerce', label: '电商' },
  { value: 'handcraft', label: '手工' }
]

const statusOptions: Array<{
  value: TeacherCourseFilterStatus
  label: string
}> = [
  { value: 'draft', label: '草稿' },
  { value: 'pending', label: '待审核' },
  { value: 'published', label: '已上架' },
  { value: 'offline', label: '已下架' }
]

const statusLabels: Record<TeacherCourseStatus, string> = {
  draft: '草稿',
  pending: '待审核',
  published: '已上架',
  rejected: '已驳回',
  offline: '已下架'
}

const filters = reactive<{
  direction: CourseDirection | ''
  status: TeacherCourseFilterStatus | ''
}>({
  direction: '',
  status: ''
})

const form = reactive<{
  id: number | null
  version: number | null
  title: string
  direction: CourseDirection
  summary: string
  tagsText: string
  durationSeconds: number | ''
  mediaSourceType: TeacherMediaSourceType
  originalMediaSourceType: TeacherMediaSourceType | null
  mediaUrl: string
}>({
  id: null,
  version: null,
  title: '',
  direction: 'agriculture',
  summary: '',
  tagsText: '',
  durationSeconds: '',
  mediaSourceType: 'external_url',
  originalMediaSourceType: null,
  mediaUrl: ''
})

const selectedFile = ref<File | null>(null)
const formError = ref('')
const mediaError = ref('')
const actionError = ref('')
const quizDraftCourseId = ref<number | null>(null)

const displayedCourses = computed(() => {
  const source = props.courses ?? store.courses
  return source.filter(course => {
    if (filters.direction && course.direction !== filters.direction) {
      return false
    }
    if (filters.status && course.status !== filters.status) {
      return false
    }
    return true
  })
})

const isBusy = computed(() => store.loading)
const formHeading = computed(() => (form.id === null ? '新建课程' : '编辑课程'))
const saveLabel = computed(() =>
  form.id === null ? '创建课程' : '保存课程'
)

function statusLabel(status: TeacherCourseStatus): string {
  return statusLabels[status]
}

function directionLabel(direction: CourseDirection): string {
  return (
    directionOptions.find(option => option.value === direction)?.label ??
    direction
  )
}

function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds} 秒`
  }
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return remainder ? `${minutes} 分 ${remainder} 秒` : `${minutes} 分钟`
}

function parseTags(value: string): string[] {
  const tags: string[] = []
  for (const rawTag of value.split(/[,，]/)) {
    const tag = rawTag.trim()
    if (tag && !tags.includes(tag)) {
      tags.push(tag)
    }
  }
  return tags
}

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

function isAllowedVideo(file: File): boolean {
  const allowedTypes = new Set(['video/mp4', 'video/webm'])
  return (
    allowedTypes.has(file.type.toLowerCase()) ||
    /\.(mp4|webm)$/i.test(file.name)
  )
}

function validateVideo(file: File): boolean {
  mediaError.value = ''
  if (!isAllowedVideo(file)) {
    mediaError.value = '仅支持 MP4 或 WebM 视频'
    return false
  }
  if (file.size > MAX_VIDEO_BYTES) {
    mediaError.value = '视频文件不能超过 500 MiB'
    return false
  }
  return true
}

function validateForm(): boolean {
  formError.value = ''
  mediaError.value = ''

  if (!form.title.trim()) {
    formError.value = '课程标题不能为空'
    return false
  }
  if (!form.summary.trim()) {
    formError.value = '课程简介/知识点要点不能为空'
    return false
  }
  if (
    form.durationSeconds === '' ||
    !Number.isInteger(Number(form.durationSeconds)) ||
    Number(form.durationSeconds) <= 0
  ) {
    formError.value = '课程时长必须大于 0 秒'
    return false
  }
  if (
    form.mediaSourceType === 'external_url' &&
    !isHttpUrl(form.mediaUrl.trim())
  ) {
    mediaError.value = '外部视频链接必须是 HTTP(S) 地址'
    return false
  }
  if (
    form.mediaSourceType === 'local_upload' &&
    !selectedFile.value &&
    !(
      form.originalMediaSourceType === 'local_upload' &&
      form.mediaUrl.trim()
    )
  ) {
    mediaError.value = '请选择视频文件'
    return false
  }
  return true
}

function handleVideoChange(event: Event) {
  mediaError.value = ''
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  selectedFile.value = file
  if (file && !validateVideo(file)) {
    selectedFile.value = null
    input.value = ''
  }
}

function startEdit(course: TeacherCourse) {
  form.id = course.id
  form.version = course.version
  form.title = course.title
  form.direction = course.direction
  form.summary = course.summary
  form.tagsText = course.content_tags.join('，')
  form.durationSeconds = course.duration_seconds
  form.mediaSourceType = course.media_source_type
  form.originalMediaSourceType = course.media_source_type
  form.mediaUrl = course.media_url
  selectedFile.value = null
  formError.value = ''
  mediaError.value = ''
  actionError.value = ''
}

function resetForm() {
  form.id = null
  form.version = null
  form.title = ''
  form.direction = 'agriculture'
  form.summary = ''
  form.tagsText = ''
  form.durationSeconds = ''
  form.mediaSourceType = 'external_url'
  form.originalMediaSourceType = null
  form.mediaUrl = ''
  selectedFile.value = null
  formError.value = ''
  mediaError.value = ''
  actionError.value = ''
  quizDraftCourseId.value = null
}

async function saveCourse() {
  if (isBusy.value || !validateForm()) {
    return
  }

  let mediaUrl = form.mediaUrl.trim()
  if (form.mediaSourceType === 'local_upload' && selectedFile.value) {
    if (!validateVideo(selectedFile.value)) {
      return
    }
    try {
      const media = await store.uploadVideo(selectedFile.value)
      mediaUrl = media.media_url
      form.mediaUrl = media.media_url
      selectedFile.value = null
    } catch {
      return
    }
  }

  const payload: TeacherCoursePayload = {
    title: form.title.trim(),
    direction: form.direction,
    summary: form.summary.trim(),
    content_tags: parseTags(form.tagsText),
    duration_seconds: Number(form.durationSeconds),
    media_source_type: form.mediaSourceType,
    media_url: mediaUrl
  }

  try {
    if (form.id === null) {
      await store.createCourse(payload)
    } else {
      await store.saveCourse(form.id, {
        ...payload,
        expected_version: form.version ?? undefined
      })
    }
    resetForm()
  } catch {
    return
  }
}

async function applyFilters() {
  if (props.courses) {
    return
  }
  actionError.value = ''
  try {
    await store.loadCourses({
      direction: filters.direction || undefined,
      status: filters.status || undefined
    })
  } catch {
    return
  }
}

async function submitCourse(course: TeacherCourse) {
  if (isBusy.value) {
    return
  }
  actionError.value = ''
  try {
    await store.submitCourse(course.id, course.version)
  } catch {
    return
  }
}

async function offlineCourse(course: TeacherCourse) {
  if (isBusy.value) {
    return
  }
  actionError.value = ''
  try {
    await store.offlineCourse(course.id, course.version)
  } catch {
    return
  }
}

async function relistCourse(course: TeacherCourse) {
  if (isBusy.value) {
    return
  }
  actionError.value = ''
  try {
    await store.relistCourse(course.id, course.version)
  } catch {
    return
  }
}
</script>

<template>
  <main
    class="course-manager"
    data-ark-theme="ark"
    data-ark-depth="maximal"
  >
    <section class="manager-section filters-section" aria-labelledby="filters-title">
      <header class="section-heading">
        <div>
          <span class="ark-data">COURSE FILTERS</span>
          <h2 id="filters-title">课程筛选</h2>
        </div>
        <span class="ark-data">{{ displayedCourses.length }} 门</span>
      </header>

      <div class="filters-grid">
        <label class="field">
          <span>学习方向</span>
          <select
            v-model="filters.direction"
            data-test="course-direction-filter"
            @change="applyFilters"
          >
            <option value="">全部方向</option>
            <option
              v-for="option in directionOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>审核状态</span>
          <select
            v-model="filters.status"
            data-test="course-status-filter"
            @change="applyFilters"
          >
            <option value="">全部状态</option>
            <option
              v-for="option in statusOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>
      </div>
    </section>

    <form
      class="manager-section course-form"
      novalidate
      @submit.prevent="saveCourse"
    >
      <header class="section-heading">
        <div>
          <span class="ark-data">
            {{ form.id === null ? 'NEW COURSE' : `COURSE ${form.id}` }}
          </span>
          <h2>{{ formHeading }}</h2>
        </div>
        <button
          v-if="form.id !== null"
          class="quiet-action"
          type="button"
          :disabled="isBusy"
          @click="resetForm"
        >
          <X :size="16" aria-hidden="true" />
          取消编辑
        </button>
      </header>

      <div class="form-body">
        <div class="form-grid">
          <label class="field">
            <span>课程标题 <b aria-hidden="true">*</b></span>
            <input
              v-model="form.title"
              data-test="course-title"
              name="title"
              type="text"
              placeholder="填写课程标题"
              required
            />
          </label>

          <label class="field">
            <span>学习方向 <b aria-hidden="true">*</b></span>
            <select
              v-model="form.direction"
              data-test="course-direction"
              name="direction"
              required
            >
              <option
                v-for="option in directionOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>课程时长（秒） <b aria-hidden="true">*</b></span>
            <input
              v-model.number="form.durationSeconds"
              data-test="course-duration"
              name="duration_seconds"
              type="number"
              min="1"
              step="1"
              inputmode="numeric"
              placeholder="例如 300"
              required
            />
          </label>

          <label class="field">
            <span>内容标签</span>
            <input
              v-model="form.tagsText"
              data-test="course-tags"
              name="content_tags"
              type="text"
              placeholder="多个标签用逗号分隔"
            />
          </label>
        </div>

        <label class="field field--full">
          <span>课程简介/知识点要点 <b aria-hidden="true">*</b></span>
          <textarea
            v-model="form.summary"
            data-test="course-summary"
            name="summary"
            rows="5"
            placeholder="课程简介/知识点要点"
            required
          />
        </label>

        <fieldset class="media-field">
          <legend>视频媒体 <b aria-hidden="true">*</b></legend>
          <div class="media-segmented" role="radiogroup" aria-label="视频媒体来源">
            <label :class="{ 'is-selected': form.mediaSourceType === 'local_upload' }">
              <input
                v-model="form.mediaSourceType"
                data-test="media-local"
                type="radio"
                name="media_source_type"
                value="local_upload"
              />
              <Upload :size="17" aria-hidden="true" />
              <span>本地上传</span>
            </label>
            <label :class="{ 'is-selected': form.mediaSourceType === 'external_url' }">
              <input
                v-model="form.mediaSourceType"
                data-test="media-external"
                type="radio"
                name="media_source_type"
                value="external_url"
              />
              <Link2 :size="17" aria-hidden="true" />
              <span>外部链接</span>
            </label>
          </div>

          <div
            v-if="form.mediaSourceType === 'local_upload'"
            class="media-control"
          >
            <label class="file-control">
              <FileVideo :size="18" aria-hidden="true" />
              <span>{{ selectedFile?.name || '选择 MP4/WebM 视频' }}</span>
              <input
                data-test="course-video"
                type="file"
                :accept="VIDEO_ACCEPT"
                @change="handleVideoChange"
              />
            </label>
            <p class="field-hint">支持 MP4/WebM，单个文件不超过 500 MiB。</p>
          </div>

          <div v-else class="media-control">
            <label class="field">
              <span>外部视频链接</span>
              <input
                v-model="form.mediaUrl"
                data-test="course-media-url"
                name="media_url"
                type="url"
                placeholder="https://example.com/course.mp4"
              />
            </label>
            <p class="field-hint">仅接受可访问的 HTTP(S) 视频地址。</p>
          </div>
        </fieldset>

        <TeacherQuizEditor
          v-if="form.id !== null"
          :key="form.id"
          :course-id="form.id"
          :summary="form.summary"
          :direction="form.direction"
          :expected-version="form.version ?? 1"
          :initial-questions="
            quizDraftCourseId === form.id
              ? store.quizDraft?.questions ?? []
              : []
          "
          :initial-enabled="
            quizDraftCourseId === form.id
              ? store.quizDraft?.enabled
              : undefined
          "
          @draft-change="quizDraftCourseId = form.id"
        />

        <p v-if="formError" class="field-error" role="alert">
          {{ formError }}
        </p>
        <p v-if="mediaError" class="field-error" role="alert">
          {{ mediaError }}
        </p>
        <p v-if="actionError" class="field-error" role="alert">
          {{ actionError }}
        </p>
        <p v-if="store.error" class="field-error" role="alert">
          {{ store.error }}
        </p>

        <footer class="form-actions">
          <p>课程提交后进入审核，审核通过前不会在学员端展示。</p>
          <button
            class="primary-action"
            type="button"
            data-test="save-course"
            :disabled="isBusy"
            @click="saveCourse"
          >
            <RefreshCw
              v-if="isBusy"
              class="spinning"
              :size="17"
              aria-hidden="true"
            />
            <Save v-else :size="17" aria-hidden="true" />
            {{ isBusy ? '处理中' : saveLabel }}
          </button>
        </footer>
      </div>
    </form>

    <section class="manager-section course-section" aria-labelledby="course-list-title">
      <header class="section-heading">
        <div>
          <span class="ark-data">COURSE LIST</span>
          <h2 id="course-list-title">我的课程</h2>
        </div>
        <span class="ark-data">{{ displayedCourses.length }} 门</span>
      </header>

      <p v-if="displayedCourses.length === 0" class="empty-state">
        暂无符合条件的课程
      </p>

      <div v-else class="course-grid">
        <article
          v-for="course in displayedCourses"
          :key="course.id"
          class="course-card"
          :data-test="`course-${course.id}`"
        >
          <header class="course-card__head">
            <div>
              <span class="ark-data">
                COURSE {{ String(course.id).padStart(2, '0') }}
              </span>
              <h3>{{ course.title }}</h3>
            </div>
            <span
              class="status-badge"
              :class="`is-${course.status}`"
              data-test="course-status"
            >
              {{ statusLabel(course.status) }}
            </span>
          </header>

          <p class="course-card__summary">{{ course.summary }}</p>

          <dl class="course-card__meta">
            <div>
              <dt>学习方向</dt>
              <dd>{{ directionLabel(course.direction) }}</dd>
            </div>
            <div>
              <dt>课程时长</dt>
              <dd class="ark-data">{{ formatDuration(course.duration_seconds) }}</dd>
            </div>
            <div>
              <dt>媒体来源</dt>
              <dd>
                {{ course.media_source_type === 'local_upload' ? '本地上传' : '外部链接' }}
              </dd>
            </div>
            <div>
              <dt>版本</dt>
              <dd class="ark-data">V{{ course.version }}</dd>
            </div>
          </dl>

          <div v-if="course.content_tags.length" class="tag-list" aria-label="内容标签">
            <span v-for="tag in course.content_tags" :key="tag">{{ tag }}</span>
          </div>

          <p
            v-if="course.status === 'rejected' && course.rejection_opinion"
            class="rejection-note"
          >
            驳回意见：{{ course.rejection_opinion }}
          </p>

          <p class="media-reference">
            <Link2 :size="15" aria-hidden="true" />
            <span>{{ course.media_url }}</span>
          </p>

          <footer class="course-card__actions">
            <button
              type="button"
              :data-test="`edit-${course.status}`"
              :disabled="isBusy"
              @click="startEdit(course)"
            >
              <Pencil :size="16" aria-hidden="true" />
              编辑
            </button>

            <button
              v-if="course.status === 'draft' || course.status === 'rejected'"
              type="button"
              :data-test="`submit-${course.status}`"
              :disabled="isBusy"
              @click="submitCourse(course)"
            >
              <Send :size="16" aria-hidden="true" />
              提交审核
            </button>

            <button
              v-if="course.status === 'published'"
              type="button"
              data-test="offline-published"
              :disabled="isBusy"
              @click="offlineCourse(course)"
            >
              <EyeOff :size="16" aria-hidden="true" />
              下架
            </button>

            <button
              v-if="course.status === 'offline'"
              type="button"
              data-test="relist-offline"
              :disabled="isBusy"
              @click="relistCourse(course)"
            >
              <RotateCcw :size="16" aria-hidden="true" />
              重新上架
            </button>
          </footer>
        </article>
      </div>
    </section>
  </main>
</template>

<style scoped>
.course-manager {
  display: grid;
  width: min(100%, 1180px);
  min-width: 0;
  gap: 16px;
  margin-inline: auto;
  padding: 40px 24px 72px;
  color-scheme: light;
  color: var(--ark-paper);
}

.manager-section {
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.section-heading {
  display: flex;
  min-width: 0;
  min-height: 64px;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.section-heading > div {
  min-width: 0;
}

.section-heading span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.section-heading h2 {
  margin: 3px 0 0;
  font-size: 1.1rem;
  line-height: 1.3;
  text-wrap: pretty;
}

.filters-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  padding: 18px;
}

.field {
  display: grid;
  min-width: 0;
  gap: 7px;
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.field > span,
.media-field legend {
  line-break: strict;
  text-wrap: pretty;
  word-break: normal;
}

.field b,
.media-field b {
  margin-left: 3px;
  color: var(--ark-signal);
}

.field input,
.field select,
.field textarea {
  width: 100%;
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.field input,
.field select {
  min-height: 44px;
  padding: 9px 11px;
}

.field textarea {
  min-height: 128px;
  padding: 11px;
  resize: vertical;
}

.field input::placeholder,
.field textarea::placeholder {
  color: var(--ark-muted);
}

.field input:hover,
.field select:hover,
.field textarea:hover {
  border-color: var(--ark-signal);
}

.field input:focus-visible,
.field select:focus-visible,
.field textarea:focus-visible {
  border-color: var(--ark-focus);
  outline-offset: 0;
}

.form-body {
  display: grid;
  gap: 18px;
  padding: 18px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.field--full {
  grid-column: 1 / -1;
}

.media-field {
  display: grid;
  min-width: 0;
  gap: 12px;
  margin: 0;
  padding: 16px;
  border: 1px solid var(--ark-line);
}

.media-field legend {
  padding: 0 5px;
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.media-segmented {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  border: 1px solid var(--ark-line);
  background: var(--ark-line);
}

.media-segmented label {
  position: relative;
  display: inline-flex;
  min-width: 0;
  min-height: 46px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 12px;
  background: var(--ark-surface-1);
  color: var(--ark-muted);
  white-space: nowrap;
}

.media-segmented input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
}

.media-segmented label.is-selected {
  background: var(--ark-surface-0);
  color: var(--ark-signal);
  box-shadow: inset 0 -2px 0 var(--ark-signal);
}

.media-segmented label:focus-within {
  outline: 2px solid var(--ark-focus);
  outline-offset: 2px;
}

.media-control {
  display: grid;
  min-width: 0;
  gap: 8px;
}

.file-control {
  position: relative;
  display: inline-flex;
  min-width: 0;
  min-height: 46px;
  align-items: center;
  gap: 9px;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  color: var(--ark-paper);
}

.file-control svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.file-control span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-control input {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  cursor: pointer;
  opacity: 0;
}

.file-control:focus-within {
  outline: 2px solid var(--ark-focus);
  outline-offset: 2px;
}

.field-hint,
.form-actions p {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.76rem;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.field-error {
  margin: 0;
  padding: 10px 12px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.form-actions {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding-top: 2px;
}

.primary-action,
.quiet-action,
.course-card__actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  border-radius: var(--ark-radius);
  background: none;
  white-space: nowrap;
}

.primary-action {
  flex: 0 0 auto;
  min-width: 132px;
  padding: 0 17px;
  border: 1px solid var(--ark-signal);
  color: var(--ark-signal);
  font-weight: 700;
}

.primary-action:hover:not(:disabled) {
  background: var(--ark-surface-1);
}

.quiet-action {
  flex: 0 0 auto;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-paper);
  font-size: 0.78rem;
}

.quiet-action:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.empty-state {
  display: grid;
  min-height: 180px;
  place-items: center;
  margin: 0;
  padding: 24px;
  color: var(--ark-muted);
  text-align: center;
}

.course-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr));
  gap: 1px;
  background: var(--ark-line);
}

.course-card {
  display: grid;
  min-width: 0;
  align-content: start;
  gap: 14px;
  padding: 18px;
  background: var(--ark-surface-0);
}

.course-card__head {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.course-card__head > div {
  min-width: 0;
}

.course-card__head > div > span {
  color: var(--ark-muted);
  font-size: 0.66rem;
}

.course-card h3 {
  margin: 4px 0 0;
  font-size: 1.08rem;
  line-height: 1.35;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.status-badge {
  flex: 0 0 auto;
  padding: 3px 7px;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-muted);
  font-size: 0.7rem;
  white-space: nowrap;
}

.status-badge.is-pending,
.status-badge.is-published {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.status-badge.is-rejected {
  color: var(--ark-paper);
}

.course-card__summary {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.course-card__meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  margin: 0;
  background: var(--ark-line);
}

.course-card__meta div {
  min-width: 0;
  padding: 9px 10px;
  background: var(--ark-surface-1);
}

.course-card__meta dt {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.course-card__meta dd {
  margin: 3px 0 0;
  overflow-wrap: break-word;
  word-break: normal;
}

.tag-list {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-list span {
  max-width: 100%;
  padding: 3px 7px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
}

.rejection-note {
  margin: 0;
  padding: 9px 10px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.media-reference {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 7px;
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.media-reference svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.media-reference span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.course-card__actions {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: auto;
  padding-top: 2px;
}

.course-card__actions button {
  flex: 1 1 104px;
  min-width: 0;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-paper);
  font-size: 0.8rem;
}

.course-card__actions button:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.course-manager :is(button, input, select, textarea):focus-visible {
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

@media (max-width: 760px), (orientation: portrait) {
  .course-manager {
    padding: 28px 14px 48px;
  }

  .section-heading {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .section-heading > span {
    width: 100%;
  }

  .filters-grid,
  .form-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .form-body,
  .filters-grid {
    padding: 14px;
  }

  .form-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .primary-action {
    width: 100%;
  }
}

@media (max-width: 360px) {
  .course-manager {
    padding-inline: 12px;
  }

  .course-card,
  .section-heading {
    padding-inline: 12px;
  }

  .media-segmented label {
    padding-inline: 8px;
  }

  .course-card__meta {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
