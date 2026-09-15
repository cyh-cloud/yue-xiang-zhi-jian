<script setup lang="ts">
import { Mail } from 'lucide-vue-next'
import { computed, onMounted } from 'vue'

import { useMessageStore } from '@/stores/messages'

const store = useMessageStore()

const badgeText = computed(() =>
  store.summary.unread_total > 99
    ? '99+'
    : String(store.summary.unread_total)
)
const accessibleLabel = computed(
  () => `消息中心，未读 ${store.summary.unread_total} 条`
)

onMounted(() => {
  void store.loadSummary().catch(() => undefined)
})
</script>

<template>
  <RouterLink
    class="message-badge"
    to="/messages"
    :aria-label="accessibleLabel"
  >
    <Mail :size="17" aria-hidden="true" />
    <span
      v-if="store.summary.unread_total > 0"
      class="message-badge-count"
      aria-hidden="true"
    >
      {{ badgeText }}
    </span>
  </RouterLink>
</template>

<style scoped>
.message-badge {
  position: relative;
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--ark-line);
  color: var(--ark-paper);
  text-decoration: none;
}

.message-badge:hover,
.message-badge:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.message-badge-count {
  position: absolute;
  top: -7px;
  right: -7px;
  display: grid;
  place-items: center;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  border: 1px solid #fff;
  border-radius: 9px;
  background: var(--ark-signal);
  color: #fff;
  font-size: 0.64rem;
  font-weight: 700;
  line-height: 1;
}
</style>
