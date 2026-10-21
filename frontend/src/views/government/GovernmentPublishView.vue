<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import {
  createGovernmentPolicy,
  getGovernmentPolicies,
  updateGovernmentPolicy,
  type GovernmentPolicy,
  type GovernmentPolicyInput,
} from "@/api/government";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

type FeedbackKind = "info" | "success" | "error";

const route = useRoute();
const router = useRouter();
const policies = ref<GovernmentPolicy[]>([]);
const loading = ref(true);
const loadError = ref("");
const saving = ref(false);
const feedback = ref<{ kind: FeedbackKind; message: string } | null>(null);
const editingPolicy = ref<GovernmentPolicy | null>(null);

const form = reactive<GovernmentPolicyInput>({
  title: "",
  category: "综合",
  date: todayString(),
  summary: "",
  source: "",
  content: "",
});

const isEditing = computed(() => editingPolicy.value !== null);
const formTitle = computed(() => (isEditing.value ? "编辑政策" : "发布新政策"));
const submitLabel = computed(() => (isEditing.value ? "保存修改" : "发布政策"));
const categoryOptions = computed(() => {
  const categories = new Set(["综合"]);
  for (const policy of policies.value) {
    if (policy.category) categories.add(policy.category);
  }
  if (form.category) categories.add(form.category);
  return Array.from(categories);
});

function todayString(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function resetForm(): void {
  form.title = "";
  form.category = "综合";
  form.date = todayString();
  form.summary = "";
  form.source = "";
  form.content = "";
  editingPolicy.value = null;
}

function sourceText(policy: GovernmentPolicy): string {
  return policy.sources
    .map((source) => {
      const title = source.title || source.url || "";
      return source.url && source.title
        ? `${title} | ${source.url}`
        : title;
    })
    .filter(Boolean)
    .join("\n");
}

function applyEditingPolicy(policy: GovernmentPolicy): void {
  editingPolicy.value = policy;
  form.title = policy.title || "";
  form.category = policy.category || "综合";
  form.date = policy.date || todayString();
  form.summary = policy.summary || "";
  form.source = sourceText(policy);
  form.content = policy.content || "";
  feedback.value = {
    kind: "info",
    message: `正在编辑《${policy.title || "未命名政策"}》，改完点「保存修改」。`,
  };
}

function syncEditMode(): void {
  const wasEditing = editingPolicy.value !== null;
  const editId = Number(route.query.edit);
  if (!Number.isInteger(editId) || editId <= 0) {
    resetForm();
    if (wasEditing && feedback.value?.kind === "info") {
      feedback.value = null;
    }
    return;
  }
  const policy = policies.value.find((item) => item.id === editId);
  if (!policy) {
    resetForm();
    feedback.value = {
      kind: "error",
      message: "未找到该政策，请刷新列表后重试。",
    };
    return;
  }
  applyEditingPolicy(policy);
}

async function loadPolicies(): Promise<void> {
  loading.value = true;
  loadError.value = "";
  try {
    policies.value = await getGovernmentPolicies();
    syncEditMode();
  } catch (requestError) {
    policies.value = [];
    loadError.value =
      requestError instanceof Error
        ? requestError.message
        : "政策分类加载失败";
  } finally {
    loading.value = false;
  }
}

function cancelEdit(): void {
  resetForm();
  feedback.value = null;
  void router.replace({ name: "government-publish" });
}

async function submitPolicy(): Promise<void> {
  feedback.value = null;
  if (!form.title.trim() || !form.content.trim()) {
    feedback.value = {
      kind: "error",
      message: "标题和内容不能为空",
    };
    return;
  }

  const wasEditing = isEditing.value;
  const policyId = editingPolicy.value?.id;
  saving.value = true;
  try {
    if (wasEditing && policyId) {
      await updateGovernmentPolicy(policyId, {
        title: form.title.trim(),
        content: form.content.trim(),
        category: form.category,
        summary: form.summary.trim(),
        date: form.date,
        source: form.source,
      });
    } else {
      await createGovernmentPolicy({
        title: form.title.trim(),
        content: form.content.trim(),
        category: form.category,
        summary: form.summary.trim(),
        date: form.date,
        source: form.source,
      });
    }

    resetForm();
    if (wasEditing) {
      void router.replace({ name: "government-publish" });
    }
    feedback.value = {
      kind: "success",
      message: wasEditing
        ? "修改已保存，学员端同步更新。"
        : "已发布，学员端首页「本土资源 → 政策信息」已同步显示。",
    };
    try {
      policies.value = await getGovernmentPolicies();
    } catch {
      // The write succeeded. A category refresh failure must not be reported
      // as a failed save.
    }
  } catch (requestError) {
    feedback.value = {
      kind: "error",
      message:
        requestError instanceof Error
          ? `保存失败：${requestError.message}`
          : "保存失败，请重试",
    };
  } finally {
    saving.value = false;
  }
}

watch(
  () => route.query.edit,
  () => {
    if (!loading.value) syncEditMode();
  },
);

onMounted(loadPolicies);
</script>

<template>
  <section
    class="backoffice-page government-policy-form-page"
    data-testid="government-policy-form-page"
  >
    <header class="backoffice-page-header">
      <div>
        <p>政务工作</p>
        <h1 data-testid="backoffice-page-title">
          {{ formTitle }}
        </h1>
        <span>
          发布后立即在学员端「本土资源 → 政策信息」可见；如需先不上线，
          发布后在政策管理列表下架。
        </span>
      </div>
    </header>

    <BackofficeState
      v-if="loading"
      kind="loading"
      title="正在读取政策分类"
    />
    <BackofficeState
      v-else-if="loadError"
      kind="error"
      title="政策分类加载失败"
      :detail="loadError"
    >
      <button
        type="button"
        class="backoffice-button"
        @click="loadPolicies"
      >
        重试
      </button>
    </BackofficeState>

    <BackofficeCard
      v-else
      :title="formTitle"
      description="分类来自现有政策数据，新增分类会随政策自动出现在这里。"
    >
      <form
        class="government-policy-form"
        data-testid="government-policy-form"
        @submit.prevent="submitPolicy"
      >
        <label class="backoffice-field">
          <span>政策标题</span>
          <input
            v-model="form.title"
            autocomplete="off"
            placeholder="政策标题（必填）"
          >
        </label>

        <div class="backoffice-form-grid">
          <label class="backoffice-field">
            <span>政策分类</span>
            <select v-model="form.category">
              <option
                v-for="category in categoryOptions"
                :key="category"
                :value="category"
              >
                {{ category }}
              </option>
            </select>
          </label>
          <label class="backoffice-field">
            <span>发布日期</span>
            <input
              v-model="form.date"
              type="date"
            >
          </label>
        </div>

        <label class="backoffice-field">
          <span>摘要</span>
          <input
            v-model="form.summary"
            autocomplete="off"
            placeholder="留空将自动截取正文首段"
          >
        </label>

        <label class="backoffice-field">
          <span>资料来源</span>
          <textarea
            v-model="form.source"
            rows="3"
            placeholder="可选，一行一条，写作：来源名称 | 链接"
          />
        </label>

        <label class="backoffice-field">
          <span>政策内容</span>
          <textarea
            v-model="form.content"
            rows="9"
            placeholder="政策内容（必填）"
          />
        </label>

        <div class="government-policy-form-actions">
          <button
            type="submit"
            class="backoffice-button"
            data-testid="government-policy-submit"
            :disabled="saving"
          >
            {{ saving ? "保存中..." : submitLabel }}
          </button>
          <button
            v-if="isEditing"
            type="button"
            class="backoffice-button is-secondary"
            data-testid="government-policy-cancel"
            :disabled="saving"
            @click="cancelEdit"
          >
            取消编辑
          </button>
        </div>
      </form>

      <BackofficeFeedback
        v-if="feedback"
        :kind="feedback.kind"
        :message="feedback.message"
        testid="government-policy-form-feedback"
      />
    </BackofficeCard>
  </section>
</template>

<style src="./government.css"></style>
