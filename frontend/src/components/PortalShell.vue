<script setup lang="ts">
import { ArrowRight, LockKeyhole, RefreshCw, ShieldCheck } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type { SnapshotSource } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import OnboardingOverlay from '@/components/OnboardingOverlay.vue'
import {
  portalDefinitions,
  type PortalId
} from '@/data/portal-guides'
import { useAuthStore } from '@/stores/auth'

interface OnboardingStateResponse {
  success: true
  required: boolean
  portal: PortalId
}

type OnboardingOutcome = 'completed' | 'skipped'

const props = defineProps<{
  portal: PortalId
}>()

const auth = useAuthStore()
const router = useRouter()
const definition = computed(() => portalDefinitions[props.portal])
const loadingOnboarding = ref(true)
const overlayOpen = ref(false)
const overlayProcessing = ref(false)
const onboardingError = ref('')
const outcomeError = ref('')
const headerSource = computed<SnapshotSource>(() =>
  onboardingError.value ? 'mock' : 'live'
)

async function loadOnboardingState() {
  loadingOnboarding.value = true
  onboardingError.value = ''

  try {
    const response = await apiFetch<OnboardingStateResponse>(
      `/api/onboarding/${props.portal}`
    )
    overlayOpen.value = response.required
  } catch (error) {
    overlayOpen.value = false
    onboardingError.value =
      error instanceof Error ? error.message : '引导状态加载失败'
  } finally {
    loadingOnboarding.value = false
  }
}

async function recordOutcome(outcome: OnboardingOutcome) {
  if (overlayProcessing.value) {
    return
  }

  overlayProcessing.value = true
  outcomeError.value = ''

  try {
    await apiFetch(`/api/onboarding/${props.portal}/complete`, {
      method: 'POST',
      body: JSON.stringify({ outcome })
    })
    overlayOpen.value = false
  } catch (error) {
    outcomeError.value =
      error instanceof Error ? error.message : '引导状态保存失败'
  } finally {
    overlayProcessing.value = false
  }
}

function closeOverlay() {
  overlayOpen.value = false
  outcomeError.value = ''
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void loadOnboardingState()
})
</script>

<template>
  <div class="portal-page">
    <AppHeader
      :source="headerSource"
      :loading="loadingOnboarding"
      :user-name="auth.user?.name"
      @logout="logout"
    />

    <main class="portal-main">
      <section class="portal-heading" aria-labelledby="portal-title">
        <div>
          <h1 id="portal-title">{{ definition.title }}</h1>
          <p>{{ definition.description }}</p>
        </div>
        <div class="identity-state">
          <ShieldCheck :size="17" aria-hidden="true" />
          <span>{{ auth.user?.name }}</span>
          <strong>{{ auth.user?.role === 'super_admin' || auth.user?.role === 'admin' ? '管理员' : '已认证' }}</strong>
        </div>
      </section>

      <slot />

      <section class="entry-index" aria-labelledby="portal-entries-title">
        <header class="section-heading">
          <h2 id="portal-entries-title">核心入口</h2>
          <span class="ark-data">{{ definition.entries.length }} 个入口</span>
        </header>

        <div class="entry-list">
          <article
            v-for="entry in definition.entries"
            :id="entry.id"
            :key="entry.id"
            class="entry-row"
          >
            <div class="entry-copy">
              <h3>{{ entry.title }}</h3>
              <p>{{ entry.description }}</p>
            </div>
            <RouterLink v-if="entry.href" class="entry-action" :to="entry.href">
              <span>进入</span>
              <ArrowRight :size="15" aria-hidden="true" />
            </RouterLink>
            <span v-else class="future-state">
              <LockKeyhole :size="15" aria-hidden="true" />
              后续开放
            </span>
          </article>
        </div>
      </section>

      <section v-if="onboardingError" class="load-error" role="alert">
        <p>{{ onboardingError }}</p>
        <button type="button" @click="loadOnboardingState">
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </section>
    </main>

    <OnboardingOverlay
      v-if="overlayOpen"
      :title="`${definition.title}首次引导`"
      :steps="definition.steps"
      :processing="overlayProcessing"
      :error="outcomeError"
      @complete="recordOutcome('completed')"
      @skipped="recordOutcome('skipped')"
      @close="closeOverlay"
    />
  </div>
</template>

<style scoped>
.portal-page {
  min-height: 100svh;
  background:
    linear-gradient(rgb(16 23 25 / 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgb(16 23 25 / 0.038) 1px, transparent 1px),
    var(--ark-ink);
  background-size: 72px 72px;
}

.portal-main {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 52px 24px 72px;
}

.portal-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 28px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.portal-heading h1 {
  margin: 0;
  font-size: 3rem;
  line-height: 1.02;
}

.portal-heading p {
  max-width: 62ch;
  margin: 16px 0 0;
  color: var(--ark-muted);
}

.identity-state {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 4px 9px;
  align-items: center;
  min-width: 176px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line);
  background: rgb(255 255 255 / 0.78);
  color: var(--ark-signal);
}

.identity-state span {
  min-width: 0;
  overflow: hidden;
  color: var(--ark-paper);
  font-size: 0.86rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.identity-state strong {
  grid-column: 2;
  color: var(--ark-muted);
  font-size: 0.72rem;
  font-weight: 400;
}

.entry-index {
  margin-top: 28px;
}

.section-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 12px;
}

.section-heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.section-heading span {
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.entry-list {
  display: grid;
  gap: 1px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.entry-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: center;
  min-height: 104px;
  padding: 20px 22px;
  background: rgb(255 255 255 / 0.88);
}

.entry-copy h3 {
  margin: 0;
  font-size: 1.08rem;
}

.entry-copy p {
  margin: 8px 0 0;
  color: var(--ark-muted);
  font-size: 0.88rem;
}

.future-state {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 34px;
  padding: 0 10px;
  border: 1px solid var(--ark-line);
  color: var(--ark-muted);
  font-size: 0.76rem;
  white-space: nowrap;
}

.entry-action {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 7px;
  min-height: 34px;
  padding: 0 10px;
  border: 1px solid var(--ark-signal);
  color: var(--ark-signal);
  font-size: 0.76rem;
  text-decoration: none;
  white-space: nowrap;
}

.entry-action:hover,
.entry-action:focus-visible {
  background: rgb(24 209 255 / 0.1);
}

.load-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 18px;
  padding: 11px 12px;
  border: 1px solid rgb(180 35 24 / 0.44);
  background: rgb(180 35 24 / 0.08);
}

.load-error p {
  margin: 0;
  color: #b42318;
  font-size: 0.82rem;
}

.load-error button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  padding: 0 11px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
  white-space: nowrap;
}

.load-error button:hover {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

@media (max-width: 720px) {
  .portal-main {
    padding: 32px 14px 48px;
  }

  .portal-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .portal-heading h1 {
    font-size: 2.25rem;
  }

  .identity-state {
    width: 100%;
  }

  .entry-row {
    grid-template-columns: 1fr;
    gap: 14px;
    padding: 18px;
  }

  .future-state {
    justify-self: start;
  }
}
</style>
