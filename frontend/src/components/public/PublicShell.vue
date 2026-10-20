<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import SharedMessageCenter from "@/components/message-center/SharedMessageCenter.vue";
import { usePreferences } from "@/shared/preferences";
import { roleLabel as labelForRole } from "@/shared/roles";
import { useSessionStore } from "@/stores/session";

import CdnFallbackNotice from "./CdnFallbackNotice.vue";

const route = useRoute();
const session = useSessionStore();
const { theme, largeText, toggleTheme, toggleLargeText } = usePreferences();

const navItems = [
  { label: "农业技能", to: "/agriculture" },
  { label: "电商运营", to: "/ecommerce" },
  { label: "手工传承", to: "/crafts" },
  { label: "本土资源", to: "/resources" },
  { label: "就业对接", to: "/employment" },
] as const;

const menuOpen = ref(false);
const userMenuOpen = ref(false);

const roleLabel = computed(() =>
  session.role ? labelForRole(session.role) : "访客",
);
const loginTarget = computed(() =>
  route.path === "/"
    ? "/login"
    : {
        path: "/login",
        query: { redirect: route.fullPath },
      },
);

function isActive(path: string): boolean {
  if (path === "/resources" && route.path.startsWith("/case-detail/")) {
    return true;
  }
  return route.path === path || route.path.startsWith(`${path}/`);
}

function closeMenus(): void {
  menuOpen.value = false;
  userMenuOpen.value = false;
}

async function logout(): Promise<void> {
  await session.logout();
  closeMenus();
}

function handleDocumentClick(event: MouseEvent): void {
  const target = event.target;
  if (!(target instanceof Element)) return;
  if (!target.closest(".public-user-menu")) {
    userMenuOpen.value = false;
  }
}

watch(
  () => route.fullPath,
  () => closeMenus(),
);

onMounted(() => {
  document.addEventListener("click", handleDocumentClick);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", handleDocumentClick);
});
</script>

<template>
  <div class="public-shell">
    <a
      href="#main-content"
      class="skip-link"
    >跳转到主要内容</a>

    <nav
      class="navbar"
      aria-label="主导航"
    >
      <div class="nav-container">
        <RouterLink
          class="nav-brand"
          to="/"
          aria-label="粤乡智匠首页"
        >
          <span class="brand-logo">
            <i
              class="fas fa-seedling"
              aria-hidden="true"
            />
          </span>
          <span class="brand-name">粤乡智匠</span>
        </RouterLink>

        <button
          type="button"
          class="hamburger-btn"
          :class="{ open: menuOpen }"
          aria-label="打开导航菜单"
          :aria-expanded="menuOpen"
          @click="menuOpen = !menuOpen"
        >
          <span class="hamburger-line" />
          <span class="hamburger-line" />
          <span class="hamburger-line" />
        </button>

        <div
          class="nav-menu"
          :class="{ open: menuOpen }"
        >
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            class="nav-item"
            :class="{ active: isActive(item.to) }"
            :to="item.to"
            :aria-current="isActive(item.to) ? 'page' : undefined"
          >
            {{ item.label }}
          </RouterLink>
        </div>

        <div class="nav-actions">
          <SharedMessageCenter />

          <div
            v-if="session.isAuthenticated"
            class="user-info public-user-menu"
          >
            <button
              type="button"
              class="user-avatar-wrap public-user-trigger"
              aria-label="打开用户菜单"
              :aria-expanded="userMenuOpen"
              @click.stop="userMenuOpen = !userMenuOpen"
            >
              <span class="avatar-circle">
                <i
                  class="fas fa-user"
                  aria-hidden="true"
                />
              </span>
              <span class="user-meta">
                <span class="user-name">{{ session.user?.name }}</span>
                <span class="user-role">{{ roleLabel }}</span>
              </span>
              <i
                class="fas fa-chevron-down chevron"
                aria-hidden="true"
              />
            </button>
            <div
              v-if="userMenuOpen"
              class="dropdown-menu"
            >
              <div class="dropdown-header">
                <span class="dropdown-name">{{ session.user?.name }}</span>
                <span class="dropdown-email">{{ roleLabel }}</span>
              </div>
              <div class="dropdown-divider" />
              <RouterLink
                class="dropdown-item"
                :to="session.defaultPath"
              >
                <i
                  class="fas fa-gauge-high"
                  aria-hidden="true"
                />
                进入工作台
              </RouterLink>
              <button
                type="button"
                class="dropdown-item logout"
                @click="logout"
              >
                <i
                  class="fas fa-sign-out-alt"
                  aria-hidden="true"
                />
                退出登录
              </button>
            </div>
          </div>

          <RouterLink
            v-else
            class="btn btn-primary btn-sm nav-login"
            :to="loginTarget"
          >
            <i
              class="fas fa-sign-in-alt"
              aria-hidden="true"
            />
            登录
          </RouterLink>

          <span
            v-if="session.status === 'unavailable'"
            class="public-connection-state"
            role="status"
          >连接服务器失败</span>

          <button
            type="button"
            class="icon-btn large-text-toggle"
            aria-label="切换大字模式"
            :aria-pressed="largeText"
            title="大字模式"
            @click="toggleLargeText"
          >
            <i
              class="fas fa-text-height"
              aria-hidden="true"
            />
          </button>
          <button
            type="button"
            class="theme-toggle"
            aria-label="切换主题"
            :title="theme === 'dark' ? '切换为浅色主题' : '切换为深色主题'"
            @click="toggleTheme"
          >
            <i
              class="fas"
              :class="theme === 'dark' ? 'fa-sun' : 'fa-moon'"
              aria-hidden="true"
            />
          </button>
          <span
            class="connection-dot"
            aria-hidden="true"
          >
            <span
              class="dot"
              :class="{ connected: session.isAuthenticated }"
            />
          </span>
        </div>
      </div>
    </nav>

    <main
      id="main-content"
      class="main-content public-main"
      tabindex="-1"
    >
      <slot />
    </main>

    <footer class="footer">
      <div class="container">
        <div class="footer-content">
          <div class="footer-brand">
            <i
              class="fas fa-seedling"
              aria-hidden="true"
            />
            <span>粤乡智匠</span>
          </div>
          <p class="footer-text">
            AI驱动的农村人才赋能平台 &copy; 2024
          </p>
          <div class="footer-tech">
            <span>Flask</span>
            <span>SQLite</span>
            <span>SiliconFlow AI</span>
          </div>
        </div>
      </div>
    </footer>

    <CdnFallbackNotice />
  </div>
</template>
