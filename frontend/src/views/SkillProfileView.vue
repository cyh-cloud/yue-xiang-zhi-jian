<script setup lang="ts">
import {
  AlertCircle,
  Check,
  ClipboardList,
  Eye,
  RefreshCw,
  ShieldCheck
} from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'

import type {
  SkillCategory,
  SkillOutcomeItem,
  SkillProfile
} from '@/api/types'
import { useJobMatchingStore } from '@/stores/jobMatching'

const categoryLabels: Record<SkillCategory, string> = {
  live_script: '直播话术脚本',
  simulation_training: '模拟训练评分',
  quiz_score: '课后测验成绩',
  learning_record: '学习记录与课程完成'
}

const categoryOrder: SkillCategory[] = [
  'live_script',
  'simulation_training',
  'quiz_score',
  'learning_record'
]

const sourceModuleLabels: Record<
  SkillOutcomeItem['source_module'],
  string
> = {
  agriculture: '03 · 农业技能',
  ecommerce: '04 · 电商训练',
  handcraft: '05 · 非遗手工'
}

const occurredAtFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false
})

const store = useJobMatchingStore()
const selectedVisibleIds = ref<string[]>([])
const saveNotice = ref('')
const visibilitySaving = ref(false)

const selectedVisibleIdSet = computed(
  () => new Set(selectedVisibleIds.value)
)
const visibleIds = computed(
  () =>
    store.skillProfile?.items
      .filter(
        item =>
          item.source_available &&
          selectedVisibleIdSet.value.has(item.item_id)
      )
      .map(item => item.item_id) ?? []
)
const isEmpty = computed(
  () => store.skillProfile !== null && store.skillProfile.items.length === 0
)
const showInitialLoading = computed(
  () => store.loading && store.skillProfile === null
)
const showInitialError = computed(
  () =>
    !store.loading &&
    store.skillProfile === null &&
    store.error.length > 0
)
const canSave = computed(
  () =>
    store.skillProfile !== null &&
    !store.saving &&
    !visibilitySaving.value
)

function syncVisibleSelection(profile: SkillProfile | null) {
  selectedVisibleIds.value =
    profile?.items
      .filter(item => item.visible && item.source_available)
      .map(item => item.item_id) ?? []
}

function itemsForCategory(category: SkillCategory) {
  return (
    store.skillProfile?.items.filter(item => item.category === category) ?? []
  )
}

function categoryCount(category: SkillCategory) {
  return store.skillProfile?.summary[category] ?? itemsForCategory(category).length
}

function isSelected(item: SkillOutcomeItem) {
  return (
    item.source_available && selectedVisibleIdSet.value.has(item.item_id)
  )
}

function setItemVisibility(item: SkillOutcomeItem, selected: boolean) {
  if (!item.source_available) {
    return
  }

  saveNotice.value = ''
  const selectedIds = new Set(selectedVisibleIds.value)
  if (selected) {
    selectedIds.add(item.item_id)
  } else {
    selectedIds.delete(item.item_id)
  }
  selectedVisibleIds.value = [...selectedIds]
}

function itemVisibilityLabel(item: SkillOutcomeItem) {
  if (!item.source_available) {
    return '来源暂不可用'
  }
  return isSelected(item) ? '企业可见' : '仅自己可见'
}

function sourceAvailabilityLabel(item: SkillOutcomeItem) {
  return item.source_available ? '来源可用' : '来源暂不可用'
}

function formalMarker(item: SkillOutcomeItem) {
  return item.is_formal ? '正式成果' : '练习成果'
}

function scoreLabel(item: SkillOutcomeItem) {
  return item.score === null ? '暂无评分' : `${item.score} 分`
}

function formatOccurredAt(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return occurredAtFormatter.format(date)
}

async function loadProfile() {
  saveNotice.value = ''
  await store.loadSkillProfile()
}

async function saveVisibility() {
  if (!canSave.value) {
    return
  }

  saveNotice.value = ''
  visibilitySaving.value = true
  try {
    const saved = await store.saveSkillVisibility(visibleIds.value)
    if (saved) {
      syncVisibleSelection(saved)
      saveNotice.value = '可见范围已保存'
    }
  } finally {
    visibilitySaving.value = false
  }
}

watch(
  () => store.skillProfile,
  profile => syncVisibleSelection(profile),
  { immediate: true }
)

onMounted(() => {
  if (!store.skillProfile) {
    void loadProfile()
  }
})
</script>

<template>
  <div class="skill-profile-page">
    <main
      class="skill-profile-main"
      :aria-busy="store.loading || store.saving"
    >
      <header class="skill-profile-heading">
        <div class="skill-profile-heading__identity">
          <span class="skill-profile-heading__icon" aria-hidden="true">
            <ShieldCheck :size="26" />
          </span>
          <div class="skill-profile-heading__copy">
            <h1>技能档案</h1>
            <p>
              逐项选择希望企业看到的技能成果。未勾选内容仅自己可见。
            </p>
          </div>
        </div>
        <div class="skill-profile-heading__summary">
          <span>当前企业可见</span>
          <strong class="ark-data">{{ visibleIds.length }} 项</strong>
        </div>
      </header>

      <section
        v-if="showInitialLoading"
        class="skill-profile-state"
        data-test="skill-profile-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="20" aria-hidden="true" />
        <p>正在加载技能档案</p>
      </section>

      <section
        v-else-if="showInitialError"
        class="skill-profile-state is-error"
        data-test="skill-profile-error"
        role="alert"
      >
        <AlertCircle :size="21" aria-hidden="true" />
        <p>{{ store.error }}</p>
        <button type="button" @click="loadProfile">
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </section>

      <template v-else-if="store.skillProfile">
        <div
          v-if="store.error"
          class="skill-profile-notice is-error"
          role="alert"
        >
          <AlertCircle :size="17" aria-hidden="true" />
          <p>{{ store.error }}</p>
        </div>

        <div
          v-if="saveNotice"
          class="skill-profile-notice is-success"
          data-test="visibility-saved"
          role="status"
        >
          <Check :size="17" aria-hidden="true" />
          <p>{{ saveNotice }}</p>
        </div>

        <section
          v-if="isEmpty"
          class="skill-profile-empty"
          data-test="skill-empty"
        >
          <ClipboardList :size="27" aria-hidden="true" />
          <div>
            <h2>暂无可展示的技能成果</h2>
            <p>
              完成课程学习、模拟训练或课后测验后，成果会汇总到这里。
            </p>
          </div>
        </section>

        <div class="skill-profile-toolbar">
          <p>
            勾选后保存。来源不可用的成果不会进入企业可见范围。
          </p>
          <button
            type="button"
            data-test="save-visibility"
            :disabled="!canSave"
            @click="saveVisibility"
          >
            <RefreshCw
              v-if="store.saving"
              class="spinning"
              :size="17"
              aria-hidden="true"
            />
            <Eye v-else :size="17" aria-hidden="true" />
            保存可见范围
          </button>
        </div>

        <div class="skill-profile-groups">
          <section
            v-for="category in categoryOrder"
            :key="category"
            class="skill-category"
            data-test="skill-category"
            :data-category="category"
            :aria-labelledby="`skill-category-${category}`"
          >
            <header class="skill-category__heading">
              <h2 :id="`skill-category-${category}`">
                {{ categoryLabels[category] }}
              </h2>
              <span class="ark-data">
                {{ categoryCount(category) }} 项
              </span>
            </header>

            <div
              v-if="itemsForCategory(category).length"
              class="skill-category__items"
            >
              <article
                v-for="item in itemsForCategory(category)"
                :key="item.item_id"
                class="skill-item"
                data-test="skill-item"
              >
                <div class="skill-item__content">
                  <header class="skill-item__heading">
                    <h3>{{ item.title }}</h3>
                    <span
                      class="skill-item__state"
                      :class="{
                        'is-visible': isSelected(item),
                        'is-unavailable': !item.source_available
                      }"
                      :data-test="
                        isSelected(item) ? 'skill-visible' : undefined
                      "
                    >
                      {{ itemVisibilityLabel(item) }}
                    </span>
                  </header>

                  <p class="skill-item__summary">{{ item.summary }}</p>

                  <dl class="skill-item__meta">
                    <div>
                      <dt>评分</dt>
                      <dd class="ark-data" data-test="item-score">
                        {{ scoreLabel(item) }}
                      </dd>
                    </div>
                    <div>
                      <dt>成果类型</dt>
                      <dd data-test="formal-marker">
                        {{ formalMarker(item) }}
                      </dd>
                    </div>
                    <div>
                      <dt>来源模块</dt>
                      <dd data-test="source-module">
                        {{ sourceModuleLabels[item.source_module] }}
                      </dd>
                    </div>
                    <div>
                      <dt>发生时间</dt>
                      <dd>
                        <time
                          class="ark-data"
                          data-test="item-occurred-at"
                          :datetime="item.occurred_at"
                        >
                          {{ formatOccurredAt(item.occurred_at) }}
                        </time>
                      </dd>
                    </div>
                    <div>
                      <dt>来源状态</dt>
                      <dd
                        :class="{
                          'is-unavailable': !item.source_available
                        }"
                        data-test="source-availability"
                      >
                        {{ sourceAvailabilityLabel(item) }}
                      </dd>
                    </div>
                  </dl>
                </div>

                <label
                  class="skill-item__visibility"
                  :class="{
                    'is-disabled':
                      !item.source_available ||
                      store.saving ||
                      visibilitySaving
                  }"
                >
                  <input
                    type="checkbox"
                    :data-test="`visibility-${item.item_id}`"
                    :checked="isSelected(item)"
                    :disabled="
                      !item.source_available || store.saving
                      || visibilitySaving
                    "
                    @change="
                      setItemVisibility(
                        item,
                        ($event.target as HTMLInputElement).checked
                      )
                    "
                  >
                  <span>企业可见</span>
                </label>
              </article>
            </div>

            <p v-else class="skill-category__empty">
              当前类别暂无成果
            </p>
          </section>
        </div>
      </template>
    </main>
  </div>
</template>

<style scoped>
.skill-profile-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.skill-profile-main {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.skill-profile-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: end;
  min-width: 0;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.skill-profile-heading__identity {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 15px;
  align-items: start;
  min-width: 0;
}

.skill-profile-heading__icon {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-signal);
}

.skill-profile-heading__copy {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.skill-profile-heading h1 {
  margin: 0;
  font-size: 2.35rem;
  line-height: 1.08;
  line-break: strict;
  text-wrap: balance;
  word-break: keep-all;
}

.skill-profile-heading p {
  max-width: 68ch;
  margin: 9px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.skill-profile-heading__summary {
  display: grid;
  min-width: 126px;
  gap: 3px;
  padding: 10px 12px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  text-align: right;
  word-break: normal;
}

.skill-profile-heading__summary strong {
  color: var(--ark-signal);
  font-size: 1rem;
}

.skill-profile-state {
  display: grid;
  min-height: 300px;
  place-items: center;
  align-content: center;
  gap: 9px;
  margin-top: 18px;
  padding: 24px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  text-align: center;
}

.skill-profile-state p {
  margin: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.skill-profile-state button {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 8px 14px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-signal);
}

.skill-profile-state.is-error {
  color: var(--ark-signal);
}

.skill-profile-notice {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 14px;
  padding: 11px 13px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  line-break: strict;
  word-break: normal;
}

.skill-profile-notice p {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
  text-wrap: pretty;
}

.skill-profile-notice.is-error {
  color: var(--ark-signal);
}

.skill-profile-notice.is-success {
  color: var(--ark-state);
}

.skill-profile-empty {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 16px;
  align-items: start;
  min-width: 0;
  margin-top: 18px;
  padding: 24px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.skill-profile-empty > svg {
  color: var(--ark-signal);
}

.skill-profile-empty h2 {
  margin: 0;
  font-size: 1.08rem;
  line-break: strict;
  text-wrap: balance;
  word-break: keep-all;
}

.skill-profile-empty p {
  max-width: 64ch;
  margin: 6px 0 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.skill-profile-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  min-width: 0;
  margin-top: 18px;
  padding: 14px 16px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.skill-profile-toolbar p {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.skill-profile-toolbar button {
  display: inline-flex;
  min-width: 144px;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 8px 14px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
  line-break: strict;
  text-align: center;
  word-break: normal;
}

.skill-profile-toolbar button:hover:not(:disabled),
.skill-profile-toolbar button:focus-visible:not(:disabled) {
  background: var(--ark-surface-0);
  color: var(--ark-signal);
}

.skill-profile-groups {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
  margin-top: 12px;
}

.skill-category {
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.skill-category__heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  min-width: 0;
  min-height: 58px;
  padding: 12px 15px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.skill-category__heading h2 {
  min-width: 0;
  margin: 0;
  font-size: 0.98rem;
  line-height: 1.35;
  line-break: strict;
  text-wrap: balance;
  word-break: keep-all;
}

.skill-category__heading span {
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.skill-category__items {
  display: grid;
  min-width: 0;
}

.skill-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: start;
  min-width: 0;
  padding: 16px 15px;
  border-bottom: 1px solid var(--ark-line);
}

.skill-item:last-child {
  border-bottom: 0;
}

.skill-item__content {
  min-width: 0;
}

.skill-item__heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: start;
  min-width: 0;
}

.skill-item__heading h3 {
  min-width: 0;
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.45;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.skill-item__state {
  display: inline-flex;
  min-height: 28px;
  align-items: center;
  justify-content: center;
  padding: 4px 7px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  color: var(--ark-muted);
  font-size: 0.68rem;
  line-break: strict;
  text-align: center;
  white-space: normal;
  word-break: keep-all;
}

.skill-item__state.is-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.skill-item__state.is-unavailable {
  border-style: dashed;
}

.skill-item__summary {
  margin: 7px 0 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.skill-item__meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
  gap: 8px 14px;
  min-width: 0;
  margin: 13px 0 0;
}

.skill-item__meta > div {
  min-width: 0;
  padding-top: 8px;
  border-top: 1px solid var(--ark-line);
}

.skill-item__meta dt,
.skill-item__meta dd {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.skill-item__meta dt {
  color: var(--ark-muted);
  font-size: 0.66rem;
}

.skill-item__meta dd {
  margin: 3px 0 0;
  font-size: 0.74rem;
}

.skill-item__meta dd.is-unavailable {
  color: var(--ark-signal);
}

.skill-item__visibility {
  display: inline-flex;
  min-width: 104px;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 8px 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  cursor: pointer;
  font-size: 0.74rem;
  line-break: strict;
  text-align: center;
  white-space: normal;
  word-break: keep-all;
}

.skill-item__visibility:hover,
.skill-item__visibility:focus-within {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.skill-item__visibility input {
  width: 18px;
  height: 18px;
  flex: 0 0 auto;
  margin: 0;
  accent-color: var(--ark-signal);
}

.skill-item__visibility.is-disabled {
  cursor: not-allowed;
}

.skill-item__visibility.is-disabled:hover {
  border-color: var(--ark-line-strong);
  color: var(--ark-muted);
}

.skill-category__empty {
  min-height: 88px;
  margin: 0;
  padding: 26px 15px;
  color: var(--ark-muted);
  font-size: 0.76rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-wrap: pretty;
  word-break: normal;
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 960px) {
  .skill-profile-groups {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .skill-profile-main {
    padding: 28px 14px 48px;
  }

  .skill-profile-heading {
    grid-template-columns: minmax(0, 1fr);
    align-items: start;
    gap: 14px;
  }

  .skill-profile-heading h1 {
    font-size: 1.95rem;
  }

  .skill-profile-heading__summary {
    min-width: 0;
    text-align: left;
  }

  .skill-profile-toolbar {
    grid-template-columns: minmax(0, 1fr);
    align-items: stretch;
  }

  .skill-profile-toolbar button {
    width: 100%;
  }

  .skill-item {
    grid-template-columns: minmax(0, 1fr);
  }

  .skill-item__visibility {
    width: 100%;
  }
}

@media (max-width: 360px) {
  .skill-profile-main {
    padding-inline: 12px;
  }

  .skill-profile-heading__identity,
  .skill-profile-empty {
    grid-template-columns: minmax(0, 1fr);
  }

  .skill-profile-heading__icon {
    width: 42px;
    height: 42px;
  }

  .skill-item__heading {
    grid-template-columns: minmax(0, 1fr);
  }

  .skill-item__state {
    justify-self: start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
