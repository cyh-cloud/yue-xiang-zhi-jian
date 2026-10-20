<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  createOperatorRecruitment,
  createOperatorRecruitmentSource,
  deleteOperatorRecruitment,
  deleteOperatorRecruitmentSource,
  getOperatorRecruitments,
  getOperatorRecruitmentSources,
  updateOperatorRecruitment,
  updateOperatorRecruitmentSource,
  type OperatorRecruitment,
  type OperatorRecruitmentSource,
} from "@/api/operator";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";
import OperatorFormDialog, {
  type OperatorFormField,
} from "@/components/operator/OperatorFormDialog.vue";

interface Feedback {
  kind: "info" | "success" | "error";
  message: string;
}

const recruitments = ref<OperatorRecruitment[]>([]);
const categories = ref<string[]>([]);
const sources = ref<OperatorRecruitmentSource[]>([]);
const selectedKey = ref("");
const loading = ref(true);
const sourcesLoading = ref(false);
const error = ref("");
const sourcesError = ref("");
const feedback = ref<Feedback | null>(null);
const categoryFilter = ref("");
const openOnly = ref(false);

const dialogOpen = ref(false);
const dialogTitle = ref("");
const dialogFields = ref<OperatorFormField[]>([]);
const dialogInitial = ref<Record<string, unknown>>({});
const dialogError = ref("");
const dialogBusy = ref(false);
let dialogSubmit:
  | ((values: Record<string, unknown>) => Promise<void>)
  | null = null;

const selectedRecruitment = computed(() =>
  recruitments.value.find((item) => item.key === selectedKey.value),
);

const visibleRecruitments = computed(() =>
  recruitments.value.filter((item) => {
    if (categoryFilter.value && item.category !== categoryFilter.value) {
      return false;
    }
    if (openOnly.value && !isOpen(item)) return false;
    return true;
  }),
);

function isOpen(item: OperatorRecruitment): boolean {
  if (!item.deadline) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const deadline = new Date(`${item.deadline}T00:00:00`);
  const start = item.signup_start
    ? new Date(`${item.signup_start}T00:00:00`)
    : null;
  return deadline >= today && (!start || start <= today);
}

function signupWindow(item: OperatorRecruitment): string {
  return [item.signup_start || "?", item.deadline || "?"].join(" 至 ");
}

async function loadRecruitments(message?: string): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const catalog = await getOperatorRecruitments();
    recruitments.value = catalog.recruitments;
    categories.value = catalog.categories;
    if (
      selectedKey.value &&
      !recruitments.value.some((item) => item.key === selectedKey.value)
    ) {
      selectedKey.value = "";
      sources.value = [];
    }
    if (message) feedback.value = { kind: "success", message };
  } catch (failure) {
    recruitments.value = [];
    sources.value = [];
    selectedKey.value = "";
    error.value =
      failure instanceof Error ? failure.message : "招募公告加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadSources(key = selectedKey.value): Promise<void> {
  if (!key) {
    sources.value = [];
    return;
  }
  sourcesLoading.value = true;
  sourcesError.value = "";
  try {
    sources.value = await getOperatorRecruitmentSources(key);
  } catch (failure) {
    sources.value = [];
    sourcesError.value =
      failure instanceof Error ? failure.message : "公告来源加载失败";
  } finally {
    sourcesLoading.value = false;
  }
}

async function selectRecruitment(key: string): Promise<void> {
  selectedKey.value = key;
  await loadSources(key);
}

function recruitmentFields(
  recruitment: OperatorRecruitment | null,
): OperatorFormField[] {
  return [
    ...(!recruitment
      ? [
          {
            key: "key",
            label: "公告 key",
            required: true,
            maxlength: 80,
            placeholder: "小写英文与数字，如 gz-gy-2026-5",
          } satisfies OperatorFormField,
        ]
      : []),
    { key: "title", label: "公告标题", required: true, maxlength: 60 },
    { key: "org", label: "发布单位", maxlength: 120 },
    { key: "region", label: "地区", maxlength: 80 },
    {
      key: "category",
      label: "岗位类别",
      type: "select",
      required: true,
      options: categories.value.map((category) => ({
        value: category,
        label: category,
      })),
    },
    { key: "job_type", label: "岗位类型", maxlength: 80 },
    { key: "headcount", label: "招聘人数", maxlength: 80 },
    { key: "education", label: "学历要求", maxlength: 120 },
    { key: "experience", label: "其他条件", maxlength: 200 },
    { key: "salary", label: "薪酬待遇", maxlength: 120 },
    { key: "description", label: "公告描述", type: "textarea", rows: 4 },
    { key: "publish_date", label: "发布日期", placeholder: "YYYY-MM-DD" },
    { key: "signup_start", label: "报名开始", placeholder: "YYYY-MM-DD" },
    {
      key: "deadline",
      label: "报名截止",
      required: true,
      placeholder: "YYYY-MM-DD",
    },
    { key: "signup_way", label: "报名方式", type: "textarea", rows: 3 },
    { key: "contact", label: "联系方式", maxlength: 120 },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
}

function sourceFields(): OperatorFormField[] {
  return [
    { key: "title", label: "来源标题", required: true, maxlength: 60 },
    { key: "media", label: "媒体 / 发布单位", maxlength: 120 },
    { key: "date", label: "日期", placeholder: "YYYY-MM-DD" },
    { key: "url", label: "链接", placeholder: "https://" },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
}

function openRecruitment(recruitment: OperatorRecruitment | null): void {
  dialogTitle.value = recruitment ? "编辑公告" : "新建公告";
  dialogInitial.value = recruitment
    ? { ...recruitment }
    : {
        key: "",
        title: "",
        org: "",
        region: "",
        category: "基层服务",
        job_type: "",
        headcount: "",
        education: "",
        experience: "",
        salary: "",
        description: "",
        publish_date: "",
        signup_start: "",
        deadline: "",
        signup_way: "",
        contact: "",
        sort_order: 0,
      };
  dialogFields.value = recruitmentFields(recruitment);
  openDialog(async (values) => {
    if (recruitment) {
      await updateOperatorRecruitment(recruitment.key, values);
    } else {
      const created = await createOperatorRecruitment(values);
      selectedKey.value = String(created.result);
    }
    finishDialog();
    await loadRecruitments(recruitment ? "公告已更新" : "公告已创建");
    await loadSources();
  });
}

function openSource(source: OperatorRecruitmentSource | null): void {
  if (!selectedKey.value) return;
  dialogTitle.value = source ? "编辑公告来源" : "新建公告来源";
  dialogInitial.value = source
    ? { ...source }
    : {
        title: "",
        media: "",
        date: "",
        url: "",
        sort_order: 0,
      };
  dialogFields.value = sourceFields();
  openDialog(async (values) => {
    if (source) {
      await updateOperatorRecruitmentSource(source.id, values);
    } else {
      await createOperatorRecruitmentSource(selectedKey.value, values);
    }
    finishDialog();
    await Promise.all([
      loadRecruitments(source ? "公告来源已更新" : "公告来源已创建"),
      loadSources(),
    ]);
  });
}

async function removeRecruitment(recruitment: OperatorRecruitment): Promise<void> {
  if (!window.confirm("删除后不可恢复，确认删除这条公告及其来源？")) return;
  feedback.value = null;
  try {
    await deleteOperatorRecruitment(recruitment.key);
    if (selectedKey.value === recruitment.key) {
      selectedKey.value = "";
      sources.value = [];
    }
    await loadRecruitments("公告已删除");
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message: failure instanceof Error ? failure.message : "删除公告失败",
    };
  }
}

async function removeSource(source: OperatorRecruitmentSource): Promise<void> {
  if (!window.confirm("确认删除这条公告来源？")) return;
  feedback.value = null;
  try {
    await deleteOperatorRecruitmentSource(source.id);
    await Promise.all([
      loadRecruitments("公告来源已删除"),
      loadSources(),
    ]);
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message: failure instanceof Error ? failure.message : "删除公告来源失败",
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
  await loadRecruitments();
});
</script>

<template>
  <section
    class="bo-page operator-recruitments"
    data-testid="operator-recruitments"
  >
    <header class="bo-page-header">
      <div>
        <p>内容运营</p>
        <h1 data-testid="backoffice-page-title">
          招募公告
        </h1>
        <span>维护公告正文与来源，公开就业页读取同一份内容。</span>
      </div>
      <button
        type="button"
        class="bo-button is-secondary"
        :disabled="loading"
        @click="loadRecruitments()"
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
      testid="operator-recruitments-feedback"
    />

    <BackofficeState
      v-if="loading"
      kind="loading"
      title="正在读取招募公告"
    />
    <BackofficeState
      v-else-if="error"
      kind="error"
      title="招募公告加载失败"
      :detail="error"
    >
      <button
        type="button"
        class="bo-button"
        @click="loadRecruitments()"
      >
        重试
      </button>
    </BackofficeState>

    <template v-else>
      <BackofficeCard
        title="公告"
        description="报名状态由报名起止日期实时计算，不单独维护状态字段。"
      >
        <template #actions>
          <button
            type="button"
            class="bo-button"
            @click="openRecruitment(null)"
          >
            <i
              class="fas fa-plus"
              aria-hidden="true"
            />
            新建公告
          </button>
        </template>

        <div class="bo-filterbar">
          <label class="bo-field">
            <span>岗位类别</span>
            <select v-model="categoryFilter">
              <option value="">
                全部类别
              </option>
              <option
                v-for="category in categories"
                :key="category"
                :value="category"
              >
                {{ category }}
              </option>
            </select>
          </label>
          <label class="operator-filter-check">
            <input
              v-model="openOnly"
              type="checkbox"
            >
            只看仍在报名期的
          </label>
        </div>

        <BackofficeState
          v-if="!visibleRecruitments.length"
          kind="empty"
          title="没有符合条件的公告"
          detail="可调整类别或报名期筛选，也可以新建公告。"
        />
        <div
          v-else
          class="bo-table-wrap"
        >
          <table class="bo-table">
            <thead>
              <tr>
                <th>标题</th>
                <th>单位</th>
                <th>类别</th>
                <th>报名期</th>
                <th>来源</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in visibleRecruitments"
                :key="item.key"
                data-testid="operator-recruitment-row"
                :data-key="item.key"
              >
                <td>
                  <strong>{{ item.title }}</strong>
                  <small>{{ item.key }}</small>
                </td>
                <td>{{ item.org }}</td>
                <td>{{ item.category }}</td>
                <td>{{ signupWindow(item) }}</td>
                <td>{{ item.source_count }}</td>
                <td>{{ item.sort_order }}</td>
                <td>
                  <div class="bo-row-actions">
                    <button
                      type="button"
                      class="bo-button is-small"
                      :class="
                        selectedKey === item.key ? 'is-secondary' : ''
                      "
                      @click="selectRecruitment(item.key)"
                    >
                      来源
                    </button>
                    <button
                      type="button"
                      class="bo-button is-small is-secondary"
                      @click="openRecruitment(item)"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      class="bo-button is-small is-danger"
                      @click="removeRecruitment(item)"
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
          selectedRecruitment
            ? `「${selectedRecruitment.title}」的来源`
            : '公告来源'
        "
        description="来源标题、媒体、日期与链接会随公告一起下发到公开就业页。"
      >
        <template #actions>
          <button
            type="button"
            class="bo-button"
            :disabled="!selectedKey"
            @click="openSource(null)"
          >
            <i
              class="fas fa-plus"
              aria-hidden="true"
            />
            新建来源
          </button>
        </template>

        <h2
          class="sr-only"
          data-testid="operator-recruitment-source-heading"
        >
          「{{ selectedKey }}」的来源
        </h2>

        <BackofficeFeedback
          v-if="sourcesError"
          kind="error"
          :message="sourcesError"
        />
        <BackofficeState
          v-if="!selectedKey"
          kind="empty"
          title="先在上方选择一条公告"
          detail="选中后可维护该公告的来源。"
        />
        <BackofficeState
          v-else-if="sourcesLoading"
          kind="loading"
          title="正在读取公告来源"
        />
        <BackofficeState
          v-else-if="!sourcesError && !sources.length"
          kind="empty"
          title="暂无公告来源"
          detail="新建来源后，公开就业页的「查看公告」会使用它。"
        />
        <div
          v-else
          class="bo-table-wrap"
        >
          <table class="bo-table">
            <thead>
              <tr>
                <th>标题</th>
                <th>媒体</th>
                <th>日期</th>
                <th>链接</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="source in sources"
                :key="source.id"
                data-testid="operator-recruitment-source-row"
                :data-source-id="source.id"
              >
                <td><strong>{{ source.title }}</strong></td>
                <td>{{ source.media }}</td>
                <td>{{ source.date }}</td>
                <td>{{ source.url }}</td>
                <td>{{ source.sort_order }}</td>
                <td>
                  <div class="bo-row-actions">
                    <button
                      type="button"
                      class="bo-button is-small is-secondary"
                      @click="openSource(source)"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      class="bo-button is-small is-danger"
                      @click="removeSource(source)"
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
.operator-filter-check {
  display: flex;
  align-items: center;
  gap: 7px;
  min-height: 38px;
  color: var(--bo-muted);
  font-size: 0.76rem;
}

.operator-filter-check input {
  width: auto;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
</style>
