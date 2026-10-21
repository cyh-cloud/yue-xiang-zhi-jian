<script setup lang="ts">
import { onMounted, ref } from "vue";

import { ApiError } from "@/api/client";
import {
  createTeacherAnnouncement,
  deleteTeacherAnnouncement,
  getTeacherAnnouncements,
  type TeacherAnnouncement,
} from "@/api/teacher";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

const announcements = ref<TeacherAnnouncement[]>([]);
const loading = ref(true);
const loadError = ref("");
const feedback = ref<{ kind: "success" | "error"; message: string } | null>(
  null,
);
const editorOpen = ref(false);
const editorSaving = ref(false);
const editorError = ref("");
const deleteTarget = ref<TeacherAnnouncement | null>(null);
const deleting = ref(false);
const form = ref({
  title: "",
  content: "",
  category: "通知",
  pinned: false,
});

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

async function loadAnnouncements(): Promise<void> {
  loading.value = true;
  loadError.value = "";
  try {
    announcements.value = await getTeacherAnnouncements();
  } catch (error) {
    announcements.value = [];
    loadError.value = errorMessage(error, "通知公告加载失败");
  } finally {
    loading.value = false;
  }
}

function openEditor(): void {
  form.value = {
    title: "",
    content: "",
    category: "通知",
    pinned: false,
  };
  editorError.value = "";
  editorOpen.value = true;
}

function closeEditor(): void {
  if (editorSaving.value) return;
  editorOpen.value = false;
}

async function publish(): Promise<void> {
  editorError.value = "";
  if (!form.value.title.trim() || !form.value.content.trim()) {
    editorError.value = "请填写标题和内容";
    return;
  }
  editorSaving.value = true;
  try {
    const response = await createTeacherAnnouncement({
      title: form.value.title.trim(),
      content: form.value.content.trim(),
      category: form.value.category,
      pinned: form.value.pinned,
    });
    editorOpen.value = false;
    feedback.value = {
      kind: "success",
      message: response.message || "发布成功",
    };
    await loadAnnouncements();
  } catch (error) {
    editorError.value = errorMessage(error, "发布失败，请稍后重试");
  } finally {
    editorSaving.value = false;
  }
}

function askDelete(announcement: TeacherAnnouncement): void {
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
    const response = await deleteTeacherAnnouncement(target.id);
    deleteTarget.value = null;
    feedback.value = {
      kind: "success",
      message: response.message || "删除成功",
    };
    await loadAnnouncements();
  } catch (error) {
    feedback.value = {
      kind: "error",
      message: errorMessage(error, "删除失败，请稍后重试"),
    };
  } finally {
    deleting.value = false;
  }
}

onMounted(loadAnnouncements);
</script>

<template>
  <section class="backoffice-page">
    <header class="backoffice-page-header">
      <div>
        <p>教学工作</p>
        <h1>通知公告</h1>
        <span>发布后，已关联平台账号的学员会在共享消息中心收到通知。</span>
      </div>
      <button
        type="button"
        class="backoffice-button"
        @click="openEditor"
      >
        <i
          class="fas fa-plus"
          aria-hidden="true"
        />
        发布通知
      </button>
    </header>

    <BackofficeFeedback
      v-if="feedback"
      :kind="feedback.kind"
      :message="feedback.message"
      testid="teacher-announcements-feedback"
    />

    <BackofficeState
      v-if="loading"
      kind="loading"
      title="正在加载通知公告"
    />
    <BackofficeState
      v-else-if="loadError"
      kind="error"
      title="通知公告加载失败"
      :detail="loadError"
    >
      <button
        type="button"
        class="backoffice-button"
        @click="loadAnnouncements"
      >
        重试
      </button>
    </BackofficeState>
    <BackofficeState
      v-else-if="!announcements.length"
      kind="empty"
      title="暂无通知公告"
      detail="发布一条通知，让学员及时收到教学信息。"
    />
    <div
      v-else
      class="teacher-announcement-list"
    >
      <article
        v-for="announcement in announcements"
        :key="announcement.id"
        class="backoffice-card teacher-announcement-card"
        :class="{ 'is-pinned': announcement.pinned }"
        data-testid="teacher-announcement-card"
        :data-announcement-id="announcement.id"
      >
        <header class="teacher-announcement-head">
          <div class="teacher-announcement-meta">
            <span class="teacher-announcement-category">
              {{ announcement.category }}
            </span>
            <span
              v-if="announcement.pinned"
              class="teacher-announcement-pin"
            >
              置顶
            </span>
            <time>{{ announcement.created_at }}</time>
          </div>
          <button
            type="button"
            class="backoffice-button is-small is-danger"
            data-testid="teacher-announcement-delete"
            @click="askDelete(announcement)"
          >
            删除
          </button>
        </header>
        <h2>{{ announcement.title }}</h2>
        <p>{{ announcement.content }}</p>
      </article>
    </div>

    <Teleport to="body">
      <div
        v-if="editorOpen"
        class="backoffice-modal-overlay"
        @click.self="closeEditor"
      >
        <form
          class="backoffice-modal"
          data-testid="teacher-announcement-editor"
          role="dialog"
          aria-modal="true"
          aria-label="发布通知"
          @submit.prevent="publish"
        >
          <header class="backoffice-modal-head">
            <div>
              <p>通知公告</p>
              <h2>发布通知</h2>
            </div>
            <button
              type="button"
              class="backoffice-icon-button"
              aria-label="关闭"
              @click="closeEditor"
            >
              <i
                class="fas fa-xmark"
                aria-hidden="true"
              />
            </button>
          </header>
          <div class="backoffice-modal-body">
            <BackofficeFeedback
              v-if="editorError"
              kind="error"
              :message="editorError"
              testid="teacher-announcement-editor-error"
            />
            <label class="backoffice-field">
              <span>标题</span>
              <input
                v-model="form.title"
                required
                autocomplete="off"
              >
            </label>
            <label class="backoffice-field">
              <span>分类</span>
              <select v-model="form.category">
                <option value="通知">
                  通知
                </option>
                <option value="公告">
                  公告
                </option>
                <option value="紧急">
                  紧急
                </option>
              </select>
            </label>
            <label class="backoffice-field">
              <span>内容</span>
              <textarea
                v-model="form.content"
                rows="5"
                required
              />
            </label>
            <label class="teacher-checkbox">
              <input
                v-model="form.pinned"
                type="checkbox"
              >
              置顶显示
            </label>
          </div>
          <footer class="backoffice-modal-actions">
            <button
              type="button"
              class="backoffice-button is-secondary"
              :disabled="editorSaving"
              @click="closeEditor"
            >
              取消
            </button>
            <button
              type="submit"
              class="backoffice-button"
              :disabled="editorSaving"
            >
              {{ editorSaving ? "发布中..." : "发布" }}
            </button>
          </footer>
        </form>
      </div>

      <div
        v-if="deleteTarget"
        class="backoffice-modal-overlay"
        @click.self="closeDelete"
      >
        <div
          class="backoffice-modal is-confirm"
          data-testid="teacher-confirm-delete"
          role="dialog"
          aria-modal="true"
          aria-label="确认删除通知"
        >
          <header class="backoffice-modal-head">
            <div>
              <p>确认删除</p>
              <h2>删除通知</h2>
            </div>
          </header>
          <div class="backoffice-modal-body">
            <p class="backoffice-confirm-copy">
              确定删除通知「{{ deleteTarget.title }}」吗？删除后学员端将不再展示这条公告。
            </p>
          </div>
          <footer class="backoffice-modal-actions">
            <button
              type="button"
              class="backoffice-button is-secondary"
              :disabled="deleting"
              @click="closeDelete"
            >
              取消
            </button>
            <button
              type="button"
              class="backoffice-button is-danger"
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

<style src="./teacher.css"></style>
