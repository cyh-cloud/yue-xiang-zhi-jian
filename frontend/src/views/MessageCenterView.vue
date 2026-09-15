<script setup lang="ts">
import {
  Bell,
  CheckCheck,
  Eraser,
  Mail,
  MessageSquare,
  RefreshCw,
  Send
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import type { PrivateMessage, SystemNotification } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import { useAuthStore } from '@/stores/auth'
import { useMessageStore } from '@/stores/messages'

type MessageTab = 'private' | 'notifications'

const auth = useAuthStore()
const router = useRouter()
const store = useMessageStore()

const activeTab = ref<MessageTab>('private')
const selectedContactId = ref<number | null>(null)
const firstMessageBody = ref('')
const replyBody = ref('')
const actionError = ref('')
const pageLoading = ref(false)

const canUsePrivateMessages = computed(() => {
  const role = auth.user?.role
  return role === 'student' || role === 'teacher' || role === 'enterprise'
})
const selectedContact = computed(
  () =>
    store.contacts.find(contact => contact.id === selectedContactId.value) ??
    null
)
const selectedConversation = computed(
  () =>
    store.conversations.find(
      conversation => conversation.id === store.activeThreadId
    ) ?? null
)
const activeMessages = computed(() =>
  [...store.messages].sort(
    (left, right) =>
      new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
  )
)
const hasVisibleContent = computed(() => {
  if (activeTab.value === 'notifications') {
    return store.notifications.length > 0
  }

  return store.conversations.length > 0 || store.messages.length > 0
})
const actionsDisabled = computed(() => pageLoading.value || store.loading)

function formatTimestamp(value: string): string {
  const normalized = value.replace('T', ' ').replace(/(?:Z|\+00:00)$/, '')
  return normalized.slice(0, 16)
}

function selectTab(tab: MessageTab) {
  activeTab.value = tab
}

function selectContact(value: string) {
  selectedContactId.value = Number(value)
  const existingConversation = store.conversations.find(
    conversation => conversation.participant.id === selectedContactId.value
  )
  if (existingConversation) {
    void openConversation(existingConversation.id)
  }
}

async function openConversation(conversationId: number) {
  actionError.value = ''

  try {
    await store.loadThread(conversationId)
    const conversation = store.conversations.find(
      item => item.id === conversationId
    )
    if (conversation) {
      selectedContactId.value = conversation.participant.id
    }
  } catch {
    actionError.value = store.error || '消息加载失败'
  }
}

async function openPrivateMessage(message: PrivateMessage) {
  if (pageLoading.value || message.read) {
    return
  }

  actionError.value = ''
  try {
    await store.markPrivateRead(message.id)
  } catch {
    actionError.value = store.error || '消息状态更新失败'
  }
}

async function openNotification(notification: SystemNotification) {
  if (pageLoading.value || notification.read) {
    return
  }

  actionError.value = ''
  try {
    await store.markNotificationRead(notification.id)
  } catch {
    actionError.value = store.error || '通知状态更新失败'
  }
}

async function submitFirstMessage() {
  if (
    pageLoading.value ||
    !selectedContact.value ||
    !firstMessageBody.value.trim()
  ) {
    return
  }

  actionError.value = ''
  try {
    await store.sendMessage(
      selectedContact.value.id,
      firstMessageBody.value.trim()
    )
    firstMessageBody.value = ''
  } catch {
    actionError.value = store.error || '消息发送失败'
  }
}

async function submitReply() {
  if (
    pageLoading.value ||
    !selectedConversation.value ||
    !replyBody.value.trim()
  ) {
    return
  }

  actionError.value = ''
  try {
    await store.reply(
      selectedConversation.value.id,
      replyBody.value.trim()
    )
    replyBody.value = ''
  } catch {
    actionError.value = store.error || '消息回复失败'
  }
}

async function markAllRead() {
  if (pageLoading.value) {
    return
  }

  actionError.value = ''
  try {
    await store.markAllRead()
  } catch {
    actionError.value = store.error || '全部已读操作失败'
  }
}

async function clearRead() {
  if (pageLoading.value) {
    return
  }

  actionError.value = ''
  try {
    await store.clearRead()
  } catch {
    actionError.value = store.error || '清除已读失败'
  }
}

async function loadPage() {
  actionError.value = ''
  pageLoading.value = true
  const tasks: Promise<unknown>[] = [
    store.loadSummary(),
    store.loadNotifications()
  ]

  try {
    if (canUsePrivateMessages.value) {
      tasks.push(store.loadContacts(), store.loadConversations())
    }

    const results = await Promise.allSettled(tasks)
    if (results.some(result => result.status === 'rejected')) {
      actionError.value = store.error || '消息数据加载失败'
    }
  } finally {
    pageLoading.value = false
  }
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  if (!canUsePrivateMessages.value) {
    activeTab.value = 'notifications'
  }
  void loadPage()
})
</script>

<template>
  <div class="message-center">
    <AppHeader
      source="live"
      :loading="store.loading"
      :user-name="auth.user?.name"
      @refresh="loadPage"
      @logout="logout"
    />

    <main class="message-main">
      <header class="message-heading">
        <div>
          <p class="ark-data">MESSAGE CENTER</p>
          <h1>消息中心</h1>
          <p>集中查看私信、系统通知与未读消息。</p>
        </div>
        <button
          class="refresh-button"
          type="button"
          :disabled="actionsDisabled"
          @click="loadPage"
        >
          <RefreshCw :size="16" :class="{ spinning: store.loading }" aria-hidden="true" />
          刷新
        </button>
      </header>

      <section class="summary-grid" aria-label="未读消息汇总">
        <article data-test="summary-private">
          <Mail :size="18" aria-hidden="true" />
          <span>未读私信</span>
          <strong>{{ store.summary.unread_private }}</strong>
        </article>
        <article data-test="summary-notifications">
          <Bell :size="18" aria-hidden="true" />
          <span>未读通知</span>
          <strong>{{ store.summary.unread_notifications }}</strong>
        </article>
        <article data-test="summary-total">
          <MessageSquare :size="18" aria-hidden="true" />
          <span>未读总计</span>
          <strong>{{ store.summary.unread_total }}</strong>
        </article>
      </section>

      <section class="message-shell">
        <header class="message-toolbar">
          <div class="message-tabs" role="tablist" aria-label="消息类型">
            <button
              data-test="tab-private"
              type="button"
              role="tab"
              :aria-selected="activeTab === 'private'"
              :class="{ active: activeTab === 'private' }"
              @click="selectTab('private')"
            >
              私信
            </button>
            <button
              data-test="tab-notifications"
              type="button"
              role="tab"
              :aria-selected="activeTab === 'notifications'"
              :class="{ active: activeTab === 'notifications' }"
              @click="selectTab('notifications')"
            >
              通知
            </button>
          </div>

          <div class="message-actions">
            <button
              data-test="mark-all-read"
              type="button"
              :disabled="actionsDisabled"
              @click="markAllRead"
            >
              <CheckCheck :size="15" aria-hidden="true" />
              全部已读
            </button>
            <button
              data-test="clear-read"
              type="button"
              :disabled="actionsDisabled"
              @click="clearRead"
            >
              <Eraser :size="15" aria-hidden="true" />
              清除已读
            </button>
          </div>
        </header>

        <div
          v-show="activeTab === 'private'"
          class="message-layout"
          role="tabpanel"
          aria-label="私信"
        >
          <aside class="message-sidebar">
            <template v-if="canUsePrivateMessages">
              <label class="contact-field">
                <span>选择联系人</span>
                <select
                  data-test="contact-select"
                  :value="selectedContactId ?? ''"
                  @change="selectContact(($event.target as HTMLSelectElement).value)"
                >
                  <option value="" disabled>请选择可联系用户</option>
                  <option
                    v-for="contact in store.contacts"
                    :key="contact.id"
                    :value="contact.id"
                  >
                    {{ contact.name }}
                  </option>
                </select>
              </label>

              <div class="conversation-list" aria-label="会话列表">
                <button
                  v-for="conversation in store.conversations"
                  :key="conversation.id"
                  :data-test="`conversation-${conversation.id}`"
                  type="button"
                  :class="{
                    active: conversation.id === store.activeThreadId,
                    unread: conversation.unread_count > 0
                  }"
                  @click="openConversation(conversation.id)"
                >
                  <span class="conversation-avatar" aria-hidden="true">
                    {{ conversation.participant.name.slice(0, 1) }}
                  </span>
                  <span class="conversation-copy">
                    <strong>{{ conversation.participant.name }}</strong>
                    <small>
                      {{ conversation.last_message?.body || '暂无可见消息' }}
                    </small>
                  </span>
                  <span
                    v-if="conversation.unread_count > 0"
                    class="conversation-unread"
                  >
                    {{ conversation.unread_count }}
                  </span>
                </button>
                <p v-if="store.conversations.length === 0" class="list-empty">
                  暂无会话
                </p>
              </div>
            </template>
            <p v-else class="private-unavailable" data-test="private-unavailable">
              当前角色不支持私信
            </p>
          </aside>

          <section class="message-content" aria-label="消息内容">
            <template v-if="!canUsePrivateMessages">
              <div class="content-placeholder">
                <Mail :size="28" aria-hidden="true" />
                <h2>当前角色不支持私信</h2>
                <p>你仍可在通知页签查看系统消息与公告。</p>
              </div>
            </template>

            <template v-else-if="selectedConversation">
              <header class="thread-heading">
                <div>
                  <h2>{{ selectedConversation.participant.name }}</h2>
                  <p>{{ selectedConversation.participant.relationship === 'teacher_student' ? '师生沟通' : '投递沟通' }}</p>
                </div>
                <span class="read-cue">
                  <CheckCheck :size="15" aria-hidden="true" />
                  点击未读消息即标记已读
                </span>
              </header>

              <div class="message-thread">
                <button
                  v-for="item in activeMessages"
                  :key="item.id"
                  :data-test="`message-${item.id}`"
                  type="button"
                  class="message-row"
                  :class="{ unread: !item.read }"
                  @click="openPrivateMessage(item)"
                >
                  <span>{{ item.body }}</span>
                  <time :datetime="item.created_at">
                    {{ formatTimestamp(item.created_at) }}
                  </time>
                </button>
                <p v-if="activeMessages.length === 0" class="thread-empty">
                  暂无可见消息
                </p>
              </div>

              <form class="reply-form" @submit.prevent="submitReply">
                <label for="reply-input">回复消息</label>
                <div>
                  <textarea
                    id="reply-input"
                    v-model="replyBody"
                    data-test="reply-input"
                    rows="3"
                    placeholder="输入回复内容"
                  />
                  <button
                    data-test="reply-submit"
                    type="button"
                    :disabled="actionsDisabled || !replyBody.trim()"
                    @click="submitReply"
                  >
                    <Send :size="16" aria-hidden="true" />
                    发送回复
                  </button>
                </div>
              </form>
            </template>

            <template v-else-if="selectedContact">
              <div class="content-placeholder compact">
                <Mail :size="28" aria-hidden="true" />
                <h2>向 {{ selectedContact.name }} 发起私信</h2>
                <p>发送后将建立或继续该联系人的会话。</p>
              </div>
              <form class="reply-form" @submit.prevent="submitFirstMessage">
                <label for="message-input">发送消息</label>
                <div>
                  <textarea
                    id="message-input"
                    v-model="firstMessageBody"
                    data-test="message-input"
                    rows="3"
                    placeholder="输入消息内容"
                  />
                  <button
                    data-test="send-message"
                    type="button"
                    :disabled="actionsDisabled || !firstMessageBody.trim()"
                    @click="submitFirstMessage"
                  >
                    <Send :size="16" aria-hidden="true" />
                    发送消息
                  </button>
                </div>
              </form>
            </template>

            <div v-else class="content-placeholder">
              <Mail :size="28" aria-hidden="true" />
              <h2>选择会话或联系人</h2>
              <p>选择已有会话继续沟通，或从联系人列表发起新私信。</p>
            </div>
          </section>
        </div>

        <div
          v-show="activeTab === 'notifications'"
          class="notification-layout"
          role="tabpanel"
          aria-label="通知"
        >
          <aside class="notification-summary">
            <Bell :size="24" aria-hidden="true" />
            <span>未读通知</span>
            <strong>{{ store.summary.unread_notifications }}</strong>
            <p>系统事件、公告和订阅推送统一显示在这里。</p>
          </aside>

          <section class="notification-list" aria-label="通知列表">
            <button
              v-for="notification in store.notifications"
              :key="notification.id"
              :data-test="`notification-${notification.id}`"
              type="button"
              class="notification-row"
              :class="{ unread: !notification.read }"
              @click="openNotification(notification)"
            >
              <span class="notification-state" aria-hidden="true"></span>
              <span class="notification-copy">
                <span class="notification-meta">
                  <strong>{{ notification.title }}</strong>
                  <time :datetime="notification.created_at">
                    {{ formatTimestamp(notification.created_at) }}
                  </time>
                </span>
                <span>{{ notification.body }}</span>
                <span
                  v-if="!notification.source_available"
                  class="source-unavailable"
                >
                  来源已不可用
                </span>
              </span>
            </button>
            <p
              v-if="store.notifications.length === 0"
              class="notification-empty"
            >
              暂无通知
            </p>
          </section>
        </div>

        <div
          v-if="!hasVisibleContent"
          class="empty-state"
          data-test="empty-state"
        >
          <Mail :size="30" aria-hidden="true" />
          <strong>暂无消息</strong>
          <p>收到的私信和通知会显示在这里。</p>
        </div>
      </section>

      <p v-if="actionError" class="action-error" role="alert">
        {{ actionError }}
      </p>
    </main>
  </div>
</template>

<style scoped>
.message-center {
  min-height: 100svh;
  background:
    linear-gradient(rgb(16 23 25 / 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgb(16 23 25 / 0.038) 1px, transparent 1px),
    var(--ark-ink);
  background-size: 72px 72px;
}

.message-main {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 48px 24px 72px;
}

.message-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.message-heading h1 {
  margin: 6px 0 0;
  font-size: 3rem;
  line-height: 1;
}

.message-heading p:not(.ark-data) {
  margin: 14px 0 0;
  color: var(--ark-muted);
}

.refresh-button,
.message-actions button,
.reply-form button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 38px;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
  font: inherit;
}

.refresh-button:hover:not(:disabled),
.message-actions button:hover:not(:disabled),
.reply-form button:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  margin-top: 20px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.summary-grid article {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-height: 76px;
  padding: 14px 16px;
  background: rgb(255 255 255 / 0.9);
}

.summary-grid svg {
  color: var(--ark-signal);
}

.summary-grid span {
  color: var(--ark-muted);
  font-size: 0.82rem;
}

.summary-grid strong {
  font-size: 1.5rem;
}

.message-shell {
  position: relative;
  margin-top: 20px;
  border: 1px solid var(--ark-line-strong);
  background: rgb(255 255 255 / 0.94);
}

.message-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-height: 58px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--ark-line);
}

.message-tabs,
.message-actions {
  display: flex;
  gap: 7px;
}

.message-tabs button {
  min-width: 82px;
  min-height: 36px;
  padding: 0 16px;
  border: 1px solid var(--ark-line);
  background: transparent;
  color: var(--ark-muted);
  font: inherit;
}

.message-tabs button.active {
  border-color: var(--ark-signal);
  background: rgb(24 209 255 / 0.1);
  color: var(--ark-paper);
}

.message-layout {
  display: grid;
  grid-template-columns: minmax(260px, 0.78fr) minmax(0, 1.7fr);
  min-height: 560px;
}

.message-sidebar {
  min-width: 0;
  border-right: 1px solid var(--ark-line);
  background: rgb(16 23 25 / 0.025);
}

.contact-field {
  display: grid;
  gap: 7px;
  padding: 15px;
  border-bottom: 1px solid var(--ark-line);
}

.contact-field span,
.reply-form > label {
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.contact-field select {
  width: 100%;
  min-height: 40px;
  padding: 0 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: 0;
  background: #fff;
  color: var(--ark-paper);
  font: inherit;
}

.conversation-list {
  display: grid;
}

.conversation-list > button {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-height: 76px;
  padding: 12px 14px;
  border: 0;
  border-bottom: 1px solid var(--ark-line);
  background: transparent;
  color: var(--ark-paper);
  text-align: left;
}

.conversation-list > button:hover,
.conversation-list > button.active {
  background: rgb(24 209 255 / 0.08);
}

.conversation-list > button.unread {
  box-shadow: inset 3px 0 0 var(--ark-signal);
}

.conversation-avatar {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-signal);
}

.conversation-copy {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.conversation-copy strong,
.conversation-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conversation-copy small {
  color: var(--ark-muted);
  font-size: 0.74rem;
}

.conversation-unread {
  display: grid;
  place-items: center;
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  border-radius: 10px;
  background: var(--ark-signal);
  color: #fff;
  font-size: 0.68rem;
}

.list-empty,
.thread-empty,
.notification-empty {
  margin: 0;
  padding: 22px 16px;
  color: var(--ark-muted);
  font-size: 0.82rem;
  text-align: center;
}

.private-unavailable {
  margin: 0;
  padding: 20px 16px;
  color: #b42318;
  font-size: 0.84rem;
}

.message-content {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  min-width: 0;
  min-height: 560px;
}

.thread-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.thread-heading h2,
.content-placeholder h2 {
  margin: 0;
  font-size: 1.08rem;
}

.thread-heading p,
.content-placeholder p {
  margin: 6px 0 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.read-cue {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ark-muted);
  font-size: 0.72rem;
  white-space: nowrap;
}

.message-thread {
  display: grid;
  align-content: start;
  gap: 9px;
  min-height: 300px;
  max-height: 430px;
  padding: 18px;
  overflow-y: auto;
  background:
    linear-gradient(rgb(16 23 25 / 0.025) 1px, transparent 1px),
    #fff;
  background-size: 100% 48px;
}

.message-row {
  display: grid;
  gap: 7px;
  justify-self: start;
  width: min(82%, 560px);
  padding: 12px 14px;
  border: 1px solid var(--ark-line);
  background: #fff;
  color: var(--ark-paper);
  font: inherit;
  text-align: left;
}

.message-row.unread {
  border-left: 3px solid var(--ark-signal);
  background: rgb(24 209 255 / 0.07);
}

.message-row time {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.reply-form {
  display: grid;
  gap: 8px;
  padding: 15px 18px 18px;
  border-top: 1px solid var(--ark-line);
}

.reply-form > div {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 9px;
  align-items: end;
}

.reply-form textarea {
  width: 100%;
  min-height: 78px;
  padding: 10px 11px;
  resize: vertical;
  border: 1px solid var(--ark-line-strong);
  border-radius: 0;
  background: #fff;
  color: var(--ark-paper);
  font: inherit;
}

.reply-form button {
  min-height: 42px;
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.content-placeholder {
  grid-row: 1 / -1;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 8px;
  min-height: 360px;
  padding: 28px;
  color: var(--ark-muted);
  text-align: center;
}

.content-placeholder svg {
  color: var(--ark-signal);
}

.content-placeholder.compact {
  grid-row: auto;
  min-height: 220px;
}

.notification-layout {
  display: grid;
  grid-template-columns: minmax(230px, 0.7fr) minmax(0, 1.8fr);
  min-height: 560px;
}

.notification-summary {
  display: grid;
  align-content: start;
  gap: 8px;
  padding: 24px;
  border-right: 1px solid var(--ark-line);
  background: rgb(16 23 25 / 0.025);
  color: var(--ark-signal);
}

.notification-summary span {
  color: var(--ark-muted);
  font-size: 0.8rem;
}

.notification-summary strong {
  font-size: 2.4rem;
}

.notification-summary p {
  margin: 14px 0 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-height: 1.7;
}

.notification-list {
  display: grid;
  align-content: start;
}

.notification-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  padding: 18px;
  border: 0;
  border-bottom: 1px solid var(--ark-line);
  background: transparent;
  color: var(--ark-paper);
  font: inherit;
  text-align: left;
}

.notification-row:hover {
  background: rgb(24 209 255 / 0.06);
}

.notification-row.unread {
  background: rgb(24 209 255 / 0.08);
}

.notification-state {
  width: 8px;
  height: 8px;
  margin-top: 6px;
  background: var(--ark-line-strong);
}

.notification-row.unread .notification-state {
  background: var(--ark-signal);
}

.notification-copy {
  display: grid;
  gap: 8px;
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.82rem;
  line-height: 1.6;
}

.notification-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
}

.notification-meta strong {
  color: var(--ark-paper);
  font-size: 0.94rem;
}

.notification-meta time {
  flex: 0 0 auto;
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.source-unavailable {
  width: fit-content;
  padding: 3px 7px;
  border: 1px solid #b42318;
  color: #b42318;
  font-size: 0.7rem;
}

.empty-state {
  display: grid;
  place-items: center;
  min-height: 300px;
  padding: 36px;
  color: var(--ark-muted);
  text-align: center;
}

.empty-state svg {
  color: var(--ark-signal);
}

.empty-state strong {
  margin-top: 10px;
  color: var(--ark-paper);
}

.empty-state p {
  margin: 7px 0 0;
  font-size: 0.8rem;
}

.action-error {
  margin: 14px 0 0;
  padding: 10px 12px;
  border: 1px solid rgb(180 35 24 / 0.44);
  background: rgb(180 35 24 / 0.08);
  color: #b42318;
  font-size: 0.82rem;
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
  .message-main {
    padding: 32px 14px 52px;
  }

  .message-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .message-heading h1 {
    font-size: 2.3rem;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .message-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .message-tabs button,
  .message-actions button {
    flex: 1;
  }

  .message-layout,
  .notification-layout {
    grid-template-columns: 1fr;
  }

  .message-sidebar,
  .notification-summary {
    border-right: 0;
    border-bottom: 1px solid var(--ark-line);
  }

  .message-content {
    min-height: 480px;
  }

  .read-cue {
    display: none;
  }

  .reply-form > div {
    grid-template-columns: 1fr;
  }

  .notification-meta {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }
}
</style>
