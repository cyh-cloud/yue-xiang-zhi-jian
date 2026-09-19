<script setup lang="ts">
import { RefreshCw } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { RouterView, useRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type { SnapshotSource } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import OnboardingOverlay from '@/components/OnboardingOverlay.vue'
import TeacherConsoleNav from '@/components/TeacherConsoleNav.vue'
import { portalDefinitions } from '@/data/portal-guides'
import { useAuthStore } from '@/stores/auth'

interface OnboardingStateResponse {
  success: true
  required: boolean
  portal: 'teacher'
}

type OnboardingOutcome = 'completed' | 'skipped'

const auth = useAuthStore()
const router = useRouter()
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
      '/api/onboarding/teacher'
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
    await apiFetch('/api/onboarding/teacher/complete', {
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
  <div class="teacher-portal">
    <AppHeader
      :source="headerSource"
      :loading="loadingOnboarding"
      :user-name="auth.user?.name"
      @logout="logout"
    />

    <TeacherConsoleNav />

    <section v-if="onboardingError" class="load-error" role="alert">
      <p>{{ onboardingError }}</p>
      <button type="button" @click="loadOnboardingState">
        <RefreshCw :size="16" aria-hidden="true" />
        重新加载
      </button>
    </section>

    <div class="teacher-console-content">
      <RouterView />
    </div>

    <OnboardingOverlay
      v-if="overlayOpen"
      :title="`${portalDefinitions.teacher.title}首次引导`"
      :steps="portalDefinitions.teacher.steps"
      :processing="overlayProcessing"
      :error="outcomeError"
      @complete="recordOutcome('completed')"
      @skipped="recordOutcome('skipped')"
      @close="closeOverlay"
    />
  </div>
</template>

<style scoped>
.teacher-portal {
  min-height: 100svh;
  background: var(--ark-ink);
}

.teacher-console-content {
  min-width: 0;
}

.load-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: min(calc(100% - 48px), 1180px);
  margin: 14px auto 0;
  padding: 11px 12px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.load-error p {
  margin: 0;
  color: var(--ark-paper);
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

@media (max-width: 760px) {
  .load-error {
    width: min(calc(100% - 28px), 1180px);
  }
}
</style>
