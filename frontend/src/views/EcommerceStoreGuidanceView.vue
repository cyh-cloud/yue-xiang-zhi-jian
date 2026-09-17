<script setup lang="ts">
import { History, RefreshCw, Sparkles, Store } from 'lucide-vue-next'
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import EcommerceTrainingNav from '@/components/EcommerceTrainingNav.vue'
import type { StorePlanValue } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import {
  STORE_PLATFORMS,
  type StorePlatform,
  type StorePlanSectionKey,
  useEcommerceStoreGuidanceStore
} from '@/stores/ecommerceStoreGuidance'

const store = useEcommerceStoreGuidanceStore()
const auth = useAuthStore()
const router = useRouter()

const platformLabels: Record<StorePlatform, string> = {
  taobao: '淘宝',
  pinduoduo: '拼多多',
  douyin_shop: '抖音小店'
}

const sections: Array<{
  key: StorePlanSectionKey
  label: string
  description: string
}> = [
  {
    key: 'home_layout',
    label: '首页布局',
    description: '首页入口、活动区域与商品展示顺序'
  },
  {
    key: 'color_scheme',
    label: '色彩方案',
    description: '主色、辅色与页面视觉层级'
  },
  {
    key: 'detail_structure',
    label: '详情页结构',
    description: '商品卖点、参数与售后信息顺序'
  },
  {
    key: 'navigation',
    label: '导航分类',
    description: '店铺主要入口与商品分类方式'
  }
]

function platformLabel(value: string): string {
  return (platformLabels as Record<string, string>)[value] ?? value
}

function formatTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
}

function formatWireValue(value: StorePlanValue, depth = 0): string {
  if (value === null || value === undefined) {
    return '未提供'
  }
  if (typeof value === 'string') {
    return value.trim() || '未提供'
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  if (Array.isArray(value)) {
    const parts = value
      .map(item => formatWireValue(item, depth + 1))
      .filter(item => item !== '未提供')
    return parts.length ? parts.join('、') : '未提供'
  }
  if (typeof value === 'object') {
    if (depth >= 3) {
      return '复杂内容'
    }

    const parts = Object.entries(value).map(
      ([key, item]) => `${key}：${formatWireValue(item, depth + 1)}`
    )
    return parts.length ? parts.join('；') : '未提供'
  }
  return String(value)
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void store.loadHistory()
})
</script>

<template>
  <div class="store-guidance-page">
    <AppHeader
      source="live"
      :loading="store.isBusy"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <EcommerceTrainingNav />

    <main class="store-guidance-shell">
      <header class="page-heading">
        <p class="page-kicker">04 / 电商运营实训</p>
        <h1>店铺装修指导</h1>
        <p>
          输入店铺定位与风格偏好，生成首页布局、<span
            class="page-heading__nowrap"
          >色彩方案</span>、详情页结构和导航分类。
        </p>
      </header>

      <div class="workspace">
        <section class="panel form-panel" aria-labelledby="store-form-title">
          <div class="panel-heading">
            <Sparkles :size="18" aria-hidden="true" />
            <h2 id="store-form-title">生成设置</h2>
          </div>

          <form
            data-test="store-guidance-form"
            class="guidance-form"
            @submit.prevent="store.generate()"
          >
            <label>
              <span>店铺类型</span>
              <input
                v-model="store.form.store_type"
                data-test="store-guidance-store-type"
                type="text"
                required
                autocomplete="off"
                placeholder="例如：农产品旗舰店"
              />
            </label>

            <label>
              <span>目标平台</span>
              <select
                v-model="store.form.platform"
                data-test="store-guidance-platform"
                required
              >
                <option
                  v-for="platform in STORE_PLATFORMS"
                  :key="platform"
                  :value="platform"
                >
                  {{ platformLabels[platform] }}
                </option>
              </select>
            </label>

            <label>
              <span>风格偏好</span>
              <textarea
                v-model="store.form.style_preference"
                data-test="store-guidance-style"
                required
                rows="3"
                placeholder="例如：温暖、可靠、突出产地"
              />
            </label>

            <div class="form-actions">
              <button
                class="primary-action"
                data-test="store-guidance-generate"
                type="submit"
                :disabled="store.isBusy"
              >
                <RefreshCw
                  v-if="store.current"
                  :size="17"
                  aria-hidden="true"
                />
                <Sparkles v-else :size="17" aria-hidden="true" />
                <span>{{ store.generating ? '生成中...' : '生成方案' }}</span>
              </button>
              <button
                class="text-action"
                type="button"
                :disabled="store.isBusy"
                @click="store.resetForm()"
              >
                清空
              </button>
            </div>

            <p
              v-if="store.error"
              class="error-message"
              role="alert"
              aria-live="assertive"
            >
              {{ store.error }}
            </p>
          </form>
        </section>

        <section class="panel output-panel" aria-labelledby="store-output-title">
          <div class="panel-heading">
            <Store :size="18" aria-hidden="true" />
            <h2 id="store-output-title">装修方案</h2>
            <span v-if="store.current" class="current-mark">已生成</span>
          </div>

          <div
            v-if="store.current"
            data-test="store-guidance-current"
            class="current-inputs"
          >
            <strong>{{ store.current.store_type }}</strong>
            <span>{{ platformLabel(store.current.platform) }}</span>
            <span>{{ store.current.style_preference }}</span>
            <time :datetime="store.current.created_at">
              {{ formatTime(store.current.created_at) }}
            </time>
          </div>

          <div class="plan-sections">
            <section
              v-for="section in sections"
              :key="section.key"
              data-test="store-guidance-section"
            >
              <div class="section-heading">
                <h3>{{ section.label }}</h3>
                <span>{{ section.description }}</span>
              </div>
              <p v-if="store.current">
                {{ formatWireValue(store.current.plan[section.key]) }}
              </p>
              <p v-else class="section-placeholder">
                生成后显示{{ section.label }}。
              </p>
            </section>
          </div>
        </section>

        <aside class="panel history-panel" aria-labelledby="store-history-title">
          <div class="panel-heading">
            <History :size="18" aria-hidden="true" />
            <h2 id="store-history-title">历史方案</h2>
            <span>{{ store.history.length }} 条</span>
          </div>

          <ul v-if="store.history.length" data-test="store-guidance-history">
            <li v-for="item in store.history" :key="item.id">
              <button
                type="button"
                :data-test="`store-guidance-history-item-${item.id}`"
                :disabled="store.isBusy"
                @click="store.openPlan(item.id)"
              >
                <span class="history-summary">
                  <strong>{{ item.store_type }}</strong>
                  <small>{{ item.style_preference }}</small>
                </span>
                <span class="history-platform">
                  {{ platformLabel(item.platform) }}
                </span>
                <time :datetime="item.created_at">
                  {{ formatTime(item.created_at) }}
                </time>
              </button>
            </li>
          </ul>

          <p v-else class="empty-state">暂无装修方案。</p>
        </aside>
      </div>
    </main>
  </div>
</template>

<style scoped>
.store-guidance-page {
  min-width: 0;
  min-height: 100vh;
  overflow-x: clip;
  color-scheme: light;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.store-guidance-shell {
  width: min(100%, var(--ark-shell-max));
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.page-heading {
  max-width: 760px;
  margin-bottom: 28px;
}

.page-heading h1 {
  margin: 0;
  font-size: 3.35rem;
  line-height: 1.05;
  text-wrap: balance;
}

.page-heading__nowrap {
  white-space: nowrap;
}

.page-heading > p:last-child {
  margin: 14px 0 0;
  color: var(--ark-muted);
}

.page-kicker {
  margin: 0 0 6px;
  color: var(--ark-signal);
  font-size: 0.78rem;
  font-weight: 700;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(280px, 0.78fr) minmax(0, 1.5fr);
  gap: 16px;
  align-items: start;
}

.panel {
  min-width: 0;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.form-panel {
  grid-row: span 2;
  position: sticky;
  top: 16px;
}

.panel-heading {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 50px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.panel-heading h2 {
  margin: 0;
  font-size: 0.96rem;
}

.panel-heading > span {
  margin-left: auto;
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.panel-heading .current-mark {
  color: var(--ark-state);
  font-weight: 700;
}

.guidance-form {
  display: grid;
  gap: 16px;
  padding: 18px;
}

.guidance-form label {
  display: grid;
  gap: 7px;
  color: var(--ark-muted);
  font-size: 0.82rem;
  font-weight: 700;
}

.guidance-form input,
.guidance-form select,
.guidance-form textarea {
  width: 100%;
  min-height: 42px;
  padding: 10px 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  outline: none;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font-weight: 400;
}

.guidance-form textarea {
  resize: vertical;
}

.guidance-form input:focus,
.guidance-form select:focus,
.guidance-form textarea:focus {
  border-color: var(--ark-focus);
  box-shadow: 0 0 0 2px var(--ark-surface-2);
}

.form-actions {
  display: flex;
  gap: 8px;
}

.form-actions button {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: var(--ark-radius);
  font-weight: 700;
}

.primary-action {
  flex: 1;
  border: 1px solid var(--ark-signal);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}

.text-action {
  padding-inline: 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.error-message {
  margin: 0;
  padding: 10px 12px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  font-size: 0.84rem;
}

.output-panel {
  min-height: clamp(280px, 42svh, 400px);
}

.current-inputs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: baseline;
  padding: 18px;
  border-bottom: 1px solid var(--ark-line);
  color: var(--ark-muted);
  font-size: 0.82rem;
}

.current-inputs strong {
  color: var(--ark-paper);
  font-size: 1.05rem;
}

.current-inputs time {
  margin-left: auto;
  font-variant-numeric: tabular-nums;
}

.plan-sections {
  display: grid;
  gap: 0;
}

.plan-sections section {
  padding: 18px;
  border-bottom: 1px solid var(--ark-line);
}

.plan-sections section:last-child {
  border-bottom: 0;
}

.section-heading {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  align-items: baseline;
}

.section-heading h3 {
  margin: 0;
  color: var(--ark-signal);
  font-size: 1rem;
}

.section-heading span {
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.plan-sections p {
  margin: 10px 0 0;
  max-width: 72ch;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.section-placeholder {
  color: var(--ark-muted);
}

.history-panel ul {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 14px;
  list-style: none;
}

.history-panel button {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 4px 14px;
  width: 100%;
  padding: 11px 12px;
  border: 1px solid var(--ark-line);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  text-align: left;
}

.history-panel button:hover,
.history-panel button:focus-visible {
  border-color: var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.history-summary {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.history-summary strong {
  color: var(--ark-paper);
  overflow-wrap: anywhere;
}

.history-summary small {
  color: var(--ark-muted);
  overflow-wrap: anywhere;
}

.history-platform {
  color: var(--ark-signal);
  font-size: 0.78rem;
  font-weight: 700;
}

.history-panel time {
  grid-column: 2;
  grid-row: 1 / span 2;
  align-self: center;
  color: var(--ark-muted);
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere;
}

.empty-state {
  margin: 0;
  padding: 26px 18px;
  color: var(--ark-muted);
}

@media (max-width: 900px) {
  .workspace {
    grid-template-columns: minmax(0, 1fr);
  }

  .form-panel {
    position: static;
    grid-row: auto;
  }
}

@media (max-width: 640px) {
  .store-guidance-shell {
    padding: 28px 14px 56px;
  }

  .page-heading h1 {
    font-size: 2.35rem;
  }

  .current-inputs time {
    width: 100%;
    margin-left: 0;
  }

  .history-panel button {
    grid-template-columns: minmax(0, 1fr);
  }

  .history-panel time {
    grid-column: 1;
    grid-row: auto;
  }
}
</style>
