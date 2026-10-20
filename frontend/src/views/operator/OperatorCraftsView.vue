<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  createOperatorCraft,
  createOperatorCraftCategory,
  createOperatorCraftItem,
  createOperatorCraftStep,
  createOperatorCraftVideo,
  deleteOperatorCraft,
  deleteOperatorCraftCategory,
  deleteOperatorCraftItem,
  deleteOperatorCraftStep,
  deleteOperatorCraftVideo,
  getOperatorCraftBudget,
  getOperatorCraftCategories,
  getOperatorCraftItems,
  getOperatorCrafts,
  getOperatorCraftSteps,
  getOperatorCraftVideos,
  updateOperatorCraft,
  updateOperatorCraftBudget,
  updateOperatorCraftCategory,
  updateOperatorCraftItem,
  updateOperatorCraftStep,
  updateOperatorCraftVideo,
  type OperatorCraftBudget,
  type OperatorCraftCategory,
  type OperatorCraftItem,
  type OperatorCraftStep,
  type OperatorCraftSummary,
  type OperatorCraftVideo,
} from "@/api/operator";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";
import OperatorFormDialog, {
  type OperatorFormField,
} from "@/components/operator/OperatorFormDialog.vue";

type DetailTab = "steps" | "categories" | "items" | "videos";

interface Feedback {
  kind: "info" | "success" | "error";
  message: string;
}

const crafts = ref<OperatorCraftSummary[]>([]);
const selectedCraftId = ref("");
const steps = ref<OperatorCraftStep[]>([]);
const categories = ref<OperatorCraftCategory[]>([]);
const items = ref<OperatorCraftItem[]>([]);
const videos = ref<OperatorCraftVideo[]>([]);
const budget = ref<OperatorCraftBudget | null>(null);

const loading = ref(true);
const listError = ref("");
const detailLoading = ref(false);
const detailError = ref("");
const budgetLoading = ref(false);
const budgetError = ref("");
const feedback = ref<Feedback | null>(null);
const activeTab = ref<DetailTab>("steps");

const dialogOpen = ref(false);
const dialogTitle = ref("");
const dialogFields = ref<OperatorFormField[]>([]);
const dialogInitial = ref<Record<string, unknown>>({});
const dialogError = ref("");
const dialogBusy = ref(false);
let dialogSubmit:
  | ((values: Record<string, unknown>) => Promise<void>)
  | null = null;
let detailSequence = 0;
let budgetSequence = 0;

const selectedCraft = computed(
  () =>
    crafts.value.find((craft) => craft.id === selectedCraftId.value) ?? null,
);
const categoryOptions = computed(() =>
  categories.value.map((category) => ({
    value: category.key,
    label: `${category.label || category.key}（${category.key}）`,
  })),
);
const detailRows = computed(() => {
  if (activeTab.value === "steps") return steps.value;
  if (activeTab.value === "categories") return categories.value;
  if (activeTab.value === "items") return items.value;
  return videos.value;
});
const detailEmptyText = computed(() => {
  const labels: Record<DetailTab, string> = {
    steps: "暂无制作步骤",
    categories: "暂无采购分类",
    items: "暂无采购条目",
    videos: "暂无教学视频",
  };
  return labels[activeTab.value];
});
const createLabel = computed(() => {
  const labels: Record<DetailTab, string> = {
    steps: "新建步骤",
    categories: "新建采购分类",
    items: "新建采购条目",
    videos: "新建视频",
  };
  return labels[activeTab.value];
});

onMounted(loadCrafts);

async function loadCrafts(message?: string): Promise<void> {
  loading.value = true;
  listError.value = "";
  try {
    crafts.value = await getOperatorCrafts();
    if (!crafts.value.some((craft) => craft.id === selectedCraftId.value)) {
      selectedCraftId.value = crafts.value[0]?.id ?? "";
    }
    if (selectedCraftId.value) {
      await Promise.all([loadDetail(), loadBudget()]);
    } else {
      clearDetail();
    }
    if (message) feedback.value = { kind: "success", message };
  } catch (failure) {
    listError.value =
      failure instanceof Error ? failure.message : "手工技艺加载失败";
  } finally {
    loading.value = false;
  }
}

async function selectCraft(craftId: string): Promise<void> {
  if (selectedCraftId.value === craftId) return;
  selectedCraftId.value = craftId;
  clearDetail();
  await Promise.all([loadDetail(), loadBudget()]);
}

async function setTab(tab: DetailTab): Promise<void> {
  if (activeTab.value === tab) return;
  activeTab.value = tab;
  await loadDetail();
}

async function loadDetail(): Promise<void> {
  const craftId = selectedCraftId.value;
  if (!craftId) {
    clearDetail();
    return;
  }
  const sequence = ++detailSequence;
  detailLoading.value = true;
  detailError.value = "";
  try {
    if (activeTab.value === "steps") {
      const rows = await getOperatorCraftSteps(craftId);
      if (sequence === detailSequence) steps.value = rows;
    } else if (activeTab.value === "categories") {
      const rows = await getOperatorCraftCategories(craftId);
      if (sequence === detailSequence) categories.value = rows;
    } else if (activeTab.value === "items") {
      const [nextCategories, rows] = await Promise.all([
        getOperatorCraftCategories(craftId),
        getOperatorCraftItems(craftId),
      ]);
      if (sequence === detailSequence) {
        categories.value = nextCategories;
        items.value = rows;
      }
    } else {
      const rows = await getOperatorCraftVideos(craftId);
      if (sequence === detailSequence) videos.value = rows;
    }
  } catch (failure) {
    if (sequence === detailSequence) {
      detailError.value =
        failure instanceof Error ? failure.message : "技艺内容加载失败";
    }
  } finally {
    if (sequence === detailSequence) detailLoading.value = false;
  }
}

async function loadBudget(): Promise<void> {
  const craftId = selectedCraftId.value;
  if (!craftId) {
    budget.value = null;
    return;
  }
  const sequence = ++budgetSequence;
  budgetLoading.value = true;
  budgetError.value = "";
  try {
    const nextBudget = await getOperatorCraftBudget(craftId);
    if (sequence === budgetSequence) budget.value = nextBudget;
  } catch (failure) {
    if (sequence === budgetSequence) {
      budgetError.value =
        failure instanceof Error ? failure.message : "采购预算加载失败";
    }
  } finally {
    if (sequence === budgetSequence) budgetLoading.value = false;
  }
}

function clearDetail(): void {
  steps.value = [];
  categories.value = [];
  items.value = [];
  videos.value = [];
  detailError.value = "";
}

function openCreateCraft(): void {
  openCraft(null);
}

function openCraft(craft: OperatorCraftSummary | null): void {
  dialogTitle.value = craft ? "编辑技艺" : "新建技艺";
  dialogInitial.value = craft
    ? { ...craft }
    : {
        id: "",
        name: "",
        origin: "",
        level: "",
        history: "",
        sort_order: 0,
      };
  dialogFields.value = [
    ...(!craft
      ? [
          {
            key: "id",
            label: "技艺 id",
            required: true,
            maxlength: 40,
            placeholder: "小写英文，如 ceramics",
          } satisfies OperatorFormField,
        ]
      : []),
    { key: "name", label: "技艺名称", required: true, maxlength: 60 },
    { key: "origin", label: "产地", maxlength: 60 },
    { key: "level", label: "等级", maxlength: 20 },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
    { key: "history", label: "历史沿革", type: "textarea", rows: 4 },
  ];
  openDialog(async (values) => {
    if (craft) {
      await updateOperatorCraft(craft.id, values);
    } else {
      const created = await createOperatorCraft(values);
      selectedCraftId.value = String(created.result);
    }
    await closeAndReload(craft ? "技艺已更新" : "技艺已创建");
  });
}

function openCreateDetail(): void {
  if (activeTab.value === "steps") openStep(null);
  else if (activeTab.value === "categories") openCategory(null);
  else if (activeTab.value === "items") openItem(null);
  else openVideo(null);
}

function openStep(step: OperatorCraftStep | null): void {
  if (!selectedCraft.value) return;
  dialogTitle.value = step ? "编辑步骤" : "新建步骤";
  dialogInitial.value = step
    ? { ...step }
    : { title: "", desc: "", tips: "", sort_order: 0 };
  dialogFields.value = [
    { key: "title", label: "步骤标题", required: true, maxlength: 60 },
    { key: "desc", label: "步骤说明", type: "textarea", rows: 3 },
    { key: "tips", label: "操作提示", type: "textarea", rows: 2 },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
  openDialog(async (values) => {
    if (step) await updateOperatorCraftStep(step.id, values);
    else await createOperatorCraftStep(selectedCraftId.value, values);
    await closeAndReload(step ? "步骤已更新" : "步骤已创建");
  });
}

function openCategory(category: OperatorCraftCategory | null): void {
  if (!selectedCraft.value) return;
  dialogTitle.value = category ? "编辑采购分类" : "新建采购分类";
  dialogInitial.value = category
    ? { ...category }
    : { key: "", label: "", desc: "", sort_order: 0 };
  dialogFields.value = [
    ...(!category
      ? [
          {
            key: "key",
            label: "分类 key",
            required: true,
            maxlength: 60,
            placeholder: "小写英文，如 essential",
          } satisfies OperatorFormField,
        ]
      : []),
    { key: "label", label: "分类标签", maxlength: 60 },
    { key: "desc", label: "分类说明", type: "textarea", rows: 2 },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
  openDialog(async (values) => {
    if (category) {
      await updateOperatorCraftCategory(
        selectedCraftId.value,
        category.key,
        values,
      );
    } else {
      await createOperatorCraftCategory(selectedCraftId.value, values);
    }
    await closeAndReload(category ? "采购分类已更新" : "采购分类已创建");
  });
}

function openItem(item: OperatorCraftItem | null): void {
  if (!selectedCraft.value) return;
  dialogTitle.value = item ? "编辑采购条目" : "新建采购条目";
  dialogInitial.value = item
    ? { ...item }
    : {
        category_key: categoryOptions.value[0]?.value ?? "",
        name: "",
        price: "",
        spec: "",
        tip: "",
        where: "",
        sort_order: 0,
      };
  dialogFields.value = [
    {
      key: "category_key",
      label: "所属分类",
      type: "select",
      required: true,
      options: categoryOptions.value,
    },
    { key: "name", label: "物品名称", required: true, maxlength: 60 },
    { key: "price", label: "价格", maxlength: 60 },
    { key: "spec", label: "规格说明", maxlength: 200 },
    { key: "tip", label: "避坑提示", maxlength: 200 },
    { key: "where", label: "购买渠道", maxlength: 200 },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
  openDialog(async (values) => {
    if (item) await updateOperatorCraftItem(item.id, values);
    else await createOperatorCraftItem(selectedCraftId.value, values);
    await closeAndReload(item ? "采购条目已更新" : "采购条目已创建");
  });
}

function openBudget(): void {
  if (!selectedCraft.value) return;
  dialogTitle.value = "采购预算";
  dialogInitial.value = budget.value
    ? { ...budget.value }
    : { starter: "", advanced: "", buying_tips: "" };
  dialogFields.value = [
    { key: "starter", label: "入门档预算", maxlength: 100 },
    { key: "advanced", label: "进阶档预算", maxlength: 100 },
    { key: "buying_tips", label: "采购建议", type: "textarea", rows: 3 },
  ];
  openDialog(async (values) => {
    await updateOperatorCraftBudget(selectedCraftId.value, values);
    await closeAndReload("采购预算已保存");
  });
}

function openVideo(video: OperatorCraftVideo | null): void {
  if (!selectedCraft.value) return;
  dialogTitle.value = video ? "编辑视频" : "新建视频";
  dialogInitial.value = video
    ? { ...video }
    : {
        bvid: "",
        title: "",
        author: "",
        cover: "",
        duration: 0,
        view_count: 0,
        danmaku: 0,
        like_count: 0,
        pubdate: 0,
        sort_order: 0,
      };
  dialogFields.value = [
    { key: "bvid", label: "bvid", required: true, maxlength: 60 },
    { key: "title", label: "视频标题", maxlength: 120 },
    { key: "author", label: "UP 主", maxlength: 60 },
    { key: "cover", label: "封面图地址", maxlength: 500 },
    { key: "duration", label: "时长（秒）", type: "number", min: 0 },
    { key: "view_count", label: "播放量", type: "number", min: 0 },
    { key: "danmaku", label: "弹幕数", type: "number", min: 0 },
    { key: "like_count", label: "点赞数", type: "number", min: 0 },
    { key: "pubdate", label: "发布日期（unix 秒）", type: "number", min: 0 },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
  openDialog(async (values) => {
    if (video) await updateOperatorCraftVideo(video.id, values);
    else await createOperatorCraftVideo(selectedCraftId.value, values);
    await closeAndReload(video ? "视频已更新" : "视频已创建");
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
  await loadCrafts(message);
}

async function removeCraft(craft: OperatorCraftSummary): Promise<void> {
  if (!window.confirm(`删除「${craft.name}」会同时删除步骤与采购指南，确认继续？`)) {
    return;
  }
  try {
    await deleteOperatorCraft(craft.id);
    if (selectedCraftId.value === craft.id) selectedCraftId.value = "";
    await loadCrafts("技艺已删除");
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message: failure instanceof Error ? failure.message : "删除失败",
    };
  }
}

async function removeStep(step: OperatorCraftStep): Promise<void> {
  if (!window.confirm(`确认删除步骤「${step.title}」？`)) return;
  await removeDetail(() => deleteOperatorCraftStep(step.id), "步骤已删除");
}

async function removeCategory(category: OperatorCraftCategory): Promise<void> {
  if (!window.confirm("删除分类会同时删除该分类下的采购条目，确认继续？")) {
    return;
  }
  await removeDetail(
    () => deleteOperatorCraftCategory(selectedCraftId.value, category.key),
    "采购分类已删除",
  );
}

async function removeItem(item: OperatorCraftItem): Promise<void> {
  if (!window.confirm(`确认删除采购条目「${item.name}」？`)) return;
  await removeDetail(() => deleteOperatorCraftItem(item.id), "采购条目已删除");
}

async function removeVideo(video: OperatorCraftVideo): Promise<void> {
  if (!window.confirm(`确认删除视频「${video.title || video.bvid}」？`)) return;
  await removeDetail(() => deleteOperatorCraftVideo(video.id), "视频已删除");
}

async function removeDetail(
  action: () => Promise<unknown>,
  message: string,
): Promise<void> {
  try {
    await action();
    await loadCrafts(message);
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message: failure instanceof Error ? failure.message : "删除失败",
    };
  }
}

function categoryName(key: string): string {
  return (
    categories.value.find((category) => category.key === key)?.label || key
  );
}

function formatDuration(seconds: number): string {
  const total = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}
</script>

<template>
  <section
    class="bo-page operator-crafts"
    data-testid="operator-crafts"
  >
    <header class="bo-page-header">
      <div>
        <p>内容运营</p>
        <h1 data-testid="backoffice-page-title">
          手工技艺
        </h1>
        <span>维护技艺、制作步骤、教学视频与材料采购指南。</span>
      </div>
      <button
        type="button"
        class="bo-button is-secondary"
        :disabled="loading"
        @click="loadCrafts()"
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
      testid="operator-crafts-feedback"
    />

    <BackofficeState
      v-if="loading && !crafts.length"
      kind="loading"
      title="正在读取手工技艺"
    />
    <BackofficeState
      v-else-if="listError"
      kind="error"
      title="手工技艺加载失败"
      :detail="listError"
    >
      <button
        type="button"
        class="bo-button"
        @click="loadCrafts()"
      >
        重试
      </button>
    </BackofficeState>

    <template v-else>
      <BackofficeCard
        title="技艺目录"
        description="删除技艺会同时删除其步骤、视频与采购指南。"
      >
        <template #actions>
          <button
            type="button"
            class="bo-button"
            :disabled="loading"
            @click="openCreateCraft"
          >
            <i
              class="fas fa-plus"
              aria-hidden="true"
            />
            新建技艺
          </button>
        </template>

        <BackofficeState
          v-if="!crafts.length"
          kind="empty"
          title="暂无手工技艺"
          detail="新建第一门技艺后即可维护步骤与采购指南。"
        />
        <div
          v-else
          class="bo-table-wrap"
        >
          <table class="bo-table">
            <thead>
              <tr>
                <th>名称</th>
                <th>产地</th>
                <th>等级</th>
                <th>步骤</th>
                <th>采购条目</th>
                <th>预算</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="craft in crafts"
                :key="craft.id"
                data-testid="operator-craft-row"
                :data-craft-id="craft.id"
                :class="{ 'is-selected': craft.id === selectedCraftId }"
              >
                <td>
                  <strong>{{ craft.name }}</strong>
                  <small>{{ craft.id }}</small>
                </td>
                <td>{{ craft.origin || "未填写" }}</td>
                <td>{{ craft.level || "未填写" }}</td>
                <td>{{ craft.step_count }}</td>
                <td>{{ craft.item_count }}</td>
                <td>
                  <span
                    class="bo-status"
                    :class="craft.has_budget ? 'is-active' : 'is-suspended'"
                  >
                    {{ craft.has_budget ? "已填" : "待填" }}
                  </span>
                </td>
                <td>{{ craft.sort_order }}</td>
                <td>
                  <div class="bo-row-actions">
                    <button
                      type="button"
                      class="bo-button is-small is-secondary"
                      @click="selectCraft(craft.id)"
                    >
                      管理内容
                    </button>
                    <button
                      type="button"
                      class="bo-button is-small is-secondary"
                      @click="openCraft(craft)"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      class="bo-button is-small is-danger"
                      @click="removeCraft(craft)"
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
        v-if="selectedCraft"
        :title="`「${selectedCraft.name}」的内容`"
        description="步骤、采购分类、采购条目与视频均按排序字段决定公开页顺序。"
      >
        <template #actions>
          <button
            type="button"
            class="bo-button"
            :disabled="loading || detailLoading"
            @click="openCreateDetail"
          >
            <i
              class="fas fa-plus"
              aria-hidden="true"
            />
            {{ createLabel }}
          </button>
        </template>

        <div class="operator-craft-budget">
          <div>
            <small>入门档预算</small>
            <strong>{{ budget?.starter || "未填写" }}</strong>
          </div>
          <div>
            <small>进阶档预算</small>
            <strong>{{ budget?.advanced || "未填写" }}</strong>
          </div>
          <p>{{ budget?.buying_tips || "尚未填写采购建议" }}</p>
          <button
            type="button"
            class="bo-button is-small is-secondary"
            :disabled="loading || budgetLoading"
            @click="openBudget"
          >
            编辑预算
          </button>
        </div>
        <BackofficeFeedback
          v-if="budgetError"
          kind="error"
          :message="budgetError"
        />

        <div
          class="operator-tabs"
          role="tablist"
          aria-label="技艺内容"
        >
          <button
            v-for="tab in [
              { key: 'steps', label: '步骤' },
              { key: 'categories', label: '采购分类' },
              { key: 'items', label: '采购条目' },
              { key: 'videos', label: '视频' },
            ] as const"
            :key="tab.key"
            type="button"
            role="tab"
            :aria-selected="activeTab === tab.key"
            :class="{ active: activeTab === tab.key }"
            @click="setTab(tab.key)"
          >
            {{ tab.label }}
          </button>
        </div>

        <BackofficeFeedback
          v-if="detailError"
          kind="error"
          :message="detailError"
        />
        <BackofficeState
          v-if="detailLoading"
          kind="loading"
          title="正在读取技艺内容"
        />
        <BackofficeState
          v-else-if="!detailError && !detailRows.length"
          kind="empty"
          :title="detailEmptyText"
        />
        <div
          v-else
          class="bo-table-wrap"
        >
          <table class="bo-table">
            <thead>
              <tr v-if="activeTab === 'steps'">
                <th>标题</th>
                <th>说明</th>
                <th>提示</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
              <tr v-else-if="activeTab === 'categories'">
                <th>key</th>
                <th>标签</th>
                <th>说明</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
              <tr v-else-if="activeTab === 'items'">
                <th>分类</th>
                <th>物品</th>
                <th>价格</th>
                <th>购买渠道</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
              <tr v-else>
                <th>bvid</th>
                <th>标题</th>
                <th>UP 主</th>
                <th>时长</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <template v-if="activeTab === 'steps'">
                <tr
                  v-for="step in steps"
                  :key="step.id"
                  data-testid="operator-craft-detail-row"
                  :data-row-id="step.id"
                >
                  <td>{{ step.title }}</td>
                  <td>{{ step.desc }}</td>
                  <td>{{ step.tips }}</td>
                  <td>{{ step.sort_order }}</td>
                  <td>
                    <div class="bo-row-actions">
                      <button
                        type="button"
                        class="bo-button is-small is-secondary"
                        @click="openStep(step)"
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        class="bo-button is-small is-danger"
                        @click="removeStep(step)"
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              </template>
              <template v-else-if="activeTab === 'categories'">
                <tr
                  v-for="category in categories"
                  :key="category.key"
                  data-testid="operator-craft-detail-row"
                  :data-row-key="category.key"
                >
                  <td>{{ category.key }}</td>
                  <td>{{ category.label }}</td>
                  <td>{{ category.desc }}</td>
                  <td>{{ category.sort_order }}</td>
                  <td>
                    <div class="bo-row-actions">
                      <button
                        type="button"
                        class="bo-button is-small is-secondary"
                        @click="openCategory(category)"
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        class="bo-button is-small is-danger"
                        @click="removeCategory(category)"
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              </template>
              <template v-else-if="activeTab === 'items'">
                <tr
                  v-for="item in items"
                  :key="item.id"
                  data-testid="operator-craft-detail-row"
                  :data-row-id="item.id"
                >
                  <td>{{ categoryName(item.category_key) }}</td>
                  <td>
                    <strong>{{ item.name }}</strong>
                    <small>{{ item.spec }}</small>
                  </td>
                  <td>{{ item.price }}</td>
                  <td>{{ item.where }}</td>
                  <td>{{ item.sort_order }}</td>
                  <td>
                    <div class="bo-row-actions">
                      <button
                        type="button"
                        class="bo-button is-small is-secondary"
                        @click="openItem(item)"
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        class="bo-button is-small is-danger"
                        @click="removeItem(item)"
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              </template>
              <template v-else>
                <tr
                  v-for="video in videos"
                  :key="video.id"
                  data-testid="operator-craft-detail-row"
                  :data-row-id="video.id"
                >
                  <td>{{ video.bvid }}</td>
                  <td>{{ video.title }}</td>
                  <td>{{ video.author }}</td>
                  <td>{{ formatDuration(video.duration) }}</td>
                  <td>{{ video.sort_order }}</td>
                  <td>
                    <div class="bo-row-actions">
                      <button
                        type="button"
                        class="bo-button is-small is-secondary"
                        @click="openVideo(video)"
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        class="bo-button is-small is-danger"
                        @click="removeVideo(video)"
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
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

<style scoped>
.operator-craft-budget {
  display: grid;
  grid-template-columns: minmax(130px, 0.5fr) minmax(130px, 0.5fr) minmax(220px, 1.4fr) auto;
  gap: 14px;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--bo-card-border);
  background: color-mix(in srgb, var(--bo-accent-soft) 55%, transparent);
}

.operator-craft-budget div {
  display: grid;
  gap: 3px;
}

.operator-craft-budget small {
  color: var(--bo-muted);
  font-size: 0.68rem;
}

.operator-craft-budget strong {
  color: var(--bo-text);
  font-size: 0.9rem;
}

.operator-craft-budget p {
  margin: 0;
  color: var(--bo-muted);
  font-size: 0.76rem;
  line-height: 1.5;
}

.operator-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  padding: 15px 20px;
  border-bottom: 1px solid var(--bo-card-border);
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

tr.is-selected {
  background: var(--bo-accent-soft);
}

@media (max-width: 900px) {
  .operator-craft-budget {
    grid-template-columns: 1fr 1fr;
  }

  .operator-craft-budget p {
    grid-column: 1 / -1;
  }
}
</style>
