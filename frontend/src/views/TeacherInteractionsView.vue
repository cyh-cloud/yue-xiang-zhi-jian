<script setup lang="ts">
import {
  Filter,
  MessageSquare,
  RefreshCw,
  Reply,
  Send
} from 'lucide-vue-next'
import { computed, onMounted, reactive, ref } from 'vue'

import type {
  TeacherComment,
  TeacherCommentContentType
} from '@/api/types'
import { useTeacherConsoleStore } from '@/stores/teacherConsole'

const store = useTeacherConsoleStore()
const activeContentType = ref<TeacherCommentContentType>('course_video')
const selectedContentId = ref('')
const replyDrafts = reactive<Record<string, string>>({})
const submittingCommentId = ref<string | null>(null)
const actionError = ref('')

const contentTypes: Array<{
  value: TeacherCommentContentType
  label: string
}> = [
  { value: 'course_video', label: '课程视频评论' },
  { value: 'handcraft_teaching_video', label: '非遗视频评论' }
]

const commentsForActiveType = computed(() =>
  store.comments.filter(
    comment => comment.content_type === activeContentType.value
  )
)

const targetOptions = computed(() => {
  const contentIds = new Set(
    commentsForActiveType.value.map(comment => comment.content_id)
  )
  return [...contentIds].sort((left, right) => {
    const leftNumber = Number(left)
    const rightNumber = Number(right)
    if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
      return leftNumber - rightNumber
    }
    return left.localeCompare(right)
  })
})

const visibleComments = computed(() =>
  commentsForActiveType.value
    .filter(
      comment =>
        !selectedContentId.value ||
        comment.content_id === selectedContentId.value
    )
    .sort((left, right) => {
      const timeDifference =
        Date.parse(left.created_at) - Date.parse(right.created_at)
      return Number.isNaN(timeDifference)
        ? left.comment_id.localeCompare(right.comment_id)
        : timeDifference || left.comment_id.localeCompare(right.comment_id)
    })
)

function formatTimestamp(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).format(date)
}

function targetLabel(contentId: string): string {
  return activeContentType.value === 'course_video'
    ? `课程 ${contentId}`
    : `非遗视频 ${contentId}`
}

function parentPreview(comment: TeacherComment): string {
  const parent = store.comments.find(
    item => item.comment_id === comment.parent_comment_id
  )
  return parent ? `回复：${parent.body}` : '回复上一条评论'
}

async function loadComments() {
  actionError.value = ''
  try {
    await store.loadComments({
      content_type: activeContentType.value
    })
  } catch {
    actionError.value = store.error || '评论加载失败'
  }
}

function selectContentType(contentType: TeacherCommentContentType) {
  if (contentType === activeContentType.value) {
    return
  }
  activeContentType.value = contentType
  selectedContentId.value = ''
  void loadComments()
}

async function submitReply(commentId: string) {
  const body = replyDrafts[commentId]?.trim() ?? ''
  if (!body || submittingCommentId.value || store.loading) {
    return
  }

  actionError.value = ''
  submittingCommentId.value = commentId
  try {
    await store.replyComment(commentId, body)
    replyDrafts[commentId] = ''
  } catch {
    actionError.value = store.error || '评论回复失败'
  } finally {
    submittingCommentId.value = null
  }
}

onMounted(() => {
  void loadComments()
})
</script>

<template>
  <div class="teacher-interactions-view">
    <header class="page-heading">
      <div>
        <span class="ark-data">08 / TEACHER INTERACTIONS</span>
        <h1>答疑互动</h1>
        <p>统一查看课程视频与非遗教学视频留言，按时间顺序回复学员问题。</p>
      </div>
      <button
        class="refresh-button"
        data-test="refresh-comments"
        type="button"
        :disabled="store.loading"
        @click="loadComments"
      >
        <RefreshCw
          :size="16"
          :class="{ spinning: store.loading }"
          aria-hidden="true"
        />
        刷新评论
      </button>
    </header>

    <main class="interaction-workspace">
      <section class="interaction-toolbar" aria-label="评论筛选">
        <div class="content-tabs" role="tablist" aria-label="评论内容类型">
          <button
            v-for="contentType in contentTypes"
            :key="contentType.value"
            :data-test="`tab-${contentType.value}`"
            type="button"
            role="tab"
            :aria-selected="activeContentType === contentType.value"
            :class="{ active: activeContentType === contentType.value }"
            @click="selectContentType(contentType.value)"
          >
            <MessageSquare :size="16" aria-hidden="true" />
            {{ contentType.label }}
          </button>
        </div>

        <label class="target-filter">
          <Filter :size="16" aria-hidden="true" />
          <span>筛选评论目标</span>
          <select
            v-model="selectedContentId"
            data-test="target-filter"
            :disabled="store.loading"
          >
            <option value="">全部目标</option>
            <option
              v-for="contentId in targetOptions"
              :key="contentId"
              :value="contentId"
            >
              {{ targetLabel(contentId) }}
            </option>
          </select>
        </label>
      </section>

      <section class="comment-panel" aria-labelledby="comment-list-title">
        <header class="panel-heading">
          <div>
            <span class="ark-data">
              {{ activeContentType === 'course_video' ? 'COURSE VIDEO' : 'HERITAGE VIDEO' }}
            </span>
            <h2 id="comment-list-title">
              {{ activeContentType === 'course_video' ? '课程视频评论' : '非遗视频评论' }}
            </h2>
          </div>
          <span class="ark-data">{{ visibleComments.length }} 条</span>
        </header>

        <p
          v-if="actionError || store.error"
          class="action-error"
          role="alert"
        >
          {{ actionError || store.error }}
        </p>

        <ol
          v-if="visibleComments.length"
          class="comment-list"
          data-test="comment-list"
        >
          <li v-for="comment in visibleComments" :key="comment.comment_id">
            <article
              class="comment-item"
              :class="{ 'is-teacher': comment.is_teacher_reply }"
              :data-test="`comment-${comment.comment_id}`"
            >
              <header class="comment-meta">
                <div>
                  <span
                    v-if="comment.is_teacher_reply"
                    class="teacher-label"
                    data-test="teacher-reply-label"
                  >
                    教师回复
                  </span>
                  <span v-else class="student-label">学员留言</span>
                  <span class="target-label">
                    {{ targetLabel(comment.content_id) }}
                  </span>
                </div>
                <time :datetime="comment.created_at">
                  {{ formatTimestamp(comment.created_at) }}
                </time>
              </header>

              <p
                v-if="comment.parent_comment_id"
                class="parent-reference"
              >
                {{ parentPreview(comment) }}
              </p>
              <p class="comment-body" data-test="comment-body">
                {{ comment.body }}
              </p>

              <form
                class="reply-form"
                @submit.prevent="submitReply(comment.comment_id)"
              >
                <label :for="`reply-${comment.comment_id}`">回复该留言</label>
                <div>
                  <textarea
                    :id="`reply-${comment.comment_id}`"
                    v-model="replyDrafts[comment.comment_id]"
                    data-test="reply-body"
                    rows="3"
                    placeholder="输入回复内容"
                    :disabled="store.loading"
                  />
                  <button
                    data-test="submit-reply"
                    type="button"
                    :disabled="
                      store.loading ||
                      submittingCommentId === comment.comment_id ||
                      !replyDrafts[comment.comment_id]?.trim()
                    "
                    @click="submitReply(comment.comment_id)"
                  >
                    <Reply :size="16" aria-hidden="true" />
                    <Send :size="16" aria-hidden="true" />
                    {{
                      submittingCommentId === comment.comment_id
                        ? '正在回复'
                        : '提交回复'
                    }}
                  </button>
                </div>
              </form>
            </article>
          </li>
        </ol>

        <div v-else class="comment-empty" data-test="comment-empty">
          <MessageSquare :size="24" aria-hidden="true" />
          <strong>
            {{ store.loading ? '正在加载评论' : '暂无可见评论' }}
          </strong>
          <p v-if="!store.loading">切换内容类型或调整目标筛选后再试。</p>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.teacher-interactions-view {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  color-scheme: light;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 40px 24px 22px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.page-heading > div {
  min-width: 0;
}

.page-heading > div > span {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.page-heading h1 {
  margin: 9px 0 0;
  font-size: 3rem;
  line-height: 1;
  text-wrap: balance;
}

.page-heading p {
  max-width: 62ch;
  margin: 15px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.refresh-button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  padding: 0 14px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.refresh-button:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.interaction-workspace {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 22px 24px 72px;
}

.interaction-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(230px, 0.75fr);
  gap: 12px;
  align-items: stretch;
}

.content-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.content-tabs button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 0;
  min-height: 52px;
  padding: 9px 12px;
  border: 0;
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  line-break: strict;
  text-align: center;
  text-wrap: pretty;
  white-space: normal;
  word-break: keep-all;
}

.content-tabs button.active {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
  box-shadow: inset 0 -3px 0 var(--ark-signal);
}

.target-filter {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 4px 8px;
  align-items: center;
  min-width: 0;
  padding: 9px 12px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.target-filter > svg {
  color: var(--ark-signal);
}

.target-filter > span {
  color: var(--ark-muted);
  font-size: 0.76rem;
  line-break: strict;
  overflow-wrap: break-word;
  word-break: normal;
}

.target-filter select {
  grid-column: 1 / -1;
  width: 100%;
  min-width: 0;
  min-height: 36px;
  padding: 0 9px;
  border: 1px solid var(--ark-line);
  border-radius: 0;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.comment-panel {
  min-width: 0;
  margin-top: 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
}

.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 62px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.panel-heading > div {
  min-width: 0;
}

.panel-heading > div > span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.panel-heading h2 {
  margin: 2px 0 0;
  font-size: 1rem;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.panel-heading > span {
  flex: 0 0 auto;
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.action-error {
  margin: 12px 14px 0;
  padding: 10px 12px;
  border: 1px solid var(--ark-line-strong);
  border-left: 3px solid var(--ark-signal);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  font-size: 0.82rem;
  overflow-wrap: anywhere;
}

.comment-list {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.comment-list > li {
  min-width: 0;
  border-bottom: 1px solid var(--ark-line);
}

.comment-list > li:last-child {
  border-bottom: 0;
}

.comment-item {
  display: grid;
  gap: 11px;
  min-width: 0;
  padding: 18px;
  border-left: 3px solid var(--ark-line-strong);
}

.comment-item.is-teacher {
  border-left-color: var(--ark-state);
  background: var(--ark-surface-1);
}

.comment-meta {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px 18px;
  min-width: 0;
}

.comment-meta > div {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 8px;
  min-width: 0;
}

.teacher-label,
.student-label,
.target-label {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  min-height: 27px;
  padding: 3px 8px;
  border: 1px solid var(--ark-line);
  font-size: 0.72rem;
  font-weight: 700;
}

.teacher-label {
  border-color: var(--ark-state);
  color: var(--ark-state);
  white-space: nowrap;
}

.student-label {
  color: var(--ark-paper);
  white-space: nowrap;
}

.target-label {
  color: var(--ark-muted);
  font-weight: 400;
  line-break: strict;
  overflow-wrap: anywhere;
  white-space: normal;
  word-break: normal;
}

.comment-meta time {
  flex: 0 0 auto;
  color: var(--ark-muted);
  font-size: 0.72rem;
  overflow-wrap: anywhere;
}

.parent-reference,
.comment-body {
  margin: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  word-break: normal;
}

.parent-reference {
  padding-left: 10px;
  border-left: 2px solid var(--ark-line-strong);
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.comment-body {
  color: var(--ark-paper);
  font-size: 0.94rem;
}

.reply-form {
  display: grid;
  gap: 7px;
  padding-top: 12px;
  border-top: 1px solid var(--ark-line);
}

.reply-form > label {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: break-word;
  word-break: normal;
}

.reply-form > div {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 9px;
  align-items: end;
}

.reply-form textarea {
  width: 100%;
  min-width: 0;
  min-height: 82px;
  padding: 10px 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  resize: vertical;
  word-break: normal;
}

.reply-form textarea:focus {
  border-color: var(--ark-focus);
  box-shadow: 0 0 0 2px var(--ark-surface-2);
}

.reply-form textarea::placeholder {
  color: var(--ark-muted);
}

.reply-form button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-width: 118px;
  min-height: 42px;
  padding: 0 13px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
  font-weight: 700;
  white-space: normal;
}

.reply-form button:hover:not(:disabled) {
  border-color: var(--ark-paper);
  background: var(--ark-paper);
}

.comment-empty {
  display: grid;
  place-items: center;
  min-height: 280px;
  padding: 32px 20px;
  color: var(--ark-muted);
  text-align: center;
}

.comment-empty svg {
  color: var(--ark-signal);
}

.comment-empty strong {
  margin-top: 10px;
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.comment-empty p {
  max-width: 38ch;
  margin: 7px 0 0;
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 820px) {
  .page-heading {
    align-items: stretch;
    flex-direction: column;
    padding: 28px 14px 20px;
  }

  .page-heading h1 {
    font-size: 2.25rem;
  }

  .refresh-button {
    width: 100%;
  }

  .interaction-workspace {
    padding: 16px 14px 52px;
  }

  .interaction-toolbar {
    grid-template-columns: minmax(0, 1fr);
  }

  .reply-form > div {
    grid-template-columns: minmax(0, 1fr);
  }

  .reply-form button {
    width: 100%;
  }
}

@media (max-width: 420px) {
  .content-tabs button {
    gap: 5px;
    padding-inline: 7px;
  }

  .comment-item {
    padding: 16px 14px;
  }

  .comment-meta {
    flex-direction: column;
  }
}
</style>
