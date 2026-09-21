<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { resolveCompanionJumpTarget } from '@/ai-companion/jumpTarget'
import type {
  AiCompanionMessage as CompanionMessage,
  UserRole
} from '@/api/types'

const props = defineProps<{
  message: CompanionMessage
  role: UserRole | null | undefined
}>()

const router = useRouter()

type TextBlock =
  | { kind: 'paragraph'; text: string }
  | { kind: 'list'; items: string[] }

// Only learning guidance is allowed to carry bullet lines; every other answer
// stays plain prose so no Markdown is ever interpreted.
const allowsBullets = computed(
  () =>
    props.message.role === 'assistant' &&
    props.message.intent === 'learning_question'
)

function parseBlocks(content: string, withBullets: boolean): TextBlock[] {
  const blocks: TextBlock[] = []
  let items: string[] = []

  const flushItems = () => {
    if (items.length > 0) {
      blocks.push({ kind: 'list', items })
      items = []
    }
  }

  for (const rawLine of content.split('\n')) {
    const line = rawLine.trim()
    if (!line) {
      flushItems()
      continue
    }
    if (withBullets && line.startsWith('- ')) {
      items.push(line.slice(2).trim())
      continue
    }
    flushItems()
    blocks.push({ kind: 'paragraph', text: line })
  }
  flushItems()

  return blocks
}

const blocks = computed(() =>
  parseBlocks(props.message.content, allowsBullets.value)
)

const jumpPath = computed<string | null>(() => {
  if (!router) {
    return null
  }
  if (props.message.role !== 'assistant') {
    return null
  }
  const intent = props.message.intent
  if (intent !== 'platform_usage' && intent !== 'learning_question') {
    return null
  }
  return resolveCompanionJumpTarget(
    router,
    props.role,
    props.message.jump_target
  )
})

function jumpToTarget() {
  if (jumpPath.value) {
    void router.push(jumpPath.value)
  }
}
</script>

<template>
  <article
    class="ai-companion-message"
    :class="`ai-companion-message--${message.role}`"
    :data-role="message.role"
    :data-intent="message.intent ?? undefined"
  >
    <p class="ai-companion-message-role">
      {{ message.role === 'user' ? '我' : 'AI 学伴' }}
    </p>
    <div class="ai-companion-message-body">
      <template v-for="(block, index) in blocks" :key="index">
        <p v-if="block.kind === 'paragraph'" class="ai-companion-message-text">
          {{ block.text }}
        </p>
        <ul v-else class="ai-companion-message-list">
          <li v-for="(item, index) in block.items" :key="`bullet-${index}`">
            {{ item }}
          </li>
        </ul>
      </template>
    </div>
    <button
      v-if="jumpPath"
      type="button"
      class="ai-companion-message-jump"
      data-test="ai-companion-jump"
      @click="jumpToTarget"
    >
      去查看
    </button>
  </article>
</template>

<style scoped>
.ai-companion-message {
  display: grid;
  gap: 6px;
  max-width: 92%;
  padding: 10px 12px;
  border: 1px solid var(--ark-line);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-1);
}

.ai-companion-message--user {
  justify-items: end;
  margin-left: auto;
  border-color: var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.ai-companion-message-role {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.72rem;
  font-weight: 600;
}

.ai-companion-message-body {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.ai-companion-message-text {
  margin: 0;
  font-size: 0.86rem;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.ai-companion-message-list {
  display: grid;
  gap: 4px;
  margin: 0;
  padding-left: 18px;
  font-size: 0.86rem;
  line-height: 1.6;
}

.ai-companion-message-jump {
  justify-self: start;
  padding: 4px 10px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: transparent;
  color: var(--ark-signal);
  font-size: 0.78rem;
  font-weight: 600;
}

.ai-companion-message-jump:hover {
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}
</style>
