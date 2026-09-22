<script setup lang="ts">
import { Send, X } from 'lucide-vue-next'
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import type { LocalDialectCode } from '@/api/types'
import { useAiCompanionStore } from '@/stores/aiCompanion'
import { useAuthStore } from '@/stores/auth'

import AiCompanionHistory from './AiCompanionHistory.vue'
import AiCompanionMessage from './AiCompanionMessage.vue'
import VoiceInputButton from './VoiceInputButton.vue'

type PanelView = 'chat' | 'history'

// tab / tabpanel 成对绑定，供 aria-controls 与 aria-labelledby 引用。
const PANEL_TABS: ReadonlyArray<{
  view: PanelView
  tabId: string
  panelId: string
  label: string
}> = [
  {
    view: 'chat',
    tabId: 'ai-companion-tab-chat',
    panelId: 'ai-companion-chat-panel',
    label: '对话'
  },
  {
    view: 'history',
    tabId: 'ai-companion-tab-history',
    panelId: 'ai-companion-history-panel',
    label: '历史会话'
  }
]

const RECOGNITION_FAILURE_MESSAGE = '未能识别，请重说或改用文字'
const MAX_QUESTION_LENGTH = 2000

// 三个方言只作为语音提问的交互上下文，既不预选也不传给 ASR。
const DIALECTS: ReadonlyArray<{ code: LocalDialectCode; label: string }> = [
  { code: 'yue', label: '粤语' },
  { code: 'hak', label: '客家话' },
  { code: 'nan', label: '潮汕话' }
]

const emit = defineEmits<{
  close: []
}>()

const auth = useAuthStore()
const companion = useAiCompanionStore()

const rootRef = ref<HTMLElement | null>(null)
const draftRef = ref<HTMLTextAreaElement | null>(null)
const tablistRef = ref<HTMLElement | null>(null)

// 历史懒加载：每次面板打开复位标记，首次切到历史 tab 才向服务端取一次。
const historyLoaded = ref(false)

async function ensureConversationsLoaded() {
  if (historyLoaded.value) {
    return
  }
  historyLoaded.value = true
  try {
    await companion.loadConversations()
    // historyError 非空说明本次加载没成功，复位后允许再次切 tab 时重试。
    if (companion.historyError) {
      historyLoaded.value = false
    }
  } catch {
    // loadConversations 自己已吞掉错误，这里只是防止将来改动把异常外溢。
    historyLoaded.value = false
  }
}

const draftModel = computed({
  get: () => companion.draft,
  set: (value: string) => companion.setDraft(value)
})

// 未显式选择方言前禁止录音；转写或回答进行中同样禁止并发录音。
const voiceDisabled = computed(
  () => companion.dialectCode === null || companion.loading
)

const canSubmit = computed(
  () => companion.draft.trim().length > 0 && !companion.loading
)

function returnFocusToLauncher() {
  document
    .querySelector<HTMLButtonElement>('[data-test="ai-companion-launcher"]')
    ?.focus()
}

function requestClose() {
  returnFocusToLauncher()
  emit('close')
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.stopPropagation()
    requestClose()
  }
}

function selectView(view: PanelView) {
  companion.activeView = view
  if (view === 'history') {
    void ensureConversationsLoaded()
  }
}

// 左右方向键在 tablist 内移动并选中相邻视图，未选中的 tab 移出 tab 序列。
function handleTabKeydown(event: KeyboardEvent) {
  const offset =
    event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
  if (offset === 0) {
    return
  }
  event.preventDefault()
  const currentIndex = PANEL_TABS.findIndex(
    tab => tab.view === companion.activeView
  )
  const nextTab =
    PANEL_TABS[(currentIndex + offset + PANEL_TABS.length) % PANEL_TABS.length]
  selectView(nextTab.view)
  void nextTick(() => {
    tablistRef.value
      ?.querySelector<HTMLButtonElement>(`#${nextTab.tabId}`)
      ?.focus()
  })
}

watch(
  () => companion.panelOpen,
  open => {
    if (!open) {
      return
    }
    // 每次打开都允许重新拉取一次历史；若打开时已停留在历史 tab，则立即重载，
    // 满足"关闭再打开会从服务端重载历史"，无需用户再次点击 tab。
    historyLoaded.value = false
    if (companion.activeView === 'history') {
      void ensureConversationsLoaded()
    }
  }
)

function selectDialect(code: LocalDialectCode) {
  companion.dialectCode = code
}

function handleRecordingChange(recording: boolean) {
  companion.recording = recording
}

async function handleRecorded(blob: Blob, filename: string) {
  // 零字节即空录音或被取消：不调用 ASR，只提示改用文字输入。
  if (blob.size === 0) {
    companion.recording = false
    companion.error = RECOGNITION_FAILURE_MESSAGE
    return
  }
  const recognized = await companion.transcribe(blob, filename)
  if (!recognized) {
    return
  }
  // transcribe 已把识别结果写入 store.recognizedText，面板从这里取值填入草稿，
  // 由用户确认后才提交，识别文本始终保持可编辑。
  companion.setDraft(companion.recognizedText)
  await nextTick()
  draftRef.value?.focus()
}

function handlePermissionDenied() {
  companion.recording = false
  companion.error = RECOGNITION_FAILURE_MESSAGE
}

async function submitQuestion() {
  if (!canSubmit.value) {
    return
  }
  await companion.sendQuestion(companion.draft)
}

onMounted(() => {
  rootRef.value?.focus()
})
</script>

<template>
  <section
    ref="rootRef"
    class="ai-companion-panel"
    data-test="ai-companion-panel"
    role="dialog"
    aria-label="AI 学伴"
    tabindex="-1"
    @keydown="handleKeydown"
  >
    <header class="ai-companion-panel-header">
      <h2 class="ai-companion-panel-title">AI 学伴</h2>
      <button
        type="button"
        class="ai-companion-panel-close"
        aria-label="关闭 AI 学伴"
        @click="requestClose"
      >
        <X :size="18" aria-hidden="true" />
      </button>
    </header>

    <div
      ref="tablistRef"
      class="ai-companion-panel-tabs"
      role="tablist"
      aria-label="AI 学伴视图"
      @keydown="handleTabKeydown"
    >
      <button
        v-for="tab in PANEL_TABS"
        :id="tab.tabId"
        :key="tab.view"
        type="button"
        role="tab"
        class="ai-companion-panel-tab"
        :aria-selected="companion.activeView === tab.view"
        :aria-controls="tab.panelId"
        :tabindex="companion.activeView === tab.view ? 0 : -1"
        :data-active="companion.activeView === tab.view"
        @click="selectView(tab.view)"
      >
        {{ tab.label }}
      </button>
    </div>

    <div class="ai-companion-panel-body">
      <div
        v-if="companion.activeView === 'chat'"
        class="ai-companion-panel-scroll"
        data-test="ai-companion-chat-region"
        role="tabpanel"
        id="ai-companion-chat-panel"
        aria-labelledby="ai-companion-tab-chat"
      >
        <slot name="chat">
          <p v-if="companion.messages.length === 0" class="ai-companion-empty">
            问一个平台使用问题，例如“怎么投简历”
          </p>
          <ul
            v-else
            class="ai-companion-messages"
            data-test="ai-companion-messages"
          >
            <li
              v-for="item in companion.messages"
              :key="item.message_id"
              class="ai-companion-messages-item"
            >
              <AiCompanionMessage :message="item" :role="auth.user?.role" />
            </li>
          </ul>
        </slot>
      </div>
      <div
        v-else
        class="ai-companion-panel-scroll"
        data-test="ai-companion-history-region"
        role="tabpanel"
        id="ai-companion-history-panel"
        aria-labelledby="ai-companion-tab-history"
      >
        <slot name="history">
          <AiCompanionHistory />
        </slot>
      </div>
    </div>

    <footer class="ai-companion-panel-composer">
      <slot name="composer">
        <form class="ai-companion-composer" @submit.prevent="submitQuestion">
          <p
            v-if="companion.error"
            class="ai-companion-composer-error"
            data-test="ai-companion-error"
            role="alert"
          >
            {{ companion.error }}
          </p>
          <div
            class="ai-companion-dialects"
            role="radiogroup"
            aria-label="提问方言"
          >
            <button
              v-for="dialect in DIALECTS"
              :key="dialect.code"
              type="button"
              role="radio"
              class="ai-companion-dialect"
              :data-test="`ai-companion-dialect-${dialect.code}`"
              :data-active="companion.dialectCode === dialect.code"
              :aria-checked="companion.dialectCode === dialect.code"
              @click="selectDialect(dialect.code)"
            >
              {{ dialect.label }}
            </button>
          </div>
          <div class="ai-companion-composer-row">
            <textarea
              ref="draftRef"
              v-model="draftModel"
              class="ai-companion-composer-input"
              data-test="ai-companion-draft"
              rows="3"
              :maxlength="MAX_QUESTION_LENGTH"
              placeholder="输入平台使用问题"
              aria-label="问题输入"
            />
            <!-- data-test 与禁用态挂在外层容器上，作为语音区整体状态钩子；
                 麦克风拒绝由 VoiceInputButton 的 emit 处理。 -->
            <div
              class="ai-companion-voice"
              data-test="ai-companion-voice"
              role="group"
              aria-label="语音提问"
              :aria-disabled="voiceDisabled"
              :disabled="voiceDisabled ? '' : null"
            >
              <VoiceInputButton
                :recording="companion.recording"
                :disabled="voiceDisabled"
                @update:recording="handleRecordingChange"
                @recorded="handleRecorded"
                @permission-denied="handlePermissionDenied"
              />
            </div>
            <button
              type="submit"
              class="ai-companion-composer-submit"
              data-test="ai-companion-submit"
              :disabled="!canSubmit"
            >
              <Send :size="16" aria-hidden="true" />
              发送
            </button>
          </div>
        </form>
      </slot>
    </footer>
  </section>
</template>

<style scoped>
.ai-companion-panel {
  position: fixed;
  right: 16px;
  bottom: 80px;
  z-index: 40;
  display: flex;
  flex-direction: column;
  width: min(420px, calc(100vw - 32px));
  /* 旧 Safari 不识别 svh，先给一条 vh 兜底，再用 svh 覆盖。 */
  height: min(680px, calc(100vh - 96px));
  height: min(680px, calc(100svh - 96px));
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  box-shadow: 0 18px 44px color-mix(in srgb, var(--ark-paper) 30%, transparent);
}

.ai-companion-panel:focus {
  outline: none;
}

.ai-companion-panel-header {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--ark-line);
}

.ai-companion-panel-title {
  margin: 0;
  font-size: 1.05rem;
  line-height: 1.3;
}

.ai-companion-panel-close {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 1px solid var(--ark-line);
  border-radius: var(--ark-radius);
  background: transparent;
  color: var(--ark-paper);
}

.ai-companion-panel-close:hover {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.ai-companion-panel-tabs {
  display: flex;
  flex: 0 0 auto;
  gap: 4px;
  padding: 8px 12px 0;
  border-bottom: 1px solid var(--ark-line);
}

.ai-companion-panel-tab {
  position: relative;
  padding: 8px 12px;
  border: 0;
  background: transparent;
  color: var(--ark-muted);
  font-size: 0.86rem;
  font-weight: 600;
  letter-spacing: 0;
}

.ai-companion-panel-tab:hover {
  color: var(--ark-paper);
}

.ai-companion-panel-tab[data-active='true'] {
  color: var(--ark-signal);
}

.ai-companion-panel-tab[data-active='true']::after {
  content: '';
  position: absolute;
  right: 12px;
  bottom: -1px;
  left: 12px;
  height: 2px;
  background: var(--ark-signal);
}

.ai-companion-panel-body {
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
}

.ai-companion-panel-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 14px 16px;
}

.ai-companion-panel-composer {
  flex: 0 0 auto;
  padding: 12px 16px 14px;
  border-top: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.ai-companion-empty {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.86rem;
  line-height: 1.6;
}

.ai-companion-messages {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.ai-companion-messages-item {
  display: block;
  min-width: 0;
}

.ai-companion-composer {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.ai-companion-composer-error {
  margin: 0;
  color: var(--ark-paper);
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.ai-companion-dialects {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  /* grid item 默认 min-width:auto 会把隐式轨道撑到 min-content；显式归零后
     轨道才收缩到面板内容宽，方言按钮按 flex-wrap 换行。 */
  min-width: 0;
}

.ai-companion-dialect {
  padding: 5px 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: transparent;
  color: var(--ark-muted);
  font-size: 0.78rem;
  font-weight: 600;
}

.ai-companion-dialect:hover {
  color: var(--ark-paper);
}

.ai-companion-dialect[data-active='true'] {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.ai-companion-composer-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  /* 同上：320px 下该行 min-content≈304 超过面板内容宽 254，不归零会把
     发送按钮推出视口右缘。 */
  min-width: 0;
}

.ai-companion-composer-input {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 72px;
  padding: 8px 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font: inherit;
  font-size: 0.86rem;
  line-height: 1.5;
  resize: vertical;
}

.ai-companion-voice {
  flex: 0 0 auto;
}

.ai-companion-composer-submit {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;
  height: 46px;
  padding: 0 14px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
  font-size: 0.84rem;
  font-weight: 600;
}

.ai-companion-composer-submit:disabled {
  border-color: var(--ark-line-strong);
  background: transparent;
  color: var(--ark-muted);
}

@media (min-width: 641px) {
  .ai-companion-panel {
    right: 24px;
    bottom: 96px;
  }
}
</style>
