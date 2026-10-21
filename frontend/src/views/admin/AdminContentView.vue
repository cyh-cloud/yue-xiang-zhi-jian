<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  deleteAdminComment,
  deleteAdminDiscussion,
  getAdminModerationContent,
  type ModerationComment,
  type ModerationDiscussion,
} from "@/api/admin";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

type FeedbackKind = "info" | "success" | "error";
type DeleteTarget =
  | { kind: "discussion"; discussion: ModerationDiscussion }
  | { kind: "comment"; comment: ModerationComment };

const discussions = ref<ModerationDiscussion[]>([]);
const comments = ref<ModerationComment[]>([]);
const loading = ref(true);
const loadError = ref("");
const feedback = ref<{ kind: FeedbackKind; message: string } | null>(null);
const deleteTarget = ref<DeleteTarget | null>(null);
const deleting = ref(false);

const isEmpty = computed(
  () => !discussions.value.length && !comments.value.length,
);
const deleteTitle = computed(() => {
  if (deleteTarget.value?.kind === "discussion") return "删除讨论帖";
  return "删除评论";
});
const deleteCopy = computed(() => {
  const target = deleteTarget.value;
  if (!target) return "";
  if (target.kind === "discussion") {
    return `确定删除「${target.discussion.title}」？该帖会立即从公开讨论列表消失。`;
  }
  return `确定删除「${target.comment.content}」？该评论会立即从公开评论列表消失，讨论帖评论数同步减少。`;
});

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

async function loadContent(): Promise<void> {
  loading.value = true;
  loadError.value = "";
  try {
    const response = await getAdminModerationContent();
    discussions.value = response.discussions;
    comments.value = response.comments;
  } catch (error) {
    discussions.value = [];
    comments.value = [];
    loadError.value = errorMessage(error, "内容监管列表加载失败");
  } finally {
    loading.value = false;
  }
}

function askDeleteDiscussion(discussion: ModerationDiscussion): void {
  deleteTarget.value = { kind: "discussion", discussion };
}

function askDeleteComment(comment: ModerationComment): void {
  deleteTarget.value = { kind: "comment", comment };
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
    const response =
      target.kind === "discussion"
        ? await deleteAdminDiscussion(target.discussion.id)
        : await deleteAdminComment(target.comment.id);
    deleteTarget.value = null;
    feedback.value = {
      kind: "success",
      message: response.message || "删除成功",
    };
    await loadContent();
  } catch (error) {
    feedback.value = {
      kind: "error",
      message: errorMessage(error, "删除失败"),
    };
  } finally {
    deleting.value = false;
  }
}

onMounted(loadContent);
</script>

<template>
  <section class="backoffice-page">
    <header class="backoffice-page-header">
      <div>
        <p>平台治理</p>
        <h1 data-testid="backoffice-page-title">
          内容监管
        </h1>
        <span>查看并删除违规讨论帖与评论，删除结果立即影响公开页面。</span>
      </div>
      <button
        type="button"
        class="backoffice-button is-secondary"
        :disabled="loading"
        @click="loadContent"
      >
        <i
          class="fas fa-rotate"
          :class="{ 'fa-spin': loading }"
          aria-hidden="true"
        />
        刷新内容
      </button>
    </header>

    <BackofficeFeedback
      v-if="feedback"
      :kind="feedback.kind"
      :message="feedback.message"
      testid="admin-content-feedback"
    />

    <BackofficeState
      v-if="loading"
      kind="loading"
      title="正在读取待监管内容"
    />
    <div
      v-else-if="loadError"
      data-testid="admin-content-error"
    >
      <BackofficeState
        kind="error"
        title="内容监管列表加载失败"
        :detail="loadError"
      >
        <button
          type="button"
          class="backoffice-button"
          @click="loadContent"
        >
          重试
        </button>
      </BackofficeState>
    </div>
    <div
      v-else-if="isEmpty"
      data-testid="admin-content-empty"
    >
      <BackofficeState
        kind="empty"
        title="暂无待监管内容"
        detail="当前没有公开可见的讨论帖或评论。"
      />
    </div>

    <template v-else>
      <BackofficeCard
        title="讨论帖"
        :description="`共 ${discussions.length} 条公开讨论帖`"
        flush
      >
        <BackofficeState
          v-if="!discussions.length"
          kind="empty"
          title="暂无讨论帖"
        />
        <div
          v-else
          class="backoffice-table-wrap"
        >
          <table class="backoffice-table">
            <thead>
              <tr>
                <th>标题</th>
                <th>作者</th>
                <th>评论数</th>
                <th>发布时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="discussion in discussions"
                :key="discussion.id"
                data-testid="admin-content-discussion-row"
                :data-discussion-id="discussion.id"
              >
                <td>
                  <strong>{{ discussion.title }}</strong>
                  <small>{{ discussion.content }}</small>
                </td>
                <td>{{ discussion.user_name || discussion.user_id }}</td>
                <td>{{ discussion.comment_count }}</td>
                <td>{{ discussion.created_at }}</td>
                <td>
                  <button
                    type="button"
                    class="backoffice-button is-small is-danger"
                    @click="askDeleteDiscussion(discussion)"
                  >
                    删除帖子
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </BackofficeCard>

      <BackofficeCard
        title="评论"
        :description="`共 ${comments.length} 条公开评论`"
        flush
      >
        <BackofficeState
          v-if="!comments.length"
          kind="empty"
          title="暂无评论"
        />
        <div
          v-else
          class="backoffice-table-wrap"
        >
          <table class="backoffice-table">
            <thead>
              <tr>
                <th>评论内容</th>
                <th>所属讨论帖</th>
                <th>作者</th>
                <th>发布时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="comment in comments"
                :key="comment.id"
                data-testid="admin-content-comment-row"
                :data-comment-id="comment.id"
              >
                <td>
                  <strong>{{ comment.content }}</strong>
                  <small>#{{ comment.id }}</small>
                </td>
                <td>{{ comment.target_title || `${comment.target_type} #${comment.target_id}` }}</td>
                <td>{{ comment.user_name || comment.user_id }}</td>
                <td>{{ comment.created_at }}</td>
                <td>
                  <button
                    type="button"
                    class="backoffice-button is-small is-danger"
                    @click="askDeleteComment(comment)"
                  >
                    删除评论
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </BackofficeCard>
    </template>

    <Teleport to="body">
      <div
        v-if="deleteTarget"
        class="backoffice-modal-overlay"
        @click.self="closeDelete"
      >
        <div
          class="backoffice-modal is-confirm"
          data-testid="admin-content-delete-dialog"
          role="dialog"
          aria-modal="true"
          :aria-label="deleteTitle"
        >
          <header class="backoffice-modal-head">
            <div>
              <p>安全确认</p>
              <h2>{{ deleteTitle }}</h2>
            </div>
          </header>
          <div class="backoffice-modal-body">
            <p class="backoffice-confirm-copy">
              {{ deleteCopy }}
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

<style src="./admin.css"></style>
