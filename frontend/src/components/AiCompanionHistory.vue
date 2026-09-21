<script setup lang="ts">
import { computed } from 'vue'

import type { AiCompanionIntent } from '@/api/types'
import { useAiCompanionStore } from '@/stores/aiCompanion'

const companion = useAiCompanionStore()

const INTENT_LABELS: Record<AiCompanionIntent, string> = {
  platform_usage: '平台使用',
  learning_question: '学习提问',
  out_of_scope: '范围外'
}

const updatedFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23'
})

// 列表顺序直接沿用服务端返回顺序（updated_at 倒序，稳定 ID 兜底）。
const conversations = computed(() => companion.conversations)
const hasConversations = computed(() => conversations.value.length > 0)

function formatUpdated(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  const parts = Object.fromEntries(
    updatedFormatter
      .formatToParts(date)
      .filter(part => part.type !== 'literal')
      .map(part => [part.type, part.value])
  )
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`
}

function intentLabel(intent: AiCompanionIntent): string {
  return INTENT_LABELS[intent] ?? intent
}

async function selectConversation(conversationId: string) {
  const messages = await companion.openConversation(conversationId)
  // openConversation 失败时会写 error 并原样返回既有消息；此时留在历史态，
  // 让用户继续看到列表与失败提示，而不是被一篇旧会话顶掉。
  if (messages.length > 0 && !companion.error) {
    companion.activeView = 'chat'
  }
}
</script>

<template>
  <div class="ai-companion-history" data-test="ai-companion-history">
    <p
      v-if="companion.loadingHistory"
      class="ai-companion-history-state"
      role="status"
    >
      正在加载历史会话
    </p>
    <div
      v-else-if="companion.historyError"
      class="ai-companion-history-state ai-companion-history-state--error"
      role="alert"
    >
      {{ companion.historyError }}
    </div>
    <p v-else-if="!hasConversations" class="ai-companion-history-state">
      暂无历史会话
    </p>
    <ul v-else class="ai-companion-history-list">
      <li
        v-for="item in conversations"
        :key="item.conversation_id"
        class="ai-companion-history-item-cell"
      >
        <button
          type="button"
          class="ai-companion-history-item"
          data-test="ai-companion-history-item"
          @click="selectConversation(item.conversation_id)"
        >
          <span class="ai-companion-history-item-title">{{ item.title }}</span>
          <span class="ai-companion-history-item-meta">
            <span class="ai-companion-history-item-intent">
              {{ intentLabel(item.last_intent) }}
            </span>
            <time
              :datetime="item.updated_at"
              class="ai-companion-history-item-updated"
            >
              {{ formatUpdated(item.updated_at) }}
            </time>
          </span>
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.ai-companion-history {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.ai-companion-history-state {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.86rem;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.ai-companion-history-state--error {
  padding: 8px 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.ai-companion-history-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.ai-companion-history-item-cell {
  display: block;
  min-width: 0;
}

.ai-companion-history-item {
  display: grid;
  gap: 6px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--ark-line);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  text-align: left;
}

.ai-companion-history-item:hover {
  border-color: var(--ark-signal);
}

.ai-companion-history-item-title {
  font-size: 0.88rem;
  font-weight: 600;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.ai-companion-history-item-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.ai-companion-history-item-intent {
  padding: 2px 8px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  font-weight: 600;
}

.ai-companion-history-item-updated {
  font-variant-numeric: tabular-nums;
}
</style>
