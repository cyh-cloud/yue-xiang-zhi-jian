<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import {
  deleteGovernmentPolicy,
  getGovernmentPolicies,
  updateGovernmentPolicy,
  type GovernmentPolicy,
} from "@/api/government";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

type FeedbackKind = "success" | "error";

const router = useRouter();
const policies = ref<GovernmentPolicy[]>([]);
const loading = ref(true);
const loadError = ref("");
const feedback = ref<{ kind: FeedbackKind; message: string } | null>(null);
const busyPolicyId = ref<number | null>(null);

function policyPreview(policy: GovernmentPolicy): string {
  const text = (policy.summary || policy.content || "")
    .replace(/\s+/g, " ")
    .trim();
  if (!text) return "";
  return text.length > 120 ? `${text.slice(0, 120)}…` : text;
}

function isPublished(policy: GovernmentPolicy): boolean {
  return Number(policy.is_published) === 1;
}

async function loadPolicies(): Promise<void> {
  loading.value = true;
  loadError.value = "";
  try {
    policies.value = await getGovernmentPolicies();
  } catch (requestError) {
    policies.value = [];
    loadError.value =
      requestError instanceof Error
        ? requestError.message
        : "政策列表加载失败";
  } finally {
    loading.value = false;
  }
}

function editPolicy(policy: GovernmentPolicy): void {
  void router.push({
    name: "government-publish",
    query: { edit: String(policy.id) },
  });
}

async function togglePolicy(policy: GovernmentPolicy): Promise<void> {
  const wasPublished = isPublished(policy);
  busyPolicyId.value = policy.id;
  feedback.value = null;
  try {
    await updateGovernmentPolicy(policy.id, {
      is_published: wasPublished ? 0 : 1,
    });
    feedback.value = {
      kind: "success",
      message: wasPublished
        ? "已下架，学员端不再显示该政策。"
        : "已上架，学员端已恢复显示。",
    };
    await loadPolicies();
  } catch (requestError) {
    feedback.value = {
      kind: "error",
      message:
        requestError instanceof Error
          ? `操作失败：${requestError.message}`
          : "操作失败，请重试",
    };
  } finally {
    busyPolicyId.value = null;
  }
}

async function removePolicy(policy: GovernmentPolicy): Promise<void> {
  if (!window.confirm(`确定删除《${policy.title || "该政策"}》？删除后无法恢复。`)) {
    return;
  }
  busyPolicyId.value = policy.id;
  feedback.value = null;
  try {
    const response = await deleteGovernmentPolicy(policy.id);
    feedback.value = {
      kind: "success",
      message: response.message || "已删除。",
    };
    await loadPolicies();
  } catch (requestError) {
    feedback.value = {
      kind: "error",
      message:
        requestError instanceof Error
          ? `删除失败：${requestError.message}`
          : "删除失败，请重试",
    };
  } finally {
    busyPolicyId.value = null;
  }
}

onMounted(loadPolicies);
</script>

<template>
  <section
    class="backoffice-page"
    data-testid="government-policies"
  >
    <header class="backoffice-page-header">
      <div>
        <p>政务工作</p>
        <h1 data-testid="backoffice-page-title">
          政策管理
        </h1>
        <span>编辑、上架或下架政策；状态变化立即影响学员端可见列表。</span>
      </div>
      <button
        type="button"
        class="backoffice-button is-secondary"
        :disabled="loading"
        @click="loadPolicies"
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
      testid="government-policies-feedback"
    />

    <BackofficeState
      v-if="loading"
      kind="loading"
      title="正在加载政策"
    />
    <BackofficeState
      v-else-if="loadError"
      kind="error"
      title="政策列表加载失败"
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
    <BackofficeState
      v-else-if="!policies.length"
      kind="empty"
      title="暂无政策"
      detail="在左侧「发布政策」发布第一条政策；发布后学员端会立即显示。"
    />

    <div
      v-else
      class="government-policy-list"
    >
      <BackofficeCard
        v-for="policy in policies"
        :key="policy.id"
        flush
      >
        <article
          class="government-policy-card"
          data-testid="government-policy-card"
          :data-policy-id="policy.id"
        >
          <header>
            <div>
              <h2>{{ policy.title || "(无标题)" }}</h2>
              <span class="backoffice-status is-active government-policy-category">
                {{ policy.category || "综合" }}
              </span>
            </div>
            <span
              class="backoffice-status"
              :class="isPublished(policy) ? 'is-active' : 'is-suspended'"
            >
              {{ isPublished(policy) ? "已上线" : "已下架" }}
            </span>
          </header>
          <p class="government-policy-meta">
            <span v-if="policy.date">发布日期 {{ policy.date }}</span>
            <span v-if="policy.created_at">
              录入于 {{ policy.created_at.slice(0, 10) }}
            </span>
            <span>发布者 {{ policy.author_id }}</span>
            <span>
              {{
                policy.sources.length
                  ? `资料来源 ${policy.sources.length} 条`
                  : "未填资料来源"
              }}
            </span>
          </p>
          <p
            v-if="policyPreview(policy)"
            class="government-policy-preview"
          >
            {{ policyPreview(policy) }}
          </p>
          <footer class="backoffice-row-actions">
            <button
              type="button"
              class="backoffice-button is-small is-secondary"
              data-testid="government-policy-toggle"
              :disabled="busyPolicyId === policy.id"
              @click="togglePolicy(policy)"
            >
              {{ isPublished(policy) ? "下架" : "上架" }}
            </button>
            <button
              type="button"
              class="backoffice-button is-small is-secondary"
              data-testid="government-policy-edit"
              :disabled="busyPolicyId === policy.id"
              @click="editPolicy(policy)"
            >
              编辑
            </button>
            <button
              type="button"
              class="backoffice-button is-small is-danger"
              data-testid="government-policy-delete"
              :disabled="busyPolicyId === policy.id"
              @click="removePolicy(policy)"
            >
              删除
            </button>
          </footer>
        </article>
      </BackofficeCard>
    </div>
  </section>
</template>

<style src="./government.css"></style>
