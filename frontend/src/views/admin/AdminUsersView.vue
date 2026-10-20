<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type ComponentPublicInstance,
} from "vue";

import {
  deleteAdminUser,
  getAdminUsers,
  setAdminUserStatus,
  updateAdminUser,
  type AdminUser,
} from "@/api/admin";
import type { Role } from "@/api/types";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";
import { ROLE_OPTIONS, roleLabel } from "@/shared/roles";
import { useSessionStore } from "@/stores/session";

type FeedbackKind = "info" | "success" | "error";
type ConfirmKind = "suspend" | "activate" | "delete";

interface EditorState {
  user: AdminUser;
  name: string;
  role: Role;
  status: "active" | "suspended";
  phone: string;
  email: string;
}

interface ConfirmState {
  kind: ConfirmKind;
  user: AdminUser;
}

const session = useSessionStore();
const users = ref<AdminUser[]>([]);
const search = ref("");
const roleFilter = ref("");
const loading = ref(true);
const loadError = ref("");
const feedback = ref<{ kind: FeedbackKind; message: string } | null>(null);
const editor = ref<EditorState | null>(null);
const editorError = ref("");
const saving = ref(false);
const confirmState = ref<ConfirmState | null>(null);
const confirming = ref(false);
const editorForm = ref<HTMLFormElement | null>(null);
const confirmDialog = ref<HTMLElement | null>(null);
const editorNameInput = ref<HTMLInputElement | null>(null);
const confirmCancelButton = ref<HTMLButtonElement | null>(null);
const editTrigger = ref<HTMLButtonElement | null>(null);
const statusTrigger = ref<HTMLButtonElement | null>(null);
let searchTimer: number | undefined;
let loadSequence = 0;

const editorTitle = computed(() =>
  editor.value ? `编辑用户：${editor.value.user.username}` : "编辑用户",
);
const confirmMessage = computed(() => {
  const current = confirmState.value;
  if (!current) return "";
  if (current.kind === "delete") {
    return `确定删除账号「${current.user.username}」？此操作不可恢复。`;
  }
  if (current.kind === "suspend") {
    return `确定停用「${current.user.username}」？停用后本人无法登录，历史数据会完整保留，可随时启用恢复。`;
  }
  return `确定启用「${current.user.username}」？启用后该账号可以重新登录。`;
});
const confirmLabel = computed(() => {
  if (confirmState.value?.kind === "delete") return "确认删除";
  if (confirmState.value?.kind === "suspend") return "确认停用";
  return "确认启用";
});

function statusLabel(status: string): string {
  return status === "suspended" ? "已停用" : "正常";
}

function relationSummary(user: AdminUser): string {
  return user.relations
    .map((relation) => `${relation.label} ${relation.count} 条`)
    .join("、");
}

function showFeedback(kind: FeedbackKind, message: string): void {
  feedback.value = { kind, message };
}

async function loadUsers(): Promise<void> {
  const sequence = ++loadSequence;
  loading.value = true;
  loadError.value = "";
  try {
    const nextUsers = await getAdminUsers({
      search: search.value.trim(),
      role: roleFilter.value,
    });
    if (sequence === loadSequence) users.value = nextUsers;
  } catch (requestError) {
    if (sequence !== loadSequence) return;
    users.value = [];
    loadError.value =
      requestError instanceof Error ? requestError.message : "用户列表加载失败";
  } finally {
    if (sequence === loadSequence) loading.value = false;
  }
}

function openEditor(user: AdminUser): void {
  editorError.value = "";
  editTrigger.value = document.activeElement instanceof HTMLButtonElement
    ? document.activeElement
    : null;
  editor.value = {
    user,
    name: user.name,
    role: user.role,
    // The backend rejects suspending the current account; keep the editor
    // from offering a state transition that the API must refuse.
    status:
      user.username === session.user?.id
        ? "active"
        : user.status === "suspended"
          ? "suspended"
          : "active",
    phone: user.phone || "",
    email: user.email || "",
  };
  void nextTick(() => editorNameInput.value?.focus());
}

function closeEditor(): void {
  if (saving.value) return;
  const trigger = editTrigger.value;
  editTrigger.value = null;
  editor.value = null;
  editorError.value = "";
  trigger?.focus();
}

async function saveEditor(): Promise<void> {
  const current = editor.value;
  if (!current) return;
  editorError.value = "";
  saving.value = true;
  try {
    const response = await updateAdminUser(current.user.username, {
      name: current.name.trim(),
      role: current.role,
      status: current.status,
      phone: current.phone.trim(),
      email: current.email.trim(),
    });
    showFeedback("success", response.message);
    editor.value = null;
    await loadUsers();
  } catch (requestError) {
    editorError.value =
      requestError instanceof Error ? requestError.message : "更新失败";
  } finally {
    saving.value = false;
  }
}

function askStatusChange(user: AdminUser): void {
  statusTrigger.value = document.activeElement instanceof HTMLButtonElement
    ? document.activeElement
    : null;
  confirmState.value = {
    kind: user.status === "suspended" ? "activate" : "suspend",
    user,
  };
  void nextTick(() => confirmCancelButton.value?.focus());
}

function askDelete(user: AdminUser): void {
  statusTrigger.value = document.activeElement instanceof HTMLButtonElement
    ? document.activeElement
    : null;
  confirmState.value = { kind: "delete", user };
  void nextTick(() => confirmCancelButton.value?.focus());
}

function closeConfirm(): void {
  if (confirming.value) return;
  const trigger = statusTrigger.value;
  statusTrigger.value = null;
  confirmState.value = null;
  trigger?.focus();
}

async function confirmOperation(): Promise<void> {
  const current = confirmState.value;
  if (!current) return;
  confirming.value = true;
  try {
    if (current.kind === "delete") {
      const response = await deleteAdminUser(current.user.username);
      showFeedback("success", response.message);
    } else {
      const response = await setAdminUserStatus(
        current.user.username,
        current.kind === "suspend" ? "suspended" : "active",
      );
      showFeedback("success", response.message);
    }
    confirmState.value = null;
    await loadUsers();
  } catch (requestError) {
    showFeedback(
      "error",
      requestError instanceof Error ? requestError.message : "操作失败，请重试",
    );
    confirmState.value = null;
  } finally {
    confirming.value = false;
  }
}

watch(search, () => {
  if (searchTimer !== undefined) window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    void loadUsers();
  }, 220);
});

watch(roleFilter, () => {
  void loadUsers();
});

function focusableElements(root: HTMLElement): HTMLElement[] {
  return Array.from(
    root.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => element.getClientRects().length > 0);
}

function trapTab(event: KeyboardEvent, root: HTMLElement | null): void {
  if (event.key !== "Tab" || !root) return;
  const focusable = focusableElements(root);
  if (!focusable.length) {
    event.preventDefault();
    root.focus();
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (!first || !last) return;
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function handleModalKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    event.preventDefault();
    if (editor.value && !saving.value) closeEditor();
    else if (confirmState.value && !confirming.value) closeConfirm();
    return;
  }
  if (editor.value) trapTab(event, editorForm.value);
  else if (confirmState.value) trapTab(event, confirmDialog.value);
}

function setEditorForm(element: Element | ComponentPublicInstance | null): void {
  editorForm.value = element instanceof HTMLFormElement ? element : null;
}

function setConfirmDialog(element: Element | ComponentPublicInstance | null): void {
  confirmDialog.value = element instanceof HTMLElement ? element : null;
}

onMounted(() => {
  document.addEventListener("keydown", handleModalKeydown);
  void loadUsers();
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", handleModalKeydown);
  if (searchTimer !== undefined) window.clearTimeout(searchTimer);
});

</script>

<template>
  <section class="backoffice-page">
    <header class="backoffice-page-header">
      <div>
        <p>平台治理</p>
        <h1 data-testid="backoffice-page-title">
          用户管理
        </h1>
        <span>编辑账号资料与角色，停用、恢复或删除用户。</span>
      </div>
      <button
        type="button"
        class="backoffice-button is-secondary"
        :disabled="loading"
        @click="loadUsers"
      >
        <i
          class="fas fa-rotate"
          :class="{ 'fa-spin': loading }"
          aria-hidden="true"
        />
        刷新
      </button>
    </header>

    <BackofficeFeedback
      v-if="feedback"
      :kind="feedback.kind"
      :message="feedback.message"
      testid="admin-users-feedback"
    />

    <BackofficeCard flush>
      <div class="backoffice-filterbar">
        <label class="backoffice-field backoffice-search-field">
          <span>搜索用户</span>
          <input
            v-model="search"
            type="search"
            placeholder="用户名或姓名"
            autocomplete="off"
          >
        </label>
        <label class="backoffice-field">
          <span>筛选角色</span>
          <select v-model="roleFilter">
            <option value="">
              全部角色
            </option>
            <option
              v-for="option in ROLE_OPTIONS"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>
      </div>

      <BackofficeState
        v-if="loading"
        kind="loading"
        title="正在加载用户"
      />
      <BackofficeState
        v-else-if="loadError"
        kind="error"
        title="用户列表加载失败"
        :detail="loadError"
      >
        <button
          type="button"
          class="backoffice-button"
          @click="loadUsers"
        >
          重试
        </button>
      </BackofficeState>
      <BackofficeState
        v-else-if="!users.length"
        kind="empty"
        title="没有匹配的用户"
        detail="调整搜索词或角色筛选后重试。"
      />
      <div
        v-else
        class="backoffice-table-wrap"
      >
        <table class="backoffice-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>姓名</th>
              <th>角色</th>
              <th>状态</th>
              <th>关联数据</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="user in users"
              :key="user.username"
              data-testid="admin-user-row"
              :data-username="user.username"
            >
              <td>
                <strong>{{ user.username }}</strong>
                <small>{{ user.created_at }}</small>
              </td>
              <td>{{ user.name }}</td>
              <td>{{ roleLabel(user.role) }}</td>
              <td>
                <span
                  class="backoffice-status"
                  :class="user.status === 'suspended' ? 'is-suspended' : 'is-active'"
                >
                  {{ statusLabel(user.status) }}
                </span>
              </td>
              <td>
                <span
                  v-if="user.relation_count"
                  :title="relationSummary(user)"
                >
                  {{ user.relation_count }} 条
                </span>
                <span
                  v-else
                  class="backoffice-muted"
                >无</span>
              </td>
              <td>
                <div class="backoffice-row-actions">
                  <button
                    type="button"
                    class="backoffice-button is-small"
                    data-testid="admin-user-edit"
                    @click="openEditor(user)"
                  >
                    编辑
                  </button>
                  <button
                    v-if="user.can_suspend"
                    type="button"
                    class="backoffice-button is-small"
                    :class="user.status === 'suspended' ? 'is-success' : 'is-secondary'"
                    data-testid="admin-user-status"
                    @click="askStatusChange(user)"
                  >
                    {{ user.status === "suspended" ? "启用" : "停用" }}
                  </button>
                  <button
                    v-if="user.can_delete"
                    type="button"
                    class="backoffice-button is-small is-danger"
                    data-testid="admin-user-delete"
                    @click="askDelete(user)"
                  >
                    删除
                  </button>
                  <span
                    v-else-if="user.block_reason"
                    class="backoffice-protection"
                    data-testid="admin-user-protection"
                  >
                    {{ user.block_reason }}
                  </span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </BackofficeCard>

    <Teleport to="body">
      <div
        v-if="editor"
        class="backoffice-modal-overlay"
        @click.self="closeEditor"
      >
        <form
          ref="setEditorForm"
          class="backoffice-modal"
          data-testid="admin-user-editor"
          role="dialog"
          aria-modal="true"
          :aria-label="editorTitle"
          @submit.prevent="saveEditor"
        >
          <header class="backoffice-modal-head">
            <div>
              <p>账号资料</p>
              <h2>{{ editorTitle }}</h2>
            </div>
            <button
              type="button"
              class="backoffice-icon-button"
              aria-label="关闭"
              @click="closeEditor"
            >
              <i
                class="fas fa-xmark"
                aria-hidden="true"
              />
            </button>
          </header>
          <div class="backoffice-modal-body">
            <BackofficeFeedback
              v-if="editorError"
              kind="error"
              :message="editorError"
              testid="admin-user-editor-error"
            />
            <label class="backoffice-field">
              <span>姓名</span>
              <input
                ref="editorNameInput"
                v-model="editor.name"
                required
                autocomplete="off"
              >
            </label>
            <div class="backoffice-form-grid">
              <label class="backoffice-field">
                <span>角色</span>
                <select v-model="editor.role">
                  <option
                    v-for="option in ROLE_OPTIONS"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </label>
              <label class="backoffice-field">
                <span>状态</span>
                <select
                  v-model="editor.status"
                  :disabled="editor.user.username === session.user?.id"
                >
                  <option value="active">
                    正常
                  </option>
                  <option value="suspended">
                    已停用
                  </option>
                </select>
                <small
                  v-if="editor.user.username === session.user?.id"
                  class="backoffice-muted"
                >
                  当前登录账号不能停用自己
                </small>
              </label>
            </div>
            <label class="backoffice-field">
              <span>手机</span>
              <input
                v-model="editor.phone"
                autocomplete="off"
              >
            </label>
            <label class="backoffice-field">
              <span>邮箱</span>
              <input
                v-model="editor.email"
                type="email"
                autocomplete="off"
              >
            </label>
          </div>
          <footer class="backoffice-modal-actions">
            <button
              type="button"
              class="backoffice-button is-secondary"
              :disabled="saving"
              @click="closeEditor"
            >
              取消
            </button>
            <button
              type="submit"
              class="backoffice-button"
              :disabled="saving"
            >
              {{ saving ? "保存中..." : "保存" }}
            </button>
          </footer>
        </form>
      </div>

      <div
        v-if="confirmState"
        class="backoffice-modal-overlay"
        @click.self="closeConfirm"
      >
        <div
          ref="setConfirmDialog"
          class="backoffice-modal is-confirm"
          data-testid="admin-confirm-dialog"
          role="dialog"
          aria-modal="true"
          :aria-label="confirmLabel"
          tabindex="-1"
        >
          <header class="backoffice-modal-head">
            <div>
              <p>安全确认</p>
              <h2>{{ confirmLabel }}</h2>
            </div>
          </header>
          <div class="backoffice-modal-body">
            <p class="backoffice-confirm-copy">
              {{ confirmMessage }}
            </p>
          </div>
          <footer class="backoffice-modal-actions">
            <button
              ref="confirmCancelButton"
              type="button"
              class="backoffice-button is-secondary"
              :disabled="confirming"
              @click="closeConfirm"
            >
              取消
            </button>
            <button
              type="button"
              class="backoffice-button"
              :class="confirmState.kind === 'delete' ? 'is-danger' : ''"
              :disabled="confirming"
              @click="confirmOperation"
            >
              {{ confirming ? "处理中..." : confirmLabel }}
            </button>
          </footer>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style src="./admin.css"></style>
