<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import LocalResourcesNav from '@/components/LocalResourcesNav.vue'
import SemanticChineseText from '@/components/SemanticChineseText.vue'
import { useLocalResourcesStore } from '@/stores/localResources'

const route = useRoute()
const store = useLocalResourcesStore()
const initialLoading = ref(true)
const loadFailed = ref(false)
const recordNotice = ref('')
const viewNotice = computed(() => store.viewNotice || recordNotice.value)

async function loadPolicyDetail() {
  const policyId = route.params.policyId as string
  initialLoading.value = true
  recordNotice.value = ''
  try {
    const opened = await store.openPolicy(policyId)
    loadFailed.value = !opened
    if (!opened) {
      return
    }

    try {
      await store.recordPolicyView(policyId)
    } catch {
      recordNotice.value = '浏览量暂未记录'
    }
  } catch {
    loadFailed.value = true
  } finally {
    initialLoading.value = false
  }
}

onMounted(() => {
  void loadPolicyDetail()
})
</script>

<template>
  <div class="local-resource-policy-detail">
    <AppHeader
      source="live"
      :loading="initialLoading || store.loading"
      :show-auth-controls="false"
    />
    <LocalResourcesNav />

    <main class="local-resource-policy-detail__main">
      <header class="local-resource-policy-detail__heading">
        <span class="local-resource-policy-detail__code ark-data">
          06 / POLICY DETAIL
        </span>
        <h1>{{ store.policyDetail?.title ?? '政策详情' }}</h1>

        <dl
          v-if="store.policyDetail"
          class="local-resource-policy-detail__meta"
        >
          <div>
            <dt>政策类别</dt>
            <dd>{{ store.policyDetail.category_label }}</dd>
          </div>
          <div>
            <dt>发布时间</dt>
            <dd>
              <time :datetime="store.policyDetail.published_at">
                {{ store.policyDetail.published_at }}
              </time>
            </dd>
          </div>
        </dl>
      </header>

      <article
        v-if="store.policyDetail && !loadFailed"
        class="local-resource-policy-detail__content"
      >
        <p data-test="policy-body">
          <SemanticChineseText :text="store.policyDetail.content" />
        </p>
        <p
          v-if="viewNotice"
          class="local-resource-policy-detail__notice"
          data-test="policy-view-notice"
          role="status"
          aria-live="polite"
        >
          {{ viewNotice }}
        </p>
      </article>

      <div
        v-else-if="initialLoading"
        class="local-resource-policy-detail__status"
        data-test="policy-detail-loading"
        role="status"
      >
        正在加载政策详情
      </div>

      <p
        v-else
        class="local-resource-policy-detail__status"
        data-test="policy-detail-unavailable"
        role="alert"
      >
        政策数据暂不可用
      </p>
    </main>
  </div>
</template>

<style scoped>
.local-resource-policy-detail {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.local-resource-policy-detail__main {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.local-resource-policy-detail__heading {
  padding-bottom: 28px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.local-resource-policy-detail__code {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.local-resource-policy-detail__heading h1 {
  max-width: 32ch;
  margin: 9px 0 0;
  font-size: 2.8rem;
  line-height: 1.08;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: balance;
  word-break: keep-all;
}

.local-resource-policy-detail__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 30px;
  margin: 18px 0 0;
}

.local-resource-policy-detail__meta div {
  min-width: 0;
}

.local-resource-policy-detail__meta dt {
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.local-resource-policy-detail__meta dd {
  min-width: 0;
  margin: 2px 0 0;
  color: var(--ark-paper);
  font-size: 0.9rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.local-resource-policy-detail__content {
  margin-top: 22px;
  border-top: 1px solid var(--ark-line-strong);
}

.local-resource-policy-detail__content > p:first-child {
  max-width: 78ch;
  margin: 0;
  padding: 24px 0 28px;
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  white-space: pre-wrap;
  word-break: keep-all;
}

.local-resource-policy-detail__notice {
  margin: 0;
  padding: 11px 0 13px;
  border-top: 1px solid var(--ark-line);
  color: var(--ark-state);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.local-resource-policy-detail__status {
  display: flex;
  min-height: 260px;
  align-items: center;
  justify-content: center;
  margin: 22px 0 0;
  border-top: 1px solid var(--ark-line-strong);
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-wrap: pretty;
  word-break: keep-all;
}

@media (max-width: 640px) {
  .local-resource-policy-detail__main {
    padding: 28px 14px 48px;
  }

  .local-resource-policy-detail__heading h1 {
    font-size: 2.2rem;
  }

  .local-resource-policy-detail__meta {
    display: grid;
    gap: 10px;
  }

  .local-resource-policy-detail__content > p:first-child {
    padding-block: 20px 24px;
  }
}
</style>
