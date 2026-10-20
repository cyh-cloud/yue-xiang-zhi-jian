<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";

import {
  getCraftDetail,
  getCrafts,
  getPublicModels3D,
  type CraftDetail,
  type CraftPurchaseCategory,
  type CraftSummary,
  type CraftVideo,
  type PublicModel3D,
} from "@/api/crafts";
import { resolveMediaUrl } from "@/shared/url";

interface ModelViewerElement extends HTMLElement {
  activateAR?: () => Promise<void>;
}

type VideoState = "idle" | "loading" | "ready" | "error";
type ModelState = "idle" | "waiting" | "ready" | "error" | "unavailable";

const CATEGORY_META: Readonly<
  Record<string, { icon: string; badge: string }>
> = {
  essential: { icon: "fa-circle-check", badge: "必买" },
  consumable: { icon: "fa-boxes-stacked", badge: "常备" },
  advanced: { icon: "fa-sliders", badge: "选配" },
};
const DEFAULT_CATEGORY_META = { icon: "fa-circle-check", badge: "必买" };
const CRAFT_ANGLES = [
  { label: "正面", orbit: "0deg 75deg auto" },
  { label: "侧面", orbit: "90deg 75deg auto" },
  { label: "顶部", orbit: "0deg 15deg auto" },
  { label: "特写", orbit: "0deg 75deg 1.5m" },
] as const;
const SUPPORTED_MODEL_EXTENSIONS = new Set(["glb", "gltf", "usdz"]);
const CRAFT_STORAGE_KEY = "yuexiang_craft_selection";
const VIDEO_LOAD_TIMEOUT_MS = 12_000;
const MODEL_VIEWER_WAIT_MS = 5_000;

const crafts = ref<CraftSummary[]>([]);
const craftsLoading = ref(true);
const craftsError = ref("");
const selectedCraftId = ref("");

const detail = ref<CraftDetail | null>(null);
const detailLoading = ref(false);
const detailError = ref("");
const activeStepIndex = ref(0);
const progressCount = ref(0);

const selectedVideoIndex = ref(-1);
const videoState = ref<VideoState>("idle");
const videoError = ref("");
const failedCoverIds = ref<Set<number>>(new Set());
let videoTimer: number | undefined;

const models = ref<PublicModel3D[]>([]);
const modelsLoading = ref(false);
const modelsError = ref("");
const selectedModelIndex = ref(-1);
const viewerAvailable = ref(false);
const modelState = ref<ModelState>("idle");
const modelError = ref("");
const modelViewer = ref<ModelViewerElement | null>(null);
const paused = ref(false);
const slow = ref(false);
const angleIndex = ref(0);

const openCategoryKeys = ref<string[]>([]);
let detailSequence = 0;
let modelSequence = 0;

const selectedVideo = computed(() => {
  if (selectedVideoIndex.value < 0) return null;
  return detail.value?.videos[selectedVideoIndex.value] ?? null;
});
const selectedModel = computed(() => {
  if (selectedModelIndex.value < 0) return null;
  return models.value[selectedModelIndex.value] ?? null;
});
const selectedModelUrl = computed(() =>
  resolveMediaUrl(selectedModel.value?.file_path),
);
const modelFormatError = computed(() => {
  const model = selectedModel.value;
  if (!model) return "";
  if (!model.file_path) return "模型文件地址缺失，无法加载。";
  const extension = modelExtension(model);
  if (!extension) return "模型文件缺少扩展名，无法确认格式。";
  if (!SUPPORTED_MODEL_EXTENSIONS.has(extension)) {
    return `暂不支持 .${extension} 格式，请使用 GLB、glTF 或 USDZ 模型。`;
  }
  return "";
});
const controlsEnabled = computed(
  () =>
    Boolean(selectedModel.value) &&
    !modelFormatError.value &&
    viewerAvailable.value &&
    modelState.value === "ready",
);
const videoEmbedUrl = computed(() => {
  const video = selectedVideo.value;
  if (!video?.bvid) return "";
  return `https://player.bilibili.com/player.html?bvid=${encodeURIComponent(
    video.bvid,
  )}&page=1&autoplay=0&high_quality=1`;
});
const purchaseGuide = computed(() => detail.value?.purchase_guide ?? null);
const purchaseCategories = computed(
  () => purchaseGuide.value?.categories ?? [],
);
const hasPurchaseGuide = computed(
  () =>
    Boolean(purchaseGuide.value?.budget) ||
    purchaseCategories.value.length > 0 ||
    Boolean(purchaseGuide.value?.buying_tips),
);
const allCategoriesOpen = computed(
  () =>
    purchaseCategories.value.length > 0 &&
    purchaseCategories.value.every((category) =>
      openCategoryKeys.value.includes(category.key),
    ),
);

watch(selectedCraftId, (craftId) => {
  if (!craftId) return;
  writeSavedCraft(craftId);
  void loadCraftDetail(craftId);
  void loadModels(craftId);
});

onMounted(() => {
  document.addEventListener("keydown", handleDocumentKeydown);
  void loadCrafts();
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", handleDocumentKeydown);
  clearVideoTimer();
});

async function loadCrafts(): Promise<void> {
  craftsLoading.value = true;
  craftsError.value = "";
  try {
    const response = await getCrafts();
    crafts.value = response.crafts;
    if (!response.crafts.length) {
      craftsError.value = "暂无手工艺数据";
      return;
    }
    const saved = readSavedCraft();
    const firstCraft = response.crafts[0];
    if (!firstCraft) {
      craftsError.value = "暂无手工艺数据";
      return;
    }
    const nextId =
      response.crafts.find((craft) => craft.id === saved)?.id ??
      firstCraft.id;
    if (selectedCraftId.value === nextId) {
      void loadCraftDetail(nextId);
      void loadModels(nextId);
    } else {
      selectedCraftId.value = nextId;
    }
  } catch {
    craftsError.value = "手工艺目录加载失败，请检查网络后重试";
  } finally {
    craftsLoading.value = false;
  }
}

async function loadCraftDetail(craftId: string): Promise<void> {
  const sequence = ++detailSequence;
  detailLoading.value = true;
  detailError.value = "";
  detail.value = null;
  closeVideo();
  try {
    const response = await getCraftDetail(craftId);
    if (sequence !== detailSequence) return;
    if (!response.success || !response.data) {
      detailError.value =
        response.message || "手工艺内容加载失败，请稍后重试";
      return;
    }
    detail.value = response.data;
    activeStepIndex.value = 0;
    progressCount.value = readProgress(craftId, response.data.steps.length);
    const firstCategory = response.data.purchase_guide?.categories[0];
    openCategoryKeys.value = firstCategory ? [firstCategory.key] : [];
  } catch {
    if (sequence !== detailSequence) return;
    detailError.value = "手工艺内容加载失败，请检查网络后重试";
  } finally {
    if (sequence === detailSequence) detailLoading.value = false;
  }
}

async function loadModels(craftId: string): Promise<void> {
  const sequence = ++modelSequence;
  modelsLoading.value = true;
  modelsError.value = "";
  clearModelState();
  try {
    const response = await getPublicModels3D(craftId);
    if (sequence !== modelSequence) return;
    models.value = response.models;
    if (!response.models.length) return;
    selectedModelIndex.value = 0;
    modelsLoading.value = false;
    await prepareModelViewer(sequence);
  } catch {
    if (sequence !== modelSequence) return;
    modelsError.value = "3D 模型加载失败，请检查网络后重试";
  } finally {
    if (sequence === modelSequence) modelsLoading.value = false;
  }
}

async function prepareModelViewer(sequence: number): Promise<void> {
  modelState.value = "waiting";
  modelError.value = "";
  if (document.documentElement.dataset.cdnModelViewer === "failed") {
    setViewerUnavailable();
    return;
  }
  if (customElements.get("model-viewer")) {
    viewerAvailable.value = true;
    await nextTick();
    syncViewerSource(selectedModelUrl.value);
    return;
  }
  try {
    await Promise.race([
      customElements.whenDefined("model-viewer"),
      new Promise((_, reject) => {
        window.setTimeout(
          () => reject(new Error("model-viewer timeout")),
          MODEL_VIEWER_WAIT_MS,
        );
      }),
    ]);
    if (sequence !== modelSequence) return;
    if (document.documentElement.dataset.cdnModelViewer === "failed") {
      setViewerUnavailable();
      return;
    }
    viewerAvailable.value = true;
    await nextTick();
    syncViewerSource(selectedModelUrl.value);
  } catch {
    if (sequence !== modelSequence) return;
    setViewerUnavailable();
  }
}

function setViewerUnavailable(): void {
  viewerAvailable.value = false;
  modelState.value = "unavailable";
  modelError.value =
    "3D 查看器资源加载失败，模型预览暂不可用，请稍后刷新页面重试。";
}

function clearModelState(): void {
  models.value = [];
  selectedModelIndex.value = -1;
  modelState.value = "idle";
  modelError.value = "";
  paused.value = false;
  slow.value = false;
  angleIndex.value = 0;
}

async function selectModel(index: number): Promise<void> {
  selectedModelIndex.value = index;
  modelState.value = "waiting";
  modelError.value = "";
  paused.value = false;
  slow.value = false;
  angleIndex.value = 0;
  await prepareModelViewer(modelSequence);
  if (viewerAvailable.value) {
    await nextTick();
    resetViewerOrbit();
    syncViewerSource(selectedModelUrl.value);
  }
}

function handleModelLoad(): void {
  modelState.value = "ready";
  modelError.value = "";
}

function handleModelError(): void {
  modelState.value = "error";
  modelError.value =
    "3D 模型文件加载失败或格式不支持，请切换模型或稍后重试。";
}

function resetViewerOrbit(): void {
  if (!modelViewer.value) return;
  modelViewer.value.setAttribute("camera-orbit", CRAFT_ANGLES[0].orbit);
  modelViewer.value.setAttribute("field-of-view", "auto");
}

function syncViewerSource(url: string): void {
  if (!modelViewer.value || !url) return;
  modelViewer.value.setAttribute("src", url);
  modelViewer.value.setAttribute("alt", selectedModel.value?.title ?? "");
}

function togglePause(): void {
  if (!controlsEnabled.value) return;
  paused.value = !paused.value;
}

function toggleSlow(): void {
  if (!controlsEnabled.value) return;
  slow.value = !slow.value;
}

function cycleAngle(): void {
  if (!controlsEnabled.value || !modelViewer.value) return;
  angleIndex.value = (angleIndex.value + 1) % CRAFT_ANGLES.length;
  const angle = CRAFT_ANGLES[angleIndex.value] ?? CRAFT_ANGLES[0];
  modelViewer.value.setAttribute("camera-orbit", angle.orbit);
  modelViewer.value.setAttribute(
    "field-of-view",
    angle.label === "特写" ? "35deg" : "auto",
  );
}

async function activateAR(): Promise<void> {
  if (!controlsEnabled.value || !modelViewer.value?.activateAR) {
    modelError.value = "当前设备或浏览器不支持 AR 实景查看。";
    return;
  }
  try {
    await modelViewer.value.activateAR();
  } catch {
    modelError.value = "AR 启动失败，请在支持 AR 的手机浏览器中重试。";
  }
}

function selectVideo(index: number): void {
  clearVideoTimer();
  selectedVideoIndex.value = index;
  videoError.value = "";
  const video = detail.value?.videos[index];
  if (!video?.bvid) {
    videoState.value = "error";
    videoError.value = "视频地址缺失，无法播放。";
    return;
  }
  videoState.value = "loading";
  videoTimer = window.setTimeout(() => {
    if (videoState.value !== "loading") return;
    videoState.value = "error";
    videoError.value =
      "视频加载超时或网络不可用，请在新窗口打开原视频。";
  }, VIDEO_LOAD_TIMEOUT_MS);
}

function closeVideo(): void {
  clearVideoTimer();
  selectedVideoIndex.value = -1;
  videoState.value = "idle";
  videoError.value = "";
}

function handleVideoLoad(): void {
  clearVideoTimer();
  videoState.value = "ready";
  videoError.value = "";
}

function handleVideoError(): void {
  clearVideoTimer();
  videoState.value = "error";
  videoError.value = "视频加载失败，请在新窗口打开原视频。";
}

function clearVideoTimer(): void {
  if (videoTimer !== undefined) {
    window.clearTimeout(videoTimer);
    videoTimer = undefined;
  }
}

function markCoverFailed(videoId: number): void {
  failedCoverIds.value = new Set(failedCoverIds.value).add(videoId);
}

function toggleCategory(key: string): void {
  openCategoryKeys.value = openCategoryKeys.value.includes(key)
    ? openCategoryKeys.value.filter((item) => item !== key)
    : [...openCategoryKeys.value, key];
}

function toggleAllCategories(): void {
  openCategoryKeys.value = allCategoriesOpen.value
    ? []
    : purchaseCategories.value.map((category) => category.key);
}

function categorySubtotal(category: CraftPurchaseCategory): string {
  let minimum = 0;
  let maximum = 0;
  let found = false;
  for (const item of category.items) {
    if (!item.price) continue;
    const head = item.price.split("元")[0] ?? "";
    const numbers = (head.match(/\d+(?:\.\d+)?/g) ?? []).map(Number);
    if (!numbers.length) continue;
    found = true;
    minimum += Math.min(...numbers);
    maximum += Math.max(...numbers);
  }
  return found ? `小计约 ${minimum}-${maximum} 元` : "";
}

function selectCraft(craftId: string): void {
  if (craftId === selectedCraftId.value) return;
  selectedCraftId.value = craftId;
}

function selectStep(index: number): void {
  activeStepIndex.value = index;
  progressCount.value = Math.max(progressCount.value, index + 1);
  writeProgress(selectedCraftId.value, progressCount.value);
  if (!controlsEnabled.value || !modelViewer.value) return;
  const angle =
    CRAFT_ANGLES[index % CRAFT_ANGLES.length] ?? CRAFT_ANGLES[0];
  modelViewer.value.setAttribute("camera-orbit", angle.orbit);
}

function isStepDone(index: number): boolean {
  return index < progressCount.value;
}

function progressPercent(): string {
  const total = detail.value?.steps.length ?? 0;
  if (!total) return "0%";
  return `${Math.round((progressCount.value / total) * 100)}%`;
}

function progressText(): string {
  const total = detail.value?.steps.length ?? 0;
  return `已完成 ${progressCount.value}/${total} 步`;
}

function readProgress(craftId: string, total: number): number {
  try {
    const value = Number.parseInt(
      localStorage.getItem(`yuexiang_craft_progress_${craftId}`) ?? "0",
      10,
    );
    return Math.max(0, Math.min(Number.isFinite(value) ? value : 0, total));
  } catch {
    return 0;
  }
}

function writeProgress(craftId: string, value: number): void {
  try {
    localStorage.setItem(`yuexiang_craft_progress_${craftId}`, String(value));
  } catch {
    // Storage can be unavailable in private browsing.
  }
}

function readSavedCraft(): string {
  try {
    return localStorage.getItem(CRAFT_STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

function writeSavedCraft(craftId: string): void {
  try {
    localStorage.setItem(CRAFT_STORAGE_KEY, craftId);
  } catch {
    // Storage can be unavailable in private browsing.
  }
}

function handleDocumentKeydown(event: KeyboardEvent): void {
  if (event.key !== "Escape") return;
  if (selectedVideoIndex.value >= 0) closeVideo();
}

function modelExtension(model: PublicModel3D): string {
  const source = model.file_name || model.file_path;
  const match = /\.([a-z0-9]+)(?:[?#].*)?$/i.exec(source);
  return match?.[1]?.toLocaleLowerCase() ?? "";
}

function formatVideoCount(value: number): string {
  const count = Number(value) || 0;
  if (count >= 100_000_000) {
    return `${(count / 100_000_000).toFixed(1).replace(/\.0$/, "")}亿`;
  }
  if (count >= 10_000) {
    return `${(count / 10_000).toFixed(1).replace(/\.0$/, "")}万`;
  }
  return String(count);
}

function formatVideoDuration(value: number): string {
  const seconds = Math.max(0, Number(value) || 0);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  const pad = (part: number) => String(part).padStart(2, "0");
  return hours
    ? `${hours}:${pad(minutes)}:${pad(remainder)}`
    : `${pad(minutes)}:${pad(remainder)}`;
}

function categoryMeta(category: CraftPurchaseCategory) {
  return CATEGORY_META[category.key] ?? DEFAULT_CATEGORY_META;
}

function externalVideoUrl(video: CraftVideo): string {
  return `https://www.bilibili.com/video/${encodeURIComponent(video.bvid)}/`;
}
</script>

<template>
  <section
    id="crafts-tab"
    class="tab-content active crafts-view"
    aria-labelledby="crafts-title"
  >
    <div class="container">
      <div class="section-label">
        Heritage Crafts
      </div>
      <h1
        id="crafts-title"
        class="section-title"
      >
        非遗手工技能传承
      </h1>
      <p class="section-desc">
        数字化保存传统手工艺技法，3D步骤拆解，AR虚拟操作指导
      </p>

      <div
        class="card-section"
        aria-labelledby="craft-select-title"
      >
        <h3
          id="craft-select-title"
          class="card-section-title"
        >
          <i
            class="fas fa-palette"
            aria-hidden="true"
          />
          选择手工艺
        </h3>

        <div
          v-if="craftsLoading"
          class="crafts-state"
          role="status"
        >
          手工艺目录加载中...
        </div>
        <div
          v-else-if="craftsError"
          class="crafts-state crafts-state-error"
          role="alert"
        >
          <i
            class="fas fa-triangle-exclamation"
            aria-hidden="true"
          />
          <strong>{{ craftsError }}</strong>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            @click="loadCrafts"
          >
            重新加载
          </button>
        </div>
        <div
          v-else
          class="craft-grid"
        >
          <button
            v-for="craft in crafts"
            :key="craft.id"
            type="button"
            class="craft-card"
            :class="{ active: craft.id === selectedCraftId }"
            :aria-pressed="craft.id === selectedCraftId"
            @click="selectCraft(craft.id)"
          >
            <span class="craft-visual">
              <i
                class="fas fa-hands"
                aria-hidden="true"
              />
            </span>
            <span class="craft-info">
              <strong class="craft-card-name">{{ craft.name }}</strong>
              <span
                v-if="craft.origin"
                class="craft-card-desc"
              >{{ craft.origin }}</span>
              <span
                v-if="craft.level"
                class="tag"
              >{{ craft.level }}</span>
            </span>
          </button>
        </div>
      </div>

      <div
        v-if="detailLoading"
        class="crafts-state"
        role="status"
      >
        手工艺内容加载中...
      </div>
      <div
        v-else-if="detailError"
        class="crafts-state crafts-state-error"
        role="alert"
      >
        <i
          class="fas fa-triangle-exclamation"
          aria-hidden="true"
        />
        <strong>{{ detailError }}</strong>
        <button
          type="button"
          class="btn btn-outline btn-sm"
          @click="loadCraftDetail(selectedCraftId)"
        >
          重新加载内容
        </button>
      </div>
      <div
        v-else-if="detail"
        class="craft-intro"
      >
        <div class="craft-intro-card">
          <div class="craft-intro-icon">
            <i
              class="fas fa-landmark"
              aria-hidden="true"
            />
          </div>
          <div class="craft-intro-body">
            <div class="craft-intro-head">
              <h2>{{ detail.name }}</h2>
              <span
                v-if="detail.origin"
                class="craft-intro-origin"
              >
                <i
                  class="fas fa-map-marker-alt"
                  aria-hidden="true"
                />
                {{ detail.origin }}
              </span>
            </div>
            <p v-if="detail.history">
              {{ detail.history }}
            </p>
          </div>
        </div>
      </div>

      <div
        class="card-section"
        aria-labelledby="craft-video-title"
      >
        <h3
          id="craft-video-title"
          class="card-section-title"
        >
          <i
            class="fas fa-video"
            aria-hidden="true"
          />
          视频教学
        </h3>

        <div
          v-if="detailError"
          class="crafts-state crafts-state-error"
          role="alert"
        >
          <i
            class="fas fa-triangle-exclamation"
            aria-hidden="true"
          />
          <strong>手工艺内容加载失败，视频教学暂不可用</strong>
        </div>
        <div
          v-else-if="detailLoading"
          class="crafts-state"
          role="status"
        >
          视频教学加载中...
        </div>
        <div
          v-else-if="!detail?.videos.length"
          class="crafts-state"
        >
          <i
            class="fas fa-film"
            aria-hidden="true"
          />
          <strong>该手工艺暂无视频教学</strong>
          <span>内容正在整理中，请稍后再来查看。</span>
        </div>
        <template v-else>
          <div
            v-if="selectedVideo"
            class="craft-video-stage"
          >
            <div class="craft-video-stage-bar">
              <span class="craft-video-stage-title">{{ selectedVideo.title }}</span>
              <button
                type="button"
                class="icon-btn"
                aria-label="收起播放器"
                title="收起播放器"
                @click="closeVideo"
              >
                <i
                  class="fas fa-times"
                  aria-hidden="true"
                />
              </button>
            </div>
            <div class="craft-video-frame">
              <div
                v-if="videoState !== 'ready'"
                class="craft-video-placeholder"
                role="status"
              >
                <i
                  class="fas"
                  :class="videoState === 'error'
                    ? 'fa-exclamation-circle'
                    : 'fa-circle-notch fa-spin'"
                  aria-hidden="true"
                />
                <p>{{ videoError || "视频加载中..." }}</p>
                <a
                  v-if="videoState === 'error'"
                  class="btn btn-outline btn-sm"
                  :href="externalVideoUrl(selectedVideo)"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  在新窗口打开
                </a>
              </div>
              <iframe
                v-if="videoEmbedUrl"
                class="craft-video-iframe"
                :class="{ 'is-hidden': videoState !== 'ready' }"
                :src="videoEmbedUrl"
                :title="selectedVideo.title || '手工艺教学演示视频'"
                scrolling="no"
                frameborder="0"
                allowfullscreen
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen"
                referrerpolicy="no-referrer-when-downgrade"
                @load="handleVideoLoad"
                @error="handleVideoError"
              />
            </div>
          </div>

          <div class="craft-video-grid">
            <article
              v-for="(video, index) in detail.videos"
              :key="video.id"
              class="craft-video-card"
              :class="{ 'is-playing': index === selectedVideoIndex }"
            >
              <button
                type="button"
                class="craft-video-card-select"
                :aria-label="`播放视频：${video.title}`"
                @click="selectVideo(index)"
              >
                <span class="craft-video-card-cover">
                  <img
                    v-if="video.cover && !failedCoverIds.has(video.id)"
                    :src="video.cover"
                    :alt="video.title"
                    loading="lazy"
                    referrerpolicy="no-referrer"
                    @error="markCoverFailed(video.id)"
                  >
                  <span
                    v-else
                    class="craft-video-card-cover-fallback"
                  >
                    <i
                      class="fas fa-film"
                      aria-hidden="true"
                    />
                  </span>
                  <span class="craft-video-card-stats">
                    <span class="craft-video-card-stat">
                      <i
                        class="fas fa-play-circle"
                        aria-hidden="true"
                      />
                      {{ formatVideoCount(video.view) }}
                    </span>
                    <span class="craft-video-card-stat">
                      <i
                        class="fas fa-comment-dots"
                        aria-hidden="true"
                      />
                      {{ formatVideoCount(video.danmaku) }}
                    </span>
                    <span class="craft-video-card-stat">
                      <i
                        class="fas fa-thumbs-up"
                        aria-hidden="true"
                      />
                      {{ formatVideoCount(video.like) }}
                    </span>
                    <span class="craft-video-card-duration">
                      {{ formatVideoDuration(video.duration) }}
                    </span>
                  </span>
                  <span class="craft-video-card-play">
                    <i
                      class="fas fa-play"
                      aria-hidden="true"
                    />
                  </span>
                </span>
                <span
                  class="craft-video-card-title"
                  :title="video.title"
                >
                  {{ video.title }}
                </span>
                <span class="craft-video-card-meta">
                  <span class="craft-video-card-author">
                    <i
                      class="fas fa-user"
                      aria-hidden="true"
                    />
                    {{ video.author }}
                  </span>
                </span>
              </button>
              <a
                class="craft-video-card-external"
                :href="externalVideoUrl(video)"
                target="_blank"
                rel="noopener noreferrer"
                title="在新窗口打开"
                aria-label="在新窗口打开"
              >
                <i
                  class="fas fa-external-link-alt"
                  aria-hidden="true"
                />
              </a>
            </article>
          </div>
          <p class="craft-video-source">
            视频来源：哔哩哔哩，共 {{ detail.videos.length }} 条；网络不佳时可点封面右下角「在新窗口打开」。
          </p>
        </template>
      </div>

      <div
        class="card-section"
        aria-labelledby="craft-3d-title"
      >
        <div class="panel-header">
          <h3
            id="craft-3d-title"
            class="card-section-title"
          >
            <i
              class="fas fa-cube"
              aria-hidden="true"
            />
            3D互动教学
          </h3>
          <div class="control-group">
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :class="{ active: slow }"
              :disabled="!controlsEnabled"
              title="切换慢放"
              @click="toggleSlow"
            >
              <i
                class="fas fa-play"
                aria-hidden="true"
              />
              慢放
            </button>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :class="{ active: paused }"
              :disabled="!controlsEnabled"
              title="暂停自动旋转"
              @click="togglePause"
            >
              <i
                class="fas fa-pause"
                aria-hidden="true"
              />
              暂停
            </button>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="!controlsEnabled"
              title="切换观察角度"
              @click="cycleAngle"
            >
              <i
                class="fas fa-sync-alt"
                aria-hidden="true"
              />
              多角度
            </button>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="!controlsEnabled"
              title="AR 实景查看"
              @click="activateAR"
            >
              <i
                class="fas fa-cube"
                aria-hidden="true"
              />
              AR 实景
            </button>
          </div>
        </div>

        <div class="learning-layout">
          <div class="viewer-3d">
            <div
              v-if="modelsLoading"
              class="viewer-placeholder"
              role="status"
            >
              <i
                class="fas fa-cube"
                aria-hidden="true"
              />
              <p>3D模型加载中...</p>
            </div>
            <div
              v-else-if="modelsError"
              class="viewer-placeholder"
              role="alert"
            >
              <i
                class="fas fa-exclamation-circle"
                aria-hidden="true"
              />
              <p>{{ modelsError }}</p>
              <button
                type="button"
                class="btn btn-outline btn-sm"
                @click="loadModels(selectedCraftId)"
              >
                重新加载模型
              </button>
            </div>
            <div
              v-else-if="!models.length"
              class="viewer-placeholder"
              role="status"
            >
              <i
                class="fas fa-exclamation-circle"
                aria-hidden="true"
              />
              <p>该手工艺暂无可展示的 3D 模型，教师可在后台上传</p>
            </div>
            <div
              v-else-if="modelFormatError || modelError || !viewerAvailable"
              class="viewer-placeholder"
              role="alert"
            >
              <i
                class="fas fa-exclamation-circle"
                aria-hidden="true"
              />
              <p>{{ modelFormatError || modelError || "3D 查看器准备中..." }}</p>
            </div>
            <model-viewer
              v-else
              ref="modelViewer"
              class="craft-3d-viewer"
              camera-controls
              :auto-rotate="paused ? undefined : ''"
              :rotation-per-second="slow ? '10deg' : '30deg'"
              :camera-orbit="CRAFT_ANGLES[0].orbit"
              shadow-intensity="1"
              exposure="1"
              environment-image="neutral"
              ar
              ar-modes="webxr scene-viewer quick-look"
              @load="handleModelLoad"
              @error="handleModelError"
            />
          </div>

          <div class="step-guide">
            <h4>
              制作步骤
              <span class="step-guide-hint">
                <i
                  class="fas fa-mouse-pointer"
                  aria-hidden="true"
                />
                点击步骤切换观察角度
              </span>
            </h4>
            <div
              v-if="detail?.steps.length"
              class="craft-progress"
            >
              <div class="craft-progress-bar">
                <div
                  class="craft-progress-fill"
                  :style="{ width: progressPercent() }"
                />
              </div>
              <span class="craft-progress-text">{{ progressText() }}</span>
            </div>
            <div
              v-if="detailError"
              class="crafts-state crafts-state-error"
              role="alert"
            >
              <i
                class="fas fa-triangle-exclamation"
                aria-hidden="true"
              />
              <strong>手工艺内容加载失败，制作步骤暂不可用</strong>
            </div>
            <div
              v-else-if="detailLoading"
              class="crafts-state"
              role="status"
            >
              制作步骤加载中...
            </div>
            <div
              v-else-if="!detail?.steps.length"
              class="crafts-state"
            >
              <i
                class="fas fa-paint-brush"
                aria-hidden="true"
              />
              <strong>暂无步骤</strong>
              <span>该手工艺的步骤正在准备中。</span>
            </div>
            <div
              v-else
              class="steps-list"
            >
              <button
                v-for="(step, index) in detail.steps"
                :key="`${step.title}-${index}`"
                type="button"
                class="step"
                :class="{
                  active: index === activeStepIndex,
                  'is-done': isStepDone(index),
                }"
                @click="selectStep(index)"
              >
                <span class="step-number">{{ index + 1 }}</span>
                <span class="step-content">
                  <strong>{{ step.title }}</strong>
                  <span>{{ step.desc }}</span>
                  <span
                    v-if="step.tips"
                    class="step-tips"
                  >
                    <i
                      class="fas fa-lightbulb"
                      aria-hidden="true"
                    />
                    {{ step.tips }}
                  </span>
                </span>
              </button>
            </div>
          </div>
        </div>

        <div
          v-if="models.length > 1"
          class="craft-model-tabs"
          aria-label="切换 3D 模型"
        >
          <button
            v-for="(model, index) in models"
            :key="model.id"
            type="button"
            class="craft-model-tab"
            :class="{ active: index === selectedModelIndex }"
            :aria-pressed="index === selectedModelIndex"
            @click="selectModel(index)"
          >
            {{ model.title || `模型${index + 1}` }}
          </button>
        </div>
      </div>

      <div
        class="card-section"
        aria-labelledby="craft-materials-title"
      >
        <h3
          id="craft-materials-title"
          class="card-section-title"
        >
          <i
            class="fas fa-shopping-basket"
            aria-hidden="true"
          />
          材料采购指南
        </h3>

        <div
          v-if="detailError"
          class="crafts-state crafts-state-error"
          role="alert"
        >
          <i
            class="fas fa-triangle-exclamation"
            aria-hidden="true"
          />
          <strong>手工艺内容加载失败，材料采购指南暂不可用</strong>
        </div>
        <div
          v-else-if="detailLoading"
          class="crafts-state"
          role="status"
        >
          材料采购指南加载中...
        </div>
        <div
          v-else-if="!hasPurchaseGuide"
          class="crafts-state"
        >
          <i
            class="fas fa-shopping-basket"
            aria-hidden="true"
          />
          <strong>暂无材料采购指南</strong>
          <span>该手工艺的采购清单正在整理中。</span>
        </div>
        <template v-else-if="purchaseGuide">
          <div
            v-if="purchaseGuide.budget"
            class="guide-budget"
          >
            <div class="budget-item starter">
              <i
                class="fas fa-piggy-bank"
                aria-hidden="true"
              />
              <div>
                <small>入门全套预算</small>
                <b>{{ purchaseGuide.budget.starter }}</b>
              </div>
            </div>
            <div class="budget-item advanced">
              <i
                class="fas fa-chart-line"
                aria-hidden="true"
              />
              <div>
                <small>进阶全套预算</small>
                <b>{{ purchaseGuide.budget.advanced }}</b>
              </div>
            </div>
          </div>
          <div
            v-if="purchaseGuide.buying_tips"
            class="guide-buying-tips"
          >
            <i
              class="fas fa-compass"
              aria-hidden="true"
            />
            <div>
              <b>学员采购建议：</b>{{ purchaseGuide.buying_tips }}
            </div>
          </div>
          <div
            v-if="purchaseCategories.length"
            class="guide-toolbar"
          >
            <button
              type="button"
              class="btn btn-text btn-sm"
              @click="toggleAllCategories"
            >
              {{ allCategoriesOpen ? "全部收起" : "全部展开" }}
              <i
                class="fas"
                :class="allCategoriesOpen ? 'fa-angles-up' : 'fa-angles-down'"
                aria-hidden="true"
              />
            </button>
          </div>
          <div
            v-for="category in purchaseCategories"
            :key="category.key"
            class="guide-category"
            :class="[
              category.key,
              { open: openCategoryKeys.includes(category.key) },
            ]"
          >
            <button
              type="button"
              class="guide-cat-head"
              :aria-expanded="openCategoryKeys.includes(category.key)"
              @click="toggleCategory(category.key)"
            >
              <i
                class="fas"
                :class="categoryMeta(category).icon"
                aria-hidden="true"
              />
              <span>{{ category.label }}</span>
              <small>{{ category.desc }}</small>
              <span class="guide-cat-meta">
                <b
                  v-if="categorySubtotal(category)"
                  class="guide-subtotal"
                >
                  {{ categorySubtotal(category) }}
                </b>
                <em class="guide-count">{{ category.items.length }} 项</em>
                <i
                  class="fas fa-chevron-down guide-chevron"
                  aria-hidden="true"
                />
              </span>
            </button>
            <div class="guide-body">
              <div class="guide-items">
                <div
                  v-for="item in category.items"
                  :key="`${category.key}-${item.name}`"
                  class="guide-item"
                  :class="category.key"
                >
                  <div class="guide-item-head">
                    <span
                      class="guide-badge"
                      :class="category.key"
                    >
                      {{ categoryMeta(category).badge }}
                    </span>
                    <h5>{{ item.name }}</h5>
                    <span class="price-tag">{{ item.price }}</span>
                  </div>
                  <div
                    v-if="item.spec"
                    class="guide-spec"
                  >
                    <i
                      class="fas fa-ruler-combined"
                      aria-hidden="true"
                    />
                    <span><b>怎么选：</b>{{ item.spec }}</span>
                  </div>
                  <div
                    v-if="item.where"
                    class="guide-where"
                  >
                    <i
                      class="fas fa-map-marker-alt"
                      aria-hidden="true"
                    />
                    <span><b>去哪买：</b>{{ item.where }}</span>
                  </div>
                  <div
                    v-if="item.tip"
                    class="guide-tip"
                  >
                    <i
                      class="fas fa-lightbulb"
                      aria-hidden="true"
                    />
                    <span><b>避坑提示：</b>{{ item.tip }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </section>
</template>

<style scoped>
.crafts-view {
  min-height: 70vh;
}

.craft-card {
  padding: 0;
  color: inherit;
  font: inherit;
  text-align: left;
}

.craft-info {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: flex-start;
}

.craft-card-name {
  color: var(--text-primary);
  font-size: 0.95rem;
  font-weight: 600;
}

.craft-card-desc {
  margin: 4px 0 8px;
  color: var(--text-secondary);
  font-size: 0.8rem;
}

.crafts-state {
  display: grid;
  justify-items: center;
  gap: 10px;
  padding: 28px 16px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  text-align: center;
}

.crafts-state i {
  color: var(--accent-gold, #d9a227);
  font-size: 1.2rem;
}

.crafts-state-error {
  border-color: color-mix(in srgb, #ef4444 35%, var(--border));
}

.crafts-state-error i {
  color: #ef4444;
}

.craft-video-card {
  position: relative;
  padding: 0;
}

.craft-video-card-select {
  display: block;
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
}

.craft-video-card-meta {
  padding-right: 26px;
}

.craft-video-card-external {
  position: absolute;
  right: 0;
  bottom: 7px;
  margin-left: 0;
}

.craft-video-card-title {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.craft-video-placeholder .btn {
  margin-top: 10px;
}

.viewer-placeholder .btn {
  margin-top: 12px;
}

.step {
  width: 100%;
  border: 0;
  color: inherit;
  font: inherit;
  text-align: left;
}

.step-content {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.step-content strong {
  margin-bottom: 2px;
  color: var(--text-primary);
  font-size: 0.85rem;
  font-weight: 600;
}

.step-content > span:not(.step-tips) {
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
}

.guide-cat-head span,
.guide-cat-head small,
.guide-cat-head b,
.guide-cat-head em {
  font-family: inherit;
}

.guide-item-head h5 {
  margin: 0;
}
</style>
