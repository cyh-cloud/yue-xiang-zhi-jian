<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type CSSProperties,
} from "vue";
import { RouterLink } from "vue-router";

import {
  checkAgricultureReminders,
  getAgricultureCalendar,
  getAgricultureProducts,
  getAgricultureSubscriptions,
  subscribeAgriculture,
  unsubscribeAgriculture,
  type AgricultureCalendar,
  type AgricultureProduct,
  type AgricultureSource,
  type AgricultureTask,
} from "@/api/agriculture";
import { ApiError } from "@/api/client";
import AgricultureQa from "@/components/agriculture/AgricultureQa.vue";
import PestDiagnosis from "@/components/agriculture/PestDiagnosis.vue";
import PestKnowledge from "@/components/agriculture/PestKnowledge.vue";
import { useSessionStore } from "@/stores/session";

type CategoryId = "all" | "fruit" | "aquatic" | "crop";

interface ProductCategory {
  id: CategoryId;
  label: string;
  icon: string;
}

interface CalendarCell {
  key: string;
  day: number | null;
  tasks: AgricultureTask[];
  term: string;
  isToday: boolean;
}

interface FeedbackMessage {
  kind: "success" | "info" | "error";
  text: string;
}

const PRODUCT_STORAGE_KEY = "yuexiang_farming_product";
const PRODUCT_CATEGORIES: ProductCategory[] = [
  { id: "all", label: "全部", icon: "🧺" },
  { id: "fruit", label: "水果", icon: "🍎" },
  { id: "aquatic", label: "水产", icon: "🐟" },
  { id: "crop", label: "作物", icon: "🌾" },
];
const PRODUCT_CATEGORY_MAP: Readonly<Record<string, Exclude<CategoryId, "all">>> = {
  lychee: "fruit",
  longan: "fruit",
  citrus: "fruit",
  banana: "fruit",
  aquatic: "aquatic",
  rice: "crop",
  tea: "crop",
  vegetable: "crop",
};
const CATEGORY_COLORS: Readonly<Record<string, string>> = {
  fertilize: "#1f5e43",
  pest: "#ef4444",
  harvest: "#d9a227",
  manage: "#4a6fa5",
  water: "#4a8a6a",
};
const FA_ICON_ALIASES: Readonly<Record<string, string>> = {
  fishing: "fish",
};

const session = useSessionStore();
const products = ref<AgricultureProduct[]>([]);
const productsLoading = ref(true);
const productsError = ref("");
const selectedProductId = ref("");
const categoryFilter = ref<CategoryId>("all");
const productKeyword = ref("");

const calendar = ref<AgricultureCalendar | null>(null);
const calendarLoading = ref(false);
const calendarError = ref("");
const selectedMonth = ref(new Date().getMonth() + 1);
const expandedTaskIds = ref<Set<number>>(new Set());
const sourceListOpen = ref(false);
const dayModal = ref<number | null>(null);
const dayModalCloseButton = ref<HTMLButtonElement | null>(null);

const subscriptionIds = ref<string[]>([]);
const subscriptionBusy = ref(false);
const subscriptionFeedback = ref<FeedbackMessage | null>(null);
const loginPrompt = ref(false);
let requestSequence = 0;
let lastReminderSessionId = "";

const selectedProduct = computed(
  () =>
    products.value.find((product) => product.id === selectedProductId.value) ??
    null,
);

const filteredProducts = computed(() => {
  const keyword = productKeyword.value.trim().toLocaleLowerCase("zh-CN");
  return products.value.filter((product) => {
    const categoryMatches =
      categoryFilter.value === "all" ||
      productCategory(product.id) === categoryFilter.value;
    const text = `${product.name} ${product.desc}`.toLocaleLowerCase("zh-CN");
    return categoryMatches && (!keyword || text.includes(keyword));
  });
});

const categoryCounts = computed<Record<CategoryId, number>>(() => {
  const counts: Record<CategoryId, number> = {
    all: products.value.length,
    fruit: 0,
    aquatic: 0,
    crop: 0,
  };
  for (const product of products.value) {
    counts[productCategory(product.id)] += 1;
  }
  return counts;
});

const currentProductId = computed(
  () =>
    calendar.value?.product.id ||
    selectedProductId.value ||
    selectedProduct.value?.id ||
    "",
);
const currentProductName = computed(
  () =>
    calendar.value?.product.name ||
    selectedProduct.value?.name ||
    "本作物",
);
const isSubscribed = computed(() =>
  subscriptionIds.value.includes(currentProductId.value),
);
const calendarTasks = computed(() => calendar.value?.tasks ?? []);
const datedTasks = computed(() =>
  calendarTasks.value
    .filter((task) => task.day !== null)
    .sort((left, right) => (left.day ?? 0) - (right.day ?? 0)),
);
const undatedTasks = computed(() =>
  calendarTasks.value.filter((task) => task.day === null),
);
const urgentTaskCount = computed(
  () => calendarTasks.value.filter((task) => task.priority === "high").length,
);
const calendarIsEmpty = computed(
  () => Boolean(calendar.value) && calendarTasks.value.length === 0,
);
const onlyContinuousTasks = computed(
  () => datedTasks.value.length === 0 && undatedTasks.value.length > 0,
);
const sources = computed(() => calendar.value?.sources_all ?? []);
const calendarCells = computed<CalendarCell[]>(() => {
  const data = calendar.value;
  if (!data) return [];

  const termsByDay = new Map<number, string>();
  for (const term of data.solar_terms) {
    termsByDay.set(term.day, term.name);
  }
  const tasksByDay = new Map<number, AgricultureTask[]>();
  for (const task of data.tasks) {
    if (task.day === null) continue;
    const items = tasksByDay.get(task.day) ?? [];
    items.push(task);
    tasksByDay.set(task.day, items);
  }

  const cells: CalendarCell[] = [];
  const firstDay = new Date(data.year, data.month - 1, 1).getDay();
  const daysInMonth = new Date(data.year, data.month, 0).getDate();
  const today = new Date();

  for (let index = 0; index < firstDay; index += 1) {
    cells.push({
      key: `blank-${index}`,
      day: null,
      tasks: [],
      term: "",
      isToday: false,
    });
  }
  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push({
      key: `day-${day}`,
      day,
      tasks: tasksByDay.get(day) ?? [],
      term: termsByDay.get(day) ?? "",
      isToday:
        data.year === today.getFullYear() &&
        data.month === today.getMonth() + 1 &&
        day === today.getDate(),
    });
  }
  return cells;
});
const calendarGridStyle = computed<CSSProperties>(() => {
  const color = calendar.value?.phenophase_current?.color;
  return color ? ({ "--phase-color": color } as CSSProperties) : {};
});
const dayModalTasks = computed(() => {
  if (dayModal.value === null) return [];
  return calendarTasks.value.filter((task) => task.day === dayModal.value);
});
const dayModalHasApproximateDate = computed(() =>
  dayModalTasks.value.some((task) => !task.is_verified),
);
const dayModalTitle = computed(() => {
  if (dayModal.value === null || !calendar.value) return "";
  return `${currentProductName.value} · ${calendar.value.month}月${dayModal.value}日农事`;
});

watch(
  () => session.isAuthenticated,
  async (authenticated) => {
    if (!authenticated) {
      subscriptionIds.value = [];
      loginPrompt.value = false;
      return;
    }
    await loadSubscriptions();
    await checkReminders();
  },
  { immediate: true },
);

onMounted(async () => {
  document.addEventListener("keydown", handleDocumentKeydown);
  await loadProducts();
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", handleDocumentKeydown);
});

async function loadProducts(): Promise<void> {
  productsLoading.value = true;
  productsError.value = "";
  try {
    const response = await getAgricultureProducts();
    products.value = response.products;
    if (!response.products.length) {
      productsError.value = "暂无农产品数据";
      return;
    }

    const saved = readSavedProduct();
    const initial =
      response.products.find((product) => product.id === saved) ??
      response.products[0];
    if (!initial) return;
    selectedProductId.value = initial.id;
    await loadCalendar(selectedMonth.value);
  } catch {
    productsError.value = "农产品目录加载失败，请稍后重试";
  } finally {
    productsLoading.value = false;
  }
}

async function loadCalendar(month: number): Promise<void> {
  const productId = selectedProductId.value;
  if (!productId) return;

  const sequence = ++requestSequence;
  calendarLoading.value = true;
  calendarError.value = "";
  try {
    const response = await getAgricultureCalendar(productId, month);
    if (sequence !== requestSequence) return;
    calendar.value = response;
    selectedMonth.value = response.month;
    expandedTaskIds.value = new Set();
    sourceListOpen.value = false;
    closeDayModal();
  } catch {
    if (sequence !== requestSequence) return;
    calendar.value = null;
    calendarError.value = "农事数据加载失败，请重试";
  } finally {
    if (sequence === requestSequence) {
      calendarLoading.value = false;
    }
  }
}

async function loadSubscriptions(): Promise<void> {
  try {
    const response = await getAgricultureSubscriptions();
    subscriptionIds.value = response.product_ids;
  } catch (error) {
    subscriptionIds.value = [];
    if (error instanceof ApiError && error.status !== 401) {
      subscriptionFeedback.value = {
        kind: "error",
        text: "订阅状态加载失败，请稍后重试",
      };
    }
  }
}

async function checkReminders(): Promise<void> {
  const sid = session.sessionId;
  if (!sid || sid === lastReminderSessionId) return;
  lastReminderSessionId = sid;
  try {
    await checkAgricultureReminders();
  } catch {
    // Reminder delivery is idempotent and retried on the next visit.
    lastReminderSessionId = "";
  }
}

function selectProduct(productId: string): void {
  if (productId === selectedProductId.value) return;
  selectedProductId.value = productId;
  saveProduct(productId);
  subscriptionFeedback.value = null;
  loginPrompt.value = false;
  void loadCalendar(calendar.value?.month ?? selectedMonth.value);
}

function changeMonth(offset: number): void {
  selectedMonth.value = ((selectedMonth.value - 1 + offset + 12) % 12) + 1;
  void loadCalendar(selectedMonth.value);
}

function retryCalendar(): void {
  void loadCalendar(selectedMonth.value);
}

function setCategory(category: CategoryId): void {
  categoryFilter.value = category;
}

function clearProductSearch(): void {
  productKeyword.value = "";
}

async function toggleSubscription(): Promise<void> {
  subscriptionFeedback.value = null;
  loginPrompt.value = false;
  if (!session.isAuthenticated) {
    loginPrompt.value = true;
    return;
  }
  if (subscriptionBusy.value || !currentProductId.value) return;

  subscriptionBusy.value = true;
  try {
    const response = isSubscribed.value
      ? await unsubscribeAgriculture(currentProductId.value)
      : await subscribeAgriculture(currentProductId.value);
    subscriptionIds.value = response.product_ids;
    subscriptionFeedback.value = {
      kind: response.subscribed ? "success" : "info",
      text: response.subscribed
        ? "订阅成功，登录后会收到当月农事提醒"
        : "已取消订阅",
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      session.clearSession();
      loginPrompt.value = true;
    } else {
      subscriptionFeedback.value = {
        kind: "error",
        text: "操作失败，请稍后重试",
      };
    }
  } finally {
    subscriptionBusy.value = false;
  }
}

function toggleTask(taskId: number): void {
  const next = new Set(expandedTaskIds.value);
  if (next.has(taskId)) {
    next.delete(taskId);
  } else {
    next.add(taskId);
  }
  expandedTaskIds.value = next;
}

function isTaskExpanded(taskId: number): boolean {
  return expandedTaskIds.value.has(taskId);
}

function taskExpandLabel(task: AgricultureTask): string {
  return isTaskExpanded(task.id)
    ? `收起${task.title}详情`
    : `展开${task.title}详情`;
}

function openDayTasks(day: number): void {
  dayModal.value = day;
  void nextTick(() => dayModalCloseButton.value?.focus());
}

function closeDayModal(): void {
  dayModal.value = null;
}

function handleDocumentKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape" && dayModal.value !== null) {
    closeDayModal();
  }
}

function productCategory(productId: string): Exclude<CategoryId, "all"> {
  return PRODUCT_CATEGORY_MAP[productId] ?? "crop";
}

function categoryCount(category: CategoryId): number {
  return categoryCounts.value[category];
}

function faIconClass(name: string): string {
  const normalized = String(name || "tasks").trim().replace(/^fa-/, "");
  return `fa-${FA_ICON_ALIASES[normalized] ?? normalized}`;
}

function taskColorStyle(task: AgricultureTask): CSSProperties {
  return {
    "--task-color": CATEGORY_COLORS[task.category] ?? "#4a6fa5",
  } as CSSProperties;
}

function taskTiming(task: AgricultureTask): string {
  if (task.day === null) return "持续性作业";
  const prefix = task.is_verified ? "" : "约 ";
  return `${prefix}${task.date ?? task.task_md ?? ""}`;
}

function sourceMeta(source: AgricultureSource): string {
  return [source.org, source.doc_type, `文号：${source.doc_no || "待核"}`]
    .filter(Boolean)
    .join(" · ");
}

function readSavedProduct(): string | null {
  try {
    return localStorage.getItem(PRODUCT_STORAGE_KEY);
  } catch {
    return null;
  }
}

function saveProduct(productId: string): void {
  try {
    localStorage.setItem(PRODUCT_STORAGE_KEY, productId);
  } catch {
    // The current selection still works when storage is unavailable.
  }
}
</script>

<template>
  <section
    id="agriculture-tab"
    class="tab-content active"
    aria-labelledby="agriculture-title"
  >
    <div class="container">
      <div class="section-label">
        Agriculture
      </div>
      <h1
        id="agriculture-title"
        class="section-title"
      >
        智能农业技能培训
      </h1>
      <p class="section-desc">
        针对广东特色农产品，AI智能推送农时管理要点
      </p>

      <div
        id="product-select-section"
        class="card-section"
      >
        <h3 class="card-section-title">
          <i
            class="fas fa-tags"
            aria-hidden="true"
          />
          选择农产品
        </h3>

        <div
          v-if="productsLoading"
          class="agriculture-loading"
          role="status"
        >
          农产品目录加载中…
        </div>
        <div
          v-else-if="productsError"
          class="agriculture-empty"
          role="alert"
        >
          <i
            class="fas fa-triangle-exclamation"
            aria-hidden="true"
          />
          <strong>{{ productsError }}</strong>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            @click="loadProducts"
          >
            重新加载
          </button>
        </div>

        <template v-else>
          <div class="product-toolbar">
            <div
              class="product-category-filter"
              role="tablist"
              aria-label="按类别筛选农产品"
            >
              <button
                v-for="category in PRODUCT_CATEGORIES"
                :key="category.id"
                type="button"
                class="product-category-btn"
                :class="{ active: categoryFilter === category.id }"
                role="tab"
                :aria-selected="categoryFilter === category.id"
                @click="setCategory(category.id)"
              >
                <span aria-hidden="true">{{ category.icon }}</span>
                {{ category.label }}
                <span class="product-category-count">
                  {{ categoryCount(category.id) }}
                </span>
              </button>
            </div>

            <div class="product-search">
              <i
                class="fas fa-search"
                aria-hidden="true"
              />
              <input
                v-model="productKeyword"
                type="search"
                maxlength="20"
                name="product_q"
                autocomplete="off"
                spellcheck="false"
                placeholder="搜索农产品名称"
                aria-label="搜索农产品"
              >
              <button
                v-if="productKeyword"
                type="button"
                class="product-search-clear"
                aria-label="清除搜索"
                @click="clearProductSearch"
              >
                <i
                  class="fas fa-times"
                  aria-hidden="true"
                />
              </button>
            </div>
          </div>

          <div class="product-grid-scroll">
            <div class="product-grid">
              <button
                v-for="product in filteredProducts"
                :key="product.id"
                type="button"
                class="product-card"
                :class="{ active: selectedProductId === product.id }"
                :aria-pressed="selectedProductId === product.id"
                :aria-label="`选择${product.name}，${product.desc}`"
                @click="selectProduct(product.id)"
              >
                <span class="product-icon">
                  <i
                    class="fas"
                    :class="faIconClass(product.icon)"
                    aria-hidden="true"
                  />
                </span>
                <h4>{{ product.name }}</h4>
                <p>{{ product.desc }}</p>
              </button>
            </div>
            <p
              v-if="!filteredProducts.length"
              class="product-filter-empty"
              role="status"
            >
              没有匹配的农产品，换个关键词或清空筛选试试。
            </p>
          </div>
        </template>
      </div>

      <div
        id="farming-calendar-section"
        class="card-section"
      >
        <h3 class="card-section-title">
          <i
            class="fas fa-calendar"
            aria-hidden="true"
          />
          农时智能日历
        </h3>

        <div class="calendar-layout">
          <div class="calendar-main">
            <div class="calendar-nav">
              <button
                type="button"
                class="icon-btn"
                aria-label="上个月"
                :disabled="calendarLoading"
                @click="changeMonth(-1)"
              >
                <i
                  class="fas fa-chevron-left"
                  aria-hidden="true"
                />
              </button>
              <span class="calendar-title-wrap">
                <span
                  class="calendar-month"
                  data-testid="agriculture-month"
                >{{ selectedMonth }}月</span>
              </span>
              <button
                type="button"
                class="icon-btn"
                aria-label="下个月"
                :disabled="calendarLoading"
                @click="changeMonth(1)"
              >
                <i
                  class="fas fa-chevron-right"
                  aria-hidden="true"
                />
              </button>
            </div>

            <div
              v-if="sources.length"
              class="farming-date-notice"
              role="note"
            >
              <i
                class="fas fa-circle-info"
                aria-hidden="true"
              />
              <div class="fdn-body">
                <button
                  type="button"
                  class="fdn-toggle"
                  :aria-expanded="sourceListOpen"
                  aria-controls="farming-date-notice-sources"
                  @click="sourceListOpen = !sourceListOpen"
                >
                  {{ sourceListOpen ? "收起数据依据" : "查看数据依据" }}
                  <i
                    class="fas"
                    :class="sourceListOpen ? 'fa-chevron-up' : 'fa-chevron-down'"
                    aria-hidden="true"
                  />
                </button>
                <ul
                  v-show="sourceListOpen"
                  id="farming-date-notice-sources"
                  class="fdn-sources"
                >
                  <li
                    v-for="source in sources"
                    :key="source.key"
                  >
                    <span class="fdn-src-name">{{ source.name }}</span>
                    <span class="fdn-src-meta">
                      {{ sourceMeta(source) }}
                      <a
                        v-if="source.url"
                        :href="source.url"
                        target="_blank"
                        rel="noopener noreferrer"
                      >查验</a>
                    </span>
                  </li>
                </ul>
              </div>
            </div>

            <div
              v-if="calendar?.phenophase_current"
              class="phenophase-bar"
              role="status"
              :style="calendarGridStyle"
            >
              <span
                class="phase-dot"
                aria-hidden="true"
              />
              <strong>当前物候期：{{ calendar.phenophase_current.name }}</strong>
              <span
                v-if="calendar.phenophase_current.description"
                class="phase-desc"
              >
                {{ calendar.phenophase_current.description }}
              </span>
            </div>

            <div
              v-if="calendarLoading"
              class="calendar-loading"
              role="status"
            >
              农事数据加载中…
            </div>
            <div
              v-else-if="calendarError"
              class="agriculture-empty calendar-error"
              role="alert"
            >
              <i
                class="fas fa-triangle-exclamation"
                aria-hidden="true"
              />
              <strong>{{ calendarError }}</strong>
              <button
                type="button"
                class="btn btn-outline btn-sm"
                @click="retryCalendar"
              >
                重新加载
              </button>
            </div>
            <div
              v-else-if="calendar"
              class="calendar-grid"
              :class="{ 'has-phase': calendar.phenophase_current }"
              :style="calendarGridStyle"
            >
              <div
                v-for="label in ['日', '一', '二', '三', '四', '五', '六']"
                :key="label"
                class="calendar-header"
              >
                {{ label }}
              </div>
              <template
                v-for="cell in calendarCells"
                :key="cell.key"
              >
                <div
                  v-if="cell.day === null"
                  class="calendar-day is-blank"
                  aria-hidden="true"
                />
                <button
                  v-else-if="cell.tasks.length"
                  type="button"
                  class="calendar-day is-clickable has-task"
                  :class="{ today: cell.isToday }"
                  :aria-label="`${cell.day}日，${cell.tasks.length}项农事`"
                  @click="openDayTasks(cell.day)"
                >
                  <span class="day-num">{{ cell.day }}</span>
                  <span
                    v-if="cell.term"
                    class="lunar-marker"
                  >{{ cell.term }}</span>
                </button>
                <div
                  v-else
                  class="calendar-day"
                  :class="{ today: cell.isToday }"
                >
                  <span class="day-num">{{ cell.day }}</span>
                  <span
                    v-if="cell.term"
                    class="lunar-marker"
                  >{{ cell.term }}</span>
                </div>
              </template>
              <div
                v-if="calendarIsEmpty"
                class="calendar-blank-notice"
              >
                <strong>本月暂无农事安排</strong><br>
                该作物尚未录入本月的农事任务。
              </div>
              <div
                v-else-if="onlyContinuousTasks"
                class="calendar-blank-notice"
              >
                <strong>本月无固定日期农事</strong><br>
                该作物本月为持续性作业，共 {{ undatedTasks.length }} 项，详见右侧「本月农事要点」。
              </div>
            </div>
          </div>

          <div class="calendar-tasks">
            <div class="calendar-tasks-head">
              <h4>
                <i
                  class="fas fa-tasks"
                  aria-hidden="true"
                />
                本月农事要点
              </h4>
              <button
                type="button"
                class="btn btn-outline btn-sm subscribe-btn"
                :class="{ 'is-subscribed': isSubscribed }"
                :disabled="subscriptionBusy"
                @click="toggleSubscription"
              >
                <i
                  class="fas"
                  :class="isSubscribed ? 'fa-star' : 'far fa-star'"
                  aria-hidden="true"
                />
                {{ subscriptionBusy ? "处理中…" : isSubscribed ? "已订阅" : "订阅本作物" }}
              </button>
            </div>

            <p
              v-if="loginPrompt"
              class="agriculture-feedback info"
              role="status"
            >
              请先登录后再订阅农事提醒。
              <RouterLink
                :to="{ path: '/login', query: { redirect: '/agriculture' } }"
              >
                去登录
              </RouterLink>
            </p>
            <p
              v-else-if="subscriptionFeedback"
              class="agriculture-feedback"
              :class="subscriptionFeedback.kind"
              role="status"
            >
              {{ subscriptionFeedback.text }}
            </p>

            <div
              v-if="calendar && !calendarError"
              class="farming-reminder-summary"
              role="status"
            >
              <i
                class="fas fa-bell"
                aria-hidden="true"
              />
              <span v-if="!session.isAuthenticated">
                登录后可订阅「<span class="frs-strong">{{ currentProductName }}</span>」，
                登录时会补发当月已到期的农事提醒。
              </span>
              <span v-else-if="!isSubscribed">
                尚未订阅「<span class="frs-strong">{{ currentProductName }}</span>」。
                点击右侧「订阅本作物」，登录时会补发当月已到期的农事提醒。
              </span>
              <span v-else>
                已订阅「<span class="frs-strong">{{ currentProductName }}</span>」·
                本月共 <span class="frs-strong">{{ calendarTasks.length }}</span> 项农事
                <template v-if="urgentTaskCount">
                  ，其中 <span class="frs-urgent">{{ urgentTaskCount }} 项紧急</span>
                </template>
                。登录时会补发当月已到期的提醒，可在消息中心查看。
              </span>
            </div>

            <div
              v-if="calendarLoading"
              class="agriculture-loading task-loading"
              role="status"
            >
              农事任务加载中…
            </div>
            <div
              v-else-if="calendarError"
              class="agriculture-empty"
              role="alert"
            >
              <i
                class="fas fa-triangle-exclamation"
                aria-hidden="true"
              />
              <strong>{{ calendarError }}</strong>
              <button
                type="button"
                class="btn btn-outline btn-sm"
                @click="retryCalendar"
              >
                重新加载
              </button>
            </div>
            <div
              v-else-if="calendarIsEmpty"
              class="agriculture-empty"
              role="status"
            >
              <i
                class="fas fa-calendar-times"
                aria-hidden="true"
              />
              <strong>本月暂无农事数据</strong>
              <p>该作物尚未录入本月的农事安排</p>
            </div>
            <div
              v-else
              class="task-list"
            >
              <template v-if="datedTasks.length">
                <div class="task-group-label">
                  本月已安排日期{{ calendar?.dates_provisional ? "（依据公开技术资料编排，待复核）" : "" }}
                </div>
                <article
                  v-for="task in datedTasks"
                  :key="task.id"
                  class="task-item task-item-rich"
                  :class="{ expanded: isTaskExpanded(task.id) }"
                  :style="taskColorStyle(task)"
                >
                  <div class="task-header">
                    <div
                      class="task-icon-wrap"
                      :style="taskColorStyle(task)"
                    >
                      <i
                        class="fas"
                        :class="faIconClass(task.icon)"
                        aria-hidden="true"
                      />
                    </div>
                    <div class="task-meta">
                      <h5>{{ task.title }}</h5>
                      <div class="task-tags">
                        <span
                          class="task-tag tag-category"
                          :style="taskColorStyle(task)"
                        >{{ task.category_label }}</span>
                        <span
                          v-if="task.priority === 'high'"
                          class="task-tag tag-urgent"
                        >
                          <i
                            class="fas fa-fire"
                            aria-hidden="true"
                          />
                          紧急
                        </span>
                        <span
                          class="task-tag tag-timing"
                          :class="{ 'tag-approx': !task.is_verified }"
                        >
                          <i
                            class="far fa-clock"
                            aria-hidden="true"
                          />
                          {{ taskTiming(task) }}
                        </span>
                        <span
                          v-if="task.evidence_level === 'verified'"
                          class="task-tag tag-verified"
                        >
                          <i
                            class="fas fa-circle-check"
                            aria-hidden="true"
                          />
                          已复核
                        </span>
                        <span
                          v-else-if="task.evidence_level === 'unsourced'"
                          class="task-tag tag-unsourced"
                        >
                          <i
                            class="fas fa-triangle-exclamation"
                            aria-hidden="true"
                          />
                          来源待补
                        </span>
                      </div>
                    </div>
                    <button
                      type="button"
                      class="task-expand-btn"
                      :aria-label="taskExpandLabel(task)"
                      :aria-expanded="isTaskExpanded(task.id)"
                      :aria-controls="`task-detail-${task.id}`"
                      @click="toggleTask(task.id)"
                    >
                      <i
                        class="fas fa-chevron-down"
                        aria-hidden="true"
                      />
                    </button>
                  </div>
                  <p class="task-desc">
                    {{ task.description }}
                  </p>
                  <div
                    :id="`task-detail-${task.id}`"
                    class="task-detail"
                  >
                    <div
                      v-if="task.tip"
                      class="task-tips"
                    >
                      <i
                        class="fas fa-lightbulb"
                        aria-hidden="true"
                      />
                      <span>{{ task.tip }}</span>
                    </div>
                    <div
                      v-if="task.date_basis"
                      class="task-basis"
                    >
                      <span class="basis-label">
                        <i
                          class="fas fa-book-open"
                          aria-hidden="true"
                        />
                        日期依据
                      </span>
                      <p>{{ task.date_basis }}</p>
                    </div>
                    <div
                      v-if="task.source"
                      class="task-basis task-source"
                    >
                      <span class="basis-label">
                        <i
                          class="fas fa-landmark"
                          aria-hidden="true"
                        />
                        来源方向
                      </span>
                      <p>
                        {{ sourceMeta(task.source) }}
                        <a
                          v-if="task.source.url"
                          :href="task.source.url"
                          target="_blank"
                          rel="noopener noreferrer"
                        >查验</a>
                      </p>
                    </div>
                  </div>
                </article>
              </template>

              <template v-if="undatedTasks.length">
                <div class="task-group-label">
                  持续性作业（不指定日期）
                </div>
                <article
                  v-for="task in undatedTasks"
                  :key="task.id"
                  class="task-item task-item-rich"
                  :class="{ expanded: isTaskExpanded(task.id) }"
                  :style="taskColorStyle(task)"
                >
                  <div class="task-header">
                    <div
                      class="task-icon-wrap"
                      :style="taskColorStyle(task)"
                    >
                      <i
                        class="fas"
                        :class="faIconClass(task.icon)"
                        aria-hidden="true"
                      />
                    </div>
                    <div class="task-meta">
                      <h5>{{ task.title }}</h5>
                      <div class="task-tags">
                        <span
                          class="task-tag tag-category"
                          :style="taskColorStyle(task)"
                        >{{ task.category_label }}</span>
                        <span
                          v-if="task.priority === 'high'"
                          class="task-tag tag-urgent"
                        >
                          <i
                            class="fas fa-fire"
                            aria-hidden="true"
                          />
                          紧急
                        </span>
                        <span class="task-tag tag-timing">
                          <i
                            class="far fa-clock"
                            aria-hidden="true"
                          />
                          {{ taskTiming(task) }}
                        </span>
                      </div>
                    </div>
                    <button
                      type="button"
                      class="task-expand-btn"
                      :aria-label="taskExpandLabel(task)"
                      :aria-expanded="isTaskExpanded(task.id)"
                      :aria-controls="`task-detail-${task.id}`"
                      @click="toggleTask(task.id)"
                    >
                      <i
                        class="fas fa-chevron-down"
                        aria-hidden="true"
                      />
                    </button>
                  </div>
                  <p class="task-desc">
                    {{ task.description }}
                  </p>
                  <div
                    :id="`task-detail-${task.id}`"
                    class="task-detail"
                  >
                    <div
                      v-if="task.tip"
                      class="task-tips"
                    >
                      <i
                        class="fas fa-lightbulb"
                        aria-hidden="true"
                      />
                      <span>{{ task.tip }}</span>
                    </div>
                    <div
                      v-if="task.date_basis"
                      class="task-basis"
                    >
                      <span class="basis-label">
                        <i
                          class="fas fa-book-open"
                          aria-hidden="true"
                        />
                        日期依据
                      </span>
                      <p>{{ task.date_basis }}</p>
                    </div>
                    <div
                      v-if="task.source"
                      class="task-basis task-source"
                    >
                      <span class="basis-label">
                        <i
                          class="fas fa-landmark"
                          aria-hidden="true"
                        />
                        来源方向
                      </span>
                      <p>
                        {{ sourceMeta(task.source) }}
                        <a
                          v-if="task.source.url"
                          :href="task.source.url"
                          target="_blank"
                          rel="noopener noreferrer"
                        >查验</a>
                      </p>
                    </div>
                  </div>
                </article>
              </template>
            </div>
          </div>
        </div>
      </div>

      <AgricultureQa
        :product-id="currentProductId"
        :product-name="currentProductName"
        :session-id="session.sessionId"
      />

      <PestDiagnosis :current-product-id="currentProductId" />

      <PestKnowledge />
    </div>

    <Teleport to="body">
      <div
        v-if="dayModal !== null && calendar"
        class="modal-overlay detail-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="day-task-modal-title"
        @click.self="closeDayModal"
      >
        <div class="modal-content">
          <div class="modal-header">
            <h3 id="day-task-modal-title">
              <i
                class="fas fa-calendar-day modal-title-icon"
                aria-hidden="true"
              />
              {{ dayModalTitle }}
            </h3>
            <button
              ref="dayModalCloseButton"
              type="button"
              class="modal-close"
              aria-label="关闭"
              @click="closeDayModal"
            >
              <i
                class="fas fa-times"
                aria-hidden="true"
              />
            </button>
          </div>
          <div class="modal-body">
            <div class="day-task-modal">
              <div class="day-task-head">
                <strong>{{ calendar.month }}月{{ dayModal }}日</strong>
                <span
                  v-if="calendar.phenophase_current"
                  class="day-task-phase"
                  :style="{
                    background: `${calendar.phenophase_current.color || '#1f5e43'}18`,
                    color: calendar.phenophase_current.color || '#1f5e43',
                  }"
                >
                  {{ calendar.phenophase_current.name }}
                </span>
              </div>
              <div
                v-if="dayModalHasApproximateDate"
                class="day-task-approx-note"
              >
                <i
                  class="fas fa-circle-info"
                  aria-hidden="true"
                />
                该日期为依据公开技术资料编排的参考值，尚未经农技人员复核，请以当地农技站指导为准。
              </div>
              <article
                v-for="task in dayModalTasks"
                :key="task.id"
                class="day-task-item"
                :style="taskColorStyle(task)"
              >
                <div class="day-task-title">
                  <i
                    class="fas"
                    :class="faIconClass(task.icon)"
                    aria-hidden="true"
                  />
                  <span>{{ task.title }}</span>
                  <span
                    class="task-tag tag-category"
                    :style="taskColorStyle(task)"
                  >{{ task.category_label }}</span>
                </div>
                <p>{{ task.description }}</p>
                <div
                  v-if="task.tip"
                  class="task-tips"
                >
                  <i
                    class="fas fa-lightbulb"
                    aria-hidden="true"
                  />
                  <span>{{ task.tip }}</span>
                </div>
                <div
                  v-if="task.date_basis"
                  class="task-basis"
                >
                  <span class="basis-label">
                    <i
                      class="fas fa-book-open"
                      aria-hidden="true"
                    />
                    日期依据
                  </span>
                  <p>{{ task.date_basis }}</p>
                </div>
                <div
                  v-if="task.source"
                  class="task-basis task-source"
                >
                  <span class="basis-label">
                    <i
                      class="fas fa-landmark"
                      aria-hidden="true"
                    />
                    来源方向
                  </span>
                  <p>{{ sourceMeta(task.source) }}</p>
                </div>
              </article>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
button.product-card {
  width: 100%;
  color: inherit;
  font: inherit;
}

button.product-card p {
  color: inherit;
}

.agriculture-loading {
  padding: 32px 0;
  color: var(--text-secondary);
  font-size: 0.88rem;
  text-align: center;
}

.task-loading {
  padding: 20px 0;
}

.agriculture-empty {
  display: grid;
  justify-items: center;
  gap: 10px;
  padding: 28px 16px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  text-align: center;
}

.agriculture-empty i {
  color: var(--accent-gold, #d9a227);
  font-size: 1.2rem;
}

.agriculture-empty p {
  margin: 0;
  font-size: 0.82rem;
}

.calendar-error {
  grid-column: 1 / -1;
}

.agriculture-feedback {
  margin: 0 0 14px;
  padding: 9px 12px;
  border-radius: var(--radius-xs);
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.5;
}

.agriculture-feedback.success {
  background: color-mix(in srgb, var(--accent-green) 12%, transparent);
  color: var(--accent-green);
}

.agriculture-feedback.error {
  background: color-mix(in srgb, #ef4444 12%, transparent);
  color: #ef4444;
}

.agriculture-feedback.info {
  background: color-mix(in srgb, var(--accent-gold, #d9a227) 12%, transparent);
}

.agriculture-feedback a {
  color: var(--accent-green);
  font-weight: 600;
  text-underline-offset: 2px;
}

.task-icon-wrap,
.tag-category,
.day-task-title > i {
  color: var(--task-color, #4a6fa5);
}

.task-icon-wrap,
.tag-category {
  background: color-mix(in srgb, var(--task-color, #4a6fa5) 12%, transparent);
}

.task-item-rich.expanded .task-detail {
  max-height: 420px;
}

.calendar-day.is-clickable {
  border: 0;
  font-family: inherit;
}
</style>
