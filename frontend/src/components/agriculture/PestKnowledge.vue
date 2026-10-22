<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import {
  getPestKnowledge,
  type PestChemRow,
  type PestCrop,
  type PestEntry,
  type PestSource,
} from "@/api/agriculture";
import { ApiError } from "@/api/client";
import { resolveMediaUrl } from "@/shared/url";

const PAGE_SIZE = 10;

const entries = ref<PestEntry[]>([]);
const crops = ref<PestCrop[]>([]);
const total = ref(0);
const allEntriesCount = ref(0);
const disclaimer = ref("");
const crop = ref("");
const keyword = ref("");
const offset = ref(0);
const loading = ref(false);
const error = ref("");
const selectedEntry = ref<PestEntry | null>(null);
const closeButton = ref<HTMLButtonElement | null>(null);
let requestSequence = 0;
let keywordTimer: ReturnType<typeof setTimeout> | null = null;

const pages = computed(() =>
  total.value > 0 ? Math.ceil(total.value / PAGE_SIZE) : 0,
);
const currentPage = computed(() =>
  total.value > 0 ? Math.floor(offset.value / PAGE_SIZE) + 1 : 0,
);
const metaText = computed(() => {
  if (loading.value) return "速查数据加载中…";
  if (error.value) return "";
  const scope =
    crops.value.find((item) => item.id === crop.value)?.name ?? "全部作物";
  if (keyword.value.trim()) {
    return `「${keyword.value.trim()}」匹配 ${total.value} 条 · ${scope} · 速查共 ${allEntriesCount.value} 条`;
  }
  return `${scope}：${total.value} 条 · 速查共 ${allEntriesCount.value} 条`;
});

watch(keyword, () => {
  if (keywordTimer) clearTimeout(keywordTimer);
  offset.value = 0;
  keywordTimer = setTimeout(() => {
    keywordTimer = null;
    void loadKnowledge();
  }, 300);
});

onMounted(() => {
  document.addEventListener("keydown", handleKeydown);
  void loadKnowledge();
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", handleKeydown);
  if (keywordTimer) clearTimeout(keywordTimer);
});

async function loadKnowledge(): Promise<void> {
  const sequence = ++requestSequence;
  loading.value = true;
  error.value = "";
  try {
    const response = await getPestKnowledge({
      crop: crop.value || undefined,
      q: keyword.value.trim() || undefined,
      limit: PAGE_SIZE,
      offset: offset.value || undefined,
    });
    if (sequence !== requestSequence) return;
    entries.value = response.entries;
    crops.value = response.crops;
    total.value = response.total;
    allEntriesCount.value = response.stats.entries;
    disclaimer.value = response.disclaimer;
  } catch (failure) {
    if (sequence !== requestSequence) return;
    entries.value = [];
    total.value = 0;
    error.value =
      failure instanceof ApiError
        ? failure.message
        : "速查数据加载失败，请稍后重试。";
  } finally {
    if (sequence === requestSequence) loading.value = false;
  }
}

function selectCrop(cropId: string): void {
  if (crop.value === cropId) return;
  crop.value = cropId;
  offset.value = 0;
  void loadKnowledge();
}

function goPage(step: number): void {
  const next = offset.value + step * PAGE_SIZE;
  if (next < 0 || next >= total.value) return;
  offset.value = next;
  void loadKnowledge();
}

function openEntry(entry: PestEntry): void {
  selectedEntry.value = entry;
  void nextTick(() => closeButton.value?.focus());
}

function closeEntry(): void {
  selectedEntry.value = null;
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape" && selectedEntry.value) closeEntry();
}

function mediaUrl(value: string | null | undefined): string {
  return resolveMediaUrl(value);
}

function safeExternalUrl(value: string): string {
  return /^https?:\/\//i.test(value.trim()) ? value.trim() : "";
}

function chemValue(value: PestChemRow[keyof PestChemRow]): string {
  if (value === null || value === undefined || String(value).trim() === "") {
    return "未提供";
  }
  return String(value);
}

function sourceMeta(source: PestSource): string {
  const bits = [source.org, source.doc_type, source.date].filter(
    (item) => item.trim().length > 0,
  );
  if (source.doc_no === "待核") bits.push("文号待核");
  else if (source.doc_no && !["\u2014", "-"].includes(source.doc_no)) {
    bits.push(source.doc_no);
  }
  return bits.join(" · ");
}
</script>

<template>
  <section
    id="pest-guide-section"
    class="card-section"
    aria-labelledby="pest-guide-title"
  >
    <h3
      id="pest-guide-title"
      class="card-section-title"
    >
      <i
        class="fas fa-book-medical"
        aria-hidden="true"
      />
      常见病虫害速查
    </h3>

    <div class="pest-guide">
      <div class="pest-guide-toolbar">
        <div
          class="pest-crop-filter"
          role="tablist"
          aria-label="按作物筛选"
        >
          <button
            type="button"
            class="pest-crop-btn"
            :class="{ active: crop === '' }"
            role="tab"
            :aria-selected="crop === ''"
            @click="selectCrop('')"
          >
            <span aria-hidden="true">📚</span>
            全部作物
            <span class="pest-crop-count">{{ total }}</span>
          </button>
          <button
            v-for="item in crops"
            :key="item.id"
            type="button"
            class="pest-crop-btn"
            :class="{ active: crop === item.id }"
            role="tab"
            :aria-selected="crop === item.id"
            @click="selectCrop(item.id)"
          >
            <span aria-hidden="true">{{ item.icon }}</span>
            {{ item.name }}
            <span class="pest-crop-count">{{ item.count }}</span>
          </button>
        </div>

        <div class="pest-guide-search">
          <i
            class="fas fa-search"
            aria-hidden="true"
          />
          <input
            v-model="keyword"
            type="search"
            maxlength="30"
            name="pest_q"
            autocomplete="off"
            spellcheck="false"
            placeholder="搜索病害名称、别名或症状关键词"
            aria-label="搜索病虫害"
          >
        </div>
      </div>

      <p
        class="pest-guide-meta"
        role="status"
      >
        {{ metaText }}
      </p>

      <div
        v-if="loading"
        class="agriculture-loading"
        role="status"
      >
        速查数据加载中…
      </div>
      <div
        v-else-if="error"
        class="agriculture-empty"
        role="alert"
      >
        <i
          class="fas fa-triangle-exclamation"
          aria-hidden="true"
        />
        <strong>{{ error }}</strong>
        <button
          type="button"
          class="btn btn-outline btn-sm"
          @click="loadKnowledge"
        >
          重新加载
        </button>
      </div>
      <div
        v-else
        class="pest-guide-grid"
      >
        <button
          v-for="entry in entries"
          :key="entry.id"
          type="button"
          class="pest-card"
          data-testid="pest-card"
          :aria-label="`查看${entry.disease}详情`"
          @click="openEntry(entry)"
        >
          <div class="pest-card-thumb">
            <div class="pest-card-tags">
              <span
                class="pest-kind-tag"
                :class="entry.kind === 'pest' ? 'is-pest' : 'is-disease'"
              >
                {{ entry.kind === "pest" ? "虫害" : "病害" }}
              </span>
              <span class="pest-kind-tag">{{ entry.crop_name }}</span>
            </div>
            <img
              v-if="entry.image?.file"
              :src="mediaUrl(entry.image.file)"
              :alt="`${entry.disease} 实拍图`"
              loading="lazy"
            >
            <div
              v-else
              class="pest-card-thumb-empty"
            >
              <i
                class="fas fa-image"
                aria-hidden="true"
              />
              <span>暂无实拍图</span>
            </div>
          </div>
          <div class="pest-card-body">
            <h4>{{ entry.disease }}</h4>
            <p
              v-if="entry.alias"
              class="pest-card-alias"
            >
              别名：{{ entry.alias }}
            </p>
            <div class="pest-card-foot">
              <span class="pest-card-part">{{ entry.part }}</span>
              <span class="pest-card-part">详情 ›</span>
            </div>
          </div>
        </button>
      </div>

      <p
        v-if="!loading && !error && entries.length === 0"
        class="pest-guide-empty"
        role="status"
      >
        没有匹配的条目，换个关键词或清空筛选试试。
      </p>

      <div
        v-if="!loading && !error && total > PAGE_SIZE"
        class="pest-pager"
        role="navigation"
        aria-label="速查结果翻页"
      >
        <button
          type="button"
          class="pest-page-btn"
          aria-label="上一页"
          :disabled="currentPage <= 1"
          @click="goPage(-1)"
        >
          ‹ 上一页
        </button>
        <span
          class="pest-page-status"
          role="status"
        >
          第 {{ currentPage }} / {{ pages }} 页 · 共 {{ total }} 条
        </span>
        <button
          type="button"
          class="pest-page-btn"
          aria-label="下一页"
          :disabled="currentPage >= pages"
          @click="goPage(1)"
        >
          下一页 ›
        </button>
      </div>

      <p
        v-if="disclaimer"
        class="pest-guide-disclaimer"
        role="note"
      >
        {{ disclaimer }}
      </p>
    </div>

    <Teleport to="body">
      <div
        v-if="selectedEntry"
        class="pest-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pest-modal-title"
        @click.self="closeEntry"
      >
        <div
          class="pest-modal-backdrop"
          @click="closeEntry"
        />
        <div class="pest-modal-panel">
          <div class="pest-modal-header">
            <h3 id="pest-modal-title">
              {{ selectedEntry.disease }}
              <span class="pest-modal-sub">
                {{ selectedEntry.crop_name }} · {{ selectedEntry.kind === "pest" ? "虫害" : "病害" }}
              </span>
            </h3>
            <button
              ref="closeButton"
              type="button"
              class="icon-btn"
              aria-label="关闭"
              @click="closeEntry"
            >
              <i
                class="fas fa-times"
                aria-hidden="true"
              />
            </button>
          </div>

          <div class="pest-modal-body">
            <figure
              v-if="selectedEntry.image?.file"
              class="pest-modal-figure"
            >
              <img
                :src="mediaUrl(selectedEntry.image.file)"
                :alt="`${selectedEntry.disease} 实拍图`"
              >
              <figcaption>
                <span
                  v-if="selectedEntry.image.caption"
                  class="pest-modal-caption-note"
                >
                  {{ selectedEntry.image.caption }}
                </span>
                {{ [selectedEntry.image.credit, selectedEntry.image.license, selectedEntry.image.shot_date].filter(Boolean).join(" · ") }}
              </figcaption>
            </figure>
            <p
              v-else
              class="pest-modal-noimg"
            >
              <i
                class="fas fa-image"
                aria-hidden="true"
              />
              该条目暂无可用授权实拍图，此处不提供示意图。请对照下方症状文字与当地农技员核实。
            </p>

            <div class="pest-facts">
              <span class="pest-fact">
                <b>类别：</b>{{ selectedEntry.kind === "pest" ? "虫害" : "病害" }}
              </span>
              <span
                v-if="selectedEntry.alias"
                class="pest-fact"
              >
                <b>别名：</b>{{ selectedEntry.alias }}
              </span>
              <span
                v-if="selectedEntry.pathogen"
                class="pest-fact"
              >
                <b>病原/学名：</b>{{ selectedEntry.pathogen }}
              </span>
              <span
                v-if="selectedEntry.part"
                class="pest-fact"
              >
                <b>主要为害部位：</b>{{ selectedEntry.part }}
              </span>
              <span
                v-if="selectedEntry.severity"
                class="pest-fact"
              >
                <b>危害程度：</b>{{ selectedEntry.severity }}
              </span>
            </div>

            <section v-if="selectedEntry.symptoms.length">
              <h4 class="pest-block-title">
                <i
                  class="fas fa-stethoscope"
                  aria-hidden="true"
                />
                典型症状
              </h4>
              <ul class="pest-list">
                <li
                  v-for="item in selectedEntry.symptoms"
                  :key="item"
                >
                  {{ item }}
                </li>
              </ul>
            </section>

            <section v-if="selectedEntry.occurrence">
              <h4 class="pest-block-title">
                <i
                  class="fas fa-cloud-rain"
                  aria-hidden="true"
                />
                发生规律
              </h4>
              <p class="pest-paragraph">
                {{ selectedEntry.occurrence }}
              </p>
            </section>

            <section v-if="selectedEntry.treatment.length">
              <h4 class="pest-block-title">
                <i
                  class="fas fa-spray-can"
                  aria-hidden="true"
                />
                化学防治要点
              </h4>
              <ul class="pest-list">
                <li
                  v-for="item in selectedEntry.treatment"
                  :key="item"
                >
                  {{ item }}
                </li>
              </ul>
            </section>

            <section v-if="selectedEntry.prevention.length">
              <h4 class="pest-block-title">
                <i
                  class="fas fa-shield"
                  aria-hidden="true"
                />
                农业防治与预防
              </h4>
              <ul class="pest-list">
                <li
                  v-for="item in selectedEntry.prevention"
                  :key="item"
                >
                  {{ item }}
                </li>
              </ul>
            </section>

            <section v-if="selectedEntry.registered.length">
              <h4 class="pest-block-title">
                <i
                  class="fas fa-flask"
                  aria-hidden="true"
                />
                推荐 / 登记药剂
              </h4>
              <div class="pest-tags">
                <span
                  v-for="item in selectedEntry.registered"
                  :key="item"
                  class="pest-tag"
                >
                  {{ item }}
                </span>
              </div>
            </section>

            <section v-if="selectedEntry.chem_table.length">
              <h4 class="pest-block-title">
                <i
                  class="fas fa-table"
                  aria-hidden="true"
                />
                用药参考表
              </h4>
              <div class="pest-table-wrap">
                <table class="pest-table">
                  <thead>
                    <tr>
                      <th>药剂</th>
                      <th>参考用量</th>
                      <th>安全间隔期</th>
                      <th>每季最多使用</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(row, index) in selectedEntry.chem_table"
                      :key="`${row.agent}-${index}`"
                    >
                      <td>{{ row.agent }}</td>
                      <td>{{ chemValue(row.dose) }}</td>
                      <td>{{ chemValue(row.interval_days) }}</td>
                      <td>{{ chemValue(row.max_times) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p class="pest-refnote">
                表中「未提供」表示所引来源未标注该项数值，本速查不作推算，实际以所购农药标签为准。
              </p>
            </section>

            <p
              v-if="selectedEntry.safety_note"
              class="pest-warn"
            >
              <i
                class="fas fa-exclamation-triangle"
                aria-hidden="true"
              />
              <span>{{ selectedEntry.safety_note }}</span>
            </p>

            <section>
              <h4 class="pest-block-title">
                <i
                  class="fas fa-book"
                  aria-hidden="true"
                />
                数据来源
              </h4>
              <div
                v-if="selectedEntry.sources.length"
                class="pest-sources"
              >
                <div
                  v-for="source in selectedEntry.sources"
                  :key="source.key"
                  class="pest-source-item"
                >
                  <strong>{{ source.name }}</strong>
                  <span class="pest-source-doc">
                    （{{ sourceMeta(source) }}）
                  </span>
                  <a
                    v-if="safeExternalUrl(source.url)"
                    :href="safeExternalUrl(source.url)"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {{ source.url }}
                  </a>
                </div>
              </div>
              <p
                v-else
                class="pest-refnote"
              >
                该条目未登记具体出处，请谨慎参考。
              </p>
              <p class="pest-refnote">
                {{ selectedEntry.is_verified ? "本条已由农技人员复核。" : "本条依据公开技术资料编排，尚未经农技人员逐条复核，仅供参考；实际防治请结合当地当期病虫情报。" }}
              </p>
            </section>
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.pest-card {
  color: inherit;
}

.pest-source-item a {
  display: block;
}
</style>
