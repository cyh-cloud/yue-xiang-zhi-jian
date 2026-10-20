<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { RouterLink, useRoute } from "vue-router";

import {
  clearReadNotifications,
  getConversation,
  getInbox,
  getJobApplications,
  getNotifications,
  getReadState,
  getSystemAnnouncements,
  getUnreadCount,
  markAllRead,
  markReadOne,
  sendMessage,
  type ConversationMessage,
  type InboxMessage,
  type MessageSource,
} from "@/api/message-center";
import { NOTIFICATION_STORAGE_KEY } from "@/shared/storageKeys";
import { useSessionStore } from "@/stores/session";

type Tab = "unread" | "read" | "messages";
type FeedbackKind = "success" | "error" | "info";

interface MessageItem {
  key: string;
  source: MessageSource;
  refId: string;
  type: string;
  tag: string;
  isRead: boolean;
  title: string;
  preview: string;
  time: string;
  timestamp: number;
  replyId?: string;
  replyName?: string;
}

interface ConversationState {
  otherId: string;
  otherName: string;
  messages: ConversationMessage[];
  loading: boolean;
  loadError: string;
  sending: boolean;
  sendError: string;
}

const BADGE_POLL_MS = 15_000;
const CONVERSATION_POLL_MS = 4_000;

const route = useRoute();
const session = useSessionStore();
const root = ref<HTMLElement | null>(null);
const panelOpen = ref(false);
const activeTab = ref<Tab>("unread");
const notificationEnabled = ref(readNotificationPreference());
const badgeCount = ref(0);
const items = ref<MessageItem[]>([]);
const inbox = ref<InboxMessage[]>([]);
const inboxFailed = ref(false);
const sourceFailures = ref<string[]>([]);
const readStateFailed = ref(false);
const loading = ref(false);
const loadAttempted = ref(false);
const actionBusy = ref(false);
const feedback = ref<{ kind: FeedbackKind; text: string } | null>(null);
const detailItem = ref<MessageItem | null>(null);
const conversation = ref<ConversationState | null>(null);
const replyDraft = ref("");

let badgePollTimer: number | undefined;
let conversationPollTimer: number | undefined;
let feedbackTimer: number | undefined;
let badgeRequestId = 0;
let dataRequestId = 0;

const loginTarget = computed(() =>
  route.path === "/login"
    ? "/login"
    : {
        path: "/login",
        query: { redirect: route.fullPath },
      },
);

const unreadItems = computed(() =>
  items.value
    .filter((item) => !item.isRead)
    .sort((left, right) => right.timestamp - left.timestamp),
);
const readItems = computed(() =>
  items.value
    .filter((item) => item.isRead)
    .sort((left, right) => right.timestamp - left.timestamp),
);
const activeItems = computed(() =>
  activeTab.value === "read" ? readItems.value : unreadItems.value,
);
const allSourcesFailed = computed(
  () =>
    loadAttempted.value &&
    !loading.value &&
    sourceFailures.value.length === 4 &&
    items.value.length === 0,
);
const partialFailureText = computed(() => {
  if (sourceFailures.value.length) {
    return `部分消息来源加载失败：${sourceFailures.value.join("、")}`;
  }
  if (readStateFailed.value) {
    return "已读状态加载失败，未读判断可能不准确";
  }
  return "";
});
const emptyText = computed(() => {
  if (activeTab.value === "read") return "暂无已读通知";
  return "全部已读，没有待处理通知";
});

watch(
  () => session.isAuthenticated,
  () => {
    syncSessionState();
  },
  { immediate: true },
);

onMounted(() => {
  document.addEventListener("click", handleDocumentClick);
  document.addEventListener("keydown", handleDocumentKeydown);
  window.addEventListener("focus", handleFocus);
  document.addEventListener("visibilitychange", handleVisibilityChange);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", handleDocumentClick);
  document.removeEventListener("keydown", handleDocumentKeydown);
  window.removeEventListener("focus", handleFocus);
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  stopBadgePolling();
  stopConversationPolling();
  if (feedbackTimer !== undefined) window.clearTimeout(feedbackTimer);
});

function readNotificationPreference(): boolean {
  try {
    return localStorage.getItem(NOTIFICATION_STORAGE_KEY) !== "0";
  } catch {
    return true;
  }
}

function writeNotificationPreference(enabled: boolean): void {
  try {
    localStorage.setItem(NOTIFICATION_STORAGE_KEY, enabled ? "1" : "0");
  } catch {
    // The current session still honors the in-memory choice.
  }
}

function syncSessionState(): void {
  if (session.isAuthenticated && notificationEnabled.value) {
    void refreshBadge();
    startBadgePolling();
    return;
  }
  badgeCount.value = 0;
  stopBadgePolling();
  closeConversation();
  items.value = [];
  inbox.value = [];
  if (!session.isAuthenticated) panelOpen.value = false;
}

function togglePanel(): void {
  panelOpen.value = !panelOpen.value;
  if (!panelOpen.value) return;
  activeTab.value = "unread";
  void refreshBadge();
  if (session.isAuthenticated && notificationEnabled.value) void loadData();
}

function closePanel(): void {
  panelOpen.value = false;
}

async function refreshBadge(): Promise<void> {
  if (!session.isAuthenticated || !notificationEnabled.value || !session.user) {
    badgeCount.value = 0;
    return;
  }
  const requestId = ++badgeRequestId;
  try {
    const count = await getUnreadCount(session.user.id);
    if (requestId === badgeRequestId) badgeCount.value = Math.max(0, count);
  } catch {
    // Keep the last known count. A visible source failure is reported when
    // the panel itself loads, while transient focus polling stays quiet.
  }
}

async function loadData(): Promise<void> {
  if (!session.isAuthenticated || !notificationEnabled.value || !session.user) {
    return;
  }
  const userId = session.user.id;
  const requestId = ++dataRequestId;
  loading.value = true;
  loadAttempted.value = true;
  sourceFailures.value = [];
  readStateFailed.value = false;
  inboxFailed.value = false;

  let systemRead = new Set<string>();
  let jobRead = new Set<string>();
  let systemDismissed = new Set<string>();
  let jobDismissed = new Set<string>();
  try {
    const readState = await getReadState(userId);
    systemRead = new Set((readState.system_announcement ?? []).map(String));
    jobRead = new Set((readState.job_application ?? []).map(String));
    systemDismissed = new Set(
      (readState.dismissed?.system_announcement ?? []).map(String),
    );
    jobDismissed = new Set(
      (readState.dismissed?.job_application ?? []).map(String),
    );
  } catch {
    if (requestId === dataRequestId) readStateFailed.value = true;
  }

  const [announcements, applications, inboxResult, notifications] =
    await Promise.allSettled([
      getSystemAnnouncements(),
      getJobApplications(userId),
      getInbox(userId),
      getNotifications(userId),
    ]);
  if (requestId !== dataRequestId) return;

  const nextItems: MessageItem[] = [];
  const failures: string[] = [];

  if (announcements.status === "fulfilled") {
    for (const announcement of announcements.value) {
      if (systemDismissed.has(String(announcement.id))) continue;
      nextItems.push({
        key: `sys:${announcement.id}`,
        source: "system_announcement",
        refId: String(announcement.id),
        type: "announcement",
        tag: "系统公告",
        isRead: systemRead.has(String(announcement.id)),
        title: announcement.title || "系统公告",
        preview: announcement.content || "",
        time: announcement.created_at || "",
        timestamp: parseTimestamp(announcement.created_at),
      });
    }
  } else {
    failures.push("系统公告");
  }

  if (applications.status === "fulfilled") {
    const statusLabels: Record<string, string> = {
      pending: "待处理",
      interview: "已通知面试",
      approved: "已通过",
      rejected: "未通过",
    };
    for (const application of applications.value) {
      if (jobDismissed.has(String(application.id))) continue;
      const status = statusLabels[application.status] || application.status;
      nextItems.push({
        key: `job:${application.id}`,
        source: "job_application",
        refId: String(application.id),
        type: "job",
        tag: "企业通知",
        isRead: jobRead.has(String(application.id)),
        title: `投递「${application.title || "岗位"}」`,
        preview: `状态：${status}　${application.company || ""}　${application.location || ""}`,
        time: application.applied_at || "",
        timestamp: parseTimestamp(application.applied_at),
        replyId: application.enterprise_id || "",
        replyName: application.company || "企业",
      });
    }
  } else {
    failures.push("投递状态");
  }

  if (inboxResult.status === "fulfilled") {
    inbox.value = inboxResult.value;
    for (const message of inboxResult.value) {
      if (message.is_mine) continue;
      nextItems.push({
        key: `msg:${message.other_id}`,
        source: "messages",
        refId: String(message.other_id),
        type: "interaction",
        tag: "互动",
        isRead: Boolean(message.is_read),
        title: `来自 ${message.other_name || "对方"} 的消息`,
        preview: message.content || "",
        time: message.created_at || "",
        timestamp: parseTimestamp(message.created_at),
        replyId: message.other_id || "",
        replyName: message.other_name || "对方",
      });
    }
  } else {
    inbox.value = [];
    inboxFailed.value = true;
    failures.push("互动私信");
  }

  if (notifications.status === "fulfilled") {
    const notificationTags: Record<string, string> = {
      announcement: "公告",
      grade: "实训批改",
      farming_reminder: "农事提醒",
    };
    for (const notification of notifications.value) {
      nextItems.push({
        key: `notif:${notification.id}`,
        source: "notifications",
        refId: String(notification.id),
        type: notification.type || "system",
        tag: notificationTags[notification.type] || "通知",
        isRead: Boolean(notification.is_read),
        title: notification.title || "通知",
        preview: notification.content || "",
        time: notification.created_at || "",
        timestamp: parseTimestamp(notification.created_at),
      });
    }
  } else {
    failures.push("站内通知");
  }

  sourceFailures.value = failures;
  items.value = nextItems.sort((left, right) => right.timestamp - left.timestamp);
  loading.value = false;
}

async function selectTab(tab: Tab): Promise<void> {
  activeTab.value = tab;
  if (tab === "messages" && session.isAuthenticated && notificationEnabled.value) {
    await loadData();
  }
}

function jumpToUnread(): void {
  activeTab.value = "unread";
}

async function handleItem(item: MessageItem): Promise<void> {
  if (!item.isRead) {
    try {
      await markReadOne(requireUserId(), item.source, item.refId);
      item.isRead = true;
      badgeCount.value = Math.max(0, badgeCount.value - 1);
      void refreshBadge();
    } catch {
      showFeedback("标记已读失败，请稍后重试", "error");
    }
  }

  if (item.replyId) {
    await openConversation(item.replyId, item.replyName || "对方");
  } else {
    detailItem.value = item;
  }
}

async function markEverythingRead(): Promise<void> {
  if (actionBusy.value || !session.isAuthenticated) return;
  actionBusy.value = true;
  try {
    await markAllRead(requireUserId());
    items.value = items.value.map((item) => ({ ...item, isRead: true }));
    badgeCount.value = 0;
    await loadData();
    await refreshBadge();
    showFeedback("已全部标记为已读", "success");
  } catch {
    showFeedback("操作失败，请稍后重试", "error");
  } finally {
    actionBusy.value = false;
  }
}

async function clearRead(): Promise<void> {
  if (actionBusy.value || !session.isAuthenticated) return;
  actionBusy.value = true;
  try {
    await clearReadNotifications(requireUserId());
    await loadData();
    await refreshBadge();
    showFeedback("已清除已读通知", "success");
  } catch {
    showFeedback("清除失败，请稍后重试", "error");
  } finally {
    actionBusy.value = false;
  }
}

function disableNotifications(): void {
  notificationEnabled.value = false;
  writeNotificationPreference(false);
  badgeCount.value = 0;
  items.value = [];
  inbox.value = [];
  stopBadgePolling();
  closeConversation();
}

function enableNotifications(): void {
  notificationEnabled.value = true;
  writeNotificationPreference(true);
  void refreshBadge();
  void loadData();
  startBadgePolling();
}

async function openConversation(otherId: string, otherName: string): Promise<void> {
  conversation.value = {
    otherId,
    otherName,
    messages: [],
    loading: true,
    loadError: "",
    sending: false,
    sendError: "",
  };
  replyDraft.value = "";
  detailItem.value = null;
  await loadConversation();
  startConversationPolling();
}

async function loadConversation(): Promise<void> {
  const current = conversation.value;
  if (!current) return;
  current.loading = true;
  current.loadError = "";
  try {
    const messages = await getConversation(current.otherId, requireUserId());
    if (conversation.value !== current) return;
    current.messages = messages;
    inbox.value = inbox.value.map((item) =>
      item.other_id === current.otherId ? { ...item, is_read: 1 } : item,
    );
    items.value = items.value.map((item) =>
      item.source === "messages" && item.replyId === current.otherId
        ? { ...item, isRead: true }
        : item,
    );
    void refreshBadge();
    await scrollConversationToBottom();
  } catch {
    if (conversation.value === current) {
      current.loadError = "历史消息加载失败";
    }
  } finally {
    if (conversation.value === current) current.loading = false;
  }
}

async function sendConversationReply(): Promise<void> {
  const current = conversation.value;
  const content = replyDraft.value.trim();
  if (!current || !content || current.sending) return;
  current.sending = true;
  current.sendError = "";
  try {
    const response = await sendMessage(current.otherId, content);
    const message: ConversationMessage = {
      id: response.id,
      sender_id: requireUserId(),
      receiver_id: current.otherId,
      content,
      is_read: 1,
      created_at: new Date().toISOString(),
    };
    mergeConversationMessages(current, [message]);
    replyDraft.value = "";
    await scrollConversationToBottom();
    void refreshBadge();
  } catch {
    current.sendError = "发送失败，请重试";
  } finally {
    current.sending = false;
  }
}

function closeConversation(): void {
  stopConversationPolling();
  conversation.value = null;
  replyDraft.value = "";
}

function startBadgePolling(): void {
  if (badgePollTimer !== undefined) return;
  badgePollTimer = window.setInterval(() => {
    if (document.visibilityState === "visible") void refreshBadge();
  }, BADGE_POLL_MS);
}

function stopBadgePolling(): void {
  if (badgePollTimer === undefined) return;
  window.clearInterval(badgePollTimer);
  badgePollTimer = undefined;
}

function startConversationPolling(): void {
  if (conversationPollTimer !== undefined) return;
  conversationPollTimer = window.setInterval(() => {
    if (
      conversation.value &&
      document.visibilityState === "visible" &&
      !conversation.value.loading
    ) {
      void pollConversation();
    }
  }, CONVERSATION_POLL_MS);
}

function stopConversationPolling(): void {
  if (conversationPollTimer === undefined) return;
  window.clearInterval(conversationPollTimer);
  conversationPollTimer = undefined;
}

async function pollConversation(): Promise<void> {
  const current = conversation.value;
  if (!current) return;
  try {
    const messages = await getConversation(current.otherId, requireUserId());
    if (conversation.value !== current) return;
    mergeConversationMessages(current, messages);
    await scrollConversationToBottom();
    void refreshBadge();
  } catch {
    // Conversation polling retries on the next interval. A visible error is
    // reserved for the initial history load and an explicit send failure.
  }
}

function mergeConversationMessages(
  current: ConversationState,
  incoming: ConversationMessage[],
): void {
  const seen = new Set(current.messages.map(conversationMessageKey));
  for (const message of incoming) {
    const key = conversationMessageKey(message);
    if (seen.has(key)) continue;
    seen.add(key);
    current.messages.push(message);
  }
  current.messages.sort(
    (left, right) => parseTimestamp(left.created_at) - parseTimestamp(right.created_at),
  );
}

async function scrollConversationToBottom(): Promise<void> {
  await nextTick();
  const box = document.querySelector<HTMLElement>(
    '[data-testid="message-center-conversation-messages"]',
  );
  if (box) box.scrollTop = box.scrollHeight;
}

function handleDocumentClick(event: MouseEvent): void {
  const target = event.target;
  if (!(target instanceof Element)) return;
  if (target.closest(".modal-overlay")) return;
  if (root.value?.contains(target)) return;
  closePanel();
}

function handleDocumentKeydown(event: KeyboardEvent): void {
  if (event.key !== "Escape") return;
  if (detailItem.value) {
    detailItem.value = null;
    return;
  }
  if (conversation.value) {
    closeConversation();
    return;
  }
  closePanel();
}

function handleFocus(): void {
  if (!session.isAuthenticated || !notificationEnabled.value) return;
  void refreshBadge();
  if (panelOpen.value) void loadData();
}

function handleVisibilityChange(): void {
  if (document.visibilityState !== "visible") return;
  if (!session.isAuthenticated || !notificationEnabled.value) return;
  void refreshBadge();
  if (panelOpen.value) void loadData();
  if (conversation.value) void pollConversation();
}

function requireUserId(): string {
  if (!session.user?.id) throw new Error("message center requires an authenticated user");
  return session.user.id;
}

function showFeedback(text: string, kind: FeedbackKind): void {
  feedback.value = { text, kind };
  if (feedbackTimer !== undefined) window.clearTimeout(feedbackTimer);
  feedbackTimer = window.setTimeout(() => {
    feedback.value = null;
    feedbackTimer = undefined;
  }, 4_000);
}

function parseTimestamp(value: string): number {
  if (!value) return 0;
  const timestamp = new Date(value.replace(" ", "T")).getTime();
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function formatTimeAgo(value: string): string {
  const timestamp = parseTimestamp(value);
  if (!timestamp) return "";
  const diff = (Date.now() - timestamp) / 1000;
  if (diff < 60) return "刚刚";
  if (diff < 3_600) return `${Math.floor(diff / 60)}分钟前`;
  if (diff < 86_400) return `${Math.floor(diff / 3_600)}小时前`;
  if (diff < 604_800) return `${Math.floor(diff / 86_400)}天前`;
  return value.slice(0, 10);
}

function formatMessageTime(value: string): string {
  if (!value) return "";
  const date = new Date(value.replace(" ", "T"));
  if (!Number.isFinite(date.getTime())) return "";
  return date.toTimeString().slice(0, 5);
}

function conversationMessageKey(message: ConversationMessage): string {
  if (message.id !== null && message.id !== undefined) return `i:${message.id}`;
  return `c:${message.sender_id}|${message.created_at}|${message.content}`;
}

function iconFor(type: string): string {
  const icons: Record<string, string> = {
    announcement: "fa-bullhorn",
    job: "fa-briefcase",
    interaction: "fa-comments",
    grade: "fa-check-circle",
    farming_reminder: "fa-seedling",
    system: "fa-bell",
  };
  return icons[type] || "fa-bell";
}

function safeType(type: string): string {
  return /^[a-z0-9_-]+$/i.test(type) ? type : "system";
}
</script>

<template>
  <div
    ref="root"
    class="msg-center-wrap message-center"
  >
    <button
      type="button"
      class="icon-btn"
      data-testid="message-center-trigger"
      aria-label="消息通知"
      :aria-expanded="panelOpen"
      @click.stop="togglePanel"
    >
      <i
        class="fas fa-bell"
        aria-hidden="true"
      />
      <span
        v-if="session.isAuthenticated && notificationEnabled && badgeCount > 0"
        class="badge"
        data-testid="message-center-badge"
      >{{ badgeCount }}</span>
    </button>

    <section
      v-if="panelOpen"
      class="msg-dropdown show message-center-panel"
      data-testid="message-center-panel"
      role="dialog"
      aria-label="消息中心"
      @click.stop
    >
      <header class="msg-dropdown-header">
        <h4>消息中心</h4>
        <div
          v-if="session.isAuthenticated && notificationEnabled"
          class="msg-dropdown-actions"
        >
          <button
            v-if="unreadItems.length"
            type="button"
            class="msg-unread-jump"
            data-testid="message-center-unread-jump"
            :aria-label="`查看 ${unreadItems.length} 条未读`"
            @click="jumpToUnread"
          >
            {{ unreadItems.length }}
          </button>
          <button
            type="button"
            data-testid="message-center-mark-all"
            aria-label="全部标记已读"
            title="全部标记已读"
            :disabled="actionBusy"
            @click="markEverythingRead"
          >
            <i
              class="fas fa-check-double"
              aria-hidden="true"
            />
          </button>
          <button
            type="button"
            data-testid="message-center-clear-read"
            aria-label="清除已读"
            title="清除已读"
            :disabled="actionBusy"
            @click="clearRead"
          >
            <i
              class="fas fa-trash-can"
              aria-hidden="true"
            />
          </button>
        </div>
      </header>

      <div
        v-if="!session.isAuthenticated"
        class="msg-empty"
        data-testid="message-center-anonymous"
      >
        <i
          class="fas fa-user-lock"
          aria-hidden="true"
        />
        <p>登录后可查看通知</p>
        <RouterLink
          class="btn btn-text btn-sm"
          :to="loginTarget"
          @click="closePanel"
        >
          去登录
        </RouterLink>
      </div>

      <div
        v-else-if="!notificationEnabled"
        class="msg-empty"
        data-testid="message-center-disabled"
      >
        <i
          class="fas fa-bell-slash"
          aria-hidden="true"
        />
        <p>消息通知已关闭</p>
        <button
          type="button"
          class="btn btn-text btn-sm"
          data-testid="message-center-enable"
          @click="enableNotifications"
        >
          开启通知
        </button>
      </div>

      <template v-else>
        <div class="msg-dropdown-tabs">
          <button
            type="button"
            class="msg-tab-btn"
            :class="{ active: activeTab === 'unread' }"
            data-testid="message-center-tab-unread"
            @click="selectTab('unread')"
          >
            <i
              class="fas fa-bell"
              aria-hidden="true"
            /> 未读
          </button>
          <button
            type="button"
            class="msg-tab-btn"
            :class="{ active: activeTab === 'read' }"
            data-testid="message-center-tab-read"
            @click="selectTab('read')"
          >
            <i
              class="fas fa-envelope-open"
              aria-hidden="true"
            /> 已读
          </button>
          <button
            type="button"
            class="msg-tab-btn"
            :class="{ active: activeTab === 'messages' }"
            data-testid="message-center-tab-messages"
            @click="selectTab('messages')"
          >
            <i
              class="fas fa-envelope"
              aria-hidden="true"
            /> 我的对话
          </button>
        </div>

        <div
          v-if="feedback"
          class="message-center-feedback"
          :class="`is-${feedback.kind}`"
          role="status"
        >
          {{ feedback.text }}
        </div>

        <div
          v-if="activeTab === 'messages'"
          class="msg-dropdown-body"
        >
          <div
            v-if="loading"
            class="msg-empty"
          >
            <i
              class="fas fa-spinner fa-spin"
              aria-hidden="true"
            />
            <p>加载中...</p>
          </div>
          <div
            v-else-if="inboxFailed"
            class="msg-empty"
            data-testid="message-center-conversation-error"
          >
            <i
              class="fas fa-triangle-exclamation"
              aria-hidden="true"
            />
            <p>私信加载失败</p>
            <button
              type="button"
              class="btn btn-text btn-sm"
              @click="loadData"
            >
              重试
            </button>
          </div>
          <div
            v-else-if="!inbox.length"
            class="msg-empty"
          >
            <i
              class="fas fa-envelope-open"
              aria-hidden="true"
            />
            <p>暂无私信</p>
          </div>
          <template v-else>
            <div
              v-for="message in inbox"
              :key="`${message.other_id}:${message.id}`"
              class="msg-item is-clickable"
              :class="{ unread: !message.is_read && !message.is_mine }"
              data-testid="message-center-conversation-item"
              role="button"
              tabindex="0"
              @click="openConversation(message.other_id, message.other_name || '对方')"
              @keydown.enter.prevent="openConversation(message.other_id, message.other_name || '对方')"
              @keydown.space.prevent="openConversation(message.other_id, message.other_name || '对方')"
            >
              <div class="msg-item-avatar">
                <i
                  class="fas fa-user"
                  aria-hidden="true"
                />
              </div>
              <div class="msg-item-text">
                <div class="msg-item-title">
                  {{ message.other_name || message.other_id }}
                </div>
                <div class="msg-item-preview">
                  {{ message.is_mine ? `我：${message.content}` : message.content }}
                </div>
                <div class="msg-item-time">
                  {{ formatTimeAgo(message.created_at) }}
                </div>
              </div>
            </div>
          </template>
        </div>

        <div
          v-else
          class="msg-dropdown-body"
        >
          <div
            v-if="partialFailureText && !allSourcesFailed"
            class="message-center-notice"
            data-testid="message-center-partial"
            role="status"
          >
            <i
              class="fas fa-triangle-exclamation"
              aria-hidden="true"
            />
            {{ partialFailureText }}
          </div>
          <div
            v-if="loading"
            class="msg-empty"
          >
            <i
              class="fas fa-spinner fa-spin"
              aria-hidden="true"
            />
            <p>加载中...</p>
          </div>
          <div
            v-else-if="allSourcesFailed"
            class="msg-empty"
            data-testid="message-center-error"
          >
            <i
              class="fas fa-exclamation-triangle"
              aria-hidden="true"
            />
            <p>消息加载失败</p>
            <button
              type="button"
              class="btn btn-text btn-sm"
              data-testid="message-center-retry"
              @click="loadData"
            >
              重试
            </button>
          </div>
          <div
            v-else-if="!activeItems.length"
            class="msg-empty"
            data-testid="message-center-empty"
          >
            <i
              class="fas fa-envelope-open"
              aria-hidden="true"
            />
            <p>{{ emptyText }}</p>
          </div>
          <template v-else>
            <div
              v-for="item in activeItems"
              :key="item.key"
              class="msg-item is-clickable"
              :class="{ unread: !item.isRead, 'has-reply': item.replyId }"
              data-testid="message-center-item"
              :data-unread="item.isRead ? 'false' : 'true'"
              role="button"
              tabindex="0"
              @click="handleItem(item)"
              @keydown.enter.prevent="handleItem(item)"
              @keydown.space.prevent="handleItem(item)"
            >
              <div
                class="msg-item-icon"
                :class="`type-${safeType(item.type)}`"
              >
                <i
                  class="fas"
                  :class="iconFor(item.type)"
                  aria-hidden="true"
                />
              </div>
              <div class="msg-item-text">
                <div class="msg-item-title">
                  {{ item.title }}
                  <span
                    class="msg-tag"
                    :class="`msg-tag-${safeType(item.type)}`"
                  >{{ item.tag }}</span>
                </div>
                <div class="msg-item-preview">
                  {{ item.preview }}
                </div>
                <div class="msg-item-time">
                  {{ formatTimeAgo(item.time) }}
                </div>
                <span
                  v-if="item.replyId"
                  class="msg-reply-btn"
                >回复</span>
              </div>
            </div>
          </template>
        </div>

        <footer class="msg-dropdown-footer">
          <button
            type="button"
            data-testid="message-center-disable"
            aria-label="关闭消息通知"
            @click="disableNotifications"
          >
            <i
              class="fas fa-bell-slash"
              aria-hidden="true"
            />
            关闭消息通知
          </button>
        </footer>
      </template>
    </section>

    <Teleport to="body">
      <div
        v-if="detailItem"
        class="modal-overlay detail-modal"
        @click.self="detailItem = null"
      >
        <div
          class="modal-content"
          data-testid="message-center-detail"
          role="dialog"
          aria-modal="true"
          :aria-label="detailItem.title"
        >
          <div class="modal-header">
            <h3>{{ detailItem.title }}</h3>
            <button
              type="button"
              class="modal-close"
              aria-label="关闭"
              @click="detailItem = null"
            >
              <i
                class="fas fa-times"
                aria-hidden="true"
              />
            </button>
          </div>
          <div class="modal-body">
            <div class="notif-detail">
              <span
                class="msg-tag"
                :class="`msg-tag-${safeType(detailItem.type)}`"
              >{{ detailItem.tag }}</span>
              <div class="notif-detail-body">
                {{ detailItem.preview || "暂无正文" }}
              </div>
              <div
                v-if="detailItem.time"
                class="notif-detail-time"
              >
                <i
                  class="far fa-clock"
                  aria-hidden="true"
                />
                {{ detailItem.time }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="conversation"
        class="modal-overlay detail-modal"
        @click.self="closeConversation"
      >
        <div
          class="modal-content conv-modal"
          role="dialog"
          aria-modal="true"
          :aria-label="`与 ${conversation.otherName} 的对话`"
        >
          <div class="modal-header">
            <h3>与 {{ conversation.otherName }} 的对话</h3>
            <button
              type="button"
              class="modal-close"
              aria-label="关闭"
              @click="closeConversation"
            >
              <i
                class="fas fa-times"
                aria-hidden="true"
              />
            </button>
          </div>
          <div class="modal-body">
            <div class="conversation-modal">
              <div
                class="conversation-messages"
                data-testid="message-center-conversation-messages"
              >
                <div
                  v-if="conversation.loading"
                  class="msg-empty"
                >
                  <i
                    class="fas fa-spinner fa-spin"
                    aria-hidden="true"
                  />
                  <p>加载中...</p>
                </div>
                <div
                  v-else-if="conversation.loadError"
                  class="msg-empty"
                >
                  <i
                    class="fas fa-triangle-exclamation"
                    aria-hidden="true"
                  />
                  <p>{{ conversation.loadError }}</p>
                  <button
                    type="button"
                    class="btn btn-text btn-sm"
                    @click="loadConversation"
                  >
                    重试
                  </button>
                </div>
                <div
                  v-else-if="!conversation.messages.length"
                  class="msg-empty"
                >
                  <i
                    class="fas fa-comments"
                    aria-hidden="true"
                  />
                  <p>暂无消息，发送第一条吧</p>
                </div>
                <template v-else>
                  <div
                    v-for="message in conversation.messages"
                    :key="conversationMessageKey(message)"
                    class="msg-bubble"
                    :class="message.sender_id === session.user?.id ? 'mine' : 'theirs'"
                    data-testid="message-center-bubble"
                  >
                    <div class="msg-bubble-content">
                      {{ message.content }}
                    </div>
                    <div class="msg-bubble-time">
                      {{ formatMessageTime(message.created_at) }}
                    </div>
                  </div>
                </template>
              </div>
              <div class="conversation-input">
                <input
                  v-model="replyDraft"
                  type="text"
                  maxlength="500"
                  autocomplete="off"
                  aria-label="输入消息"
                  placeholder="输入消息..."
                  @keydown.enter.prevent="sendConversationReply"
                >
                <button
                  type="button"
                  class="conversation-send"
                  aria-label="发送消息"
                  :disabled="conversation.sending || !replyDraft.trim()"
                  @click="sendConversationReply"
                >
                  <i
                    class="fas fa-paper-plane"
                    aria-hidden="true"
                  />
                </button>
              </div>
              <p
                v-if="conversation.sendError"
                class="message-center-send-error"
                role="alert"
              >
                {{ conversation.sendError }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.message-center-panel {
  width: min(380px, calc(100vw - 24px));
}

.message-center-feedback,
.message-center-notice {
  margin: 8px 12px 0;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 0.76rem;
  line-height: 1.45;
}

.message-center-feedback.is-success {
  background: rgba(31, 94, 67, 0.1);
  color: var(--accent-blue);
}

.message-center-feedback.is-error {
  background: rgba(239, 68, 68, 0.1);
  color: #b3382f;
}

.message-center-feedback.is-info,
.message-center-notice {
  background: rgba(217, 162, 39, 0.12);
  color: #7a5600;
}

.message-center-notice i {
  margin-right: 6px;
}

.msg-item-icon.type-job {
  background: linear-gradient(135deg, #ba7517, #d9a227);
}

.msg-item-icon.type-interaction {
  background: linear-gradient(135deg, #0f6e56, #2f9e7f);
}

.msg-tag-job,
.msg-tag-grade {
  background: #faeeda;
  color: #ba7517;
}

.msg-tag-interaction {
  background: #e1f5ee;
  color: #0f6e56;
}

.msg-tag-system,
.msg-tag-farming_reminder {
  background: #eef2f6;
  color: #4b5563;
}

.message-center-send-error {
  margin: 0;
  padding: 0 16px 10px;
  color: #b3382f;
  font-size: 0.78rem;
}

.msg-dropdown-actions button:disabled,
.conversation-send:disabled {
  cursor: wait;
  opacity: 0.55;
}

[data-theme="dark"] .message-center-feedback.is-error,
[data-theme="dark"] .message-center-send-error {
  color: #f28b82;
}

[data-theme="dark"] .message-center-notice {
  color: #efc75e;
}
</style>
