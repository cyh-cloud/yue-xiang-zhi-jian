<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  createOperatorDialect,
  createOperatorDialectPhrase,
  createOperatorDialectQuestion,
  deleteOperatorDialect,
  deleteOperatorDialectPhrase,
  deleteOperatorDialectQuestion,
  getOperatorDialectPhrases,
  getOperatorDialectQuestions,
  getOperatorDialects,
  updateOperatorDialect,
  updateOperatorDialectPhrase,
  updateOperatorDialectQuestion,
  type OperatorDialect,
  type OperatorDialectPhrase,
  type OperatorDialectQuestion,
} from "@/api/operator";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";
import OperatorFormDialog, {
  type OperatorFormField,
} from "@/components/operator/OperatorFormDialog.vue";

type DetailTab = "phrases" | "questions";

interface Feedback {
  kind: "info" | "success" | "error";
  message: string;
}

const dialects = ref<OperatorDialect[]>([]);
const selectedDialectId = ref("");
const phrases = ref<OperatorDialectPhrase[]>([]);
const questions = ref<OperatorDialectQuestion[]>([]);

const loading = ref(true);
const listError = ref("");
const detailLoading = ref(false);
const detailError = ref("");
const feedback = ref<Feedback | null>(null);
const activeTab = ref<DetailTab>("phrases");

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

const selectedDialect = computed(
  () =>
    dialects.value.find(
      (dialect) => dialect.id === selectedDialectId.value,
    ) ?? null,
);
const detailRows = computed(() =>
  activeTab.value === "phrases" ? phrases.value : questions.value,
);
const createLabel = computed(() =>
  activeTab.value === "phrases" ? "新建短语" : "新建快捷问题",
);
const detailEmptyText = computed(() =>
  activeTab.value === "phrases" ? "暂无短语" : "暂无快捷问题",
);

onMounted(loadDialects);

async function loadDialects(message?: string): Promise<void> {
  loading.value = true;
  listError.value = "";
  try {
    dialects.value = await getOperatorDialects();
    if (
      !dialects.value.some(
        (dialect) => dialect.id === selectedDialectId.value,
      )
    ) {
      selectedDialectId.value = dialects.value[0]?.id ?? "";
    }
    if (selectedDialectId.value) await loadDetail();
    else clearDetail();
    if (message) feedback.value = { kind: "success", message };
  } catch (failure) {
    listError.value =
      failure instanceof Error ? failure.message : "方言知识加载失败";
  } finally {
    loading.value = false;
  }
}

async function selectDialect(dialectId: string): Promise<void> {
  if (selectedDialectId.value === dialectId) return;
  selectedDialectId.value = dialectId;
  clearDetail();
  await loadDetail();
}

async function setTab(tab: DetailTab): Promise<void> {
  if (activeTab.value === tab) return;
  activeTab.value = tab;
  await loadDetail();
}

async function loadDetail(): Promise<void> {
  const dialectId = selectedDialectId.value;
  if (!dialectId) {
    clearDetail();
    return;
  }
  const sequence = ++detailSequence;
  detailLoading.value = true;
  detailError.value = "";
  try {
    if (activeTab.value === "phrases") {
      const rows = await getOperatorDialectPhrases(dialectId);
      if (sequence === detailSequence) phrases.value = rows;
    } else {
      const rows = await getOperatorDialectQuestions(dialectId);
      if (sequence === detailSequence) questions.value = rows;
    }
  } catch (failure) {
    if (sequence === detailSequence) {
      detailError.value =
        failure instanceof Error ? failure.message : "方言内容加载失败";
    }
  } finally {
    if (sequence === detailSequence) detailLoading.value = false;
  }
}

function clearDetail(): void {
  phrases.value = [];
  questions.value = [];
  detailError.value = "";
}

function openCreateDialect(): void {
  openDialect(null);
}

function openDialect(dialect: OperatorDialect | null): void {
  dialogTitle.value = dialect ? "编辑方言" : "新建方言";
  dialogInitial.value = dialect
    ? { ...dialect, features: [...dialect.features] }
    : {
        id: "",
        name: "",
        region: "",
        emoji: "",
        areas: "",
        speakers: "",
        greeting: "",
        greeting_meaning: "",
        features: [],
        sort_order: 0,
      };
  dialogFields.value = [
    ...(!dialect
      ? [
          {
            key: "id",
            label: "方言 id",
            required: true,
            maxlength: 40,
            placeholder: "小写英文，如 hakka",
          } satisfies OperatorFormField,
        ]
      : []),
    { key: "name", label: "方言名称", required: true, maxlength: 60 },
    { key: "region", label: "地区", maxlength: 60 },
    { key: "emoji", label: "图标", maxlength: 8 },
    { key: "areas", label: "使用范围", maxlength: 120 },
    { key: "speakers", label: "使用人数", maxlength: 60 },
    { key: "greeting", label: "问候语", maxlength: 120 },
    { key: "greeting_meaning", label: "问候语意思", maxlength: 200 },
    {
      key: "features",
      label: "特色标签（一行一条）",
      type: "list",
      rows: 4,
    },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
  openDialog(async (values) => {
    if (dialect) {
      await updateOperatorDialect(dialect.id, values);
    } else {
      const created = await createOperatorDialect(values);
      selectedDialectId.value = String(created.result);
    }
    await closeAndReload(dialect ? "方言已更新" : "方言已创建");
  });
}

function openCreateDetail(): void {
  if (activeTab.value === "phrases") openPhrase(null);
  else openQuestion(null);
}

function openPhrase(phrase: OperatorDialectPhrase | null): void {
  if (!selectedDialect.value) return;
  dialogTitle.value = phrase ? "编辑短语" : "新建短语";
  dialogInitial.value = phrase
    ? { ...phrase }
    : { dialect: "", mandarin: "", pinyin: "", sort_order: 0 };
  dialogFields.value = [
    { key: "dialect", label: "方言说法", maxlength: 60 },
    { key: "mandarin", label: "普通话说法", required: true, maxlength: 60 },
    { key: "pinyin", label: "拼音", maxlength: 60 },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
  openDialog(async (values) => {
    if (phrase) await updateOperatorDialectPhrase(phrase.id, values);
    else await createOperatorDialectPhrase(selectedDialectId.value, values);
    await closeAndReload(phrase ? "短语已更新" : "短语已创建");
  });
}

function openQuestion(question: OperatorDialectQuestion | null): void {
  if (!selectedDialect.value) return;
  dialogTitle.value = question ? "编辑快捷问题" : "新建快捷问题";
  dialogInitial.value = question
    ? { ...question }
    : { question: "", sort_order: 0 };
  dialogFields.value = [
    { key: "question", label: "快捷问题", required: true, maxlength: 500 },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
  openDialog(async (values) => {
    if (question) await updateOperatorDialectQuestion(question.id, values);
    else await createOperatorDialectQuestion(selectedDialectId.value, values);
    await closeAndReload(question ? "快捷问题已更新" : "快捷问题已创建");
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
  await loadDialects(message);
}

async function removeDialect(dialect: OperatorDialect): Promise<void> {
  if (dialect.id === "cantonese") {
    feedback.value = {
      kind: "error",
      message: "粤语是未知方言的兜底内容，不能删除",
    };
    return;
  }
  if (!window.confirm(`删除「${dialect.name}」会同时删除短语与快捷问题，确认继续？`)) {
    return;
  }
  try {
    await deleteOperatorDialect(dialect.id);
    if (selectedDialectId.value === dialect.id) selectedDialectId.value = "";
    await loadDialects("方言已删除");
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message: failure instanceof Error ? failure.message : "删除失败",
    };
  }
}

async function removePhrase(phrase: OperatorDialectPhrase): Promise<void> {
  if (!window.confirm(`确认删除短语「${phrase.mandarin}」？`)) return;
  await removeDetail(() => deleteOperatorDialectPhrase(phrase.id), "短语已删除");
}

async function removeQuestion(
  question: OperatorDialectQuestion,
): Promise<void> {
  if (!window.confirm(`确认删除快捷问题「${question.question}」？`)) return;
  await removeDetail(
    () => deleteOperatorDialectQuestion(question.id),
    "快捷问题已删除",
  );
}

async function removeDetail(
  action: () => Promise<unknown>,
  message: string,
): Promise<void> {
  try {
    await action();
    await loadDialects(message);
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message: failure instanceof Error ? failure.message : "删除失败",
    };
  }
}
</script>

<template>
  <section
    class="bo-page operator-dialects"
    data-testid="operator-dialects"
  >
    <header class="bo-page-header">
      <div>
        <p>内容运营</p>
        <h1 data-testid="backoffice-page-title">
          方言知识
        </h1>
        <span>维护方言介绍、特色标签、短语与快捷问题。</span>
      </div>
      <button
        type="button"
        class="bo-button is-secondary"
        :disabled="loading"
        @click="loadDialects()"
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
      testid="operator-dialects-feedback"
    />

    <BackofficeState
      v-if="loading && !dialects.length"
      kind="loading"
      title="正在读取方言知识"
    />
    <BackofficeState
      v-else-if="listError"
      kind="error"
      title="方言知识加载失败"
      :detail="listError"
    >
      <button
        type="button"
        class="bo-button"
        @click="loadDialects()"
      >
        重试
      </button>
    </BackofficeState>

    <template v-else>
      <BackofficeCard
        title="方言目录"
        description="粤语是未知方言的兜底内容，不能删除。"
      >
        <template #actions>
          <button
            type="button"
            class="bo-button"
            :disabled="loading"
            @click="openCreateDialect"
          >
            <i
              class="fas fa-plus"
              aria-hidden="true"
            />
            新建方言
          </button>
        </template>

        <BackofficeState
          v-if="!dialects.length"
          kind="empty"
          title="暂无可维护方言"
        />
        <div
          v-else
          class="bo-table-wrap"
        >
          <table class="bo-table">
            <thead>
              <tr>
                <th>名称</th>
                <th>地区</th>
                <th>问候语</th>
                <th>特色</th>
                <th>短语</th>
                <th>快问</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="dialect in dialects"
                :key="dialect.id"
                data-testid="operator-dialect-row"
                :data-dialect-id="dialect.id"
                :class="{
                  'is-selected': dialect.id === selectedDialectId,
                }"
              >
                <td>
                  <strong>{{ dialect.emoji }} {{ dialect.name }}</strong>
                  <small>{{ dialect.id }}</small>
                </td>
                <td>{{ dialect.region || "未填写" }}</td>
                <td>{{ dialect.greeting || "未填写" }}</td>
                <td>{{ dialect.feature_count }}</td>
                <td>{{ dialect.phrase_count }}</td>
                <td>{{ dialect.question_count }}</td>
                <td>{{ dialect.sort_order }}</td>
                <td>
                  <div class="bo-row-actions">
                    <button
                      type="button"
                      class="bo-button is-small is-secondary"
                      @click="selectDialect(dialect.id)"
                    >
                      管理内容
                    </button>
                    <button
                      type="button"
                      class="bo-button is-small is-secondary"
                      @click="openDialect(dialect)"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      class="bo-button is-small is-danger"
                      :disabled="dialect.id === 'cantonese'"
                      @click="removeDialect(dialect)"
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
        v-if="selectedDialect"
        :title="`「${selectedDialect.name}」的内容`"
        description="短语与快捷问题按排序字段决定公开资源页的展示顺序。"
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

        <div
          class="operator-tabs"
          role="tablist"
          aria-label="方言内容"
        >
          <button
            v-for="tab in [
              { key: 'phrases', label: '短语' },
              { key: 'questions', label: '快捷问题' },
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
          title="正在读取方言内容"
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
              <tr v-if="activeTab === 'phrases'">
                <th>方言说法</th>
                <th>普通话</th>
                <th>拼音</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
              <tr v-else>
                <th>快捷问题</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <template v-if="activeTab === 'phrases'">
                <tr
                  v-for="phrase in phrases"
                  :key="phrase.id"
                  data-testid="operator-dialect-detail-row"
                  :data-row-id="phrase.id"
                >
                  <td>{{ phrase.dialect }}</td>
                  <td>{{ phrase.mandarin }}</td>
                  <td>{{ phrase.pinyin }}</td>
                  <td>{{ phrase.sort_order }}</td>
                  <td>
                    <div class="bo-row-actions">
                      <button
                        type="button"
                        class="bo-button is-small is-secondary"
                        @click="openPhrase(phrase)"
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        class="bo-button is-small is-danger"
                        @click="removePhrase(phrase)"
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              </template>
              <template v-else>
                <tr
                  v-for="question in questions"
                  :key="question.id"
                  data-testid="operator-dialect-detail-row"
                  :data-row-id="question.id"
                >
                  <td>{{ question.question }}</td>
                  <td>{{ question.sort_order }}</td>
                  <td>
                    <div class="bo-row-actions">
                      <button
                        type="button"
                        class="bo-button is-small is-secondary"
                        @click="openQuestion(question)"
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        class="bo-button is-small is-danger"
                        @click="removeQuestion(question)"
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
</style>
