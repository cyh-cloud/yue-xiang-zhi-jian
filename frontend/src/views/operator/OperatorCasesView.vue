<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  createOperatorCase,
  createOperatorCaseLesson,
  createOperatorCaseMilestone,
  createOperatorCaseSource,
  createOperatorCaseStat,
  deleteOperatorCase,
  deleteOperatorCaseLesson,
  deleteOperatorCaseMilestone,
  deleteOperatorCaseSource,
  deleteOperatorCaseStat,
  getOperatorCaseLessons,
  getOperatorCaseMilestones,
  getOperatorCases,
  getOperatorCaseSources,
  getOperatorCaseStats,
  updateOperatorCase,
  updateOperatorCaseLesson,
  updateOperatorCaseMilestone,
  updateOperatorCaseSource,
  updateOperatorCaseStat,
  type OperatorCaseLesson,
  type OperatorCaseMilestone,
  type OperatorCaseSource,
  type OperatorCaseStat,
  type OperatorCaseSummary,
} from "@/api/operator";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";
import OperatorFormDialog, {
  type OperatorFormField,
} from "@/components/operator/OperatorFormDialog.vue";

type CaseChildTab = "stats" | "milestones" | "sources" | "lessons";
type CaseChild =
  | OperatorCaseStat
  | OperatorCaseMilestone
  | OperatorCaseSource
  | OperatorCaseLesson;

interface Feedback {
  kind: "info" | "success" | "error";
  message: string;
}

const TABS: Array<{ key: CaseChildTab; label: string }> = [
  { key: "stats", label: "数据指标" },
  { key: "milestones", label: "里程碑" },
  { key: "sources", label: "来源" },
  { key: "lessons", label: "借鉴点" },
];

const cases = ref<OperatorCaseSummary[]>([]);
const selectedCaseId = ref<number | null>(null);
const activeTab = ref<CaseChildTab>("stats");
const childRows = ref<CaseChild[]>([]);
const loading = ref(true);
const childLoading = ref(false);
const error = ref("");
const childError = ref("");
const feedback = ref<Feedback | null>(null);

const dialogOpen = ref(false);
const dialogTitle = ref("");
const dialogFields = ref<OperatorFormField[]>([]);
const dialogInitial = ref<Record<string, unknown>>({});
const dialogError = ref("");
const dialogBusy = ref(false);
let dialogSubmit:
  | ((values: Record<string, unknown>) => Promise<void>)
  | null = null;

const selectedCase = computed(() =>
  cases.value.find((item) => item.id === selectedCaseId.value),
);

const childLabel = computed(
  () => TABS.find((tab) => tab.key === activeTab.value)?.label ?? "内容",
);

const childCreateLabel = computed(() => {
  const labels: Record<CaseChildTab, string> = {
    stats: "新建指标",
    milestones: "新建里程碑",
    sources: "新建来源",
    lessons: "新建借鉴点",
  };
  return labels[activeTab.value];
});

const childTestId = computed(() => {
  const ids: Record<CaseChildTab, string> = {
    stats: "operator-case-stat-row",
    milestones: "operator-case-milestone-row",
    sources: "operator-case-source-row",
    lessons: "operator-case-lesson-row",
  };
  return ids[activeTab.value];
});

const childColumns = computed(() => {
  const columns: Record<CaseChildTab, string[]> = {
    stats: ["指标", "数值", "图标", "排序", "操作"],
    milestones: ["时期", "标题", "说明", "排序", "操作"],
    sources: ["标题", "媒体", "日期", "链接", "排序", "操作"],
    lessons: ["借鉴点", "排序", "操作"],
  };
  return columns[activeTab.value];
});

function childValues(row: CaseChild): string[] {
  if (activeTab.value === "stats") {
    const stat = row as OperatorCaseStat;
    return [stat.label, stat.value, stat.icon, String(stat.sort_order)];
  }
  if (activeTab.value === "milestones") {
    const milestone = row as OperatorCaseMilestone;
    return [
      milestone.period,
      milestone.title,
      milestone.desc,
      String(milestone.sort_order),
    ];
  }
  if (activeTab.value === "sources") {
    const source = row as OperatorCaseSource;
    return [
      source.title,
      source.media,
      source.date,
      source.url,
      String(source.sort_order),
    ];
  }
  const lesson = row as OperatorCaseLesson;
  return [lesson.text, String(lesson.sort_order)];
}

async function loadCases(message?: string): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    cases.value = await getOperatorCases();
    if (
      selectedCaseId.value !== null &&
      !cases.value.some((item) => item.id === selectedCaseId.value)
    ) {
      selectedCaseId.value = null;
      childRows.value = [];
    }
    if (message) feedback.value = { kind: "success", message };
  } catch (failure) {
    cases.value = [];
    selectedCaseId.value = null;
    childRows.value = [];
    error.value = failure instanceof Error ? failure.message : "成功案例加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadChildren(): Promise<void> {
  const caseId = selectedCaseId.value;
  if (!caseId) {
    childRows.value = [];
    return;
  }
  childLoading.value = true;
  childError.value = "";
  try {
    if (activeTab.value === "stats") {
      childRows.value = await getOperatorCaseStats(caseId);
    } else if (activeTab.value === "milestones") {
      childRows.value = await getOperatorCaseMilestones(caseId);
    } else if (activeTab.value === "sources") {
      childRows.value = await getOperatorCaseSources(caseId);
    } else {
      childRows.value = await getOperatorCaseLessons(caseId);
    }
  } catch (failure) {
    childRows.value = [];
    childError.value =
      failure instanceof Error ? failure.message : `${childLabel.value}加载失败`;
  } finally {
    childLoading.value = false;
  }
}

async function refreshAll(message?: string): Promise<void> {
  await loadCases(message);
  await loadChildren();
}

async function selectCase(item: OperatorCaseSummary): Promise<void> {
  selectedCaseId.value = item.id;
  await loadChildren();
}

async function selectTab(tab: CaseChildTab): Promise<void> {
  activeTab.value = tab;
  await loadChildren();
}

function caseFields(): OperatorFormField[] {
  return [
    { key: "title", label: "案例标题", required: true, maxlength: 60 },
    { key: "region", label: "地区", maxlength: 80 },
    { key: "location", label: "地点", maxlength: 120 },
    { key: "background", label: "背景", type: "textarea", rows: 5 },
    { key: "description", label: "描述", type: "textarea", rows: 4 },
    { key: "quote", label: "引语", type: "textarea", rows: 3 },
    { key: "quote_author", label: "受访者", maxlength: 80 },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
}

function childFields(
  tab: CaseChildTab,
): OperatorFormField[] {
  if (tab === "stats") {
    return [
      { key: "label", label: "指标名称", required: true, maxlength: 60 },
      { key: "value", label: "数值", maxlength: 60 },
      { key: "icon", label: "图标", maxlength: 40, placeholder: "fa-leaf" },
      { key: "sort_order", label: "排序", type: "number", min: 0 },
    ];
  }
  if (tab === "milestones") {
    return [
      { key: "period", label: "时期", maxlength: 60 },
      { key: "title", label: "标题", required: true, maxlength: 60 },
      { key: "desc", label: "说明", type: "textarea", rows: 4 },
      { key: "sort_order", label: "排序", type: "number", min: 0 },
    ];
  }
  if (tab === "sources") {
    return [
      { key: "title", label: "来源标题", required: true, maxlength: 60 },
      { key: "media", label: "媒体", maxlength: 120 },
      { key: "date", label: "日期", placeholder: "YYYY-MM-DD" },
      { key: "url", label: "链接", placeholder: "https://" },
      { key: "sort_order", label: "排序", type: "number", min: 0 },
    ];
  }
  return [
    { key: "text", label: "借鉴点", type: "textarea", required: true, rows: 4 },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
}

function openCase(testCase: OperatorCaseSummary | null): void {
  dialogTitle.value = testCase ? "编辑案例" : "新建案例";
  dialogInitial.value = testCase
    ? { ...testCase }
    : {
        title: "",
        region: "",
        location: "",
        background: "",
        description: "",
        quote: "",
        quote_author: "",
        sort_order: 0,
      };
  dialogFields.value = caseFields();
  openDialog(async (values) => {
    if (testCase) {
      await updateOperatorCase(testCase.id, values);
    } else {
      const created = await createOperatorCase(values);
      selectedCaseId.value = Number(created.result);
    }
    finishDialog();
    await refreshAll(testCase ? "案例已更新" : "案例已创建");
  });
}

function openChild(row: CaseChild | null): void {
  if (!selectedCaseId.value) return;
  const labels: Record<CaseChildTab, string> = {
    stats: "数据指标",
    milestones: "里程碑",
    sources: "来源",
    lessons: "借鉴点",
  };
  dialogTitle.value = row ? `编辑${labels[activeTab.value]}` : childCreateLabel.value;
  dialogInitial.value = row
    ? { ...row }
    : defaultChildValues(activeTab.value);
  dialogFields.value = childFields(activeTab.value);
  const caseId = selectedCaseId.value;
  const tab = activeTab.value;
  openDialog(async (values) => {
    if (row) {
      if (tab === "stats") {
        await updateOperatorCaseStat((row as OperatorCaseStat).id, values);
      } else if (tab === "milestones") {
        await updateOperatorCaseMilestone(
          (row as OperatorCaseMilestone).id,
          values,
        );
      } else if (tab === "sources") {
        await updateOperatorCaseSource((row as OperatorCaseSource).id, values);
      } else {
        await updateOperatorCaseLesson((row as OperatorCaseLesson).id, values);
      }
    } else if (tab === "stats") {
      await createOperatorCaseStat(caseId, values);
    } else if (tab === "milestones") {
      await createOperatorCaseMilestone(caseId, values);
    } else if (tab === "sources") {
      await createOperatorCaseSource(caseId, values);
    } else {
      await createOperatorCaseLesson(caseId, values);
    }
    finishDialog();
    await refreshAll(`${labels[tab]}${row ? "已更新" : "已创建"}`);
  });
}

function defaultChildValues(tab: CaseChildTab): Record<string, unknown> {
  if (tab === "stats") {
    return { label: "", value: "", icon: "", sort_order: 0 };
  }
  if (tab === "milestones") {
    return { period: "", title: "", desc: "", sort_order: 0 };
  }
  if (tab === "sources") {
    return { title: "", media: "", date: "", url: "", sort_order: 0 };
  }
  return { text: "", sort_order: 0 };
}

async function removeCase(testCase: OperatorCaseSummary): Promise<void> {
  if (
    !window.confirm(
      "删除后不可恢复，确认删除这条案例？四个子表与审核记录会一起删除。",
    )
  ) {
    return;
  }
  feedback.value = null;
  try {
    await deleteOperatorCase(testCase.id);
    if (selectedCaseId.value === testCase.id) {
      selectedCaseId.value = null;
      childRows.value = [];
    }
    await loadCases("案例已删除");
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message: failure instanceof Error ? failure.message : "删除案例失败",
    };
  }
}

async function removeChild(row: CaseChild): Promise<void> {
  if (!window.confirm(`确认删除这条${childLabel.value}？`)) return;
  feedback.value = null;
  try {
    if (activeTab.value === "stats") {
      await deleteOperatorCaseStat((row as OperatorCaseStat).id);
    } else if (activeTab.value === "milestones") {
      await deleteOperatorCaseMilestone((row as OperatorCaseMilestone).id);
    } else if (activeTab.value === "sources") {
      await deleteOperatorCaseSource((row as OperatorCaseSource).id);
    } else {
      await deleteOperatorCaseLesson((row as OperatorCaseLesson).id);
    }
    await refreshAll(`${childLabel.value}已删除`);
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message:
        failure instanceof Error
          ? failure.message
          : `删除${childLabel.value}失败`,
    };
  }
}

function openDialog(
  submit: (values: Record<string, unknown>) => Promise<void>,
): void {
  dialogSubmit = submit;
  dialogError.value = "";
  dialogBusy.value = false;
  dialogOpen.value = true;
}

function closeDialog(): void {
  if (dialogBusy.value) return;
  finishDialog();
}

function finishDialog(): void {
  dialogOpen.value = false;
  dialogSubmit = null;
}

async function submitDialog(values: Record<string, unknown>): Promise<void> {
  if (!dialogSubmit) return;
  dialogBusy.value = true;
  dialogError.value = "";
  try {
    await dialogSubmit(values);
  } catch (failure) {
    dialogError.value =
      failure instanceof Error ? failure.message : "保存失败，请稍后重试";
  } finally {
    dialogBusy.value = false;
  }
}

onMounted(async () => {
  await loadCases();
});
</script>

<template>
  <section
    class="bo-page operator-cases"
    data-testid="operator-cases"
  >
    <header class="bo-page-header">
      <div>
        <p>内容运营</p>
        <h1 data-testid="backoffice-page-title">
          成功案例
        </h1>
        <span>维护案例正文、指标、里程碑、来源与借鉴点，审核通过后公开。</span>
      </div>
      <button
        type="button"
        class="bo-button is-secondary"
        :disabled="loading"
        @click="refreshAll()"
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
      testid="operator-cases-feedback"
    />

    <BackofficeState
      v-if="loading"
      kind="loading"
      title="正在读取成功案例"
    />
    <BackofficeState
      v-else-if="error"
      kind="error"
      title="成功案例加载失败"
      :detail="error"
    >
      <button
        type="button"
        class="bo-button"
        @click="loadCases()"
      >
        重试
      </button>
    </BackofficeState>

    <template v-else>
      <BackofficeCard
        title="案例"
        description="新建案例先进入审核队列，超级管理员通过后学员端才可见。"
      >
        <template #actions>
          <button
            type="button"
            class="bo-button"
            @click="openCase(null)"
          >
            <i
              class="fas fa-plus"
              aria-hidden="true"
            />
            新建案例
          </button>
        </template>

        <BackofficeState
          v-if="!cases.length"
          kind="empty"
          title="还没有案例"
          detail="新建案例后会进入审核队列。"
        />
        <div
          v-else
          class="bo-table-wrap"
        >
          <table class="bo-table">
            <thead>
              <tr>
                <th>标题</th>
                <th>地区</th>
                <th>指标</th>
                <th>里程碑</th>
                <th>来源</th>
                <th>借鉴点</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in cases"
                :key="item.id"
                data-testid="operator-case-row"
                :data-case-id="item.id"
              >
                <td>
                  <strong>{{ item.title }}</strong>
                  <small>#{{ item.id }}</small>
                </td>
                <td>{{ item.region }}</td>
                <td>{{ item.stat_count }}</td>
                <td>{{ item.milestone_count }}</td>
                <td>{{ item.source_count }}</td>
                <td>{{ item.lesson_count }}</td>
                <td>{{ item.sort_order }}</td>
                <td>
                  <div class="bo-row-actions">
                    <button
                      type="button"
                      class="bo-button is-small"
                      @click="selectCase(item)"
                    >
                      查看内容
                    </button>
                    <button
                      type="button"
                      class="bo-button is-small is-secondary"
                      @click="openCase(item)"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      class="bo-button is-small is-danger"
                      @click="removeCase(item)"
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

      <BackofficeCard
        :title="
          selectedCase ? `「${selectedCase.title}」的内容` : '案例内容'
        "
        description="四类子表按排序值组装，审核通过后与公开详情保持同源。"
      >
        <template #actions>
          <button
            type="button"
            class="bo-button"
            :disabled="!selectedCaseId"
            @click="openChild(null)"
          >
            <i
              class="fas fa-plus"
              aria-hidden="true"
            />
            {{ childCreateLabel }}
          </button>
        </template>

        <BackofficeState
          v-if="!selectedCaseId"
          kind="empty"
          title="先在上方选择一条案例"
          detail="选中后可维护数据指标、里程碑、来源与借鉴点。"
        />
        <template v-else>
          <div
            class="operator-tabs"
            role="tablist"
            aria-label="案例内容类型"
          >
            <button
              v-for="tab in TABS"
              :key="tab.key"
              type="button"
              role="tab"
              :aria-selected="activeTab === tab.key"
              :class="{ active: activeTab === tab.key }"
              @click="selectTab(tab.key)"
            >
              {{ tab.label }}
            </button>
          </div>

          <BackofficeFeedback
            v-if="childError"
            kind="error"
            :message="childError"
          />
          <BackofficeState
            v-if="childLoading"
            kind="loading"
            :title="`正在读取${childLabel}`"
          />
          <BackofficeState
            v-else-if="!childError && !childRows.length"
            kind="empty"
            :title="`暂无${childLabel}`"
            detail="可用右上角按钮新建内容。"
          />
          <div
            v-else
            class="bo-table-wrap"
          >
            <table class="bo-table">
              <thead>
                <tr>
                  <th
                    v-for="column in childColumns"
                    :key="column"
                  >
                    {{ column }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in childRows"
                  :key="row.id"
                  :data-testid="childTestId"
                  :data-row-id="row.id"
                >
                  <td
                    v-for="(value, index) in childValues(row)"
                    :key="index"
                  >
                    {{ value }}
                  </td>
                  <td>
                    <div class="bo-row-actions">
                      <button
                        type="button"
                        class="bo-button is-small is-secondary"
                        @click="openChild(row)"
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        class="bo-button is-small is-danger"
                        @click="removeChild(row)"
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </BackofficeCard>
    </template>

    <OperatorFormDialog
      v-if="dialogOpen"
      :title="dialogTitle"
      :fields="dialogFields"
      :initial="dialogInitial"
      :busy="dialogBusy"
      :error="dialogError"
      @close="closeDialog"
      @submit="submitDialog"
    />
  </section>
</template>

<style scoped>
.operator-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-bottom: 15px;
}

.operator-tabs button {
  min-height: 32px;
  padding: 5px 13px;
  border: 1px solid var(--bo-input-border);
  border-radius: 999px;
  background: var(--bo-card-bg);
  color: var(--bo-text);
  font: inherit;
  font-size: 0.76rem;
  cursor: pointer;
}

.operator-tabs button.active {
  border-color: var(--bo-accent);
  background: var(--bo-accent);
  color: #fff;
}
</style>
