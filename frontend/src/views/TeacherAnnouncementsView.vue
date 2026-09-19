<script setup lang="ts">
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Lock,
  Megaphone,
  RefreshCw,
  Send
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import type { TeacherAnnouncement } from '@/api/types'
import { useTeacherConsoleStore } from '@/stores/teacherConsole'

const store = useTeacherConsoleStore()
const title = ref('')
const body = ref('')
const actionError = ref('')

const statusLabels: Record<
  TeacherAnnouncement['delivery_status'],
  string
> = {
  pending: '待发送',
  sent: '已群发',
  failed: '群发失败'
}

const orderedAnnouncements = computed(() =>
  [...store.announcements].sort((left, right) => {
    const timeDifference =
      Date.parse(right.created_at) - Date.parse(left.created_at)
    return Number.isNaN(timeDifference)
      ? right.announcement_id.localeCompare(left.announcement_id)
      : timeDifference ||
          right.announcement_id.localeCompare(left.announcement_id)
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

async function loadAnnouncements() {
  actionError.value = ''
  try {
    await store.loadAnnouncements()
  } catch {
    actionError.value = store.error || '公告加载失败'
  }
}

async function publishAnnouncement() {
  const normalizedTitle = title.value.trim()
  const normalizedBody = body.value.trim()
  actionError.value = ''

  if (!normalizedTitle || !normalizedBody) {
    actionError.value = '请填写公告标题和正文'
    return
  }
  if (store.loading) {
    return
  }

  try {
    await store.publishAnnouncement({
      title: normalizedTitle,
      body: normalizedBody
    })
    title.value = ''
    body.value = ''
  } catch {
    actionError.value = store.error || '公告发布失败'
  }
}

onMounted(() => {
  void loadAnnouncements()
})
</script>

<template>
  <div class="teacher-announcements-view">
    <header class="page-heading">
      <div>
        <span class="ark-data">08 / TEACHER ANNOUNCEMENTS</span>
        <h1>教学公告</h1>
        <p>发布后由系统通知群发全体学员，并保留完整的投递状态记录。</p>
      </div>
      <button
        class="refresh-button"
        data-test="refresh-announcements"
        type="button"
        :disabled="store.loading"
        @click="loadAnnouncements"
      >
        <RefreshCw
          :size="16"
          :class="{ spinning: store.loading }"
          aria-hidden="true"
        />
        刷新历史
      </button>
    </header>

    <div class="announcement-workspace">
      <section class="panel composer-panel" aria-labelledby="announcement-form-title">
        <header class="panel-heading">
          <Megaphone :size="18" aria-hidden="true" />
          <h2 id="announcement-form-title">发布公告</h2>
        </header>

        <form class="announcement-form" @submit.prevent="publishAnnouncement">
          <label>
            <span>公告标题</span>
            <input
              v-model="title"
              data-test="announcement-title"
              type="text"
              autocomplete="off"
              placeholder="例如：本周课程安排调整"
            />
          </label>

          <label>
            <span>公告正文</span>
            <textarea
              v-model="body"
              data-test="announcement-body"
              rows="7"
              placeholder="填写需要通知全体学员的内容"
            />
          </label>

          <button
            class="publish-button"
            data-test="publish-announcement"
            type="button"
            :disabled="store.loading"
            @click="publishAnnouncement"
          >
            <Send :size="17" aria-hidden="true" />
            {{ store.loading ? '正在发布' : '发布并群发' }}
          </button>

          <p
            v-if="actionError || store.error"
            class="action-error"
            role="alert"
          >
            {{ actionError || store.error }}
          </p>
        </form>
      </section>

      <section class="panel history-panel" aria-labelledby="announcement-history-title">
        <header class="panel-heading">
          <Clock :size="18" aria-hidden="true" />
          <h2 id="announcement-history-title">公告历史</h2>
          <span class="ark-data">{{ orderedAnnouncements.length }} 条</span>
        </header>

        <div
          v-if="orderedAnnouncements.length"
          class="announcement-history"
          data-test="announcement-history"
        >
          <article
            v-for="item in orderedAnnouncements"
            :key="item.announcement_id"
            class="announcement-item"
            data-test="announcement-item"
            :data-status="item.delivery_status"
          >
            <header>
              <span
                class="status-badge"
                :data-status="item.delivery_status"
              >
                <CheckCircle2
                  v-if="item.delivery_status === 'sent'"
                  :size="15"
                  aria-hidden="true"
                />
                <AlertCircle
                  v-else-if="item.delivery_status === 'failed'"
                  :size="15"
                  aria-hidden="true"
                />
                <Clock v-else :size="15" aria-hidden="true" />
                {{ statusLabels[item.delivery_status] }}
              </span>
              <time :datetime="item.created_at">
                {{ formatTimestamp(item.created_at) }}
              </time>
            </header>

            <h3>{{ item.title }}</h3>
            <p>{{ item.body }}</p>

            <div
              v-if="item.delivery_status === 'sent'"
              class="immutable-note"
              data-test="sent-immutable"
            >
              <Lock :size="15" aria-hidden="true" />
              <span>已群发，不可编辑或撤回</span>
            </div>
            <p v-else-if="item.delivery_status === 'pending'" class="status-note">
              投递处理中，完成后可刷新查看结果。
            </p>
            <p v-else class="status-note">
              本次群发未完成，请核对内容后重新发布一条公告。
            </p>
          </article>
        </div>

        <p v-else class="history-empty" data-test="announcement-empty">
          {{ store.loading ? '正在加载公告历史' : '暂无公告历史' }}
        </p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.teacher-announcements-view {
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

.refresh-button,
.publish-button {
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

.announcement-workspace {
  display: grid;
  grid-template-columns: minmax(280px, 0.78fr) minmax(0, 1.5fr);
  gap: 16px;
  align-items: start;
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 22px 24px 72px;
}

.panel {
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
}

.composer-panel {
  position: sticky;
  top: 16px;
}

.panel-heading {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 54px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.panel-heading svg {
  color: var(--ark-signal);
}

.panel-heading h2 {
  margin: 0;
  font-size: 0.98rem;
}

.panel-heading > span {
  margin-left: auto;
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.announcement-form {
  display: grid;
  gap: 16px;
  padding: 18px;
}

.announcement-form label {
  display: grid;
  gap: 7px;
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.8rem;
  font-weight: 700;
}

.announcement-form input,
.announcement-form textarea {
  width: 100%;
  min-width: 0;
  min-height: 42px;
  padding: 10px 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font-weight: 400;
  line-break: strict;
  overflow-wrap: break-word;
  resize: vertical;
  word-break: normal;
}

.announcement-form input:focus,
.announcement-form textarea:focus {
  border-color: var(--ark-focus);
  box-shadow: 0 0 0 2px var(--ark-surface-2);
}

.announcement-form input::placeholder,
.announcement-form textarea::placeholder {
  color: var(--ark-muted);
}

.publish-button {
  width: 100%;
  border-color: var(--ark-signal);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
  font-weight: 700;
}

.publish-button:hover:not(:disabled) {
  border-color: var(--ark-paper);
  background: var(--ark-paper);
}

.action-error {
  margin: 0;
  padding: 10px 12px;
  border: 1px solid var(--ark-line-strong);
  border-left: 3px solid var(--ark-signal);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  font-size: 0.82rem;
  overflow-wrap: anywhere;
}

.announcement-history {
  display: grid;
}

.announcement-item {
  display: grid;
  gap: 9px;
  min-width: 0;
  padding: 18px;
  border-bottom: 1px solid var(--ark-line);
}

.announcement-item:last-child {
  border-bottom: 0;
}

.announcement-item > header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 14px;
}

.announcement-item time {
  color: var(--ark-muted);
  font-size: 0.72rem;
  overflow-wrap: anywhere;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: fit-content;
  min-height: 28px;
  padding: 3px 8px;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-muted);
  font-size: 0.74rem;
  font-weight: 700;
  white-space: nowrap;
}

.status-badge[data-status="sent"] {
  border-color: var(--ark-state);
  color: var(--ark-state);
}

.status-badge[data-status="pending"] {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.status-badge[data-status="failed"] {
  border-color: var(--ark-paper);
  color: var(--ark-paper);
}

.announcement-item h3 {
  margin: 0;
  font-size: 1.05rem;
  line-height: 1.45;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.announcement-item > p {
  margin: 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  word-break: normal;
}

.immutable-note,
.status-note {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin: 4px 0 0;
  padding-top: 11px;
  border-top: 1px solid var(--ark-line);
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.immutable-note svg {
  flex: 0 0 auto;
  margin-top: 3px;
  color: var(--ark-state);
}

.history-empty {
  display: grid;
  place-items: center;
  min-height: 260px;
  margin: 0;
  padding: 28px;
  color: var(--ark-muted);
  text-align: center;
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

  .announcement-workspace {
    grid-template-columns: minmax(0, 1fr);
    padding: 16px 14px 52px;
  }

  .composer-panel {
    position: static;
  }
}

@media (max-width: 420px) {
  .announcement-item {
    padding: 16px 14px;
  }

  .announcement-item > header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
