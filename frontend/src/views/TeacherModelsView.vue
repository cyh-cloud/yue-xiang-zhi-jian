<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";

import { ApiError } from "@/api/client";
import {
  deleteTeacherModel3d,
  getTeacherModels3d,
  type TeacherModel3d,
} from "@/api/teacher";
import {
  MODEL_3D_EXTENSIONS,
  uploadModel3d,
  validateModel3dFile,
} from "@/api/upload";
import { MAX_UPLOAD_MEGABYTES } from "@/api/uploadLimits";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";
import CdnFallbackNotice from "@/components/public/CdnFallbackNotice.vue";
import { resolveMediaUrl } from "@/shared/url";
import { useSessionStore } from "@/stores/session";

interface ModelViewerElement extends HTMLElement {
  activateAR?: () => Promise<void>;
}

type FeedbackKind = "success" | "error";
type PreviewState = "idle" | "waiting" | "ready" | "error" | "unavailable";

const PREVIEW_EXTENSIONS = new Set(["glb", "gltf", "usdz"]);
const MODEL_VIEWER_WAIT_MS = 5_000;
const CRAFT_LABELS: Readonly<Record<string, string>> = {
  embroidery: "广绣",
  woodcarving: "潮汕木雕",
  ceramics: "石湾陶艺",
  lacquer: "阳江漆器",
};

const session = useSessionStore();
const models = ref<TeacherModel3d[]>([]);
const loading = ref(true);
const loadError = ref("");
const feedback = ref<{ kind: FeedbackKind; message: string } | null>(null);

const fileInput = ref<HTMLInputElement | null>(null);
const selectedFile = ref<File | null>(null);
const title = ref("");
const description = ref("");
const craftType = ref("");
const uploading = ref(false);

const previewModel = ref<TeacherModel3d | null>(null);
const previewState = ref<PreviewState>("idle");
const previewError = ref("");
const viewerAvailable = ref(false);
const modelViewer = ref<ModelViewerElement | null>(null);

const deleteTarget = ref<TeacherModel3d | null>(null);
const deleteError = ref("");
const deleting = ref(false);

let loadSequence = 0;
let previewSequence = 0;

const accept = computed(() =>
  MODEL_3D_EXTENSIONS.map((extension) => `.${extension}`).join(","),
);
const selectedFileSummary = computed(() => {
  const file = selectedFile.value;
  return file ? `${file.name}，${formatBytes(file.size)}` : "";
});
const previewUrl = computed(() =>
  resolveMediaUrl(previewModel.value?.file_path),
);

function formatBytes(value: number): string {
  const bytes = Number(value) || 0;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function craftLabel(value: string): string {
  return CRAFT_LABELS[value] ?? (value || "未指定技艺");
}

function reviewStatusLabel(value: string): string {
  if (value === "approved") return "已通过";
  if (value === "rejected") return "已驳回";
  return "待审核";
}

function reviewStatusClass(value: string): string {
  if (value === "approved") return "is-approved";
  if (value === "rejected") return "is-rejected";
  return "is-pending";
}

function publicationLabel(model: TeacherModel3d): string {
  if (model.review_status === "approved" && model.is_published) return "已公开";
  if (model.review_status === "rejected") return "未公开";
  return "审核通过后公开";
}

function modelExtension(model: TeacherModel3d): string {
  const source = model.file_name || model.file_path;
  return /\.([a-z0-9]+)(?:[?#].*)?$/i.exec(source)?.[1]?.toLowerCase() ?? "";
}

function canPreview(model: TeacherModel3d): boolean {
  return PREVIEW_EXTENSIONS.has(modelExtension(model));
}

function canDelete(model: TeacherModel3d): boolean {
  return (
    session.can("course.manage") &&
    model.teacher_id === session.user?.id
  );
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

async function loadModels(): Promise<void> {
  const sequence = ++loadSequence;
  loading.value = true;
  loadError.value = "";
  try {
    const nextModels = await getTeacherModels3d();
    if (sequence === loadSequence) models.value = nextModels;
  } catch (error) {
    if (sequence !== loadSequence) return;
    models.value = [];
    loadError.value = errorMessage(error, "3D 模型列表加载失败");
  } finally {
    if (sequence === loadSequence) loading.value = false;
  }
}

function chooseFile(event: Event): void {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] ?? null;
  feedback.value = null;
  if (selectedFile.value) {
    title.value ||= selectedFile.value.name.replace(/\.[^.]+$/, "");
  }
}

function resetUploadForm(): void {
  selectedFile.value = null;
  title.value = "";
  description.value = "";
  craftType.value = "";
  if (fileInput.value) fileInput.value.value = "";
}

async function submitUpload(): Promise<void> {
  feedback.value = null;
  const file = selectedFile.value;
  const invalid = validateModel3dFile(file);
  if (!file || invalid) {
    feedback.value = {
      kind: "error",
      message: invalid?.message ?? "请选择一个非空的 3D 模型文件。",
    };
    return;
  }

  uploading.value = true;
  try {
    const response = await uploadModel3d({
      file,
      title: title.value,
      description: description.value,
      craftType: craftType.value,
    });
    resetUploadForm();
    feedback.value = {
      kind: "success",
      message: response.message || "3D 模型上传成功，等待审核。",
    };
    await loadModels();
  } catch (error) {
    feedback.value = {
      kind: "error",
      message: errorMessage(
        error,
        "服务器拒绝了这次上传，请检查文件后重试。",
      ),
    };
  } finally {
    uploading.value = false;
  }
}

async function openPreview(model: TeacherModel3d): Promise<void> {
  if (!canPreview(model)) {
    feedback.value = {
      kind: "error",
      message: `暂不支持 .${modelExtension(model) || "未知"} 格式在线预览，请打开原文件查看。`,
    };
    return;
  }

  previewModel.value = model;
  previewState.value = "waiting";
  previewError.value = "";
  viewerAvailable.value = false;
  const sequence = ++previewSequence;
  await nextTick();
  await prepareViewer(sequence);
}

async function prepareViewer(sequence: number): Promise<void> {
  if (document.documentElement.dataset.cdnModelViewer === "failed") {
    setViewerUnavailable();
    return;
  }

  if (customElements.get("model-viewer")) {
    viewerAvailable.value = true;
    await nextTick();
    if (sequence === previewSequence) syncViewerSource();
    return;
  }

  let timer: number | undefined;
  try {
    await Promise.race([
      customElements.whenDefined("model-viewer"),
      new Promise((_, reject) => {
        timer = window.setTimeout(
          () => reject(new Error("model-viewer timeout")),
          MODEL_VIEWER_WAIT_MS,
        );
      }),
    ]);
    if (timer !== undefined) window.clearTimeout(timer);
    if (sequence !== previewSequence) return;
    if (document.documentElement.dataset.cdnModelViewer === "failed") {
      setViewerUnavailable();
      return;
    }
    viewerAvailable.value = true;
    await nextTick();
    if (sequence === previewSequence) syncViewerSource();
  } catch {
    if (timer !== undefined) window.clearTimeout(timer);
    if (sequence !== previewSequence) return;
    setViewerUnavailable();
  }
}

function syncViewerSource(source = previewUrl.value): void {
  if (!source || !modelViewer.value) {
    previewState.value = "error";
    previewError.value = "模型文件地址缺失，无法加载预览。";
    return;
  }
  modelViewer.value.setAttribute("src", source);
  modelViewer.value.setAttribute("alt", previewModel.value?.title ?? "3D 模型");
  previewState.value = "waiting";
  previewError.value = "";
}

function setViewerUnavailable(): void {
  viewerAvailable.value = false;
  previewState.value = "unavailable";
  previewError.value =
    "3D 查看器资源加载失败，模型预览暂不可用，请稍后刷新页面重试。";
}

function handleModelLoad(): void {
  previewState.value = "ready";
  previewError.value = "";
}

function handleModelError(): void {
  previewState.value = "error";
  previewError.value =
    "3D 模型文件加载失败或格式不支持，请打开原文件或稍后重试。";
}

async function retryPreview(): Promise<void> {
  if (!previewModel.value) return;
  const sequence = ++previewSequence;
  previewState.value = "waiting";
  previewError.value = "";
  await nextTick();
  if (!viewerAvailable.value) {
    await prepareViewer(sequence);
    return;
  }
  if (sequence !== previewSequence) return;
  const separator = previewUrl.value.includes("?") ? "&" : "?";
  syncViewerSource(`${previewUrl.value}${separator}retry=${Date.now()}`);
}

function closePreview(): void {
  previewSequence += 1;
  previewModel.value = null;
  previewState.value = "idle";
  previewError.value = "";
  viewerAvailable.value = false;
  modelViewer.value = null;
}

function askDelete(model: TeacherModel3d): void {
  deleteError.value = "";
  deleteTarget.value = model;
}

function closeDelete(): void {
  if (deleting.value) return;
  deleteTarget.value = null;
  deleteError.value = "";
}

async function confirmDelete(): Promise<void> {
  const target = deleteTarget.value;
  if (!target) return;
  deleting.value = true;
  deleteError.value = "";
  try {
    const response = await deleteTeacherModel3d(target.id);
    deleteTarget.value = null;
    feedback.value = {
      kind: "success",
      message: response.message || "删除成功",
    };
    await loadModels();
  } catch (error) {
    deleteError.value = errorMessage(error, "删除失败，请稍后重试");
  } finally {
    deleting.value = false;
  }
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== "Escape") return;
  if (previewModel.value) closePreview();
  else if (deleteTarget.value) closeDelete();
}

onMounted(() => {
  document.addEventListener("keydown", handleKeydown);
  void loadModels();
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", handleKeydown);
  previewSequence += 1;
});
</script>

<template>
  <section class="backoffice-page model-page">
    <header class="backoffice-page-header">
      <div>
        <p>教学工作</p>
        <h1>3D 模型</h1>
        <span>
          支持 {{ MODEL_3D_EXTENSIONS.join("/") }}，单个文件不超过
          {{ MAX_UPLOAD_MEGABYTES }}MB。上传后需经审核才会出现在公开手工艺页。
        </span>
      </div>
    </header>

    <BackofficeFeedback
      v-if="feedback"
      :kind="feedback.kind"
      :message="feedback.message"
      testid="teacher-models-feedback"
    />
    <CdnFallbackNotice />

    <form
      class="backoffice-card model-upload-card"
      data-testid="teacher-model-upload"
      @submit.prevent="submitUpload"
    >
      <header class="backoffice-card-head">
        <div>
          <h2>上传模型</h2>
          <p>文件通过真实 multipart 请求上传，保存后立即出现在下方列表。</p>
        </div>
      </header>
      <div class="model-form-grid">
        <label class="backoffice-field is-wide">
          <span>模型文件</span>
          <input
            id="model-file"
            ref="fileInput"
            :accept="accept"
            type="file"
            @change="chooseFile"
          >
        </label>
        <p
          v-if="selectedFileSummary"
          class="model-file-summary"
        >
          已选择：{{ selectedFileSummary }}
        </p>
        <label class="backoffice-field">
          <span>标题</span>
          <input
            id="model-title"
            v-model="title"
            autocomplete="off"
            placeholder="默认使用文件名"
          >
        </label>
        <label class="backoffice-field">
          <span>技艺类型</span>
          <select
            id="model-craft"
            v-model="craftType"
          >
            <option value="">
              不指定
            </option>
            <option value="embroidery">
              广绣
            </option>
            <option value="woodcarving">
              潮汕木雕
            </option>
            <option value="ceramics">
              石湾陶艺
            </option>
            <option value="lacquer">
              阳江漆器
            </option>
          </select>
        </label>
        <label class="backoffice-field is-wide">
          <span>描述</span>
          <textarea
            id="model-description"
            v-model="description"
            rows="3"
            placeholder="可选，说明模型内容或教学用途"
          />
        </label>
      </div>
      <div class="model-upload-actions">
        <button
          type="submit"
          class="backoffice-button"
          :disabled="uploading"
        >
          <i
            class="fas"
            :class="uploading ? 'fa-spinner fa-spin' : 'fa-cloud-arrow-up'"
            aria-hidden="true"
          />
          {{ uploading ? "正在上传..." : "上传模型" }}
        </button>
      </div>
    </form>

    <BackofficeCard
      title="已上传模型"
      description="只显示当前教师账号上传的模型，删除后列表与公开结果同步更新。"
      flush
    >
      <template #actions>
        <button
          type="button"
          class="backoffice-button is-secondary is-small"
          :disabled="loading"
          @click="loadModels"
        >
          <i
            class="fas fa-rotate"
            :class="{ 'fa-spin': loading }"
            aria-hidden="true"
          />
          刷新列表
        </button>
      </template>

      <BackofficeState
        v-if="loading"
        kind="loading"
        title="正在加载 3D 模型"
      />
      <BackofficeState
        v-else-if="loadError"
        kind="error"
        title="3D 模型列表加载失败"
        :detail="loadError"
      >
        <button
          type="button"
          class="backoffice-button"
          @click="loadModels"
        >
          重试
        </button>
      </BackofficeState>
      <BackofficeState
        v-else-if="!models.length"
        kind="empty"
        title="暂无 3D 模型"
        detail="上传第一个模型，审核通过后学员可在手工艺页查看。"
      />
      <div
        v-else
        class="backoffice-table-wrap"
      >
        <table class="backoffice-table model-table">
          <thead>
            <tr>
              <th>模型</th>
              <th>文件</th>
              <th>审核状态</th>
              <th>上传时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="model in models"
              :key="model.id"
              data-testid="teacher-model-row"
              :data-model-id="model.id"
            >
              <td>
                <strong>{{ model.title }}</strong>
                <small>{{ craftLabel(model.craft_type) }}</small>
                <small v-if="model.description">
                  {{ model.description }}
                </small>
              </td>
              <td>
                <strong>{{ model.file_name }}</strong>
                <small>{{ formatBytes(model.file_size) }}</small>
                <small v-if="!canPreview(model)">
                  该格式暂不支持在线预览
                </small>
              </td>
              <td>
                <span
                  class="backoffice-status model-status"
                  :class="reviewStatusClass(model.review_status)"
                >
                  {{ reviewStatusLabel(model.review_status) }}
                </span>
                <small>{{ publicationLabel(model) }}</small>
                <small
                  v-if="model.review_comment"
                  class="model-review-reason"
                >
                  驳回理由：{{ model.review_comment }}
                </small>
              </td>
              <td>
                <span>{{ model.created_at }}</span>
              </td>
              <td>
                <div class="backoffice-row-actions model-actions">
                  <button
                    v-if="canPreview(model)"
                    type="button"
                    class="backoffice-button is-secondary is-small"
                    data-testid="teacher-model-preview"
                    @click="openPreview(model)"
                  >
                    预览
                  </button>
                  <a
                    class="backoffice-button is-secondary is-small"
                    :href="resolveMediaUrl(model.file_path)"
                    target="_blank"
                    rel="noopener"
                  >
                    打开文件
                  </a>
                  <button
                    v-if="canDelete(model)"
                    type="button"
                    class="backoffice-button is-danger is-small"
                    data-testid="teacher-model-delete"
                    @click="askDelete(model)"
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

    <Teleport to="body">
      <div
        v-if="previewModel"
        class="backoffice-modal-overlay"
        @click.self="closePreview"
      >
        <section
          class="backoffice-modal model-preview-dialog"
          role="dialog"
          aria-modal="true"
          aria-label="3D 模型预览"
          data-testid="teacher-model-preview-dialog"
        >
          <header class="backoffice-modal-head">
            <div>
              <p>模型预览</p>
              <h2>{{ previewModel.title }}</h2>
            </div>
            <button
              type="button"
              class="backoffice-icon-button"
              aria-label="关闭预览"
              @click="closePreview"
            >
              <i
                class="fas fa-xmark"
                aria-hidden="true"
              />
            </button>
          </header>
          <div class="backoffice-modal-body">
            <div class="model-preview-meta">
              <span>{{ previewModel.file_name }}</span>
              <span>{{ formatBytes(previewModel.file_size) }}</span>
              <span>{{ reviewStatusLabel(previewModel.review_status) }}</span>
            </div>
            <div class="model-preview-stage">
              <div
                v-if="previewState === 'error' || previewState === 'unavailable'"
                class="model-preview-placeholder"
                data-testid="teacher-model-preview-state"
                role="alert"
              >
                <i
                  class="fas fa-triangle-exclamation"
                  aria-hidden="true"
                />
                <strong>{{ previewError }}</strong>
                <button
                  v-if="previewState === 'error'"
                  type="button"
                  class="backoffice-button is-secondary is-small"
                  @click="retryPreview"
                >
                  重新加载
                </button>
              </div>
              <model-viewer
                v-else-if="viewerAvailable"
                ref="modelViewer"
                class="teacher-model-viewer"
                camera-controls
                auto-rotate
                shadow-intensity="1"
                exposure="1"
                environment-image="neutral"
                ar
                ar-modes="webxr scene-viewer quick-look"
                @load="handleModelLoad"
                @error="handleModelError"
              />
              <div
                v-else
                class="model-preview-placeholder"
                data-testid="teacher-model-preview-state"
                role="status"
              >
                <i
                  class="fas fa-cube"
                  aria-hidden="true"
                />
                <strong>正在准备 3D 查看器...</strong>
              </div>
            </div>
            <div
              v-if="previewState === 'waiting' && viewerAvailable"
              class="model-preview-state"
              data-testid="teacher-model-preview-state"
              role="status"
            >
              模型加载中...
            </div>
            <div
              v-else-if="previewState === 'ready'"
              class="model-preview-state is-ready"
              data-testid="teacher-model-preview-state"
              role="status"
            >
              预览已就绪，可拖动旋转模型。
            </div>
            <div class="model-preview-footer">
              <span>模型预览依赖外部 model-viewer 资源。</span>
              <a
                class="backoffice-button is-secondary is-small"
                :href="previewUrl"
                target="_blank"
                rel="noopener"
              >
                打开原文件
              </a>
            </div>
          </div>
        </section>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="deleteTarget"
        class="backoffice-modal-overlay"
        @click.self="closeDelete"
      >
        <section
          class="backoffice-modal is-confirm"
          role="dialog"
          aria-modal="true"
          aria-label="删除 3D 模型"
          data-testid="teacher-model-delete-dialog"
        >
          <header class="backoffice-modal-head">
            <div>
              <p>删除模型</p>
              <h2>{{ deleteTarget.title }}</h2>
            </div>
            <button
              type="button"
              class="backoffice-icon-button"
              aria-label="关闭删除确认"
              :disabled="deleting"
              @click="closeDelete"
            >
              <i
                class="fas fa-xmark"
                aria-hidden="true"
              />
            </button>
          </header>
          <div class="backoffice-modal-body">
            <BackofficeFeedback
              v-if="deleteError"
              kind="error"
              :message="deleteError"
            />
            <p class="model-delete-copy">
              删除后，模型文件、审核记录和公开结果都会移除，此操作不可恢复。
            </p>
            <div class="model-delete-actions">
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
                {{ deleting ? "正在删除..." : "确认删除" }}
              </button>
            </div>
          </div>
        </section>
      </div>
    </Teleport>
  </section>
</template>

<style src="./teacher/teacher.css"></style>
