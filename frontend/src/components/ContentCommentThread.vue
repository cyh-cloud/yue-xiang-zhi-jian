<script setup lang="ts">
import { RefreshCw, Send } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'

import { ApiError, apiFetch } from '@/api/client'
import type { ContentComment } from '@/api/types'

const props = defineProps<{
  endpoint: string
  title: string
}>()

const comments = ref<ContentComment[]>([])
const commentBody = ref('')
const loading = ref(false)
const submitting = ref(false)
const error = ref('')

function errorMessage(fallback: string): string {
  return error.value || fallback
}

async function loadComments() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const response = await apiFetch<{
      success: true
      comments: ContentComment[]
    }>(props.endpoint)
    comments.value = response.comments
  } catch (caught) {
    error.value =
      caught instanceof ApiError || caught instanceof Error
        ? caught.message
        : '评论加载失败'
  } finally {
    loading.value = false
  }
}

async function submitComment() {
  const body = commentBody.value.trim()
  if (!body || loading.value || submitting.value) return

  submitting.value = true
  error.value = ''
  try {
    await apiFetch<{
      success: true
      comment: ContentComment
    }>(props.endpoint, {
      method: 'POST',
      body: JSON.stringify({ body })
    })
    commentBody.value = ''
    await loadComments()
  } catch (caught) {
    error.value =
      caught instanceof ApiError || caught instanceof Error
        ? caught.message
        : '评论提交失败'
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  void loadComments()
})
</script>

<template>
  <section class="content-comments" aria-labelledby="content-comments-title">
    <header class="content-comments__heading">
      <div>
        <span class="ark-data">COMMENT THREAD</span>
        <h3 id="content-comments-title">{{ props.title }}</h3>
      </div>
      <button
        type="button"
        data-test="refresh-comments"
        :disabled="loading"
        @click="loadComments"
      >
        <RefreshCw
          :class="{ spinning: loading }"
          :size="16"
          aria-hidden="true"
        />
        刷新
      </button>
    </header>

    <p v-if="error" class="content-comments__error" role="alert">
      {{ errorMessage('评论加载失败') }}
    </p>

    <ol v-if="comments.length" class="content-comments__list">
      <li
        v-for="comment in comments"
        :key="comment.comment_id"
        :data-test="`comment-${comment.comment_id}`"
      >
        <article>
          <header>
            <span
              v-if="comment.is_teacher_reply"
              class="teacher-reply"
              data-test="teacher-reply-label"
            >
              教师回复
            </span>
            <span v-else>学员留言</span>
            <time :datetime="comment.created_at">
              {{ comment.created_at }}
            </time>
          </header>
          <p data-test="comment-body">{{ comment.body }}</p>
        </article>
      </li>
    </ol>
    <p v-else class="content-comments__empty">
      {{ loading ? '正在加载评论' : '暂无评论' }}
    </p>

    <form @submit.prevent="submitComment">
      <label for="content-comment-input">发表评论</label>
      <textarea
        id="content-comment-input"
        v-model="commentBody"
        data-test="comment-input"
        rows="3"
        :disabled="loading || submitting"
        placeholder="输入你的问题或留言"
      />
      <button
        type="submit"
        data-test="submit-comment"
        :disabled="loading || submitting || !commentBody.trim()"
        @click="submitComment"
      >
        <Send :size="16" aria-hidden="true" />
        {{ submitting ? '提交中' : '提交评论' }}
      </button>
    </form>
  </section>
</template>

<style scoped>
.content-comments {
  display: grid;
  min-width: 0;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.content-comments__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.content-comments__heading span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.content-comments__heading h3 {
  margin: 3px 0 0;
  font-size: 1rem;
}

.content-comments__heading button,
.content-comments form button {
  display: inline-flex;
  min-height: 38px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

.content-comments form {
  display: grid;
  gap: 7px;
}

.content-comments form label {
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.content-comments textarea {
  width: 100%;
  min-width: 0;
  min-height: 82px;
  padding: 10px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  resize: vertical;
}

.content-comments form button {
  justify-self: start;
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.content-comments__list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.content-comments__list article {
  display: grid;
  min-width: 0;
  gap: 7px;
  padding: 10px;
  border-left: 3px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.content-comments__list article header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 7px;
}

.teacher-reply {
  color: var(--ark-state);
  font-weight: 700;
}

.content-comments__list time,
.content-comments__empty,
.content-comments__error {
  color: var(--ark-muted);
  font-size: 0.74rem;
}

.content-comments__list p,
.content-comments__error {
  margin: 0;
  overflow-wrap: anywhere;
}

.content-comments__empty {
  margin: 0;
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 640px) {
  .content-comments__heading,
  .content-comments form button {
    width: 100%;
  }

  .content-comments form button {
    justify-self: stretch;
  }
}
</style>
