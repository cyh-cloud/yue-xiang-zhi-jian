<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
} from "vue";

import {
  getPolicies,
  type PoliciesResponse,
  type Policy,
  type PolicySource,
} from "@/api/resources";

const CATEGORY_ORDER = ["补贴", "电商", "非遗", "培训", "认证", "综合"];
const CATEGORY_STYLES: Readonly<
  Record<string, { icon: string; tag: string }>
> = {
  补贴: { icon: "fa-hand-holding-usd", tag: "tag-subsidy" },
  电商: { icon: "fa-shopping-cart", tag: "tag-ecommerce" },
  非遗: { icon: "fa-university", tag: "tag-heritage" },
  培训: { icon: "fa-graduation-cap", tag: "tag-training" },
  认证: { icon: "fa-certificate", tag: "tag-cert" },
  综合: { icon: "fa-file-alt", tag: "tag-general" },
};
const CATEGORY_FALLBACK = { icon: "fa-file-alt", tag: "tag-general" };

const data = ref<PoliciesResponse | null>(null);
const loading = ref(true);
const error = ref("");
const activeCategory = ref("all");
const selected = ref<Policy | null>(null);
const closeButton = ref<HTMLButtonElement | null>(null);

const categories = computed(() => {
  const present: string[] = [];
  for (const item of data.value?.policies ?? []) {
    if (!present.includes(item.category)) present.push(item.category);
  }
  return present.sort((left, right) => {
    const leftIndex = CATEGORY_ORDER.indexOf(left);
    const rightIndex = CATEGORY_ORDER.indexOf(right);
    return (
      (leftIndex === -1 ? CATEGORY_ORDER.length : leftIndex) -
      (rightIndex === -1 ? CATEGORY_ORDER.length : rightIndex)
    );
  });
});

const visiblePolicies = computed(() => {
  const policies = data.value?.policies ?? [];
  if (activeCategory.value === "all") return policies;
  return policies.filter((item) => item.category === activeCategory.value);
});

const dialogTitleId = "policy-detail-title";

onMounted(() => {
  document.addEventListener("keydown", handleKeydown);
  void loadPolicies();
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", handleKeydown);
});

async function loadPolicies(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    data.value = await getPolicies();
    if (
      activeCategory.value !== "all" &&
      !categories.value.includes(activeCategory.value)
    ) {
      activeCategory.value = "all";
    }
  } catch {
    data.value = null;
    error.value = "政策加载失败，请检查网络后重试";
  } finally {
    loading.value = false;
  }
}

function categoryStyle(category: string) {
  return CATEGORY_STYLES[category] ?? CATEGORY_FALLBACK;
}

function selectCategory(category: string): void {
  activeCategory.value = category;
}

async function openPolicy(policy: Policy): Promise<void> {
  selected.value = policy;
  await nextTick();
  closeButton.value?.focus();
}

function closePolicy(): void {
  selected.value = null;
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape" && selected.value) closePolicy();
}

function sourceMeta(source: PolicySource): string {
  return [source.media, source.date].filter(Boolean).join(" · ");
}

function safeUrl(value: string | undefined): string {
  const candidate = (value ?? "").trim();
  return /^https?:\/\//i.test(candidate) ? candidate : "";
}

interface PolicyTextRun {
  text: string;
  bold: boolean;
}

interface PolicyBlock {
  type: "heading" | "paragraph" | "list";
  runs: PolicyTextRun[];
  ordered?: boolean;
  items?: PolicyTextRun[][];
}

function parseInline(text: string): PolicyTextRun[] {
  return text
    .split(/(\*\*[^*]+\*\*)/g)
    .filter(Boolean)
    .map((part) => ({
      text: part.startsWith("**") && part.endsWith("**")
        ? part.slice(2, -2)
        : part,
      bold: part.startsWith("**") && part.endsWith("**"),
    }));
}

function parsePolicyContent(content: string): PolicyBlock[] {
  const blocks: PolicyBlock[] = [];
  if (!content) {
    return [{ type: "paragraph", runs: [{ text: "暂无详细内容", bold: false }] }];
  }
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    if (line.startsWith("【") && line.endsWith("】")) {
      blocks.push({
        type: "heading",
        runs: parseInline(line.slice(1, -1)),
      });
      continue;
    }
    const unordered = line.startsWith("•") || line.startsWith("-");
    const ordered = /^\d+\./.test(line);
    if (unordered || ordered) {
      const text = line.replace(/^(?:[•-]|\d+\.)\s*/, "");
      const previous = blocks[blocks.length - 1];
      if (
        previous?.type === "list" &&
        previous.ordered === ordered
      ) {
        previous.items = [...(previous.items ?? []), parseInline(text)];
      } else {
        blocks.push({
          type: "list",
          runs: [],
          ordered,
          items: [parseInline(text)],
        });
      }
      continue;
    }
    blocks.push({ type: "paragraph", runs: parseInline(line) });
  }
  return blocks;
}

const selectedBlocks = computed(() =>
  selected.value ? parsePolicyContent(selected.value.content) : [],
);
</script>

<template>
  <section
    class="card-section"
    aria-labelledby="policies-title"
  >
    <h2
      id="policies-title"
      class="card-section-title"
    >
      <i
        class="fas fa-file-alt"
        aria-hidden="true"
      />
      政策信息推送
    </h2>

    <div
      v-if="loading"
      class="policy-placeholder"
      role="status"
    >
      <i
        class="fas fa-spinner fa-spin"
        aria-hidden="true"
      />
      正在加载政策…
    </div>
    <div
      v-else-if="error"
      class="policies-error"
      role="alert"
    >
      <i
        class="fas fa-exclamation-circle"
        aria-hidden="true"
      />
      <p>{{ error }}</p>
      <button
        type="button"
        class="btn btn-outline btn-sm"
        @click="loadPolicies"
      >
        <i
          class="fas fa-redo"
          aria-hidden="true"
        />
        重试
      </button>
    </div>
    <template v-else>
      <div
        class="policy-filters"
        role="group"
        aria-label="政策分类"
      >
        <button
          type="button"
          class="policy-filter"
          :class="{ active: activeCategory === 'all' }"
          :aria-pressed="activeCategory === 'all'"
          @click="selectCategory('all')"
        >
          全部
        </button>
        <button
          v-for="category in categories"
          :key="category"
          type="button"
          class="policy-filter"
          :class="{ active: activeCategory === category }"
          :aria-pressed="activeCategory === category"
          @click="selectCategory(category)"
        >
          {{ category }}
        </button>
      </div>

      <div class="policy-grid">
        <div
          v-if="!visiblePolicies.length"
          class="policies-empty"
          role="status"
        >
          <i
            class="fas fa-folder-open"
            aria-hidden="true"
          />
          <p>
            {{
              activeCategory === "all"
                ? "暂时没有可显示的政策"
                : `「${activeCategory}」分类下暂时没有政策`
            }}
          </p>
          <p class="policies-empty-sub">
            政策由各地农业农村主管部门发布；未发布或已下架时此处为空。
          </p>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            @click="loadPolicies"
          >
            <i
              class="fas fa-redo"
              aria-hidden="true"
            />
            刷新
          </button>
        </div>
        <button
          v-for="policy in visiblePolicies"
          :key="policy.id"
          type="button"
          class="policy-card"
          @click="openPolicy(policy)"
        >
          <span class="policy-card-top">
            <span class="policy-icon-lg">
              <i
                class="fas"
                :class="categoryStyle(policy.category).icon"
                aria-hidden="true"
              />
            </span>
            <span
              class="policy-tag"
              :class="categoryStyle(policy.category).tag"
            >
              {{ policy.category }}
            </span>
          </span>
          <h3>{{ policy.title }}</h3>
          <p v-if="policy.summary">
            {{ policy.summary }}
          </p>
          <span class="policy-card-footer">
            <span class="policy-date">
              <i
                v-if="policy.date"
                class="far fa-calendar-alt"
                aria-hidden="true"
              />
              {{ policy.date }}
            </span>
            <span class="policy-detail-btn">
              查看详情
              <i
                class="fas fa-arrow-right"
                aria-hidden="true"
              />
            </span>
          </span>
        </button>
      </div>
    </template>
  </section>

  <Teleport to="body">
    <div
      v-if="selected"
      class="modal-overlay detail-modal"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="dialogTitleId"
      @click.self="closePolicy"
    >
      <div class="modal-content policy-modal">
        <div class="modal-header">
          <h3 :id="dialogTitleId">
            {{ selected.title }}
          </h3>
          <button
            ref="closeButton"
            type="button"
            class="modal-close"
            aria-label="关闭"
            @click="closePolicy"
          >
            <i
              class="fas fa-times"
              aria-hidden="true"
            />
          </button>
        </div>
        <div class="modal-body">
          <div class="policy-detail-content">
            <template
              v-for="(block, index) in selectedBlocks"
              :key="`${block.type}-${index}`"
            >
              <h4 v-if="block.type === 'heading'">
                <template
                  v-for="(run, runIndex) in block.runs"
                  :key="runIndex"
                >
                  <strong v-if="run.bold">{{ run.text }}</strong>
                  <span v-else>{{ run.text }}</span>
                </template>
              </h4>
              <p v-else-if="block.type === 'paragraph'">
                <template
                  v-for="(run, runIndex) in block.runs"
                  :key="runIndex"
                >
                  <strong v-if="run.bold">{{ run.text }}</strong>
                  <span v-else>{{ run.text }}</span>
                </template>
              </p>
              <ol v-else-if="block.ordered">
                <li
                  v-for="(item, itemIndex) in block.items ?? []"
                  :key="itemIndex"
                >
                  <template
                    v-for="(run, runIndex) in item"
                    :key="runIndex"
                  >
                    <strong v-if="run.bold">{{ run.text }}</strong>
                    <span v-else>{{ run.text }}</span>
                  </template>
                </li>
              </ol>
              <ul v-else>
                <li
                  v-for="(item, itemIndex) in block.items ?? []"
                  :key="itemIndex"
                >
                  <template
                    v-for="(run, runIndex) in item"
                    :key="runIndex"
                  >
                    <strong v-if="run.bold">{{ run.text }}</strong>
                    <span v-else>{{ run.text }}</span>
                  </template>
                </li>
              </ul>
            </template>
          </div>

          <div
            v-if="selected.sources.length"
            class="policy-sources"
          >
            <h4>
              <i
                class="fas fa-book"
                aria-hidden="true"
              />
              资料来源
            </h4>
            <ul>
              <li
                v-for="source in selected.sources"
                :key="`${source.title}-${source.url ?? ''}`"
              >
                <a
                  v-if="safeUrl(source.url)"
                  :href="safeUrl(source.url)"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {{ source.title || source.media || source.url }}
                </a>
                <span v-else>
                  {{ source.title || source.media || "" }}
                </span>
                <span
                  v-if="sourceMeta(source)"
                  class="src-meta"
                >
                  {{ sourceMeta(source) }}
                </span>
              </li>
            </ul>
          </div>

          <div
            v-if="
              data &&
                (selected.sources.length
                  ? data.source_note || data.disclaimer
                  : data.disclaimer)
            "
            class="policy-disclaimer"
          >
            <i
              class="fas fa-info-circle"
              aria-hidden="true"
            />
            <span>
              <template v-if="selected.sources.length && data.source_note">
                {{ data.source_note }}<br>
              </template>
              {{ data.disclaimer }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.policy-card {
  width: 100%;
  color: inherit;
  font: inherit;
  text-align: left;
}

.policy-card h3 {
  margin: 0 0 8px;
  color: var(--text-primary);
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.4;
}

.policy-card p {
  flex: 1;
}

.policy-card-top,
.policy-card-footer {
  width: 100%;
}

.policy-modal {
  max-width: 600px;
}

.policy-modal .modal-body {
  max-height: 60vh;
  overflow-y: auto;
}

.policy-disclaimer {
  align-items: flex-start;
}
</style>
