<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  createAdminAnnouncement,
  deleteAdminAnnouncement,
  getAdminAnnouncements,
  type AdminAnnouncement,
} from "@/api/admin";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

type FeedbackKind = "info" | "success" | "error";

const announcements = ref<AdminAnnouncement[]>([]);
const loading = ref(true);
const loadError = ref("");
const feedback = ref<{ kind: FeedbackKind; message: string } | null>(null);
const title = ref("");
const content = ref("");
const pinned = ref(false);
const publishing = ref(false);
const publishError = ref("");
const deleteTarget = ref<AdminAnnouncement | null>(null);
const deleting = ref(false);

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

async function loadAnnouncements(): Promise<void> {
  loading.value = true;
  loadError.value = "";
  try {
    announcements.value = (await getAdminAnnouncements()).filter(
      (announcement) => announcement.is_active,
    );
  } catch (error) {
    announcements.value = [];
    loadError.value = errorMessage(error, "系统公告加载失败");
  } finally {
    loading.value = false;
  }
}

async function publish(): Promise<void> {
  const nextTitle = title.value.trim();
  const nextContent = content.value.trim();
  publishError.value = "";
  if (!nextTitle || !nextContent) {
    publishError.value = "请填写公告标题和内容";
    return;
  }
  publishing.value = true;
  try {
    const response = await createAdminAnnouncement({
      title: nextTitle,
      content: nextContent,
      is_pinned: pinned.value,
    });
    feedback.value = {
      kind: "success",
      message: response.message || "发布成功",
    };
    title.value = "";
    content.value = "";
    pinned.value = false;
    await loadAnnouncements();
  } catch (error) {
    publishError.value = errorMessage(error, "公告发布失败");
  } finally {
    publishing.value = false;
  }
}

function askDelete(announcement: AdminAnnouncement): void {
  deleteTarget.value = announcement;
}

function closeDelete(): void {
  if (deleting.value) return;
  deleteTarget.value = null;
}

async function confirmDelete(): Promise<void> {
  const target = deleteTarget.value;
  if (!target) return;
  deleting.value = true;
  try {
    const response = await deleteAdminAnnouncement(target.id);
    deleteTarget.value = null;
    feedback.value = {
      kind: "success",
      message: response.message || "已删除",
    };
    await loadAnnouncements();
  } catch (error) {
    feedback.value = {
      kind: "error",
      message: errorMessage(error, "公告删除失败"),
    };
  } finally {
    deleting.value = false;
  }
}

onMounted(loadAnnouncements);
</script>

<template>
  <section class="bo-page">
    <header class="bo-page-header">
      <div>
        <p>平台治理</p>
        <h1 data-testid="backoffice-page-title">
          系统公告
        </h1>
        <span>发布后立即进入所有登录用户的共享消息中心。</span>
      </div>
      <button
        type="button"
        class="bo-button is-secondary"
        :disabled="loading"
        @click="loadAnnouncements"
      >
        <i
          class="fas fa-rotate"
          :class="{ 'fa-spin': loading }"
          aria-hidden="true"
        />
        刷新公告
      </button>
    </header>

    <BackofficeFeedback
      v-if="feedback"
      :kind="feedback.kind"
      :message="feedback.message"
      testid="admin-announcements-feedback"
    />

    <BackofficeCard
      title="发布公告"
      description="公告由共享消息中心读取，不创建第二套消息存储。"
    >
      <form
        class="admin-announcement-form"
        @submit.prevent="publish"
      >
        <BackofficeFeedback
          v-if="publishError"
          kind="error"
          :message="publishError"
        />
        <label class="bo-field">
          <span>公告标题</span>
          <input
            v-model="title"
            required
            autocomplete="off"
          >
        </label>
        <label class="bo-field">
          <span>公告内容</span>
          <textarea
            v-model="content"
            rows="4"
            required
          />
        </label>
        <div class="admin-announcement-form-foot">
          <label class="admin-announcement-check">
            <input
              v-model="pinned"
              type="checkbox"
            >
            置顶公告
          </label>
          <button
            type="submit"
            class="bo-button"
            :disabled="publishing"
          >
            {{ publishing ? "发布中..." : "发布公告" }}
          </button>
        </div>
      </form>
    </BackofficeCard>

    <BackofficeCard
      title="公告记录"
      description="删除后公告立即从共享消息中心消失。"
      flush
    >
      <BackofficeState
        v-if="loading"
        kind="loading"
        title="正在加载系统公告"
      />
      <div
        v-else-if="loadError"
        data-testid="admin-announcements-error"
      >
        <BackofficeState
          kind="error"
          title="系统公告加载失败"
          :detail="loadError"
        >
          <button
            type="button"
            class="bo-button"
            @click="loadAnnouncements"
          >
            重试
          </button>
        </BackofficeState>
      </div>
      <div
        v-else-if="!announcements.length"
        data-testid="admin-announcements-empty"
      >
        <BackofficeState
          kind="empty"
          title="暂无系统公告"
          detail="发布第一条公告后，所有登录用户会在共享消息中心看到它。"
        />
      </div>
      <div
        v-else
        class="admin-announcement-list"
      >
        <article
          v-for="announcement in announcements"
          :key="announcement.id"
          class="admin-announcement-row"
          data-testid="admin-announcement-row"
          :data-announcement-id="announcement.id"
        >
          <header>
            <div>
              <span
                v-if="announcement.is_pinned"
                class="admin-announcement-pin"
              >
                置顶
              </span>
            </div>
            <time>{{ announcement.created_at }}</time>
          </header>
          <h2>{{ announcement.title }}</h2>
          <p>{{ announcement.content }}</p>
          <footer>
            <small>发布人 {{ announcement.created_by || "未知" }}</small>
            <button
              type="button"
              class="bo-button is-small is-danger"
              @click="askDelete(announcement)"
            >
              删除
            </button>
          </footer>
        </article>
      </div>
    </BackofficeCard>

    <Teleport to="body">
      <div
        v-if="deleteTarget"
        class="bo-modal-overlay"
        @click.self="closeDelete"
      >
        <div
          class="bo-modal is-confirm"
          data-testid="admin-announcement-delete-dialog"
          role="dialog"
          aria-modal="true"
          aria-label="删除系统公告"
        >
          <header class="bo-modal-head">
            <div>
              <p>安全确认</p>
              <h2>删除系统公告</h2>
            </div>
          </header>
          <div class="bo-modal-body">
            <p class="bo-confirm-copy">
              确定删除「{{ deleteTarget.title }}」？删除后所有用户的消息中心会立即停止展示这条公告。
            </p>
          </div>
          <footer class="bo-modal-actions">
            <button
              type="button"
              class="bo-button is-secondary"
              :disabled="deleting"
              @click="closeDelete"
            >
              取消
            </button>
            <button
              type="button"
              class="bo-button is-danger"
              :disabled="deleting"
              @click="confirmDelete"
            >
              {{ deleting ? "删除中..." : "确认删除" }}
            </button>
          </footer>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.admin-announcement-form {
  display: grid;
  gap: 12px;
}

.admin-announcement-form-foot,
.admin-announcement-row header,
.admin-announcement-row footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.admin-announcement-check {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--bo-muted);
  font-size: 0.84rem;
}

.admin-announcement-list {
  display: grid;
}

.admin-announcement-row {
  padding: 16px;
  border-bottom: 1px solid var(--bo-card-border);
}

.admin-announcement-row:last-child {
  border-bottom: 0;
}

.admin-announcement-row h2 {
  margin: 10px 0 6px;
  font-size: 0.98rem;
}

.admin-announcement-row p {
  margin: 0;
  color: var(--bo-muted);
  font-size: 0.84rem;
  line-height: 1.7;
  white-space: pre-wrap;
}

.admin-announcement-row time,
.admin-announcement-row small {
  color: var(--bo-muted);
  font-size: 0.72rem;
}

.admin-announcement-row footer {
  margin-top: 12px;
}

.admin-announcement-pin {
  display: inline-flex;
  margin-right: 6px;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
}

.admin-announcement-pin {
  background: #fff2cf;
  color: #835d00;
}
</style>
