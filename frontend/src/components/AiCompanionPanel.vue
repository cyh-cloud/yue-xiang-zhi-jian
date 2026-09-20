<script setup lang="ts">
import { X } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'

type PanelView = 'chat' | 'history'

const emit = defineEmits<{
  close: []
}>()

const rootRef = ref<HTMLElement | null>(null)
const activeView = ref<PanelView>('chat')

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

    <div class="ai-companion-panel-tabs" role="tablist" aria-label="AI 学伴视图">
      <button
        type="button"
        role="tab"
        class="ai-companion-panel-tab"
        :aria-selected="activeView === 'chat'"
        :data-active="activeView === 'chat'"
        @click="activeView = 'chat'"
      >
        对话
      </button>
      <button
        type="button"
        role="tab"
        class="ai-companion-panel-tab"
        :aria-selected="activeView === 'history'"
        :data-active="activeView === 'history'"
        @click="activeView = 'history'"
      >
        历史会话
      </button>
    </div>

    <div class="ai-companion-panel-body">
      <div
        v-if="activeView === 'chat'"
        class="ai-companion-panel-scroll"
        data-test="ai-companion-chat-region"
      >
        <slot name="chat" />
      </div>
      <div
        v-else
        class="ai-companion-panel-scroll"
        data-test="ai-companion-history-region"
      >
        <slot name="history" />
      </div>
    </div>

    <footer class="ai-companion-panel-composer">
      <slot name="composer" />
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

@media (min-width: 641px) {
  .ai-companion-panel {
    right: 24px;
    bottom: 96px;
  }
}
</style>
