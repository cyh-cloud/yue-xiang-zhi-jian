<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { ApiError } from "@/api/client";
import {
  createDiscussion,
  DISCUSSION_CONTENT_MAX_LEN,
  DISCUSSION_PAGE_SIZE,
  DISCUSSION_TITLE_MAX_LEN,
  getDiscussions,
  type Discussion,
  type DiscussionCategory,
} from "@/api/community";
import { useSessionStore } from "@/stores/session";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();

const CATEGORIES: ReadonlyArray<{ value: "" | DiscussionCategory; label: string }> = [
  { value: "", label: "全部" },
  { value: "general", label: "综合" },
  { value: "agriculture", label: "农业" },
  { value: "ecommerce", label: "电商" },
  { value: "crafts", label: "手工" },
];

const discussions = ref<Discussion[]>([]);
const total = ref(0);
const activeCategory = ref<"" | DiscussionCategory>("");
const loading = ref(true);
const loadingMore = ref(false);
const loadError = ref("");
const showComposer = ref(false);
const title = ref("");
const content = ref("");
const category = ref<DiscussionCategory>("general");
const submitting = ref(false);
const feedback = ref<{ kind: "success" | "error"; text: string } | null>(null);
const titleInput = ref<HTMLInputElement | null>(null);

const activeCategoryLabel = computed(
  () =>
    CATEGORIES.find((item) => item.value === activeCategory.value)?.label ??
    "全部",
);

watch(
  () => route.query.action,
  (action) => {
    if (action === "new" && session.isAuthenticated) {
      void openComposer();
    }
  },
);

onMounted(() => {
  void loadDiscussions();
  if (route.query.action === "new" && session.isAuthenticated) {
    void openComposer();
  }
});

async function loadDiscussions(reset = true): Promise<void> {
  const nextPage = reset
    ? 1
    : Math.floor(discussions.value.length / DISCUSSION_PAGE_SIZE) + 1;
  if (reset) {
    loading.value = true;
  } else {
    loadingMore.value = true;
  }
  loadError.value = "";
  try {
    const response = await getDiscussions(activeCategory.value, nextPage);
    discussions.value = reset
      ? response.discussions
      : [...discussions.value, ...response.discussions];
    total.value = response.total;
  } catch (error) {
    const message =
      error instanceof ApiError && error.status !== 0
        ? error.message
        : "讨论加载失败，请检查网络后重试";
    if (reset) {
      discussions.value = [];
      total.value = 0;
      loadError.value = message;
    } else {
      feedback.value = { kind: "error", text: message };
    }
  } finally {
    loading.value = false;
    loadingMore.value = false;
  }
}

function selectCategory(value: "" | DiscussionCategory): void {
  if (activeCategory.value === value) return;
  activeCategory.value = value;
  void loadDiscussions(true);
}

function loadMore(): void {
  void loadDiscussions(false);
}

function retryLoad(): void {
  void loadDiscussions(true);
}

async function openComposer(focus = true): Promise<void> {
  if (!session.isAuthenticated) {
    await router.push({
      path: "/login",
      query: { redirect: "/community?action=new" },
    });
    return;
  }
  showComposer.value = true;
  feedback.value = null;
  if (focus) {
    await nextTick();
    titleInput.value?.focus();
  }
}

async function closeComposer(): Promise<void> {
  showComposer.value = false;
  title.value = "";
  content.value = "";
  category.value = "general";
  if (route.query.action === "new") {
    await router.replace({ path: "/community" });
  }
}

async function submitDiscussion(): Promise<void> {
  feedback.value = null;
  const cleanTitle = title.value.trim();
  const cleanContent = content.value.trim();
  if (!cleanTitle || !cleanContent) {
    feedback.value = { kind: "error", text: "标题和内容不能为空" };
    return;
  }
  if (cleanTitle.length > DISCUSSION_TITLE_MAX_LEN) {
    feedback.value = {
      kind: "error",
      text: `标题不能超过 ${DISCUSSION_TITLE_MAX_LEN} 字`,
    };
    return;
  }
  if (cleanContent.length > DISCUSSION_CONTENT_MAX_LEN) {
    feedback.value = {
      kind: "error",
      text: `帖子内容不能超过 ${DISCUSSION_CONTENT_MAX_LEN} 字`,
    };
    return;
  }

  submitting.value = true;
  try {
    const response = await createDiscussion({
      title: cleanTitle,
      content: cleanContent,
      category: category.value,
    });
    if (activeCategory.value && activeCategory.value !== category.value) {
      activeCategory.value = category.value;
    }
    title.value = "";
    content.value = "";
    showComposer.value = false;
    feedback.value = { kind: "success", text: response.message || "发布成功" };
    await router.replace({ path: "/community" });
    await loadDiscussions(true);
  } catch (error) {
    feedback.value = {
      kind: "error",
      text:
        error instanceof ApiError && error.status !== 0
          ? error.message
          : "网络连接失败，请稍后重试",
    };
  } finally {
    submitting.value = false;
  }
}

function categoryLabel(value: string): string {
  return CATEGORIES.find((item) => item.value === value)?.label ?? value;
}

function formatTime(value: string): string {
  return value ? value.slice(0, 16) : "";
}

function preview(value: string): string {
  return value.length > 150 ? `${value.slice(0, 150)}...` : value;
}
</script>

<template>
  <section
    id="community-tab"
    class="tab-content active community-view"
    aria-labelledby="community-title"
  >
    <div class="container community-container">
      <div class="community-heading">
        <div>
          <div class="section-label">
            Community
          </div>
          <h1
            id="community-title"
            class="section-title"
          >
            社区讨论
          </h1>
          <p class="section-desc">
            分享经验、交流问题，与教师和同伴一起讨论学习与实践
          </p>
        </div>
        <button
          type="button"
          class="btn btn-primary"
          data-testid="community-new-button"
          @click="openComposer()"
        >
          <i
            class="fas fa-pen-to-square"
            aria-hidden="true"
          />
          发起讨论
        </button>
      </div>

      <div
        v-if="feedback"
        class="community-feedback"
        :class="`is-${feedback.kind}`"
        :role="feedback.kind === 'error' ? 'alert' : 'status'"
        data-testid="community-feedback"
      >
        {{ feedback.text }}
      </div>

      <form
        v-if="showComposer"
        class="card-section community-composer"
        data-testid="community-composer"
        @submit.prevent="submitDiscussion"
      >
        <div class="community-composer-head">
          <div>
            <h2>发布新讨论</h2>
            <p>标题与正文会公开展示，请勿填写个人敏感信息。</p>
          </div>
          <button
            type="button"
            class="community-text-button"
            @click="closeComposer"
          >
            取消
          </button>
        </div>
        <div class="form-group">
          <label for="community-title-input">讨论标题</label>
          <input
            id="community-title-input"
            ref="titleInput"
            v-model="title"
            type="text"
            placeholder="用一句话说明你想讨论的问题"
          >
          <span class="community-counter">
            {{ title.length }}/{{ DISCUSSION_TITLE_MAX_LEN }}
          </span>
        </div>
        <div class="form-group">
          <label for="community-category-input">讨论分类</label>
          <select
            id="community-category-input"
            v-model="category"
          >
            <option
              v-for="item in CATEGORIES.slice(1)"
              :key="item.value"
              :value="item.value"
            >
              {{ item.label }}
            </option>
          </select>
        </div>
        <div class="form-group">
          <label for="community-content-input">讨论正文</label>
          <textarea
            id="community-content-input"
            v-model="content"
            rows="6"
            placeholder="补充背景、已尝试的方法或希望得到的建议"
          />
          <span class="community-counter">
            {{ content.length }}/{{ DISCUSSION_CONTENT_MAX_LEN }}
          </span>
        </div>
        <div class="community-composer-actions">
          <button
            type="submit"
            class="btn btn-primary"
            data-testid="community-submit"
            :disabled="submitting"
          >
            {{ submitting ? "正在发布..." : "发布讨论" }}
          </button>
        </div>
      </form>

      <div class="community-toolbar">
        <div
          class="community-categories"
          role="group"
          aria-label="讨论分类"
        >
          <button
            v-for="item in CATEGORIES"
            :key="item.value || 'all'"
            type="button"
            class="community-category"
            :class="{ active: activeCategory === item.value }"
            :aria-pressed="activeCategory === item.value"
            @click="selectCategory(item.value)"
          >
            {{ item.label }}
          </button>
        </div>
        <span class="community-total">
          {{ activeCategoryLabel }} · 共 {{ total }} 条讨论
        </span>
      </div>

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
          @click="retryLoad"
        >
          <i
            class="fas fa-redo"
            aria-hidden="true"
          />
          重试
        </button>
      </div>
      <div
        v-else-if="discussions.length === 0"
        class="card-section community-state"
        role="status"
        data-testid="community-empty"
      >
        <i
          class="fas fa-comments"
          aria-hidden="true"
        />
        <p>暂无讨论帖，快来发第一个帖子吧！</p>
        <button
          type="button"
          class="btn btn-outline btn-sm"
          @click="openComposer()"
        >
          发起讨论
        </button>
      </div>
      <div
        v-else
        class="community-list"
      >
        <article
          v-for="discussion in discussions"
          :key="discussion.id"
          class="discussion-card community-card"
          data-testid="community-discussion"
        >
          <div class="community-card-head">
            <span class="community-tag">
              {{ categoryLabel(discussion.category) }}
            </span>
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
          <h2>
            <RouterLink :to="`/community/${discussion.id}`">
              {{ discussion.title }}
            </RouterLink>
          </h2>
          <p>{{ preview(discussion.content) }}</p>
          <div class="community-card-meta">
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
          <RouterLink
            class="community-detail-link"
            :to="`/community/${discussion.id}`"
          >
            查看讨论
            <i
              class="fas fa-arrow-right"
              aria-hidden="true"
            />
          </RouterLink>
        </article>
        <button
          v-if="discussions.length < total"
          type="button"
          class="btn btn-outline community-load-more"
          :disabled="loadingMore"
          @click="loadMore"
        >
          {{ loadingMore ? "正在加载..." : `加载更多（${discussions.length}/${total}）` }}
        </button>
      </div>
    </div>
  </section>
</template>

<style src="@/styles/community.css"></style>
