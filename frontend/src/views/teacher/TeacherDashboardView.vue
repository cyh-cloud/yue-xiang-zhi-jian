<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";

import { ApiError } from "@/api/client";
import {
  addTeacherStudent,
  deleteTeacherStudent,
  generateTeacherReport,
  getLinkableAccounts,
  getTeacherStats,
  getTeacherStudent,
  getTeacherStudents,
  linkTeacherStudent,
  updateTeacherStudent,
  type LinkableAccount,
  type TeacherReport,
  type TeacherStats,
  type TeacherStudent,
} from "@/api/teacher";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

type FeedbackKind = "info" | "success" | "error";
type AccountMode = "link" | "create" | "none";

interface AddForm {
  name: string;
  className: string;
  direction: string;
  accountMode: AccountMode;
  linkUsername: string;
  newUsername: string;
  newPassword: string;
}

interface EditForm {
  id: string;
  name: string;
  className: string;
  direction: string;
  status: "active" | "suspended";
  currentAccount: string;
  linkUsername: string;
}

const DIRECTIONS = ["荔枝种植", "电商运营", "广绣工艺", "水产养殖"];
const SUGGESTIONS = [
  "帮我做一份学员学习总结",
  "分析进度滞后的学员并给出干预建议",
  "对比各方向的教学效果",
  "哪些学员有掉队风险？",
];

const stats = ref<TeacherStats | null>(null);
const students = ref<TeacherStudent[]>([]);
const loading = ref(true);
const rosterLoading = ref(true);
const dashboardError = ref("");
const rosterError = ref("");
const feedback = ref<{ kind: FeedbackKind; message: string } | null>(null);
const search = ref("");
const linkableAccounts = ref<LinkableAccount[]>([]);
const accountsError = ref("");
const addOpen = ref(false);
const editOpen = ref(false);
const detailOpen = ref(false);
const deleteTarget = ref<TeacherStudent | null>(null);
const detailStudent = ref<TeacherStudent | null>(null);
const detailLoading = ref(false);
const editorSaving = ref(false);
const deleting = ref(false);
const editorError = ref("");
const addForm = ref<AddForm>(newAddForm());
const editForm = ref<EditForm | null>(null);
const addNameInput = ref<HTMLInputElement | null>(null);
const editNameInput = ref<HTMLInputElement | null>(null);
const reportPrompt = ref("");
const report = ref<TeacherReport | null>(null);
const reportLoading = ref(false);
const reportError = ref("");
const reportDegradedText = computed(() => {
  if (!report.value?.degraded) return "";
  return report.value.degraded_reason === "no_roster_data"
    ? "当前没有名册数据，以下为平台生成的降级报告。"
    : "AI 服务暂时不可用，以下为平台生成的降级报告。";
});
let searchTimer: number | undefined;

const statCards = computed(() => {
  const value = stats.value;
  return [
    {
      label: "学员总数",
      value: value ? String(value.total_students) : "-",
      testid: "teacher-stat-total",
    },
    {
      label: "已获证书",
      value: value ? String(value.certificates_earned) : "-",
      testid: "teacher-stat-certificates",
    },
    {
      label: "学员获证率",
      value: value ? `${value.completion_rate}%` : "-",
      testid: "teacher-stat-completion",
    },
    {
      label: "平均完成度（证书）",
      value: value ? `${value.avg_score}%` : "-",
      testid: "teacher-stat-avg",
    },
  ];
});

const recentStudents = computed(() =>
  [...students.value]
    .sort((left, right) =>
      String(right.created_at || "").localeCompare(String(left.created_at || "")),
    )
    .slice(0, 5),
);

const addDirectionOptions = computed(() => {
  const options = [...DIRECTIONS];
  if (addForm.value.direction && !options.includes(addForm.value.direction)) {
    options.push(addForm.value.direction);
  }
  return options;
});

const editDirectionOptions = computed(() => {
  const current = editForm.value?.direction;
  const options = [...DIRECTIONS];
  if (current && !options.includes(current)) options.push(current);
  return options;
});

const editAccountOptions = computed(() => {
  const current = editForm.value?.currentAccount || "";
  return linkableAccounts.value.filter((account) => account.username !== current);
});

function newAddForm(): AddForm {
  return {
    name: "",
    className: "",
    direction: DIRECTIONS[0] ?? "",
    accountMode: "link",
    linkUsername: "",
    newUsername: "",
    newPassword: "",
  };
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

function showFeedback(kind: FeedbackKind, message: string): void {
  feedback.value = { kind, message };
}

async function loadStats(): Promise<void> {
  dashboardError.value = "";
  try {
    stats.value = await getTeacherStats();
  } catch (error) {
    stats.value = null;
    dashboardError.value = errorMessage(error, "教师统计加载失败");
  } finally {
    loading.value = false;
  }
}

async function loadStudents(): Promise<void> {
  rosterLoading.value = true;
  rosterError.value = "";
  try {
    students.value = await getTeacherStudents(search.value.trim());
  } catch (error) {
    students.value = [];
    rosterError.value = errorMessage(error, "学员名册加载失败");
  } finally {
    rosterLoading.value = false;
  }
}

async function loadDashboard(): Promise<void> {
  await Promise.all([loadStats(), loadStudents()]);
}

async function loadAccounts(): Promise<void> {
  accountsError.value = "";
  try {
    linkableAccounts.value = await getLinkableAccounts();
  } catch (error) {
    linkableAccounts.value = [];
    accountsError.value = errorMessage(error, "可关联账号加载失败");
  }
}

async function openAdd(): Promise<void> {
  addForm.value = newAddForm();
  editorError.value = "";
  addOpen.value = true;
  await loadAccounts();
  await nextTick();
  addNameInput.value?.focus();
}

function closeAdd(): void {
  if (editorSaving.value) return;
  addOpen.value = false;
  editorError.value = "";
}

async function submitAdd(): Promise<void> {
  const form = addForm.value;
  editorError.value = "";
  if (!form.name.trim()) {
    editorError.value = "请输入学员姓名";
    return;
  }
  if (form.accountMode === "link" && !form.linkUsername) {
    editorError.value = "请选择一个要关联的学员账号，或改选「暂不关联」";
    return;
  }
  if (form.accountMode === "create") {
    if (!form.newUsername.trim()) {
      editorError.value = "请输入用户名";
      return;
    }
    if (form.newPassword.trim().length < 6) {
      editorError.value = "初始密码至少 6 位";
      return;
    }
  }

  editorSaving.value = true;
  try {
    const response = await addTeacherStudent({
      name: form.name.trim(),
      class_name: form.className.trim(),
      direction: form.direction,
      ...(form.accountMode === "link"
        ? { link_username: form.linkUsername }
        : form.accountMode === "create"
          ? {
              new_username: form.newUsername.trim(),
              new_password: form.newPassword.trim(),
            }
          : {}),
    });
    addOpen.value = false;
    showFeedback("success", response.message || "添加成功");
    await loadDashboard();
  } catch (error) {
    editorError.value = errorMessage(error, "添加失败，请稍后重试");
  } finally {
    editorSaving.value = false;
  }
}

async function openEdit(studentId: string): Promise<void> {
  editorError.value = "";
  detailOpen.value = false;
  editOpen.value = true;
  try {
    const [student] = await Promise.all([
      getTeacherStudent(studentId),
      loadAccounts(),
    ]);
    editForm.value = {
      id: student.id,
      name: student.name,
      className: student.class_name || "",
      direction: student.direction || DIRECTIONS[0] || "",
      status: student.status === "suspended" ? "suspended" : "active",
      currentAccount: student.user_id || "",
      linkUsername: student.user_id || "",
    };
    await nextTick();
    editNameInput.value?.focus();
  } catch (error) {
    editOpen.value = false;
    showFeedback("error", errorMessage(error, "学员信息加载失败"));
  }
}

function closeEdit(): void {
  if (editorSaving.value) return;
  editOpen.value = false;
  editForm.value = null;
  editorError.value = "";
}

async function submitEdit(): Promise<void> {
  const form = editForm.value;
  if (!form) return;
  editorError.value = "";
  if (!form.name.trim()) {
    editorError.value = "请输入姓名";
    return;
  }
  editorSaving.value = true;
  try {
    await updateTeacherStudent(form.id, {
      name: form.name.trim(),
      class_name: form.className.trim(),
      direction: form.direction,
      status: form.status,
    });
    if (form.linkUsername !== form.currentAccount) {
      const linked = await linkTeacherStudent(form.id, form.linkUsername);
      showFeedback("success", linked.message || "已保存");
    } else {
      showFeedback("success", "已保存");
    }
    editOpen.value = false;
    editForm.value = null;
    await loadDashboard();
  } catch (error) {
    editorError.value = errorMessage(error, "更新失败，请稍后重试");
  } finally {
    editorSaving.value = false;
  }
}

async function openDetail(studentId: string): Promise<void> {
  detailLoading.value = true;
  detailOpen.value = true;
  detailStudent.value = null;
  try {
    detailStudent.value = await getTeacherStudent(studentId);
  } catch (error) {
    detailOpen.value = false;
    showFeedback("error", errorMessage(error, "学员详情加载失败"));
  } finally {
    detailLoading.value = false;
  }
}

function askDelete(student: TeacherStudent): void {
  deleteTarget.value = student;
}

function closeDelete(): void {
  if (deleting.value) return;
  deleteTarget.value = null;
}

async function confirmDelete(): Promise<void> {
  const target = deleteTarget.value;
  if (!target) return;
  deleting.value = true;
  try {
    const response = await deleteTeacherStudent(target.id);
    deleteTarget.value = null;
    showFeedback("success", response.message || "删除成功");
    await loadDashboard();
  } catch (error) {
    showFeedback("error", errorMessage(error, "删除失败，请稍后重试"));
  } finally {
    deleting.value = false;
  }
}

async function generateReport(): Promise<void> {
  reportError.value = "";
  if (!reportPrompt.value.trim()) {
    reportError.value = "请描述你想分析的内容";
    return;
  }
  reportLoading.value = true;
  report.value = null;
  try {
    report.value = await generateTeacherReport(reportPrompt.value.trim());
  } catch (error) {
    reportError.value = errorMessage(error, "报告生成失败，请稍后重试");
  } finally {
    reportLoading.value = false;
  }
}

function useSuggestion(suggestion: string): void {
  reportPrompt.value = suggestion;
}

watch(search, () => {
  if (searchTimer !== undefined) window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    void loadStudents();
  }, 220);
});

onMounted(() => {
  void loadDashboard();
});

onBeforeUnmount(() => {
  if (searchTimer !== undefined) window.clearTimeout(searchTimer);
});
</script>

<template>
  <section
    class="backoffice-page teacher-dashboard"
    data-testid="teacher-dashboard"
  >
    <header class="backoffice-page-header">
      <div>
        <p>教学工作</p>
        <h1>教师工作台</h1>
        <span>查看真实教学统计，维护学员名册并跟进学习进度。</span>
      </div>
      <button
        type="button"
        class="backoffice-button is-secondary"
        :disabled="loading || rosterLoading"
        @click="loadDashboard"
      >
        <i
          class="fas fa-rotate"
          :class="{ 'fa-spin': loading || rosterLoading }"
          aria-hidden="true"
        />
        刷新
      </button>
    </header>

    <BackofficeFeedback
      v-if="feedback"
      :kind="feedback.kind"
      :message="feedback.message"
      testid="teacher-dashboard-feedback"
    />

    <div
      class="backoffice-stat-grid teacher-stat-grid"
      data-testid="teacher-stat-grid"
    >
      <article
        v-for="card in statCards"
        :key="card.label"
        class="backoffice-stat-card"
        :data-testid="card.testid"
      >
        <strong>{{ card.value }}</strong>
        <span>{{ card.label }}</span>
      </article>
    </div>

    <BackofficeState
      v-if="dashboardError"
      kind="error"
      title="教师统计加载失败"
      :detail="dashboardError"
    >
      <button
        type="button"
        class="backoffice-button"
        @click="loadStats"
      >
        重试
      </button>
    </BackofficeState>

    <BackofficeCard
      title="学员管理"
      description="名册行与平台账号分开维护。未关联账号的学员无法登录，也收不到站内通知。"
    >
      <template #actions>
        <button
          type="button"
          class="backoffice-button"
          @click="openAdd"
        >
          <i
            class="fas fa-plus"
            aria-hidden="true"
          />
          添加学员
        </button>
      </template>

      <div class="backoffice-filterbar teacher-filterbar">
        <label class="backoffice-field backoffice-search-field">
          <span>搜索学员</span>
          <input
            v-model="search"
            type="search"
            placeholder="姓名、学号或方向"
            autocomplete="off"
          >
        </label>
        <span class="backoffice-muted">{{ students.length }} 人</span>
      </div>

      <BackofficeState
        v-if="rosterLoading"
        kind="loading"
        title="正在加载学员名册"
      />
      <BackofficeState
        v-else-if="rosterError"
        kind="error"
        title="学员名册加载失败"
        :detail="rosterError"
      >
        <button
          type="button"
          class="backoffice-button"
          @click="loadStudents"
        >
          重试
        </button>
      </BackofficeState>
      <BackofficeState
        v-else-if="!students.length"
        kind="empty"
        title="没有匹配的学员"
        :detail="search ? '调整搜索词后重试。' : '还没有添加学员。'"
      />
      <div
        v-else
        class="backoffice-table-wrap"
      >
        <table class="backoffice-table teacher-roster-table">
          <thead>
            <tr>
              <th>学号</th>
              <th>姓名</th>
              <th>学习方向</th>
              <th>完成度（证书）</th>
              <th>状态</th>
              <th>平台账号</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="student in students"
              :key="student.id"
              data-testid="teacher-student-row"
              :data-student-id="student.id"
            >
              <td>
                <code class="teacher-student-id">{{ student.id }}</code>
              </td>
              <td>
                <strong>{{ student.name }}</strong>
                <small v-if="student.class_name">{{ student.class_name }}</small>
              </td>
              <td>
                <span class="teacher-direction-tag">
                  {{ student.direction || "未分类" }}
                </span>
              </td>
              <td>
                <template v-if="student.has_cert_data">
                  <div class="teacher-progress">
                    <span class="teacher-progress-track">
                      <span
                        class="teacher-progress-fill"
                        :style="{ width: `${Math.max(0, Math.min(100, student.completion))}%` }"
                      />
                    </span>
                    <span>
                      {{ student.completion }}%（证书 {{ student.cert_earned }}/{{ student.cert_total }}）
                    </span>
                  </div>
                </template>
                <span
                  v-else
                  class="backoffice-muted"
                >
                  暂无证书记录{{ student.user_id ? "" : "（未关联账号）" }}
                </span>
              </td>
              <td>
                <span
                  class="backoffice-status"
                  :class="student.status === 'suspended' ? 'is-suspended' : 'is-active'"
                >
                  {{ student.status === "suspended" ? "停课" : "在读" }}
                </span>
              </td>
              <td>
                <template v-if="student.user_id">
                  <span class="backoffice-status is-active">已关联</span>
                  <small>{{ student.user_id }}</small>
                </template>
                <template v-else>
                  <span class="backoffice-status is-suspended">未关联</span>
                  <small>无法登录</small>
                </template>
              </td>
              <td>
                <div class="backoffice-row-actions">
                  <button
                    type="button"
                    class="backoffice-button is-small is-secondary"
                    data-testid="teacher-student-view"
                    @click="openDetail(student.id)"
                  >
                    查看
                  </button>
                  <button
                    type="button"
                    class="backoffice-button is-small"
                    data-testid="teacher-student-edit"
                    @click="openEdit(student.id)"
                  >
                    编辑
                  </button>
                  <button
                    type="button"
                    class="backoffice-button is-small is-danger"
                    data-testid="teacher-student-delete"
                    @click="askDelete(student)"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </BackofficeCard>

    <div class="teacher-dashboard-grid">
      <BackofficeCard
        title="AI 教学报告"
        description="AI 只根据当前名册与证书真实完成度生成报告。"
      >
        <label class="backoffice-field">
          <span>分析需求</span>
          <textarea
            v-model="reportPrompt"
            rows="4"
            placeholder="告诉 AI 你想分析什么"
          />
        </label>
        <div class="teacher-suggestions">
          <button
            v-for="suggestion in SUGGESTIONS"
            :key="suggestion"
            type="button"
            class="teacher-suggestion"
            @click="useSuggestion(suggestion)"
          >
            {{ suggestion }}
          </button>
        </div>
        <div class="teacher-card-actions">
          <button
            type="button"
            class="backoffice-button"
            :disabled="reportLoading"
            @click="generateReport"
          >
            {{ reportLoading ? "正在生成..." : "生成报告" }}
          </button>
        </div>
        <BackofficeFeedback
          v-if="reportError"
          kind="error"
          :message="reportError"
          testid="teacher-report-error"
        />
        <article
          v-if="report"
          class="teacher-report"
          data-testid="teacher-report"
        >
          <div
            v-if="report.degraded"
            class="teacher-report-degraded"
            data-testid="teacher-report-degraded"
            role="status"
          >
            <strong>降级结果</strong>
            <span>{{ reportDegradedText }}</span>
          </div>
          <h3>{{ report.title }}</h3>
          <small>{{ report.generated_at }}</small>
          <p>{{ report.content }}</p>
        </article>
      </BackofficeCard>

      <BackofficeCard
        title="最近加入的学员"
        description="来自当前名册的真实记录。"
      >
        <ul
          v-if="recentStudents.length"
          class="teacher-recent-list"
        >
          <li
            v-for="student in recentStudents"
            :key="student.id"
          >
            <span>
              <strong>{{ student.name }}</strong>
              <small>{{ student.id }} · {{ student.direction || "未分类" }}</small>
            </span>
            <time>{{ student.created_at || "时间未记录" }}</time>
          </li>
        </ul>
        <p
          v-else
          class="backoffice-muted"
        >
          暂无学员动态。
        </p>
      </BackofficeCard>
    </div>

    <Teleport to="body">
      <div
        v-if="addOpen"
        class="backoffice-modal-overlay"
        @click.self="closeAdd"
      >
        <form
          class="backoffice-modal"
          data-testid="teacher-student-editor"
          role="dialog"
          aria-modal="true"
          aria-label="添加学员"
          @submit.prevent="submitAdd"
        >
          <header class="backoffice-modal-head">
            <div>
              <p>名册维护</p>
              <h2>添加学员</h2>
            </div>
            <button
              type="button"
              class="backoffice-icon-button"
              aria-label="关闭"
              @click="closeAdd"
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
              testid="teacher-student-editor-error"
            />
            <label class="backoffice-field">
              <span>学员姓名</span>
              <input
                ref="addNameInput"
                v-model="addForm.name"
                required
                autocomplete="off"
              >
            </label>
            <div class="backoffice-form-grid">
              <label class="backoffice-field">
                <span>班级</span>
                <input
                  v-model="addForm.className"
                  autocomplete="off"
                  placeholder="可选"
                >
              </label>
              <label class="backoffice-field">
                <span>学习方向</span>
                <select v-model="addForm.direction">
                  <option
                    v-for="direction in addDirectionOptions"
                    :key="direction"
                    :value="direction"
                  >
                    {{ direction }}
                  </option>
                </select>
              </label>
            </div>
            <label class="backoffice-field">
              <span>平台账号</span>
              <select v-model="addForm.accountMode">
                <option value="link">关联已有学员账号</option>
                <option value="create">新建账号</option>
                <option value="none">暂不关联</option>
              </select>
            </label>
            <label
              v-if="addForm.accountMode === 'link'"
              class="backoffice-field"
            >
              <span>选择要关联的账号</span>
              <select v-model="addForm.linkUsername">
                <option value="">
                  请选择
                </option>
                <option
                  v-for="account in linkableAccounts"
                  :key="account.username"
                  :value="account.username"
                >
                  {{ account.name || account.username }}（{{ account.username }}）
                </option>
              </select>
              <small class="backoffice-muted">
                {{ accountsError || (linkableAccounts.length ? `仅显示未被占用的学员账号，共 ${linkableAccounts.length} 个。` : "目前没有空闲的学员账号。") }}
              </small>
            </label>
            <div
              v-if="addForm.accountMode === 'create'"
              class="backoffice-form-grid"
            >
              <label class="backoffice-field">
                <span>用户名</span>
                <input
                  v-model="addForm.newUsername"
                  autocomplete="off"
                  placeholder="登录用"
                >
              </label>
              <label class="backoffice-field">
                <span>初始密码</span>
                <input
                  v-model="addForm.newPassword"
                  autocomplete="off"
                  placeholder="至少 6 位"
                >
              </label>
            </div>
            <p
              v-if="addForm.accountMode === 'none'"
              class="backoffice-note"
            >
              该学员将无法登录、收不到站内通知，之后可在编辑中关联账号。
            </p>
          </div>
          <footer class="backoffice-modal-actions">
            <button
              type="button"
              class="backoffice-button is-secondary"
              :disabled="editorSaving"
              @click="closeAdd"
            >
              取消
            </button>
            <button
              type="submit"
              class="backoffice-button"
              :disabled="editorSaving"
            >
              {{ editorSaving ? "保存中..." : "确认添加" }}
            </button>
          </footer>
        </form>
      </div>

      <div
        v-if="editOpen && editForm"
        class="backoffice-modal-overlay"
        @click.self="closeEdit"
      >
        <form
          class="backoffice-modal"
          data-testid="teacher-student-editor"
          role="dialog"
          aria-modal="true"
          aria-label="编辑学员"
          @submit.prevent="submitEdit"
        >
          <header class="backoffice-modal-head">
            <div>
              <p>名册维护</p>
              <h2>编辑学员 · {{ editForm.id }}</h2>
            </div>
            <button
              type="button"
              class="backoffice-icon-button"
              aria-label="关闭"
              @click="closeEdit"
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
              testid="teacher-student-editor-error"
            />
            <label class="backoffice-field">
              <span>学员姓名</span>
              <input
                ref="editNameInput"
                v-model="editForm.name"
                required
                autocomplete="off"
              >
            </label>
            <div class="backoffice-form-grid">
              <label class="backoffice-field">
                <span>班级</span>
                <input
                  v-model="editForm.className"
                  autocomplete="off"
                >
              </label>
              <label class="backoffice-field">
                <span>学习方向</span>
                <select v-model="editForm.direction">
                  <option
                    v-for="direction in editDirectionOptions"
                    :key="direction"
                    :value="direction"
                  >
                    {{ direction }}
                  </option>
                </select>
              </label>
            </div>
            <label class="backoffice-field">
              <span>状态</span>
              <select v-model="editForm.status">
                <option value="active">
                  在读
                </option>
                <option value="suspended">
                  停课
                </option>
              </select>
            </label>
            <label class="backoffice-field">
              <span>平台账号</span>
              <select v-model="editForm.linkUsername">
                <option value="">
                  {{ editForm.currentAccount ? "（改为不关联账号）" : "（不关联账号）" }}
                </option>
                <option
                  v-if="editForm.currentAccount"
                  :value="editForm.currentAccount"
                >
                  {{ editForm.currentAccount }}（当前已关联）
                </option>
                <option
                  v-for="account in editAccountOptions"
                  :key="account.username"
                  :value="account.username"
                >
                  {{ account.name || account.username }}（{{ account.username }}）
                </option>
              </select>
              <small class="backoffice-muted">
                {{ accountsError || (editForm.currentAccount ? `当前已关联账号 ${editForm.currentAccount}。选择「改为不关联账号」会保留名册与历史学习数据。` : "该学员尚未关联账号，无法登录、收不到站内通知。") }}
              </small>
            </label>
          </div>
          <footer class="backoffice-modal-actions">
            <button
              type="button"
              class="backoffice-button is-secondary"
              :disabled="editorSaving"
              @click="closeEdit"
            >
              取消
            </button>
            <button
              type="submit"
              class="backoffice-button"
              :disabled="editorSaving"
            >
              {{ editorSaving ? "保存中..." : "保存修改" }}
            </button>
          </footer>
        </form>
      </div>

      <div
        v-if="detailOpen"
        class="backoffice-modal-overlay"
        @click.self="detailOpen = false"
      >
        <div
          class="backoffice-modal"
          data-testid="teacher-student-detail"
          role="dialog"
          aria-modal="true"
          aria-label="学员详情"
        >
          <header class="backoffice-modal-head">
            <div>
              <p>学员详情</p>
              <h2>{{ detailStudent?.name || "加载中" }}</h2>
            </div>
            <button
              type="button"
              class="backoffice-icon-button"
              aria-label="关闭"
              @click="detailOpen = false"
            >
              <i
                class="fas fa-xmark"
                aria-hidden="true"
              />
            </button>
          </header>
          <div class="backoffice-modal-body">
            <BackofficeState
              v-if="detailLoading"
              kind="loading"
              title="正在加载学员详情"
            />
            <template v-else-if="detailStudent">
              <div class="teacher-detail-head">
                <span class="teacher-detail-avatar">
                  {{ detailStudent.name.slice(0, 1) }}
                </span>
                <div>
                  <h3>{{ detailStudent.name }}</h3>
                  <p>{{ detailStudent.id }} · {{ detailStudent.direction || "未分类" }}</p>
                </div>
              </div>
              <dl class="teacher-detail-grid">
                <div>
                  <dt>完成度（证书）</dt>
                  <dd>
                    {{ detailStudent.has_cert_data ? `${detailStudent.completion}%（${detailStudent.cert_earned}/${detailStudent.cert_total}）` : "暂无证书记录" }}
                  </dd>
                </div>
                <div>
                  <dt>平台账号</dt>
                  <dd>{{ detailStudent.user_id || "未关联" }}</dd>
                </div>
                <div>
                  <dt>状态</dt>
                  <dd>{{ detailStudent.status === "suspended" ? "停课" : "在读" }}</dd>
                </div>
                <div>
                  <dt>班级</dt>
                  <dd>{{ detailStudent.class_name || "未填写" }}</dd>
                </div>
              </dl>
            </template>
          </div>
          <footer class="backoffice-modal-actions">
            <button
              type="button"
              class="backoffice-button is-secondary"
              @click="detailOpen = false"
            >
              关闭
            </button>
            <button
              v-if="detailStudent"
              type="button"
              class="backoffice-button"
              @click="openEdit(detailStudent.id)"
            >
              编辑信息
            </button>
          </footer>
        </div>
      </div>

      <div
        v-if="deleteTarget"
        class="backoffice-modal-overlay"
        @click.self="closeDelete"
      >
        <div
          class="backoffice-modal is-confirm"
          data-testid="teacher-confirm-delete"
          role="dialog"
          aria-modal="true"
          aria-label="确认删除"
        >
          <header class="backoffice-modal-head">
            <div>
              <p>确认删除</p>
              <h2>删除学员</h2>
            </div>
          </header>
          <div class="backoffice-modal-body">
            <p class="backoffice-confirm-copy">
              确定要删除学员「{{ deleteTarget.name }}」吗？仅删除名册记录，平台账号不会被删除，历史学习数据仍会保留。
            </p>
          </div>
          <footer class="backoffice-modal-actions">
            <button
              type="button"
              class="backoffice-button is-secondary"
              :disabled="deleting"
              @click="closeDelete"
            >
              取消
            </button>
            <button
              type="button"
              class="backoffice-button is-danger"
              :disabled="deleting"
              @click="confirmDelete"
            >
              {{ deleting ? "删除中..." : "确认删除" }}
            </button>
          </footer>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style src="./teacher.css"></style>
