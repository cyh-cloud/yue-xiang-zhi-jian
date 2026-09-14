<script setup lang="ts">
import { Check, SkipForward } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type { InterestTag } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import { useAuthStore } from '@/stores/auth'

interface InterestTagsResponse {
  success: true
  tags: InterestTag[]
}

const groupOrder: Array<{
  key: InterestTag['group_key']
  label: string
}> = [
  { key: 'crop', label: '作物类目' },
  { key: 'skill', label: '技能兴趣' },
  { key: 'job', label: '岗位类别' }
]

const auth = useAuthStore()
const router = useRouter()
const tags = ref<InterestTag[]>([])
const selectedIds = ref<number[]>([])
const loadingTags = ref(true)
const loadError = ref('')

const groups = computed(() =>
  groupOrder.map(group => ({
    ...group,
    tags: tags.value.filter(tag => tag.group_key === group.key)
  }))
)

async function loadTags() {
  loadingTags.value = true
  loadError.value = ''

  try {
    const response = await apiFetch<InterestTagsResponse>('/api/interest-tags')
    tags.value = response.tags
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '兴趣标签加载失败'
  } finally {
    loadingTags.value = false
  }
}

async function complete(tagIds: number[]) {
  if (auth.loading) {
    return
  }

  const response = await auth.completeInterestTags(tagIds)
  if (!response) {
    return
  }

  await router.push('/student')
}

onMounted(() => {
  void loadTags()
})
</script>

<template>
  <div class="tags-page">
    <AppHeader
      source="mock"
      :loading="false"
      variant="auth"
      :show-auth-controls="false"
    />

    <main class="tags-layout" aria-labelledby="tags-title">
      <header class="tags-heading">
        <div>
          <h1 id="tags-title">选择兴趣标签</h1>
          <p>选择你关注的作物、技能和岗位类别，用于优先展示匹配内容。也可以直接跳过。</p>
        </div>
        <span class="selected-count ark-data">{{ selectedIds.length }} 已选</span>
      </header>

      <section class="tag-workbench" :aria-busy="loadingTags">
        <p v-if="loadingTags" class="state-message" role="status">正在加载兴趣标签</p>
        <template v-else-if="loadError">
          <p class="state-message error" role="alert">{{ loadError }}</p>
          <button class="retry-button" type="button" @click="loadTags">重新加载</button>
        </template>
        <template v-else>
          <section v-for="group in groups" :key="group.key" class="tag-group">
            <header>
              <h2>{{ group.label }}</h2>
              <span class="ark-data">{{ group.tags.length }}</span>
            </header>
            <div v-if="group.tags.length" class="tag-options">
              <label v-for="tag in group.tags" :key="tag.id">
                <input v-model="selectedIds" type="checkbox" :value="tag.id" />
                <span>{{ tag.name }}</span>
              </label>
            </div>
            <p v-else class="group-empty">暂无标签</p>
          </section>
        </template>
      </section>

      <p v-if="auth.error" class="save-error" role="alert">{{ auth.error }}</p>

      <footer class="tags-actions">
        <button
          class="ghost-action"
          data-test="skip-tags"
          type="button"
          :disabled="auth.loading"
          @click="complete([])"
        >
          <SkipForward :size="17" aria-hidden="true" />
          跳过
        </button>
        <button
          class="primary-action"
          data-test="save-tags"
          type="button"
          :disabled="auth.loading"
          @click="complete(selectedIds)"
        >
          <Check :size="17" aria-hidden="true" />
          {{ auth.loading ? '正在保存' : '保存并进入' }}
        </button>
      </footer>
    </main>
  </div>
</template>

<style scoped>
.tags-page {
  min-height: 100svh;
  background:
    linear-gradient(rgb(16 23 25 / 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgb(16 23 25 / 0.038) 1px, transparent 1px),
    var(--ark-ink);
  background-size: 72px 72px;
}

.tags-layout {
  width: min(100%, 1120px);
  margin-inline: auto;
  padding: 52px 24px 72px;
}

.tags-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.tags-heading h1 {
  margin: 0;
  font-size: 2.65rem;
  line-height: 1.05;
}

.tags-heading p {
  max-width: 66ch;
  margin: 14px 0 0;
  color: var(--ark-muted);
}

.selected-count {
  flex: 0 0 auto;
  padding: 7px 9px;
  border: 1px solid var(--ark-line);
  color: var(--ark-signal);
  font-size: 0.78rem;
}

.tag-workbench {
  display: grid;
  min-height: 320px;
  margin-top: 22px;
  border: 1px solid var(--ark-line-strong);
  background: rgb(255 255 255 / 0.84);
}

.state-message {
  align-self: center;
  justify-self: center;
  margin: 0;
  color: var(--ark-muted);
}

.state-message.error {
  color: #b42318;
}

.retry-button {
  justify-self: center;
  min-height: 38px;
  padding: 0 13px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

.tag-group {
  display: grid;
  grid-template-columns: minmax(150px, 0.2fr) minmax(0, 0.8fr);
  gap: 22px;
  padding: 20px;
  border-bottom: 1px solid var(--ark-line);
}

.tag-group:last-child {
  border-bottom: 0;
}

.tag-group header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.tag-group h2 {
  margin: 0;
  font-size: 1rem;
}

.tag-group header span {
  color: var(--ark-muted);
  font-size: 0.74rem;
}

.tag-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-options label {
  position: relative;
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-muted);
}

.tag-options input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
}

.tag-options span {
  padding: 7px 10px;
  font-size: 0.82rem;
}

.tag-options label:has(input:checked) {
  border-color: var(--ark-signal);
  background: rgb(24 209 255 / 0.1);
  color: var(--ark-paper);
}

.tag-options label:focus-within {
  outline: 2px solid var(--ark-focus);
  outline-offset: 2px;
}

.group-empty {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.82rem;
}

.save-error {
  margin: 16px 0 0;
  padding: 10px 11px;
  border: 1px solid rgb(180 35 24 / 0.44);
  background: rgb(180 35 24 / 0.08);
  color: #b42318;
  font-size: 0.8rem;
}

.tags-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}

.ghost-action,
.primary-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 46px;
  padding: 0 18px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: transparent;
  color: var(--ark-paper);
  font-size: 0.9rem;
}

.primary-action {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.ghost-action:hover:not(:disabled),
.primary-action:hover:not(:disabled) {
  background: rgb(24 209 255 / 0.12);
}

@media (max-width: 720px) {
  .tags-layout {
    padding: 32px 14px 48px;
  }

  .tags-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .tags-heading h1 {
    font-size: 2.15rem;
  }

  .tag-group {
    grid-template-columns: 1fr;
    gap: 14px;
  }

  .tags-actions {
    align-items: stretch;
    flex-direction: column-reverse;
  }
}
</style>
