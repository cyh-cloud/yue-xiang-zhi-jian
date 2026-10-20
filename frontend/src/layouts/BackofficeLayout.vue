<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";

import type { Role } from "@/api/types";
import SharedMessageCenter from "@/components/message-center/SharedMessageCenter.vue";
import { usePreferences } from "@/shared/preferences";
import { ROLE_FACTS } from "@/shared/roles";
import { useSessionStore } from "@/stores/session";

type BackofficeRole = Exclude<Role, "student">;

interface NavItem {
  label: string;
  to: string;
  icon: string;
  capability?: string;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

interface RoleConfig {
  label: string;
  title: string;
  groups: NavGroup[];
}

const ROLE_CONFIG: Record<BackofficeRole, RoleConfig> = {
  teacher: {
    label: ROLE_FACTS.teacher.label,
    title: ROLE_FACTS.teacher.backofficeTitle,
    groups: [
      {
        label: "教学工作",
        items: [
          { label: "工作台", to: "/teacher/dashboard", icon: "fa-gauge-high" },
          {
            label: "通知公告",
            to: "/teacher/announcements",
            icon: "fa-bullhorn",
          },
          {
            label: "学情分析",
            to: "/teacher/analytics",
            icon: "fa-chart-column",
          },
          {
            label: "实训提交",
            to: "/teacher/trainings",
            icon: "fa-clipboard-check",
          },
          { label: "3D 模型", to: "/teacher/models", icon: "fa-cube" },
        ],
      },
    ],
  },
  government: {
    label: ROLE_FACTS.government.backofficeLabel ?? ROLE_FACTS.government.label,
    title: ROLE_FACTS.government.backofficeTitle,
    groups: [
      {
        label: "政务管理",
        items: [
          {
            label: "数据大屏",
            to: "/government/dashboard",
            icon: "fa-chart-pie",
          },
          {
            label: "政策管理",
            to: "/government/policies",
            icon: "fa-file-lines",
            capability: "policy.manage",
          },
          {
            label: "发布政策",
            to: "/government/publish",
            icon: "fa-circle-plus",
            capability: "policy.manage",
          },
        ],
      },
    ],
  },
  enterprise: {
    label: ROLE_FACTS.enterprise.label,
    title: ROLE_FACTS.enterprise.backofficeTitle,
    groups: [
      {
        label: "招聘管理",
        items: [
          {
            label: "工作台",
            to: "/enterprise/dashboard",
            icon: "fa-gauge-high",
          },
          {
            label: "职位管理",
            to: "/enterprise/jobs",
            icon: "fa-briefcase",
            capability: "job.manage",
          },
          {
            label: "简历管理",
            to: "/enterprise/applications",
            icon: "fa-file-lines",
            capability: "job.manage",
          },
        ],
      },
    ],
  },
  operator: {
    label: ROLE_FACTS.operator.label,
    title: ROLE_FACTS.operator.backofficeTitle,
    groups: [
      {
        label: "内容运营",
        items: [
          {
            label: "总览",
            to: "/operator/overview",
            icon: "fa-gauge-high",
          },
          {
            label: "农时日历",
            to: "/operator/farming",
            icon: "fa-seedling",
            capability: "farming.manage",
          },
          {
            label: "病虫害知识",
            to: "/operator/pest",
            icon: "fa-bug",
            capability: "pest.manage",
          },
          {
            label: "手工技艺",
            to: "/operator/crafts",
            icon: "fa-paintbrush",
            capability: "craft.content.manage",
          },
          {
            label: "方言知识",
            to: "/operator/dialects",
            icon: "fa-comments",
            capability: "dialect.manage",
          },
          {
            label: "招募公告",
            to: "/operator/recruitments",
            icon: "fa-bullhorn",
            capability: "recruit.manage",
          },
          {
            label: "成功案例",
            to: "/operator/cases",
            icon: "fa-trophy",
            capability: "case.manage",
          },
        ],
      },
    ],
  },
  super_admin: {
    label: ROLE_FACTS.super_admin.label,
    title: ROLE_FACTS.super_admin.backofficeTitle,
    groups: [
      {
        label: "系统管理",
        items: [
          {
            label: "仪表盘",
            to: "/admin/dashboard",
            icon: "fa-gauge-high",
          },
          {
            label: "用户管理",
            to: "/admin/users",
            icon: "fa-users",
            capability: "user.manage",
          },
          {
            label: "内容审核",
            to: "/admin/reviews",
            icon: "fa-circle-check",
            capability: "review.moderate",
          },
          {
            label: "系统公告",
            to: "/admin/announcements",
            icon: "fa-bullhorn",
            capability: "announcement.manage",
          },
          {
            label: "内容监管",
            to: "/admin/content",
            icon: "fa-shield-halved",
            capability: "community.manage",
          },
        ],
      },
    ],
  },
};

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const { theme, largeText, toggleTheme, toggleLargeText } = usePreferences();
const mainRef = ref<HTMLElement | null>(null);
const collapsed = ref(false);
const drawerOpen = ref(false);
const userMenuOpen = ref(false);
const connectionLost = ref(false);
const SIDEBAR_KEY = "yuexiang_backoffice_sidebar_collapsed";

function isBackofficeRole(value: Role | null | undefined): value is BackofficeRole {
  return Boolean(value && value !== "student");
}

const role = computed<BackofficeRole>(() => {
  const metaRole = route.meta.backofficeRole;
  if (metaRole) return metaRole;
  return isBackofficeRole(session.role) ? session.role : "teacher";
});
const config = computed(() => ROLE_CONFIG[role.value]);
const pageTitle = computed(() => route.meta.title || config.value.title);
const visibleGroups = computed(() =>
  config.value.groups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => !item.capability || session.can(item.capability),
      ),
    }))
    .filter((group) => group.items.length > 0),
);

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(`${path}/`);
}

function closeMenus(): void {
  drawerOpen.value = false;
  userMenuOpen.value = false;
}

function toggleSidebar(): void {
  collapsed.value = !collapsed.value;
  try {
    localStorage.setItem(SIDEBAR_KEY, collapsed.value ? "1" : "0");
  } catch {
    // Preferences remain usable when storage is unavailable.
  }
}

async function logout(): Promise<void> {
  await session.logout();
  closeMenus();
  await router.push("/login");
}

function handleDocumentClick(event: MouseEvent): void {
  const target = event.target;
  if (!(target instanceof Element)) return;
  if (!target.closest(".bo-user-menu")) userMenuOpen.value = false;
}

function setConnectionState(
  event: WindowEventMap["yuexiang:connection"],
): void {
  const detail = event.detail;
  connectionLost.value = Boolean(detail?.unavailable);
}

function enterMainContent(): void {
  if (window.matchMedia("(max-width: 1024px)").matches) {
    drawerOpen.value = false;
  }
  void nextTick(() => mainRef.value?.focus());
}

function handleShortcut(event: KeyboardEvent): void {
  if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "b") return;
  const target = event.target;
  if (
    target instanceof HTMLElement &&
    target.matches("input, textarea, select, [contenteditable='true']")
  ) {
    return;
  }
  event.preventDefault();
  toggleSidebar();
}

watch(
  () => route.fullPath,
  async () => {
    closeMenus();
    await nextTick();
    mainRef.value?.focus();
  },
);

onMounted(() => {
  try {
    collapsed.value = localStorage.getItem(SIDEBAR_KEY) === "1";
  } catch {
    collapsed.value = false;
  }
  document.addEventListener("click", handleDocumentClick);
  document.addEventListener("keydown", handleShortcut);
  window.addEventListener("yuexiang:connection", setConnectionState);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", handleDocumentClick);
  document.removeEventListener("keydown", handleShortcut);
  window.removeEventListener("yuexiang:connection", setConnectionState);
});
</script>

<template>
  <div
    class="bo-shell"
    :class="{ 'is-collapsed': collapsed }"
    :data-role="role"
    data-testid="backoffice-shell"
  >
    <a
      href="#backoffice-main"
      class="bo-skip-link"
      @click.prevent="enterMainContent"
    >跳转到主要内容</a>

    <header class="bo-topbar">
      <div class="bo-topbar-left">
        <button
          type="button"
          class="bo-sidebar-toggle"
          data-testid="backoffice-sidebar-toggle"
          :aria-label="collapsed ? '展开侧栏' : '收起侧栏'"
          :aria-expanded="!collapsed"
          :aria-controls="`backoffice-sidebar-${role}`"
          :title="collapsed ? '展开侧栏' : '收起侧栏'"
          @click="toggleSidebar"
        >
          <i
            class="fas fa-angles-left"
            aria-hidden="true"
          />
        </button>
        <RouterLink
          class="bo-brand"
          to="/"
          aria-label="粤乡智匠首页"
        >
          <span class="bo-brand-mark">
            <i
              class="fas fa-seedling"
              aria-hidden="true"
            />
          </span>
          <span>粤乡智匠</span>
        </RouterLink>
        <span
          class="bo-role-chip"
          data-testid="backoffice-role"
        >{{ config.label }}</span>
      </div>

      <div class="bo-topbar-actions">
        <SharedMessageCenter />
        <button
          type="button"
          class="icon-btn"
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
        <div class="bo-user-menu">
          <button
            type="button"
            class="bo-user-trigger"
            aria-label="打开用户菜单"
            :aria-expanded="userMenuOpen"
            @click.stop="userMenuOpen = !userMenuOpen"
          >
            <span class="bo-avatar">
              <i
                class="fas fa-user"
                aria-hidden="true"
              />
            </span>
            <span class="bo-user-copy">
              <strong>{{ session.user?.name || config.label }}</strong>
              <small>{{ config.label }}</small>
            </span>
            <i
              class="fas fa-chevron-down"
              aria-hidden="true"
            />
          </button>
          <div
            v-if="userMenuOpen"
            class="bo-user-dropdown"
          >
            <div class="bo-user-dropdown-head">
              <strong>{{ session.user?.name }}</strong>
              <span>{{ session.user?.id }}</span>
            </div>
            <button
              type="button"
              @click="logout"
            >
              <i
                class="fas fa-arrow-right-from-bracket"
                aria-hidden="true"
              />
              退出登录
            </button>
          </div>
        </div>
      </div>
    </header>

    <div class="bo-body">
      <button
        v-if="drawerOpen"
        type="button"
        class="bo-drawer-overlay"
        aria-label="关闭侧栏"
        @click="drawerOpen = false"
      />
      <aside
        :id="`backoffice-sidebar-${role}`"
        class="bo-sidebar"
        :class="{ open: drawerOpen }"
        data-testid="backoffice-sidebar"
      >
        <div class="bo-sidebar-head">
          <span class="bo-sidebar-mark">{{ config.label.slice(0, 1) }}</span>
          <span class="bo-sidebar-copy">
            <strong>{{ config.title }}</strong>
            <small>{{ session.user?.name }}</small>
          </span>
        </div>
        <nav
          class="bo-nav"
          aria-label="后台导航"
        >
          <section
            v-for="group in visibleGroups"
            :key="group.label"
            class="bo-nav-group"
          >
            <h2 class="bo-nav-group-title">
              {{ group.label }}
            </h2>
            <RouterLink
              v-for="item in group.items"
              :key="item.to"
              :to="item.to"
              class="bo-nav-link"
              :class="{ active: isActive(item.to) }"
              :aria-current="isActive(item.to) ? 'page' : undefined"
              :title="item.label"
              :data-tip="item.label"
            >
              <i
                class="fas"
                :class="item.icon"
                aria-hidden="true"
              />
              <span>{{ item.label }}</span>
            </RouterLink>
          </section>
        </nav>
        <div class="bo-sidebar-foot">
          <i
            class="fas fa-circle-nodes"
            aria-hidden="true"
          />
          <span>统一后台外壳</span>
        </div>
      </aside>

      <div class="bo-main">
        <div class="bo-mainbar">
          <div>
            <p>{{ config.label }}</p>
            <h2>{{ pageTitle }}</h2>
          </div>
          <span
            class="bo-connection"
            :class="{ 'is-offline': connectionLost }"
            data-testid="backoffice-connection"
            aria-live="polite"
          >
            <i
              class="fas fa-circle"
              aria-hidden="true"
            />
            {{ connectionLost ? "连接失败" : "已连接" }}
          </span>
        </div>
        <main
          id="backoffice-main"
          ref="mainRef"
          class="bo-content"
          data-testid="backoffice-main"
          tabindex="-1"
        >
          <RouterView />
        </main>
      </div>
    </div>
  </div>
</template>

<style src="../styles/backoffice.css"></style>
