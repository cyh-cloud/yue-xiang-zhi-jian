<script setup lang="ts">
import { computed, ref, watch } from "vue";

import {
  diagnoseAgriculture,
  getPestKnowledge,
  type PestCrop,
  type PestDiagnosis,
} from "@/api/agriculture";
import { ApiError } from "@/api/client";

const props = defineProps<{
  currentProductId: string;
}>();

const MAX_IMAGES = 3;
const MAX_IMAGE_BYTES = 4 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
]);

const panelOpen = ref(false);
const crops = ref<PestCrop[]>([]);
const crop = ref("");
const cropLoadError = ref("");
const symptoms = ref("");
const images = ref<string[]>([]);
const busy = ref(false);
const error = ref("");
const result = ref<PestDiagnosis | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const symptomInput = ref<HTMLTextAreaElement | null>(null);
let userSelectedCrop = false;

const availableCrops = computed(() => crops.value);
const symptomPlaceholder = computed(() =>
  crop.value === "aquatic"
    ? "例如：虾体甲壳内侧出现白色斑点，游塘、反应迟钝..."
    : "例如：叶片发黄，有褐色斑点，部分果实脱落...",
);

watch(
  () => props.currentProductId,
  (productId) => {
    if (!productId || userSelectedCrop) return;
    if (availableCrops.value.some((item) => item.id === productId)) {
      crop.value = productId;
    }
  },
  { immediate: true },
);

void loadCrops();

async function loadCrops(): Promise<void> {
  cropLoadError.value = "";
  try {
    const response = await getPestKnowledge({ limit: 1 });
    crops.value = response.crops;
    if (
      !userSelectedCrop &&
      response.crops.some((item) => item.id === props.currentProductId)
    ) {
      crop.value = props.currentProductId;
    } else if (
      !userSelectedCrop &&
      !response.crops.some((item) => item.id === crop.value)
    ) {
      crop.value = response.crops[0]?.id ?? "";
    }
  } catch {
    crops.value = [];
    crop.value = "";
    cropLoadError.value = "作物数据加载失败，请检查网络后重试。";
  }
}

function togglePanel(): void {
  panelOpen.value = !panelOpen.value;
}

function selectCrop(cropId: string): void {
  crop.value = cropId;
  userSelectedCrop = true;
  error.value = "";
}

function openFilePicker(): void {
  fileInput.value?.click();
}

async function handleFiles(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  input.value = "";
  if (!files.length) return;

  error.value = "";
  const room = MAX_IMAGES - images.value.length;
  if (room <= 0) {
    error.value = `一次最多上传 ${MAX_IMAGES} 张照片。`;
    return;
  }
  if (files.length > room) {
    error.value = `一次最多上传 ${MAX_IMAGES} 张照片，已保留前 ${room} 张。`;
  }

  for (const file of files.slice(0, room)) {
    if (file.size === 0) {
      error.value = "照片为空，请重新选择。";
      continue;
    }
    if (!ALLOWED_IMAGE_TYPES.has(file.type)) {
      error.value = "照片格式不受支持，请上传 JPG / PNG / WebP 格式的照片。";
      continue;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      error.value = "照片过大，请换一张小于 4 MB 的图片。";
      continue;
    }
    try {
      images.value.push(await readFileAsDataUrl(file));
    } catch {
      error.value = "读取照片失败，请重新选择。";
    }
  }
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") resolve(reader.result);
      else reject(new Error("read_failed"));
    };
    reader.onerror = () => reject(reader.error ?? new Error("read_failed"));
    reader.readAsDataURL(file);
  });
}

function removeImage(index: number): void {
  images.value.splice(index, 1);
}

async function runDiagnosis(): Promise<void> {
  if (busy.value) return;
  error.value = "";
  result.value = null;

  const trimmedSymptoms = symptoms.value.trim();
  if (!crop.value) {
    error.value = "请先选择作物类型后再开始诊断。";
    return;
  }
  if (!trimmedSymptoms && !images.value.length) {
    error.value = "请先上传一张作物照片，或描述症状后再开始诊断。";
    symptomInput.value?.focus();
    return;
  }
  if (trimmedSymptoms.length > 500) {
    error.value = "症状描述过长，请控制在 500 字以内。";
    symptomInput.value?.focus();
    return;
  }

  busy.value = true;
  try {
    const response = await diagnoseAgriculture({
      crop: crop.value,
      symptoms: trimmedSymptoms,
      ...(images.value.length ? { image: [...images.value] } : {}),
    });
    result.value = response.diagnosis;
  } catch (failure) {
    error.value = diagnosisErrorMessage(failure);
  } finally {
    busy.value = false;
  }
}

function resetDiagnosis(): void {
  result.value = null;
  error.value = "";
  symptoms.value = "";
  images.value = [];
  symptomInput.value?.focus();
}

function diagnosisErrorMessage(failure: unknown): string {
  if (failure instanceof ApiError) {
    if (failure.status === 0) {
      return "无法连接诊断服务，请检查网络后重试。";
    }
    return failure.message;
  }
  return "诊断服务暂时不可用，请稍后重试。";
}
</script>

<template>
  <section
    id="pest-diagnosis-section"
    class="card-section"
    aria-labelledby="pest-diagnosis-title"
  >
    <h3
      id="pest-diagnosis-title"
      class="card-section-title"
    >
      <i
        class="fas fa-bug"
        aria-hidden="true"
      />
      病虫害AI诊断
    </h3>

    <div class="diagnosis-entry">
      <div class="diagnosis-entry-card">
        <div class="module-icon">
          <i
            class="fas fa-bug"
            aria-hidden="true"
          />
        </div>
        <h4>病虫害智能诊断</h4>
        <p>选择作物类型，描述症状，AI智能诊断并给出防治方案</p>
        <button
          type="button"
          class="btn btn-primary btn-sm"
          :aria-expanded="panelOpen"
          @click="togglePanel"
        >
          <i
            class="fas"
            :class="panelOpen ? 'fa-chevron-up' : 'fa-chevron-down'"
            aria-hidden="true"
          />
          {{ panelOpen ? "收起诊断面板" : "展开诊断面板" }}
        </button>
      </div>
    </div>

    <div
      v-show="panelOpen"
      class="sim-panel"
      data-testid="pest-diagnosis-panel"
    >
      <div class="diagnosis-setup">
        <div class="crop-selector">
          <label>选择作物类型</label>
          <div
            class="crop-options"
            role="group"
            aria-label="选择诊断作物"
          >
            <button
              v-for="item in availableCrops"
              :key="item.id"
              type="button"
              class="crop-btn"
              :class="{ active: crop === item.id }"
              :aria-pressed="crop === item.id"
              :disabled="busy"
              @click="selectCrop(item.id)"
            >
              {{ item.icon }} {{ item.name }}
            </button>
          </div>
          <p
            v-if="cropLoadError"
            class="diag-error"
            data-testid="pest-crop-error"
            role="alert"
          >
            {{ cropLoadError }}
            <button
              type="button"
              class="btn btn-outline btn-sm"
              @click="loadCrops"
            >
              重试
            </button>
          </p>
        </div>

        <div class="symptom-input-area">
          <label for="symptom-text">
            描述症状（照片与文字至少提供一项，两者同时提供更准确）
          </label>
          <textarea
            id="symptom-text"
            ref="symptomInput"
            v-model="symptoms"
            maxlength="500"
            rows="3"
            aria-label="描述症状"
            :placeholder="symptomPlaceholder"
          />
          <p class="symptom-hint">
            {{ symptoms.length }}/500 字 · 最多可上传 {{ MAX_IMAGES }} 张照片，单张不超过 4 MB
          </p>
        </div>

        <div class="diagnosis-actions">
          <button
            type="button"
            class="btn btn-primary"
            :disabled="busy || !crop"
            @click="runDiagnosis"
          >
            <i
              class="fas"
              :class="busy ? 'fa-spinner fa-spin' : 'fa-search'"
              aria-hidden="true"
            />
            {{ busy ? "正在分析..." : "开始诊断" }}
          </button>
          <button
            type="button"
            class="btn btn-outline"
            :disabled="busy"
            @click="openFilePicker"
          >
            <i
              class="fas fa-camera"
              aria-hidden="true"
            />
            上传照片
          </button>
        </div>

        <input
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          aria-label="选择诊断照片"
          class="diagnosis-file-input"
          @change="handleFiles"
        >

        <div
          v-if="images.length"
          class="diag-photo-preview"
        >
          <span class="diag-photo-tip">
            已选择 {{ images.length }} 张照片，将随诊断一并提交
          </span>
          <div
            v-for="(image, index) in images"
            :key="index"
            class="diag-photo-item"
          >
            <img
              :src="image"
              :alt="`待诊断照片 ${index + 1}`"
            >
            <button
              type="button"
              class="diag-photo-remove"
              aria-label="移除这张照片"
              @click="removeImage(index)"
            >
              <i
                class="fas fa-times"
                aria-hidden="true"
              />
            </button>
          </div>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            @click="images = []"
          >
            清空照片
          </button>
        </div>
      </div>

      <p
        v-if="error"
        class="diag-error"
        role="alert"
      >
        {{ error }}
      </p>

      <div
        v-if="result"
        class="diagnosis-result"
        data-testid="diagnosis-result"
      >
        <div class="result-header">
          <h4>
            <i
              class="fas fa-stethoscope"
              aria-hidden="true"
            />
            {{ result.source === "knowledge_base" ? "知识库匹配结果" : "诊断结果" }}
          </h4>
          <span
            v-if="result.severity"
            class="severity-badge"
          >
            {{ result.severity }}
          </span>
        </div>

        <p
          class="diag-source"
          :data-source="result.source"
        >
          结论来源：{{ result.source_label }} · {{ result.source_note }}
        </p>

        <div class="result-info">
          <div class="disease-badge">
            <i
              class="fas fa-exclamation-triangle"
              aria-hidden="true"
            />
            <span>{{ result.crop_icon }} {{ result.disease }}</span>
          </div>
        </div>

        <div class="diagnosis-grid">
          <div class="diagnosis-section">
            <h5>
              <i
                class="fas fa-thermometer-half"
                aria-hidden="true"
              />
              {{ result.source === "knowledge_base" ? "该病典型症状" : "症状表现" }}
            </h5>
            <ul>
              <li
                v-for="item in result.symptoms"
                :key="item"
              >
                {{ item }}
              </li>
            </ul>
          </div>
          <div class="diagnosis-section">
            <h5>
              <i
                class="fas fa-prescription-bottle-alt"
                aria-hidden="true"
              />
              防治方案
            </h5>
            <ul>
              <li
                v-for="item in result.treatment"
                :key="item"
              >
                {{ item }}
              </li>
            </ul>
          </div>
          <div class="diagnosis-section">
            <h5>
              <i
                class="fas fa-shield-alt"
                aria-hidden="true"
              />
              预防措施
            </h5>
            <ul>
              <li
                v-for="item in result.prevention"
                :key="item"
              >
                {{ item }}
              </li>
            </ul>
          </div>
        </div>

        <div class="diagnosis-extra">
          <div class="extra-item">
            <i
              class="fas fa-clock"
              aria-hidden="true"
            />
            <span>
              <strong>最佳防治期：</strong>
              {{ result.timing }}
            </span>
          </div>
          <div
            v-if="result.note"
            class="extra-item"
          >
            <i
              class="fas fa-info-circle"
              aria-hidden="true"
            />
            <span>{{ result.note }}</span>
          </div>
        </div>

        <p
          class="pest-warn"
          data-testid="diagnosis-disclaimer"
        >
          <i
            class="fas fa-exclamation-triangle"
            aria-hidden="true"
          />
          <span>
            用药免责声明：农药种类、用量、安全间隔期与混配方式请以所购产品标签和当地农技站指导为准；
            本诊断不作为处方，请勿仅凭结果自行加大剂量。
          </span>
        </p>

        <div class="diagnosis-actions">
          <button
            type="button"
            class="btn btn-outline btn-sm"
            @click="resetDiagnosis"
          >
            <i
              class="fas fa-redo"
              aria-hidden="true"
            />
            重新诊断
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.diagnosis-file-input {
  display: none;
}

.diag-error {
  margin: 16px 0;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, #ef4444 10%, transparent);
  color: #b91c1c;
}
</style>
