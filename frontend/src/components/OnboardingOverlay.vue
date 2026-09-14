<script setup lang="ts">
import {
  ArrowRight,
  Check,
  ChevronLeft,
  SkipForward,
  X
} from 'lucide-vue-next'
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch
} from 'vue'
import type { CSSProperties } from 'vue'

import type { PortalGuideStep } from '@/data/portal-guides'

const props = withDefaults(
  defineProps<{
    title: string
    steps: PortalGuideStep[]
    processing?: boolean
    error?: string
  }>(),
  {
    processing: false,
    error: ''
  }
)

const emit = defineEmits<{
  complete: []
  skipped: []
  close: []
}>()

const panel = ref<HTMLElement | null>(null)
const currentIndex = ref(0)
const targetRect = ref<DOMRect | null>(null)
const viewportWidth = ref(
  typeof window === 'undefined' ? 1024 : window.innerWidth
)
let revealTimer: number | undefined

const currentStep = computed(() => props.steps[currentIndex.value] ?? null)
const isLastStep = computed(
  () => currentIndex.value === Math.max(props.steps.length - 1, 0)
)

const spotlightStyle = computed<CSSProperties>(() => {
  const rect = targetRect.value
  if (!rect) {
    return {}
  }

  const inset = 8
  return {
    top: `${Math.max(rect.top - inset, 0)}px`,
    left: `${Math.max(rect.left - inset, 0)}px`,
    width: `${Math.max(rect.width + inset * 2, 1)}px`,
    height: `${Math.max(rect.height + inset * 2, 1)}px`
  }
})

const panelStyle = computed<CSSProperties>(() => {
  if (viewportWidth.value <= 860) {
    return {
      left: '14px',
      right: '14px',
      bottom: '14px'
    }
  }

  const rect = targetRect.value
  if (!rect) {
    return {
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)'
    }
  }

  const targetIsOnLeft =
    rect.left + rect.width / 2 < viewportWidth.value / 2
  return targetIsOnLeft
    ? {
        top: '50%',
        right: '28px',
        transform: 'translateY(-50%)'
      }
    : {
        top: '50%',
        left: '28px',
        transform: 'translateY(-50%)'
      }
})

function syncTarget() {
  viewportWidth.value = window.innerWidth
  const selector = currentStep.value?.selector
  if (!selector) {
    targetRect.value = null
    return
  }

  const target = document.querySelector<HTMLElement>(selector)
  targetRect.value = target?.getBoundingClientRect() ?? null
}

function revealCurrentStep() {
  window.clearTimeout(revealTimer)
  void nextTick(() => {
    syncTarget()
    const selector = currentStep.value?.selector
    const target = selector
      ? document.querySelector<HTMLElement>(selector)
      : null

    if (target && typeof target.scrollIntoView === 'function') {
      target.scrollIntoView({
        block: 'center',
        inline: 'nearest',
        behavior: 'smooth'
      })
    }

    revealTimer = window.setTimeout(syncTarget, 320)
  })
}

function goToStep(index: number) {
  currentIndex.value = Math.min(
    Math.max(index, 0),
    Math.max(props.steps.length - 1, 0)
  )
  revealCurrentStep()
}

function finish() {
  if (!props.processing) {
    emit('complete')
  }
}

function skip() {
  if (!props.processing) {
    emit('skipped')
  }
}

function close() {
  if (!props.processing) {
    emit('close')
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    close()
    return
  }

  if (event.key !== 'Tab' || !panel.value) {
    return
  }

  const focusable = Array.from(
    panel.value.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
    )
  )
  if (!focusable.length) {
    return
  }

  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(currentIndex, revealCurrentStep)

onMounted(() => {
  window.addEventListener('resize', syncTarget)
  window.addEventListener('scroll', syncTarget, true)
  revealCurrentStep()
  void nextTick(() => panel.value?.focus())
})

onBeforeUnmount(() => {
  window.clearTimeout(revealTimer)
  window.removeEventListener('resize', syncTarget)
  window.removeEventListener('scroll', syncTarget, true)
})
</script>

<template>
  <div class="onboarding-root">
    <div
      v-if="targetRect"
      class="onboarding-spotlight"
      :style="spotlightStyle"
      aria-hidden="true"
    ></div>
    <div v-else class="onboarding-backdrop" aria-hidden="true"></div>

    <section
      ref="panel"
      class="guide-panel"
      :style="panelStyle"
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-title"
      tabindex="-1"
      @keydown="handleKeydown"
    >
      <header class="panel-header">
        <div>
          <h2 id="onboarding-title">{{ title }}</h2>
          <p v-if="currentStep" class="step-progress ark-data">
            {{ currentIndex + 1 }} / {{ steps.length }}
          </p>
        </div>
        <button
          class="icon-action"
          data-test="close"
          type="button"
          :disabled="processing"
          aria-label="关闭引导"
          @click="close"
        >
          <X :size="18" aria-hidden="true" />
        </button>
      </header>

      <div v-if="currentStep" class="step-copy" aria-live="polite">
        <h3>{{ currentStep.title }}</h3>
        <p>{{ currentStep.description }}</p>
      </div>

      <ol class="step-rail" aria-label="引导进度">
        <li
          v-for="(step, index) in steps"
          :key="step.selector"
          :class="{
            current: index === currentIndex,
            complete: index < currentIndex
          }"
        >
          <span class="ark-sr-only">
            第 {{ index + 1 }} 步：{{ step.title }}
          </span>
        </li>
      </ol>

      <p v-if="error" class="guide-error" role="alert">{{ error }}</p>

      <footer class="panel-actions">
        <button
          class="skip-action"
          data-test="skip"
          type="button"
          :disabled="processing"
          @click="skip"
        >
          <SkipForward :size="16" aria-hidden="true" />
          跳过
        </button>

        <div class="step-actions">
          <button
            v-if="currentIndex > 0"
            class="icon-action"
            data-test="previous-step"
            type="button"
            :disabled="processing"
            aria-label="上一步"
            @click="goToStep(currentIndex - 1)"
          >
            <ChevronLeft :size="18" aria-hidden="true" />
          </button>
          <button
            v-if="!isLastStep"
            class="primary-action"
            data-test="next-step"
            type="button"
            :disabled="processing"
            @click="goToStep(currentIndex + 1)"
          >
            下一步
            <ArrowRight :size="16" aria-hidden="true" />
          </button>
          <button
            v-else
            class="primary-action"
            data-test="finish"
            type="button"
            :disabled="processing"
            @click="finish"
          >
            <Check :size="16" aria-hidden="true" />
            {{ processing ? '正在记录' : '完成' }}
          </button>
        </div>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.onboarding-root {
  position: fixed;
  z-index: 100;
  inset: 0;
}

.onboarding-backdrop {
  position: absolute;
  inset: 0;
  background: rgb(0 0 0 / 0.76);
}

.onboarding-spotlight {
  position: fixed;
  pointer-events: none;
  border: 1px solid var(--ark-signal);
  box-shadow:
    0 0 0 100vmax rgb(0 0 0 / 0.76),
    0 0 28px rgb(24 209 255 / 0.16);
  transition:
    top 220ms cubic-bezier(0.22, 0.8, 0.2, 1),
    left 220ms cubic-bezier(0.22, 0.8, 0.2, 1),
    width 220ms cubic-bezier(0.22, 0.8, 0.2, 1),
    height 220ms cubic-bezier(0.22, 0.8, 0.2, 1);
}

.guide-panel {
  position: fixed;
  width: min(410px, calc(100vw - 28px));
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: rgb(5 6 7 / 0.98);
  box-shadow: 14px 18px 44px rgb(0 0 0 / 0.48);
}

.guide-panel::before {
  content: "";
  position: absolute;
  top: -1px;
  left: -1px;
  width: 92px;
  height: 3px;
  background: var(--ark-signal);
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 20px 16px;
  border-bottom: 1px solid var(--ark-line);
}

.panel-header h2 {
  margin: 0;
  font-size: 1.3rem;
  line-height: 1.25;
}

.step-progress {
  margin: 7px 0 0;
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.icon-action {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--ark-line);
  border-radius: var(--ark-radius);
  background: transparent;
  color: var(--ark-paper);
}

.icon-action:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.step-copy {
  min-height: 116px;
  padding: 19px 20px 17px;
}

.step-copy h3 {
  margin: 0;
  font-size: 1.08rem;
}

.step-copy p {
  margin: 10px 0 0;
  color: #c4cdcf;
  font-size: 0.9rem;
  line-height: 1.7;
}

.step-rail {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  margin: 0;
  padding: 0 20px 18px;
  list-style: none;
}

.step-rail li {
  height: 3px;
  background: var(--ark-line);
}

.step-rail li.complete,
.step-rail li.current {
  background: var(--ark-signal);
}

.guide-error {
  margin: 0 20px 16px;
  padding: 9px 10px;
  border: 1px solid rgb(255 138 138 / 0.44);
  background: rgb(255 138 138 / 0.08);
  color: #ff9c9c;
  font-size: 0.8rem;
}

.panel-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 20px 18px;
  border-top: 1px solid var(--ark-line);
}

.step-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.skip-action,
.primary-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  padding: 0 14px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: transparent;
  color: var(--ark-paper);
  font-size: 0.86rem;
}

.primary-action {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.skip-action:hover:not(:disabled),
.primary-action:hover:not(:disabled) {
  background: rgb(24 209 255 / 0.12);
}

@media (max-width: 860px) {
  .guide-panel {
    max-height: calc(100svh - 28px);
    overflow-y: auto;
  }
}

@media (max-width: 520px) {
  .panel-actions {
    align-items: stretch;
    flex-direction: column-reverse;
  }

  .step-actions,
  .skip-action,
  .primary-action {
    width: 100%;
  }

  .step-actions .icon-action {
    flex: 0 0 42px;
  }

  .step-actions .primary-action {
    flex: 1;
  }
}
</style>
