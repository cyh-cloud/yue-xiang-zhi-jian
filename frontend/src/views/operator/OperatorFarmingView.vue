<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import {
  createOperatorFarmingCategory,
  createOperatorFarmingProduct,
  createOperatorFarmingSource,
  createOperatorFarmingTask,
  createOperatorPhenophase,
  deleteOperatorFarmingCategory,
  deleteOperatorFarmingProduct,
  deleteOperatorFarmingSource,
  deleteOperatorFarmingTask,
  deleteOperatorPhenophase,
  getOperatorFarmingCategories,
  getOperatorFarmingProducts,
  getOperatorFarmingSources,
  getOperatorFarmingTasks,
  getOperatorPhenophases,
  updateOperatorFarmingCategory,
  updateOperatorFarmingProduct,
  updateOperatorFarmingSource,
  updateOperatorFarmingTask,
  updateOperatorPhenophase,
  verifyOperatorFarmingTask,
  type OperatorFarmingCategory,
  type OperatorFarmingProduct,
  type OperatorFarmingSource,
  type OperatorFarmingTask,
  type OperatorPhenophase,
} from "@/api/operator";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";
import OperatorFormDialog, {
  type OperatorFormField,
} from "@/components/operator/OperatorFormDialog.vue";

type ReferenceTab = "products" | "phenophases" | "sources" | "categories";
type EditorKind = ReferenceTab | "task";

interface Feedback {
  kind: "info" | "success" | "error";
  message: string;
}

const PRIORITY_OPTIONS = [
  { value: "high", label: "高" },
  { value: "medium", label: "中" },
  { value: "low", label: "低" },
];

const products = ref<OperatorFarmingProduct[]>([]);
const phenophases = ref<OperatorPhenophase[]>([]);
const sources = ref<OperatorFarmingSource[]>([]);
const categories = ref<OperatorFarmingCategory[]>([]);
const tasks = ref<OperatorFarmingTask[]>([]);

const loading = ref(true);
const tasksLoading = ref(false);
const error = ref("");
const tasksError = ref("");
const feedback = ref<Feedback | null>(null);

const activeReferenceTab = ref<ReferenceTab>("phenophases");
const productFilter = ref("");
const monthFilter = ref<number | "">("");
const overdueOnly = ref(false);

const dialogOpen = ref(false);
const dialogTitle = ref("");
const dialogFields = ref<OperatorFormField[]>([]);
const dialogInitial = ref<Record<string, unknown>>({});
const dialogError = ref("");
const dialogBusy = ref(false);
let tasksRequestId = 0;
let dialogSubmit:
  | ((values: Record<string, unknown>) => Promise<void>)
  | null = null;

const productOptions = computed(() =>
  products.value.map((product) => ({
    value: product.id,
    label: `${product.name}${product.is_active ? "" : "（已停用）"}`,
  })),
);
const phaseOptions = computed(() =>
  phenophases.value.map((phase) => ({
    value: phase.id,
    label: `${productName(phase.product_id)} · ${phase.name}`,
  })),
);
const categoryOptions = computed(() =>
  categories.value.map((category) => ({
    value: category.key,
    label: category.label,
  })),
);
const sourceOptions = computed(() =>
  sources.value.map((source) => ({
    value: source.key,
    label: `${source.name}（${source.key}）`,
  })),
);
const referenceTitle = computed(() => {
  const labels: Record<ReferenceTab, string> = {
    products: "作物",
    phenophases: "物候期",
    sources: "来源登记",
    categories: "分类标签",
  };
  return labels[activeReferenceTab.value];
});
const createLabel = computed(() => {
  const labels: Record<ReferenceTab, string> = {
    products: "新建作物",
    phenophases: "新建物候期",
    sources: "新建来源",
    categories: "新建分类",
  };
  return labels[activeReferenceTab.value];
});

async function loadBasics(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [nextProducts, nextPhases, nextSources, nextCategories] =
      await Promise.all([
        getOperatorFarmingProducts(),
        getOperatorPhenophases(),
        getOperatorFarmingSources(),
        getOperatorFarmingCategories(),
      ]);
    products.value = nextProducts;
    phenophases.value = nextPhases;
    sources.value = nextSources;
    categories.value = nextCategories;
  } catch (failure) {
    error.value =
      failure instanceof Error ? failure.message : "农时基础数据加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadTasks(): Promise<void> {
  const requestId = ++tasksRequestId;
  tasksLoading.value = true;
  tasksError.value = "";
  try {
    const nextTasks = await getOperatorFarmingTasks({
      productId: productFilter.value,
      month: monthFilter.value,
      overdue: overdueOnly.value,
    });
    if (requestId !== tasksRequestId) return;
    tasks.value = nextTasks;
  } catch (failure) {
    if (requestId !== tasksRequestId) return;
    tasks.value = [];
    tasksError.value =
      failure instanceof Error ? failure.message : "农事任务加载失败";
  } finally {
    if (requestId === tasksRequestId) tasksLoading.value = false;
  }
}

async function reloadAll(message?: string): Promise<void> {
  await Promise.all([loadBasics(), loadTasks()]);
  if (message) feedback.value = { kind: "success", message };
}

function productName(productId: string): string {
  return (
    products.value.find((product) => product.id === productId)?.name ??
    productId
  );
}

function categoryLabel(category: string): string {
  return (
    categories.value.find((item) => item.key === category)?.label ?? category
  );
}

function priorityLabel(priority: string): string {
  return (
    PRIORITY_OPTIONS.find((option) => option.value === priority)?.label ??
    priority
  );
}

function verificationText(task: OperatorFarmingTask): string {
  return task.is_verified
    ? `${task.verified_by || "已复核"} ${task.verified_at || ""}`.trim()
    : "待复核";
}

function openCreate(): void {
  if (activeReferenceTab.value === "products") openProduct(null);
  else if (activeReferenceTab.value === "phenophases") openPhenophase(null);
  else if (activeReferenceTab.value === "sources") openSource(null);
  else openCategory(null);
}

function openEdit(
  kind: EditorKind,
  row: OperatorFarmingProduct | OperatorPhenophase | OperatorFarmingSource | OperatorFarmingCategory,
): void {
  if (kind === "products") openProduct(row as OperatorFarmingProduct);
  else if (kind === "phenophases") openPhenophase(row as OperatorPhenophase);
  else if (kind === "sources") openSource(row as OperatorFarmingSource);
  else if (kind === "categories") openCategory(row as OperatorFarmingCategory);
}

function openProduct(product: OperatorFarmingProduct | null): void {
  dialogTitle.value = product ? "编辑作物" : "新建作物";
  dialogInitial.value = product
    ? { ...product }
    : {
        id: "",
        name: "",
        icon: "seedling",
        summary: "",
        region: "广东",
        sort_order: 0,
        is_active: true,
      };
  dialogFields.value = [
    ...(!product
      ? [
          {
            key: "id",
            label: "作物 id",
            required: true,
            maxlength: 40,
            placeholder: "小写英文，如 lychee",
          } satisfies OperatorFormField,
        ]
      : []),
    { key: "name", label: "作物名称", required: true, maxlength: 60 },
    { key: "icon", label: "图标", placeholder: "seedling" },
    { key: "summary", label: "摘要", type: "textarea", rows: 3 },
    { key: "region", label: "地区", placeholder: "广东" },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
    { key: "is_active", label: "启用", type: "checkbox" },
  ];
  openDialog(async (values) => {
    if (product) {
      await updateOperatorFarmingProduct(product.id, values);
    } else {
      await createOperatorFarmingProduct(values);
    }
    await closeAndReload(product ? "作物已更新" : "作物已创建");
  });
}

function openPhenophase(phase: OperatorPhenophase | null): void {
  dialogTitle.value = phase ? "编辑物候期" : "新建物候期";
  dialogInitial.value = phase
    ? { ...phase }
    : {
        product_id: "",
        name: "",
        start_month: 1,
        end_month: 12,
        color: "#1f5e43",
        description: "",
        sort_order: 0,
      };
  dialogFields.value = [
    {
      key: "product_id",
      label: "作物",
      type: "select",
      required: true,
      options: productOptions.value,
    },
    { key: "name", label: "物候期名称", required: true, maxlength: 60 },
    {
      key: "start_month",
      label: "起始月份",
      type: "number",
      required: true,
      min: 1,
      max: 12,
    },
    {
      key: "end_month",
      label: "结束月份",
      type: "number",
      required: true,
      min: 1,
      max: 12,
    },
    { key: "color", label: "颜色", placeholder: "#1f5e43" },
    { key: "description", label: "说明", type: "textarea", rows: 3 },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
  openDialog(async (values) => {
    if (phase) await updateOperatorPhenophase(phase.id, values);
    else await createOperatorPhenophase(values);
    await closeAndReload(phase ? "物候期已更新" : "物候期已创建");
  });
}

function openSource(source: OperatorFarmingSource | null): void {
  dialogTitle.value = source ? "编辑来源" : "新建来源";
  dialogInitial.value = source
    ? { ...source }
    : {
        key: "",
        name: "",
        org: "",
        doc_type: "",
        doc_no: "待核",
        url: "",
        sort_order: 0,
      };
  dialogFields.value = [
    ...(!source
      ? [
          {
            key: "key",
            label: "来源 key",
            required: true,
            maxlength: 80,
          } satisfies OperatorFormField,
        ]
      : []),
    { key: "name", label: "来源名称", required: true, maxlength: 80 },
    { key: "org", label: "机构" },
    { key: "doc_type", label: "文件类型" },
    { key: "doc_no", label: "文号", placeholder: "待核" },
    { key: "url", label: "链接", placeholder: "https://" },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
  openDialog(async (values) => {
    if (source) await updateOperatorFarmingSource(source.key, values);
    else await createOperatorFarmingSource(values);
    await closeAndReload(source ? "来源已更新" : "来源已创建");
  });
}

function openCategory(category: OperatorFarmingCategory | null): void {
  dialogTitle.value = category ? "编辑分类" : "新建分类";
  dialogInitial.value = category
    ? { ...category }
    : { key: "", label: "", color: "#4a6fa5", sort_order: 0 };
  dialogFields.value = [
    ...(!category
      ? [
          {
            key: "key",
            label: "分类 key",
            required: true,
            maxlength: 40,
          } satisfies OperatorFormField,
        ]
      : []),
    { key: "label", label: "分类标签", required: true, maxlength: 40 },
    { key: "color", label: "颜色", placeholder: "#4a6fa5" },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
  openDialog(async (values) => {
    if (category) await updateOperatorFarmingCategory(category.key, values);
    else await createOperatorFarmingCategory(values);
    await closeAndReload(category ? "分类已更新" : "分类已创建");
  });
}

function openTask(task: OperatorFarmingTask | null): void {
  dialogTitle.value = task ? "编辑农事任务" : "新建农事任务";
  dialogInitial.value = task
    ? { ...task }
    : {
        product_id: "",
        phase_id: "",
        title: "",
        category: "",
        month: new Date().getMonth() + 1,
        task_md: "",
        priority: "medium",
        icon: "tasks",
        source_key: "",
        description: "",
        tip: "",
        date_basis: "",
        sort_order: 0,
        is_active: true,
      };
  dialogFields.value = [
    {
      key: "product_id",
      label: "作物",
      type: "select",
      required: true,
      options: productOptions.value,
    },
    {
      key: "phase_id",
      label: "物候期",
      type: "select",
      options: phaseOptions.value,
    },
    { key: "title", label: "任务标题", required: true, maxlength: 60 },
    {
      key: "category",
      label: "任务分类",
      type: "select",
      required: true,
      options: categoryOptions.value,
    },
    {
      key: "month",
      label: "月份",
      type: "number",
      required: true,
      min: 1,
      max: 12,
    },
    {
      key: "task_md",
      label: "任务日期",
      placeholder: "MM-DD，可留空表示本月内",
    },
    {
      key: "priority",
      label: "优先级",
      type: "select",
      required: true,
      options: PRIORITY_OPTIONS,
    },
    { key: "icon", label: "图标", placeholder: "tasks" },
    {
      key: "source_key",
      label: "来源",
      type: "select",
      options: sourceOptions.value,
    },
    { key: "description", label: "描述", type: "textarea", rows: 3 },
    { key: "tip", label: "提示", type: "textarea", rows: 2 },
    { key: "date_basis", label: "日期依据", type: "textarea", rows: 3 },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
    { key: "is_active", label: "启用", type: "checkbox" },
  ];
  openDialog(async (values) => {
    if (task) await updateOperatorFarmingTask(task.id, values);
    else await createOperatorFarmingTask(values);
    await closeAndReload(task ? "农事任务已更新" : "农事任务已创建");
  });
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

async function closeAndReload(message: string): Promise<void> {
  dialogOpen.value = false;
  dialogSubmit = null;
  await reloadAll(message);
}

async function verifyTask(task: OperatorFarmingTask): Promise<void> {
  feedback.value = null;
  try {
    await verifyOperatorFarmingTask(task.id);
    await reloadAll("农事任务已标记复核");
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message: failure instanceof Error ? failure.message : "复核失败",
    };
  }
}

async function removeTask(task: OperatorFarmingTask): Promise<void> {
  if (!window.confirm("删除后不可恢复，确认删除这条农事任务？")) return;
  try {
    await deleteOperatorFarmingTask(task.id);
    await reloadAll("农事任务已删除");
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message: failure instanceof Error ? failure.message : "删除失败",
    };
  }
}

async function removeReference(
  kind: ReferenceTab,
  row: OperatorFarmingProduct | OperatorPhenophase | OperatorFarmingSource | OperatorFarmingCategory,
): Promise<void> {
  if (!window.confirm("确认删除？")) return;
  try {
    if (kind === "products") {
      await deleteOperatorFarmingProduct((row as OperatorFarmingProduct).id);
    } else if (kind === "phenophases") {
      await deleteOperatorPhenophase((row as OperatorPhenophase).id);
    } else if (kind === "sources") {
      await deleteOperatorFarmingSource((row as OperatorFarmingSource).key);
    } else {
      await deleteOperatorFarmingCategory((row as OperatorFarmingCategory).key);
    }
    await reloadAll("内容已删除");
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message: failure instanceof Error ? failure.message : "删除失败",
    };
  }
}

function setReferenceTab(tab: ReferenceTab): void {
  activeReferenceTab.value = tab;
}

function refreshTasks(): void {
  void loadTasks();
}

watch([productFilter, monthFilter, overdueOnly], () => {
  void loadTasks();
});

onMounted(async () => {
  await Promise.all([loadBasics(), loadTasks()]);
});
</script>

<template>
  <section
    class="backoffice-page operator-farming"
    data-testid="operator-farming"
  >
    <header class="backoffice-page-header">
      <div>
        <p>农业内容</p>
        <h1 data-testid="backoffice-page-title">
          农时日历
        </h1>
        <span>维护作物、物候期、任务、来源与分类，并记录每次复核。</span>
      </div>
      <button
        type="button"
        class="backoffice-button is-secondary"
        :disabled="loading || tasksLoading"
        @click="reloadAll()"
      >
        <i
          class="fas fa-rotate"
          :class="{ 'fa-spin': loading || tasksLoading }"
          aria-hidden="true"
        />
        刷新
      </button>
    </header>

    <BackofficeFeedback
      v-if="feedback"
      :kind="feedback.kind"
      :message="feedback.message"
      testid="operator-farming-feedback"
    />

    <BackofficeState
      v-if="loading"
      kind="loading"
      title="正在读取农时基础数据"
    />
    <BackofficeState
      v-else-if="error"
      kind="error"
      title="农时基础数据加载失败"
      :detail="error"
    >
      <button
        type="button"
        class="backoffice-button"
        @click="reloadAll()"
      >
        重试
      </button>
    </BackofficeState>

    <template v-else>
      <BackofficeCard
        title="农事任务"
        description="筛选只影响当前列表。超期筛选不受月份限制，避免漏掉该重新复核的内容。"
      >
        <template #actions>
          <button
            type="button"
            class="backoffice-button"
            @click="openTask(null)"
          >
            <i
              class="fas fa-plus"
              aria-hidden="true"
            />
            新建任务
          </button>
        </template>

        <div class="backoffice-filterbar">
          <label class="backoffice-field">
            <span>作物筛选</span>
            <select v-model="productFilter">
              <option value="">
                全部作物
              </option>
              <option
                v-for="product in products"
                :key="product.id"
                :value="product.id"
              >
                {{ product.name }}
              </option>
            </select>
          </label>
          <label class="backoffice-field">
            <span>月份筛选</span>
            <select v-model="monthFilter">
              <option value="">
                全部月份
              </option>
              <option
                v-for="month in 12"
                :key="month"
                :value="month"
              >
                {{ month }} 月
              </option>
            </select>
          </label>
          <label class="operator-filter-check">
            <input
              v-model="overdueOnly"
              type="checkbox"
            >
            只看该重新核的（超 183 天或从未复核）
          </label>
          <button
            type="button"
            class="backoffice-button is-secondary"
            :disabled="tasksLoading"
            @click="refreshTasks"
          >
            刷新任务
          </button>
        </div>

        <BackofficeFeedback
          v-if="tasksError"
          kind="error"
          :message="tasksError"
        />
        <BackofficeState
          v-if="tasksLoading"
          kind="loading"
          title="正在读取农事任务"
        />
        <BackofficeState
          v-else-if="!tasks.length"
          kind="empty"
          title="暂无农事任务"
          detail="当前筛选条件下没有任务。"
        />
        <div
          v-else
          class="backoffice-table-wrap"
        >
          <table class="backoffice-table">
            <thead>
              <tr>
                <th>日期</th>
                <th>标题</th>
                <th>分类</th>
                <th>优先级</th>
                <th>复核</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="task in tasks"
                :key="task.id"
                data-testid="operator-farming-task-row"
                :data-task-id="task.id"
              >
                <td>
                  <strong>{{ task.task_md || `${task.month} 月内` }}</strong>
                  <small>{{ productName(task.product_id) }}</small>
                </td>
                <td>
                  <strong>{{ task.title }}</strong>
                  <small>{{ task.phase_name || "未指定物候期" }}</small>
                </td>
                <td>{{ task.category_label || categoryLabel(task.category) }}</td>
                <td>{{ priorityLabel(task.priority) }}</td>
                <td>
                  <span
                    class="backoffice-status"
                    :class="task.is_verified ? 'is-active' : 'is-suspended'"
                  >
                    {{ task.is_verified ? "已复核" : "待复核" }}
                  </span>
                  <small>{{ verificationText(task) }}</small>
                </td>
                <td>
                  <div class="backoffice-row-actions">
                    <button
                      type="button"
                      class="backoffice-button is-small is-success"
                      @click="verifyTask(task)"
                    >
                      {{ task.is_verified ? "重新复核" : "标记已复核" }}
                    </button>
                    <button
                      type="button"
                      class="backoffice-button is-small is-secondary"
                      @click="openTask(task)"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      class="backoffice-button is-small is-danger"
                      @click="removeTask(task)"
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
        :title="`${referenceTitle}维护`"
        description="所有字段都来自现有内容接口，修改后公开页立即读取新值。"
      >
        <template #actions>
          <button
            type="button"
            class="backoffice-button"
            @click="openCreate"
          >
            <i
              class="fas fa-plus"
              aria-hidden="true"
            />
            {{ createLabel }}
          </button>
        </template>

        <div
          class="operator-tabs"
          role="tablist"
          aria-label="农时基础数据"
        >
          <button
            v-for="tab in [
              { key: 'products', label: '作物' },
              { key: 'phenophases', label: '物候期' },
              { key: 'sources', label: '来源登记' },
              { key: 'categories', label: '分类标签' },
            ] as const"
            :key="tab.key"
            type="button"
            role="tab"
            :aria-selected="activeReferenceTab === tab.key"
            :class="{ active: activeReferenceTab === tab.key }"
            @click="setReferenceTab(tab.key)"
          >
            {{ tab.label }}
          </button>
        </div>

        <div
          v-if="activeReferenceTab === 'products'"
          class="backoffice-table-wrap"
        >
          <table class="backoffice-table">
            <thead>
              <tr>
                <th>id</th>
                <th>名称</th>
                <th>地区</th>
                <th>状态</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="product in products"
                :key="product.id"
                data-testid="operator-reference-row"
              >
                <td>{{ product.id }}</td>
                <td>
                  <strong>{{ product.name }}</strong>
                  <small>{{ product.summary }}</small>
                </td>
                <td>{{ product.region }}</td>
                <td>{{ product.is_active ? "启用" : "停用" }}</td>
                <td>{{ product.sort_order }}</td>
                <td>
                  <div class="backoffice-row-actions">
                    <button
                      type="button"
                      class="backoffice-button is-small is-secondary"
                      @click="openEdit('products', product)"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      class="backoffice-button is-small is-danger"
                      @click="removeReference('products', product)"
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <BackofficeState
            v-if="!products.length"
            kind="empty"
            title="暂无作物"
          />
        </div>

        <div
          v-else-if="activeReferenceTab === 'phenophases'"
          class="backoffice-table-wrap"
        >
          <table class="backoffice-table">
            <thead>
              <tr>
                <th>作物</th>
                <th>名称</th>
                <th>月份</th>
                <th>说明</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="phase in phenophases"
                :key="phase.id"
                data-testid="operator-reference-row"
              >
                <td>{{ productName(phase.product_id) }}</td>
                <td>
                  <strong>{{ phase.name }}</strong>
                  <small :style="{ color: phase.color || undefined }">
                    {{ phase.color || "未设置颜色" }}
                  </small>
                </td>
                <td>{{ phase.start_month }} 月至 {{ phase.end_month }} 月</td>
                <td>{{ phase.description }}</td>
                <td>{{ phase.sort_order }}</td>
                <td>
                  <div class="backoffice-row-actions">
                    <button
                      type="button"
                      class="backoffice-button is-small is-secondary"
                      @click="openEdit('phenophases', phase)"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      class="backoffice-button is-small is-danger"
                      @click="removeReference('phenophases', phase)"
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <BackofficeState
            v-if="!phenophases.length"
            kind="empty"
            title="暂无物候期"
          />
        </div>

        <div
          v-else-if="activeReferenceTab === 'sources'"
          class="backoffice-table-wrap"
        >
          <table class="backoffice-table">
            <thead>
              <tr>
                <th>key</th>
                <th>名称</th>
                <th>机构</th>
                <th>文号</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="source in sources"
                :key="source.key"
                data-testid="operator-reference-row"
              >
                <td>{{ source.key }}</td>
                <td>
                  <strong>{{ source.name }}</strong>
                  <small>{{ source.url }}</small>
                </td>
                <td>{{ source.org }}</td>
                <td>{{ source.doc_no || "待核" }}</td>
                <td>{{ source.sort_order }}</td>
                <td>
                  <div class="backoffice-row-actions">
                    <button
                      type="button"
                      class="backoffice-button is-small is-secondary"
                      @click="openEdit('sources', source)"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      class="backoffice-button is-small is-danger"
                      @click="removeReference('sources', source)"
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <BackofficeState
            v-if="!sources.length"
            kind="empty"
            title="暂无来源"
          />
        </div>

        <div
          v-else
          class="backoffice-table-wrap"
        >
          <table class="backoffice-table">
            <thead>
              <tr>
                <th>key</th>
                <th>标签</th>
                <th>颜色</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="category in categories"
                :key="category.key"
                data-testid="operator-reference-row"
              >
                <td>{{ category.key }}</td>
                <td>{{ category.label }}</td>
                <td>{{ category.color || "未设置" }}</td>
                <td>{{ category.sort_order }}</td>
                <td>
                  <div class="backoffice-row-actions">
                    <button
                      type="button"
                      class="backoffice-button is-small is-secondary"
                      @click="openEdit('categories', category)"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      class="backoffice-button is-small is-danger"
                      @click="removeReference('categories', category)"
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <BackofficeState
            v-if="!categories.length"
            kind="empty"
            title="暂无分类"
          />
        </div>
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

<style src="./operator.css"></style>
