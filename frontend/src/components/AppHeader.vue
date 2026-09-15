<script setup lang="ts">
import { LogIn, LogOut, Menu, RefreshCw, Sprout, UserPlus, X } from 'lucide-vue-next'

import { computed, ref } from 'vue'

import type { SnapshotSource } from '@/api/types'

import MessageBadge from './MessageBadge.vue'

const props = withDefaults(defineProps<{
  source: SnapshotSource
  loading: boolean
  userName?: string
  variant?: 'home' | 'auth'
  showAuthControls?: boolean
}>(), {
  variant: 'home',
  showAuthControls: true
})

const emit = defineEmits<{
  refresh: []
  logout: []
}>()

const sourceLabel: Record<SnapshotSource, string> = {
  live: 'Flask 已连接',
  mixed: '混合数据',
  mock: '示例数据'
}

const mobileNavOpen = ref(false)
const isAuthVariant = computed(() => props.variant === 'auth')

function closeMobileNav() {
  mobileNavOpen.value = false
}
</script>

<template>
  <header class="app-header">
    <div class="header-inner">
      <RouterLink class="brand" to="/" aria-label="粤乡智匠首页">
        <span class="brand-mark" aria-hidden="true">
          <Sprout :size="18" stroke-width="2" />
        </span>
        <span class="brand-copy">
          <strong>粤乡智匠</strong>
          <small>RURAL ARTISAN SYSTEM</small>
        </span>
      </RouterLink>

      <nav
        v-if="!isAuthVariant"
        id="module-navigation"
        class="header-nav"
        :class="{ 'mobile-open': mobileNavOpen }"
        aria-label="六大学习方向"
      >
        <a href="#module-agriculture" @click="closeMobileNav">农业技能</a>
        <a href="#module-ecommerce" @click="closeMobileNav">电商运营</a>
        <a href="#module-crafts" @click="closeMobileNav">手工传承</a>
        <a href="#module-simulation" @click="closeMobileNav">虚拟实训</a>
        <a href="#module-resources" @click="closeMobileNav">本土资源</a>
        <a href="#module-employment" @click="closeMobileNav">就业对接</a>
      </nav>

      <div class="header-actions">
        <span v-if="!isAuthVariant" class="source-pill" :data-source="source">
          <span aria-hidden="true"></span>
          {{ sourceLabel[source] }}
        </span>
        <button
          v-if="!isAuthVariant"
          class="icon-button"
          type="button"
          :disabled="loading"
          @click="emit('refresh')"
        >
          <RefreshCw :size="16" :class="{ spinning: loading }" aria-hidden="true" />
          <span class="ark-sr-only">刷新数据</span>
        </button>
        <button
          v-if="!isAuthVariant"
          class="icon-button nav-toggle"
          type="button"
          :aria-expanded="mobileNavOpen"
          aria-controls="module-navigation"
          @click="mobileNavOpen = !mobileNavOpen"
        >
          <X v-if="mobileNavOpen" :size="16" aria-hidden="true" />
          <Menu v-else :size="16" aria-hidden="true" />
          <span class="ark-sr-only">学习方向菜单</span>
        </button>
        <template v-if="showAuthControls && userName">
          <MessageBadge />
          <span class="user-chip">{{ userName }}</span>
          <button class="icon-button" type="button" @click="emit('logout')">
            <LogOut :size="16" aria-hidden="true" />
            <span class="ark-sr-only">退出登录</span>
          </button>
        </template>
        <template v-else-if="showAuthControls">
          <RouterLink class="ghost-button" to="/login">
            <LogIn :size="15" aria-hidden="true" />
            登录
          </RouterLink>
          <RouterLink class="primary-button" to="/register">
            <UserPlus :size="15" aria-hidden="true" />
            注册
          </RouterLink>
        </template>
      </div>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 30;
  border-bottom: 1px solid var(--ark-line);
  background: rgb(255 255 255 / 0.96);
  backdrop-filter: blur(12px);
}

.header-inner {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 18px;
  align-items: center;
  width: min(100%, var(--ark-shell-max));
  min-height: 72px;
  margin-inline: auto;
  padding: 10px 24px;
}

.app-header.auth-variant .header-inner {
  grid-template-columns: auto minmax(0, 1fr);
}

.app-header.auth-variant .header-actions {
  justify-content: flex-end;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--ark-paper);
  text-decoration: none;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-signal);
}

.brand-copy {
  display: grid;
}

.brand-copy strong {
  font-size: 1rem;
  line-height: 1.2;
}

.brand-copy small {
  color: var(--ark-muted);
  font-size: 0.63rem;
  line-height: 1.2;
}

.header-nav {
  display: flex;
  gap: 4px;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.nav-toggle {
  display: none;
}

.header-nav::-webkit-scrollbar {
  display: none;
}

.header-nav a {
  flex: 0 0 auto;
  padding: 8px 10px;
  color: var(--ark-muted);
  font-size: 0.86rem;
  text-decoration: none;
  border-bottom: 1px solid transparent;
}

.header-nav a:hover,
.header-nav a:focus-visible {
  color: var(--ark-paper);
  border-bottom-color: var(--ark-signal);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.source-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--ark-line);
  color: var(--ark-muted);
  font-size: 0.75rem;
  white-space: nowrap;
}

.source-pill span {
  width: 7px;
  height: 7px;
  background: var(--ark-muted);
}

.source-pill[data-source="live"] span {
  background: var(--ark-state);
}

.source-pill[data-source="mixed"] span,
.source-pill[data-source="mock"] span {
  background: var(--ark-signal);
}

.icon-button {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--ark-line);
  background: transparent;
  color: var(--ark-paper);
}

.icon-button:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.user-chip {
  display: inline-flex;
  align-items: center;
  height: 36px;
  max-width: 120px;
  padding: 0 10px;
  overflow: hidden;
  border: 1px solid var(--ark-line);
  color: var(--ark-paper);
  font-size: 0.8rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ghost-button,
.primary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
  font-size: 0.82rem;
  text-decoration: none;
}

.primary-button {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.ghost-button:hover,
.primary-button:hover {
  background: rgb(24 209 255 / 0.12);
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1180px) {
  .header-inner {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .header-actions {
    grid-column: 1 / -1;
    justify-content: space-between;
  }
}

@media (max-width: 640px) {
  .header-inner {
    grid-template-columns: minmax(0, 1fr) auto;
    min-height: 64px;
    padding: 10px 14px;
  }

  .brand-copy small {
    display: none;
  }

  .header-nav {
    display: none;
    flex-direction: column;
    gap: 0;
    grid-row: 2;
    grid-column: 1 / -1;
    overflow: visible;
    margin-inline: -14px;
    padding-inline: 14px;
    border-top: 1px solid var(--ark-line);
  }

  .header-nav.mobile-open {
    display: flex;
  }

  .header-nav a {
    display: flex;
    align-items: center;
    min-height: 44px;
    border-bottom: 1px solid var(--ark-line);
  }

  .header-nav a:last-child {
    border-bottom: 0;
  }

  .nav-toggle {
    display: grid;
  }

  .header-actions {
    grid-row: 1;
    grid-column: 2;
  }

  .source-pill,
  .user-chip {
    display: none;
  }
}
</style>
