<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import {
  createOperatorPestCrop,
  createOperatorPestEntry,
  createOperatorPestSource,
  deleteOperatorPestCrop,
  deleteOperatorPestEntry,
  deleteOperatorPestImage,
  deleteOperatorPestSource,
  getOperatorPestCrops,
  getOperatorPestEntries,
  getOperatorPestEntry,
  getOperatorPestSources,
  setOperatorPestImage,
  updateOperatorPestCrop,
  updateOperatorPestEntry,
  updateOperatorPestSource,
  verifyOperatorPestEntry,
  type OperatorPestCrop,
  type OperatorPestEntryDetail,
  type OperatorPestEntrySummary,
  type OperatorPestSource,
} from "@/api/operator";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";
import OperatorFormDialog, {
  type OperatorFormField,
} from "@/components/operator/OperatorFormDialog.vue";

type ReferenceTab = "crops" | "sources";
type EditorKind = ReferenceTab | "entry";

interface Feedback {
  kind: "info" | "success" | "error";
  message: string;
}

const IMAGE_FIELDS = [
  "file",
  "credit",
  "license",
  "caption",
  "source_url",
  "shot_date",
  "note",
] as const;

const crops = ref<OperatorPestCrop[]>([]);
const sources = ref<OperatorPestSource[]>([]);
const entries = ref<OperatorPestEntrySummary[]>([]);

const loading = ref(true);
const entriesLoading = ref(false);
const error = ref("");
const entriesError = ref("");
const feedback = ref<Feedback | null>(null);

const activeReferenceTab = ref<ReferenceTab>("crops");
const cropFilter = ref("");
const overdueOnly = ref(false);

const dialogOpen = ref(false);
const dialogTitle = ref("");
const dialogFields = ref<OperatorFormField[]>([]);
const dialogInitial = ref<Record<string, unknown>>({});
const dialogError = ref("");
const dialogBusy = ref(false);
let dialogSubmit:
  | ((values: Record<string, unknown>) => Promise<void>)
  | null = null;

const cropOptions = computed(() =>
  crops.value.map((crop) => ({ value: crop.id, label: crop.name })),
);
const sourceOptions = computed(() =>
  sources.value.map((source) => ({
    value: source.key,
    label: `${source.name}（${source.key}）`,
  })),
);
const referenceTitle = computed(() =>
  activeReferenceTab.value === "crops" ? "作物" : "来源登记",
);
const createLabel = computed(() =>
  activeReferenceTab.value === "crops" ? "新建作物" : "新建来源",
);

async function loadBasics(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [nextCrops, nextSources] = await Promise.all([
      getOperatorPestCrops(),
      getOperatorPestSources(),
    ]);
    crops.value = nextCrops;
    sources.value = nextSources;
  } catch (failure) {
    error.value =
      failure instanceof Error ? failure.message : "病虫害基础数据加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadEntries(): Promise<void> {
  entriesLoading.value = true;
  entriesError.value = "";
  try {
    entries.value = await getOperatorPestEntries({
      cropId: cropFilter.value,
      overdue: overdueOnly.value,
    });
  } catch (failure) {
    entries.value = [];
    entriesError.value =
      failure instanceof Error ? failure.message : "病虫害条目加载失败";
  } finally {
    entriesLoading.value = false;
  }
}

async function reloadAll(message?: string): Promise<void> {
  await Promise.all([loadBasics(), loadEntries()]);
  if (message) feedback.value = { kind: "success", message };
}

function verificationText(entry: OperatorPestEntrySummary): string {
  return entry.is_verified
    ? `${entry.verified_by || "已复核"} ${entry.verified_at || ""}`.trim()
    : "待复核";
}

function setReferenceTab(tab: ReferenceTab): void {
  activeReferenceTab.value = tab;
}

function openCreate(): void {
  if (activeReferenceTab.value === "crops") openCrop(null);
  else openSource(null);
}

function openEdit(
  kind: EditorKind,
  row: OperatorPestCrop | OperatorPestSource,
): void {
  if (kind === "crops") openCrop(row as OperatorPestCrop);
  else openSource(row as OperatorPestSource);
}

function openCrop(crop: OperatorPestCrop | null): void {
  dialogTitle.value = crop ? "编辑速查作物" : "新建速查作物";
  dialogInitial.value = crop
    ? { ...crop }
    : { id: "", name: "", icon: "🌱", summary: "", sort_order: 0 };
  dialogFields.value = [
    ...(!crop
      ? [
          {
            key: "id",
            label: "作物 id",
            required: true,
            maxlength: 40,
          } satisfies OperatorFormField,
        ]
      : []),
    { key: "name", label: "作物名称", required: true, maxlength: 60 },
    { key: "icon", label: "图标", maxlength: 8 },
    { key: "summary", label: "摘要", type: "textarea", rows: 3 },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
  openDialog(async (values) => {
    if (crop) await updateOperatorPestCrop(crop.id, values);
    else await createOperatorPestCrop(values);
    await closeAndReload(crop ? "速查作物已更新" : "速查作物已创建");
  });
}

function openSource(source: OperatorPestSource | null): void {
  dialogTitle.value = source ? "编辑病虫来源" : "新建病虫来源";
  dialogInitial.value = source
    ? { ...source }
    : {
        key: "",
        name: "",
        org: "",
        doc_type: "",
        doc_no: "",
        date: "",
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
    { key: "date", label: "日期", placeholder: "YYYY-MM-DD" },
    { key: "url", label: "链接", placeholder: "https://" },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
  openDialog(async (values) => {
    if (source) await updateOperatorPestSource(source.key, values);
    else await createOperatorPestSource(values);
    await closeAndReload(source ? "病虫来源已更新" : "病虫来源已创建");
  });
}

function openEntry(entry: OperatorPestEntryDetail | null): void {
  dialogTitle.value = entry ? "编辑病虫害条目" : "新建病虫害条目";
  dialogInitial.value = entry
    ? {
        ...entry,
        crop_id: entry.crop_id || entry.crop,
        source_keys: entry.sources.map((source) => source.key),
        ...imageInitial(entry),
      }
    : {
        id: "",
        crop_id: "",
        disease: "",
        kind: "disease",
        alias: "",
        pathogen: "",
        part: "",
        severity: "",
        occurrence: "",
        safety_note: "",
        symptoms: [],
        treatment: [],
        prevention: [],
        registered: [],
        chem_table: [],
        source_keys: [],
        sort_order: 0,
        file: "",
        credit: "",
        license: "",
        caption: "",
        source_url: "",
        shot_date: "",
        note: "",
      };
  dialogFields.value = [
    ...(!entry
      ? [
          {
            key: "id",
            label: "条目 id",
            required: true,
            maxlength: 80,
          } satisfies OperatorFormField,
        ]
      : []),
    {
      key: "crop_id",
      label: "作物",
      type: "select",
      required: true,
      options: cropOptions.value,
    },
    { key: "disease", label: "病害名称", required: true, maxlength: 60 },
    {
      key: "kind",
      label: "类型",
      type: "select",
      required: true,
      options: [
        { value: "disease", label: "病害" },
        { value: "pest", label: "虫害" },
      ],
    },
    { key: "alias", label: "别名", maxlength: 60 },
    { key: "pathogen", label: "病原", maxlength: 120 },
    { key: "part", label: "受害部位", maxlength: 80 },
    { key: "severity", label: "危害程度", maxlength: 80 },
    { key: "occurrence", label: "发生规律", type: "textarea", rows: 3 },
    { key: "safety_note", label: "安全提示", type: "textarea", rows: 2 },
    {
      key: "symptoms",
      label: "症状（一行一条）",
      type: "list",
      rows: 5,
    },
    {
      key: "treatment",
      label: "防治方法（一行一条）",
      type: "list",
      rows: 5,
    },
    {
      key: "prevention",
      label: "预防措施（一行一条）",
      type: "list",
      rows: 5,
    },
    {
      key: "registered",
      label: "登记药剂（一行一种）",
      type: "list",
      rows: 4,
    },
    {
      key: "chem_table",
      label: "用药参考表（一行一条，用 | 分隔）",
      type: "chem",
      rows: 4,
      hint: "列顺序：药剂 | 参考用量 | 安全间隔期 | 每季最多使用",
    },
    {
      key: "source_keys",
      label: "来源登记",
      type: "checkboxes",
      options: sourceOptions.value,
      hint: "可多选。未登记的来源不能保存。",
    },
    { key: "file", label: "实拍图路径", placeholder: "/images/pest/example.jpg" },
    { key: "credit", label: "图片署名" },
    { key: "license", label: "图片授权" },
    { key: "caption", label: "图片说明", type: "textarea", rows: 2 },
    { key: "source_url", label: "图片来源链接", placeholder: "https://" },
    { key: "shot_date", label: "拍摄日期", placeholder: "YYYY-MM-DD" },
    { key: "note", label: "图片备注", type: "textarea", rows: 2 },
    { key: "sort_order", label: "排序", type: "number", min: 0 },
  ];
  openDialog(async (values) => {
    const sourceKeys = Array.isArray(values.source_keys)
      ? values.source_keys.map(String)
      : [];
    const imagePayload = Object.fromEntries(
      IMAGE_FIELDS.map((key) => [key, String(values[key] ?? "").trim()]),
    );
    const entryPayload: Record<string, unknown> = {
      crop_id: values.crop_id,
      disease: values.disease,
      kind: values.kind,
      alias: values.alias,
      pathogen: values.pathogen,
      part: values.part,
      severity: values.severity,
      occurrence: values.occurrence,
      safety_note: values.safety_note,
      symptoms: values.symptoms,
      treatment: values.treatment,
      prevention: values.prevention,
      registered: values.registered,
      chem_table: values.chem_table,
      source_keys: sourceKeys,
      sort_order: values.sort_order,
    };
    let entryId = entry?.id ?? "";
    if (entry) {
      await updateOperatorPestEntry(entry.id, entryPayload);
    } else {
      entryPayload.id = values.id;
      const created = await createOperatorPestEntry(entryPayload);
      entryId = String(created.result);
    }

    if (imagePayload.file) {
      await setOperatorPestImage(entryId, imagePayload);
    } else if (entry?.image) {
      await deleteOperatorPestImage(entryId);
    }
    await closeAndReload(entry ? "病虫害条目已更新" : "病虫害条目已创建");
  });
}

function imageInitial(
  entry: OperatorPestEntryDetail,
): Record<string, string> {
  return Object.fromEntries(
    IMAGE_FIELDS.map((key) => [key, entry.image?.[key] ?? ""]),
  );
}

async function editEntry(entry: OperatorPestEntrySummary): Promise<void> {
  feedback.value = null;
  try {
    openEntry(await getOperatorPestEntry(entry.id));
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message: failure instanceof Error ? failure.message : "条目加载失败",
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

async function verifyEntry(entry: OperatorPestEntrySummary): Promise<void> {
  feedback.value = null;
  try {
    await verifyOperatorPestEntry(entry.id);
    await reloadAll("病虫害条目已标记复核");
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message: failure instanceof Error ? failure.message : "复核失败",
    };
  }
}

async function removeEntry(entry: OperatorPestEntrySummary): Promise<void> {
  if (!window.confirm("删除后不可恢复，确认删除这条病虫害条目？")) return;
  try {
    await deleteOperatorPestEntry(entry.id);
    await reloadAll("病虫害条目已删除");
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message: failure instanceof Error ? failure.message : "删除失败",
    };
  }
}

async function removeReference(
  kind: ReferenceTab,
  row: OperatorPestCrop | OperatorPestSource,
): Promise<void> {
  if (!window.confirm("确认删除？")) return;
  try {
    if (kind === "crops") {
      await deleteOperatorPestCrop((row as OperatorPestCrop).id);
    } else {
      await deleteOperatorPestSource((row as OperatorPestSource).key);
    }
    await reloadAll("内容已删除");
  } catch (failure) {
    feedback.value = {
      kind: "error",
      message: failure instanceof Error ? failure.message : "删除失败",
    };
  }
}

watch([cropFilter, overdueOnly], () => {
  void loadEntries();
});

onMounted(async () => {
  await Promise.all([loadBasics(), loadEntries()]);
});
</script>

<template>
  <section
    class="bo-page operator-pest"
    data-testid="operator-pest"
  >
    <header class="bo-page-header">
      <div>
        <p>农业内容</p>
        <h1 data-testid="backoffice-page-title">
          病虫害知识
        </h1>
        <span>维护条目、多值字段、来源、实拍图与复核记录。</span>
      </div>
      <button
        type="button"
        class="bo-button is-secondary"
        :disabled="loading || entriesLoading"
        @click="reloadAll()"
      >
        <i
          class="fas fa-rotate"
          :class="{ 'fa-spin': loading || entriesLoading }"
          aria-hidden="true"
        />
        刷新
      </button>
    </header>

    <BackofficeFeedback
      v-if="feedback"
      :kind="feedback.kind"
      :message="feedback.message"
      testid="operator-pest-feedback"
    />

    <BackofficeState
      v-if="loading"
      kind="loading"
      title="正在读取病虫害基础数据"
    />
    <BackofficeState
      v-else-if="error"
      kind="error"
      title="病虫害基础数据加载失败"
      :detail="error"
    >
      <button
        type="button"
        class="bo-button"
        @click="reloadAll()"
      >
        重试
      </button>
    </BackofficeState>

    <template v-else>
      <BackofficeCard
        title="病虫害条目"
        description="来源、实拍图和多值字段都从现有接口读写，公开速查立即反映。"
      >
        <template #actions>
          <button
            type="button"
            class="bo-button"
            @click="openEntry(null)"
          >
            <i
              class="fas fa-plus"
              aria-hidden="true"
            />
            新建条目
          </button>
        </template>

        <div class="bo-filterbar">
          <label class="bo-field">
            <span>作物筛选</span>
            <select v-model="cropFilter">
              <option value="">
                全部作物
              </option>
              <option
                v-for="crop in crops"
                :key="crop.id"
                :value="crop.id"
              >
                {{ crop.name }}
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
            class="bo-button is-secondary"
            :disabled="entriesLoading"
            @click="loadEntries"
          >
            刷新条目
          </button>
        </div>

        <BackofficeFeedback
          v-if="entriesError"
          kind="error"
          :message="entriesError"
        />
        <BackofficeState
          v-if="entriesLoading"
          kind="loading"
          title="正在读取病虫害条目"
        />
        <BackofficeState
          v-else-if="!entries.length"
          kind="empty"
          title="暂无病虫害条目"
          detail="当前筛选条件下没有条目。"
        />
        <div
          v-else
          class="bo-table-wrap"
        >
          <table class="bo-table">
            <thead>
              <tr>
                <th>作物</th>
                <th>名称</th>
                <th>类型</th>
                <th>复核</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="entry in entries"
                :key="entry.id"
                data-testid="operator-pest-entry-row"
                :data-entry-id="entry.id"
              >
                <td>{{ entry.crop_name }}</td>
                <td>
                  <strong>{{ entry.disease }}</strong>
                  <small>{{ entry.id }}</small>
                </td>
                <td>{{ entry.kind === "pest" ? "虫害" : "病害" }}</td>
                <td>
                  <span
                    class="bo-status"
                    :class="entry.is_verified ? 'is-active' : 'is-suspended'"
                  >
                    {{ entry.is_verified ? "已复核" : "待复核" }}
                  </span>
                  <small>{{ verificationText(entry) }}</small>
                </td>
                <td>
                  <div class="bo-row-actions">
                    <button
                      type="button"
                      class="bo-button is-small is-success"
                      @click="verifyEntry(entry)"
                    >
                      {{ entry.is_verified ? "重新复核" : "标记已复核" }}
                    </button>
                    <button
                      type="button"
                      class="bo-button is-small is-secondary"
                      @click="editEntry(entry)"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      class="bo-button is-small is-danger"
                      @click="removeEntry(entry)"
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
        description="作物和来源是条目可读性的基础，删除来源会同步移除条目关联。"
      >
        <template #actions>
          <button
            type="button"
            class="bo-button"
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
          aria-label="病虫害基础数据"
        >
          <button
            v-for="tab in [
              { key: 'crops', label: '作物' },
              { key: 'sources', label: '来源登记' },
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
          v-if="activeReferenceTab === 'crops'"
          class="bo-table-wrap"
        >
          <table class="bo-table">
            <thead>
              <tr>
                <th>id</th>
                <th>名称</th>
                <th>摘要</th>
                <th>排序</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="crop in crops"
                :key="crop.id"
                data-testid="operator-reference-row"
              >
                <td>{{ crop.id }}</td>
                <td>{{ crop.icon }} {{ crop.name }}</td>
                <td>{{ crop.summary }}</td>
                <td>{{ crop.sort_order }}</td>
                <td>
                  <div class="bo-row-actions">
                    <button
                      type="button"
                      class="bo-button is-small is-secondary"
                      @click="openEdit('crops', crop)"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      class="bo-button is-small is-danger"
                      @click="removeReference('crops', crop)"
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <BackofficeState
            v-if="!crops.length"
            kind="empty"
            title="暂无速查作物"
          />
        </div>

        <div
          v-else
          class="bo-table-wrap"
        >
          <table class="bo-table">
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
                  <small>{{ source.date }}</small>
                </td>
                <td>{{ source.org }}</td>
                <td>{{ source.doc_no || "待核" }}</td>
                <td>{{ source.sort_order }}</td>
                <td>
                  <div class="bo-row-actions">
                    <button
                      type="button"
                      class="bo-button is-small is-secondary"
                      @click="openEdit('sources', source)"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      class="bo-button is-small is-danger"
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
            title="暂无病虫来源"
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
</style>
