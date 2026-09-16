<script setup lang="ts">
import { History, RefreshCw, Sparkles } from 'lucide-vue-next'
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import EcommerceTrainingNav from '@/components/EcommerceTrainingNav.vue'
import {
  LIVE_SCRIPT_STYLES,
  type LiveScriptStyle,
  useEcommerceLiveScriptStore
} from '@/stores/ecommerceLiveScript'
import { useAuthStore } from '@/stores/auth'

const store = useEcommerceLiveScriptStore()
const auth = useAuthStore()
const router = useRouter()

const styleLabels: Record<LiveScriptStyle, string> = {
  enthusiastic: '热情',
  professional: '专业',
  humorous: '幽默'
}

const sections = [
  { key: 'opening', label: '开场白' },
  { key: 'product_intro', label: '产品介绍' },
  { key: 'interaction', label: '互动话术' },
  { key: 'closing', label: '促单话术' }
] as const

const actionLabel = computed(() =>
  store.current ? '重新生成' : '生成直播话术'
)

function formatTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  store.loadHistory()
})
</script>

<template>
  <div class="live-script-page">
    <AppHeader
      source="live"
      :loading="store.loading || store.generating"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <EcommerceTrainingNav />

    <main class="live-script-shell">
      <header class="page-heading">
        <p class="page-kicker">04 / 电商运营实训</p>
        <h1>直播话术</h1>
        <p>
          填写商品信息并选择表达风格，生成包含开场、介绍、互动和促单的完整直播脚本。
        </p>
      </header>

      <div class="workspace">
        <section class="panel form-panel" aria-labelledby="form-title">
          <div class="panel-heading">
            <Sparkles :size="18" aria-hidden="true" />
            <h2 id="form-title">生成设置</h2>
          </div>

          <form
            data-test="live-script-form"
            class="script-form"
            @submit.prevent="store.generate()"
          >
            <label>
              <span>商品名称</span>
              <input
                v-model="store.form.product_name"
                data-test="live-script-product-name"
                type="text"
                required
                autocomplete="off"
                placeholder="例如：广东荔枝干"
              />
            </label>

            <label>
              <span>商品卖点</span>
              <textarea
                v-model="store.form.selling_points"
                data-test="live-script-selling-points"
                required
                rows="3"
                placeholder="例如：香甜、耐储存、产地直发"
              />
            </label>

            <label>
              <span>价格文案</span>
              <input
                v-model="store.form.price_text"
                data-test="live-script-price"
                type="text"
                autocomplete="off"
                placeholder="例如：限时 39.9 元"
              />
            </label>

            <fieldset>
              <legend>话术风格</legend>
              <div class="style-options">
                <label
                  v-for="style in LIVE_SCRIPT_STYLES"
                  :key="style"
                  data-test="live-script-style"
                  class="style-option"
                >
                  <input
                    v-model="store.form.style"
                    type="radio"
                    name="live-script-style"
                    :value="style"
                  />
                  <span>{{ styleLabels[style] }}</span>
                </label>
              </div>
            </fieldset>

            <div class="form-actions">
              <button
                class="primary-action"
                type="submit"
                :data-test="
                  store.current
                    ? 'live-script-regenerate'
                    : 'live-script-generate'
                "
                :disabled="store.generating"
              >
                <RefreshCw
                  v-if="store.current"
                  :size="17"
                  aria-hidden="true"
                />
                <Sparkles v-else :size="17" aria-hidden="true" />
                <span>{{ store.generating ? '生成中...' : actionLabel }}</span>
              </button>
              <button
                class="text-action"
                type="button"
                :disabled="store.generating"
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

        <section class="panel output-panel" aria-labelledby="output-title">
          <div class="panel-heading">
            <RefreshCw :size="18" aria-hidden="true" />
            <h2 id="output-title">当前话术</h2>
            <span v-if="store.current?.is_current" class="current-mark">
              最新版本
            </span>
          </div>

          <div
            v-if="store.current"
            data-test="live-script-current"
            class="current-version"
          >
            <div class="version-meta">
              <strong>{{ store.current.product_name }}</strong>
              <span class="style-label">
                {{ styleLabels[store.current.style] }}
              </span>
              <span data-test="live-script-current-selling-points">
                卖点：{{ store.current.selling_points.join('、') || '未填写' }}
              </span>
              <span data-test="live-script-current-price">
                价格：{{ store.current.price_text || '未填写' }}
              </span>
              <time :datetime="store.current.created_at">
                {{ formatTime(store.current.created_at) }}
              </time>
            </div>

            <div class="script-sections">
              <section
                v-for="section in sections"
                :key="section.key"
                data-test="live-script-section"
              >
                <h3>{{ section.label }}</h3>
                <p>{{ store.current.script[section.key] }}</p>
              </section>
            </div>
          </div>

          <p v-else class="empty-state">
            填写商品信息并生成后，四段直播话术会显示在这里。
          </p>
        </section>

        <aside class="panel history-panel" aria-labelledby="history-title">
          <div class="panel-heading">
            <History :size="18" aria-hidden="true" />
            <h2 id="history-title">模块历史</h2>
            <span>{{ store.history.length }} 条</span>
          </div>

          <ul v-if="store.history.length" data-test="live-script-history">
            <li v-for="item in store.history" :key="item.id">
              <button
                type="button"
                :data-test="`live-script-history-item-${item.id}`"
                :class="{ 'is-current': item.is_current }"
                @click="store.openVersion(item.id)"
              >
                <span class="history-title">
                  {{ item.product_name }}
                  <small>{{ styleLabels[item.style] }}</small>
                </span>
                <time :datetime="item.created_at">
                  {{ formatTime(item.created_at) }}
                </time>
                <span class="history-selling-points">
                  卖点：{{ item.selling_points.join('、') || '未填写' }}
                </span>
                <span class="history-price">
                  价格：{{ item.price_text || '未填写' }}
                </span>
                <em v-if="item.is_current">当前</em>
              </button>
            </li>
          </ul>

          <p v-else class="empty-state">暂无生成记录。</p>
        </aside>
      </div>
    </main>
  </div>
</template>

<style scoped>
.live-script-page {
  min-width: 0;
  min-height: 100vh;
  overflow-x: clip;
  color-scheme: light;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.live-script-shell {
  width: min(100%, var(--ark-shell-max));
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.page-heading {
  max-width: 760px;
  margin-bottom: 28px;
}

.page-kicker {
  margin: 0 0 6px;
  color: var(--ark-signal);
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0;
  font-size: clamp(2rem, 4vw, 3.4rem);
  line-height: 1.05;
}

.page-heading > p:last-child {
  margin: 14px 0 0;
  color: var(--ark-muted);
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

.script-form {
  display: grid;
  gap: 16px;
  padding: 18px;
}

.script-form label {
  display: grid;
  gap: 7px;
  color: var(--ark-muted);
  font-size: 0.82rem;
  font-weight: 700;
}

.script-form input[type="text"],
.script-form textarea {
  width: 100%;
  min-height: 42px;
  padding: 10px 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  outline: none;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font-weight: 400;
  resize: vertical;
}

.script-form input[type="text"]:focus,
.script-form textarea:focus {
  border-color: var(--ark-focus);
  box-shadow: 0 0 0 2px var(--ark-surface-2);
}

.script-form fieldset {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.script-form legend {
  margin-bottom: 8px;
  color: var(--ark-muted);
  font-size: 0.82rem;
  font-weight: 700;
}

.style-options {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.style-option {
  display: flex !important;
  min-height: 44px;
  align-items: center;
  justify-content: center;
  gap: 7px !important;
  border: 1px solid var(--ark-line);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-1);
  color: var(--ark-paper) !important;
  cursor: pointer;
}

.style-option:has(input:checked) {
  border-color: var(--ark-signal);
  background: var(--ark-surface-2);
}

.style-option input {
  accent-color: var(--ark-signal);
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
  min-height: 360px;
}

.current-version {
  padding: 18px;
}

.version-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: baseline;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--ark-line);
  color: var(--ark-muted);
  font-size: 0.82rem;
}

.version-meta strong {
  color: var(--ark-paper);
  font-size: 1.05rem;
}

.version-meta > * {
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.version-meta .style-label {
  color: var(--ark-signal);
  font-weight: 700;
}

.version-meta time {
  margin-left: auto;
}

.script-sections {
  display: grid;
  gap: 18px;
  margin-top: 18px;
}

.script-sections section {
  padding-left: 14px;
  border-left: 2px solid var(--ark-signal);
}

.script-sections h3 {
  margin: 0 0 6px;
  font-size: 0.86rem;
}

.script-sections p {
  margin: 0;
  color: var(--ark-muted);
  white-space: pre-wrap;
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

.history-panel button.is-current {
  border-color: var(--ark-signal);
}

.history-title {
  overflow-wrap: anywhere;
  color: var(--ark-paper);
  font-weight: 700;
}

.history-panel button > span {
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.history-title small {
  margin-left: 7px;
  color: var(--ark-signal);
  font-weight: 700;
}

.history-panel time {
  grid-column: 2;
  grid-row: 1 / span 2;
  align-self: center;
  font-size: 0.75rem;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.history-panel em {
  color: var(--ark-state);
  font-size: 0.75rem;
  font-style: normal;
  font-weight: 700;
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

@media (max-width: 540px) {
  .live-script-shell {
    padding: 28px 14px 56px;
  }

  .style-options {
    grid-template-columns: minmax(0, 1fr);
  }

  .version-meta time {
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
