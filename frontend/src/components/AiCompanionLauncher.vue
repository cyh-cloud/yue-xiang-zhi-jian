<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next'
import { computed } from 'vue'

import { canUseAiCompanion } from '@/ai-companion/jumpTarget'
import { useAiCompanionStore } from '@/stores/aiCompanion'
import { useAuthStore } from '@/stores/auth'

import AiCompanionPanel from './AiCompanionPanel.vue'

const auth = useAuthStore()
const companion = useAiCompanionStore()

// Visibility is derived only from the authenticated user's role. It never
// reads the current route, its name/path, or route meta.roles (SC-002).
const canSeeLauncher = computed(
  () => auth.isAuthenticated && canUseAiCompanion(auth.user?.role)
)

function openPanel() {
  companion.open()
}

function closePanel() {
  companion.close()
}
</script>

<template>
  <template v-if="canSeeLauncher">
    <button
      type="button"
      class="ai-companion-launcher"
      data-test="ai-companion-launcher"
      aria-label="打开 AI 学伴"
      @click="openPanel"
    >
      <Sparkles class="ai-companion-launcher-icon" :size="20" aria-hidden="true" />
      <span class="ai-companion-launcher-label">打开 AI 学伴</span>
    </button>
    <AiCompanionPanel v-if="companion.panelOpen" @close="closePanel" />
  </template>
</template>

<style scoped>
.ai-companion-launcher {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 40;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 56px;
  padding: 0 18px;
  border: 1px solid var(--ark-signal);
  border-radius: 999px;
  background: var(--ark-signal);
  color: var(--ark-surface-0);
  font-size: 0.9rem;
  font-weight: 600;
  letter-spacing: 0;
  box-shadow: 0 10px 26px color-mix(in srgb, var(--ark-paper) 26%, transparent);
  transition:
    transform var(--ark-transition),
    box-shadow var(--ark-transition);
}

.ai-companion-launcher:hover {
  box-shadow: 0 12px 30px color-mix(in srgb, var(--ark-paper) 32%, transparent);
  transform: translateY(-1px);
}

.ai-companion-launcher-icon {
  flex: 0 0 auto;
}

.ai-companion-launcher-label {
  white-space: nowrap;
}

@media (min-width: 641px) {
  .ai-companion-launcher {
    right: 24px;
    bottom: 24px;
    height: 60px;
    padding: 0 22px;
  }
}
</style>
