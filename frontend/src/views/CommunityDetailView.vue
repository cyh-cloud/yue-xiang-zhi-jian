<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { ApiError } from "@/api/client";
import {
  COMMENT_CONTENT_MAX_LEN,
  createComment,
  getDiscussion,
  type Discussion,
  type DiscussionComment,
} from "@/api/community";
import { useSessionStore } from "@/stores/session";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();

const discussion = ref<Discussion | null>(null);
const comments = ref<DiscussionComment[]>([]);
const loading = ref(true);
const loadError = ref("");
const notFound = ref(false);
const commentContent = ref("");
const commentSubmitting = ref(false);
const commentFeedback = ref<{
  kind: "success" | "error";
  text: string;
} | null>(null);
const commentInput = ref<HTMLTextAreaElement | null>(null);

const discussionId = computed(() => {
  const value = Number(route.params.id);
  return Number.isInteger(value) && value > 0 ? value : 0;
});

const categoryLabel = computed(() => {
  const labels: Record<string, string> = {
    general: "综合",
    agriculture: "农业",
    ecommerce: "电商",
    crafts: "手工",
  };
  return discussion.value
    ? labels[discussion.value.category] ?? discussion.value.category
    : "";
});

watch(
  () => route.params.id,
  () => {
    void loadDiscussion();
  },
);

watch(
  [discussion, () => session.isAuthenticated, () => route.query.action],
  async ([current, authenticated, action]) => {
    if (current && authenticated && action === "comment") {
      await nextTick();
      commentInput.value?.focus();
    }
  },
  { flush: "post" },
);

onMounted(() => {
  void loadDiscussion();
});

async function loadDiscussion(): Promise<void> {
  if (!discussionId.value) {
    notFound.value = true;
    loading.value = false;
    return;
  }
  loading.value = true;
  loadError.value = "";
  notFound.value = false;
  try {
    const response = await getDiscussion(discussionId.value);
    discussion.value = response.discussion;
    comments.value = response.comments;
  } catch (error) {
    discussion.value = null;
    comments.value = [];
    if (error instanceof ApiError && error.status === 404) {
      notFound.value = true;
    } else {
      loadError.value =
        error instanceof ApiError && error.status !== 0
          ? error.message
          : "讨论加载失败，请检查网络后重试";
    }
  } finally {
    loading.value = false;
  }
}

async function goToLogin(): Promise<void> {
  await router.push({
    path: "/login",
    query: {
      redirect: `/community/${discussionId.value}?action=comment`,
    },
  });
}

async function submitComment(): Promise<void> {
  commentFeedback.value = null;
  const cleanContent = commentContent.value.trim();
  if (!cleanContent) {
    commentFeedback.value = { kind: "error", text: "请输入评论内容" };
    return;
  }
  if (cleanContent.length > COMMENT_CONTENT_MAX_LEN) {
    commentFeedback.value = {
      kind: "error",
      text: `评论不能超过 ${COMMENT_CONTENT_MAX_LEN} 字`,
    };
    return;
  }
  if (!session.isAuthenticated) {
    await goToLogin();
    return;
  }

  commentSubmitting.value = true;
  try {
    const response = await createComment({
      target_type: "discussion",
      target_id: discussionId.value,
      content: cleanContent,
    });
    commentContent.value = "";
    commentFeedback.value = {
      kind: "success",
      text: response.message || "评论成功",
    };
    await router.replace({ path: `/community/${discussionId.value}` });
    await loadDiscussion();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      session.clearSession();
      await goToLogin();
      return;
    }
    commentFeedback.value = {
      kind: "error",
      text:
        error instanceof ApiError && error.status !== 0
          ? error.message
          : "网络连接失败，请稍后重试",
    };
  } finally {
    commentSubmitting.value = false;
  }
}

function formatTime(value: string): string {
  return value ? value.slice(0, 16) : "";
}
</script>

<template>
  <section
    id="community-detail-tab"
    class="tab-content active community-view community-detail-view"
    aria-labelledby="community-detail-title"
  >
    <div class="container community-container">
      <RouterLink
        class="community-back"
        to="/community"
      >
        <i
          class="fas fa-arrow-left"
          aria-hidden="true"
        />
        返回社区讨论
      </RouterLink>

      <div
        v-if="loading"
        class="card-section community-state"
        role="status"
      >
        <i
          class="fas fa-spinner fa-spin"
          aria-hidden="true"
        />
        正在加载讨论...
      </div>
      <div
        v-else-if="notFound"
        class="card-section community-state"
        role="status"
        data-testid="community-not-found"
      >
        <i
          class="fas fa-comment-slash"
          aria-hidden="true"
        />
        <p>帖子不存在或已被移除</p>
        <RouterLink
          class="btn btn-outline btn-sm"
          to="/community"
        >
          返回讨论列表
        </RouterLink>
      </div>
      <div
        v-else-if="loadError"
        class="card-section community-state community-state-error"
        role="alert"
        data-testid="community-load-error"
      >
        <i
          class="fas fa-exclamation-circle"
          aria-hidden="true"
        />
        <p>{{ loadError }}</p>
        <button
          type="button"
          class="btn btn-outline btn-sm"
          @click="loadDiscussion"
        >
          <i
            class="fas fa-redo"
            aria-hidden="true"
          />
          重试
        </button>
      </div>
      <template v-else-if="discussion">
        <article
          class="card-section community-detail"
          data-testid="community-detail"
        >
          <div class="community-card-head">
            <span class="community-tag">{{ categoryLabel }}</span>
            <span
              v-if="discussion.is_pinned"
              class="community-pinned"
            >
              <i
                class="fas fa-thumbtack"
                aria-hidden="true"
              />
              置顶
            </span>
          </div>
          <h1
            id="community-detail-title"
            class="community-detail-title"
          >
            {{ discussion.title }}
          </h1>
          <div class="community-detail-meta">
            <span>{{ discussion.user_name || discussion.user_id }}</span>
            <span>{{ formatTime(discussion.created_at) }}</span>
            <span>
              <i
                class="far fa-eye"
                aria-hidden="true"
              />
              {{ discussion.view_count }}
            </span>
            <span>
              <i
                class="far fa-comment"
                aria-hidden="true"
              />
              {{ discussion.comment_count }}
            </span>
          </div>
          <div class="community-detail-content">
            {{ discussion.content }}
          </div>
        </article>

        <section
          class="card-section community-comments"
          aria-labelledby="community-comments-title"
        >
          <div class="community-comments-head">
            <h2 id="community-comments-title">
              评论（{{ comments.length }}）
            </h2>
            <span>请友善交流，不发布个人敏感信息</span>
          </div>

          <div
            v-if="commentFeedback"
            class="community-feedback"
            :class="`is-${commentFeedback.kind}`"
            :role="commentFeedback.kind === 'error' ? 'alert' : 'status'"
            data-testid="community-comment-feedback"
          >
            {{ commentFeedback.text }}
          </div>

          <form
            v-if="session.isAuthenticated"
            class="community-comment-form"
            @submit.prevent="submitComment"
          >
            <label for="community-comment-input">评论内容</label>
            <textarea
              id="community-comment-input"
              ref="commentInput"
              v-model="commentContent"
              rows="3"
              placeholder="写下你的看法或补充..."
            />
            <div class="community-comment-actions">
              <span class="community-counter">
                {{ commentContent.length }}/{{ COMMENT_CONTENT_MAX_LEN }}
              </span>
              <button
                type="submit"
                class="btn btn-primary btn-sm"
                data-testid="community-comment-submit"
                :disabled="commentSubmitting"
              >
                {{ commentSubmitting ? "正在发表..." : "发表评论" }}
              </button>
            </div>
          </form>
          <div
            v-else
            class="community-login-prompt"
            data-testid="community-login-prompt"
          >
            <p>登录后即可参与讨论</p>
            <button
              type="button"
              class="btn btn-primary btn-sm"
              @click="goToLogin"
            >
              登录后评论
            </button>
          </div>

          <div
            v-if="comments.length === 0"
            class="community-comments-empty"
            role="status"
          >
            暂无评论，来说两句吧
          </div>
          <div
            v-else
            class="community-comment-list"
          >
            <article
              v-for="comment in comments"
              :key="comment.id"
              class="comment-item community-comment"
              data-testid="community-comment"
            >
              <div class="community-comment-head">
                <strong>{{ comment.user_name || comment.user_id }}</strong>
                <span>{{ formatTime(comment.created_at) }}</span>
              </div>
              <p>{{ comment.content }}</p>
            </article>
          </div>
        </section>
      </template>
    </div>
  </section>
</template>

<style src="@/styles/community.css"></style>
