<script setup lang="ts">
import {
  BookOpen,
  CheckCircle2,
  Circle,
  RefreshCw,
  Sparkles,
  Video
} from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { useActiveLearningHeartbeat } from '@/composables/activeLearningHeartbeat'
import ContentCommentThread from '@/components/ContentCommentThread.vue'
import {
  useHandcraftInheritanceStore
} from '@/stores/handcraftInheritance'

const props = defineProps<{
  craftKey: string
}>()

const store = useHandcraftInheritanceStore()
const viewLoading = ref(false)
const loadError = ref('')
const stepError = ref('')
const stepCompletionErrors = ref<Record<number, string>>({})
const arError = ref('')
const projectLabel = ref('')

const craftHeartbeat = useActiveLearningHeartbeat(
  payload => store.heartbeatCraft(props.craftKey, payload)
)
const arHeartbeat = useActiveLearningHeartbeat(
  payload => store.heartbeatAr(props.craftKey, payload)
)

const craft = computed(() =>
  store.activeCraft?.craft_key === props.craftKey
    ? store.activeCraft
    : null
)

const progress = computed(() => store.progressByCraft[props.craftKey])

const orderedSteps = computed(() =>
  [...(craft.value?.steps ?? [])].sort(
    (first, second) => first.step_no - second.step_no
  )
)

const materialGuide = computed(() => craft.value?.material_guide ?? [])

const approvedVideos = computed(() =>
  (store.videosByCraft[props.craftKey] ?? []).filter(video => {
    const approved =
      video.review_status === 'approved' ||
      video.review_status === 'published'
    return (
      approved &&
      video.available &&
      video.source_available &&
      Boolean(video.playback_url)
    )
  })
)

const completedSteps = computed(
  () => new Set(progress.value?.completed_steps ?? [])
)

const completedCount = computed(() => {
  const count = progress.value?.completed_step_count ?? completedSteps.value.size
  return Math.min(orderedSteps.value.length, Math.max(0, count))
})

const completedPercent = computed(() => {
  if (orderedSteps.value.length === 0) {
    return 0
  }
  return Math.round((completedCount.value / orderedSteps.value.length) * 100)
})

const hasValidSteps = computed(() => {
  if (orderedSteps.value.length !== 6) {
    return false
  }
  return orderedSteps.value.every((step, index) => {
    const hasTip = step.tips.some(tip => tip.trim().length > 0)
    return (
      step.step_no === index + 1 &&
      step.title.trim().length > 0 &&
      step.description.trim().length > 0 &&
      hasTip
    )
  })
})

const isUnavailable = computed(() => {
  const currentCraft = craft.value
  if (!currentCraft) {
    return false
  }
  return (
    !currentCraft.available ||
    !currentCraft.source_available ||
    !currentCraft.craft_key ||
    !hasValidSteps.value
  )
})

const unavailableReason = computed(
  () =>
    craft.value?.unavailable_reason ||
    '技艺内容不完整，暂不可学习'
)

const resumeText = computed(() => {
  const currentProgress = progress.value
  if (!currentProgress) {
    return '进度读取中'
  }
  if (currentProgress.is_completed) {
    return '已完成全部步骤，可从头复习'
  }
  return `从第 ${currentProgress.resume_step_no ?? 1} 步继续`
})

function stepIsCompleted(stepNo: number) {
  return completedSteps.value.has(stepNo)
}

function stepIsDisabled(stepNo: number) {
  return (
    stepIsCompleted(stepNo) ||
    store.completingStep ||
    !progress.value?.available
  )
}

function completionFeedback(reason: string | null) {
  const normalizedReason = reason?.trim() ?? ''
  const safeReason =
    normalizedReason.length > 0 &&
    normalizedReason.length <= 80 &&
    /[\u3400-\u9fff]/.test(normalizedReason)
  return safeReason ? normalizedReason : '请按顺序完成前面的步骤'
}

async function completeStep(stepNo: number) {
  const currentCraft = craft.value
  if (!currentCraft?.craft_key || stepIsDisabled(stepNo)) {
    return
  }
  stepError.value = ''
  delete stepCompletionErrors.value[stepNo]
  const segmentId = await craftHeartbeat.flush()
  const completed = await store.completeStep(
    currentCraft.craft_key,
    stepNo,
    segmentId
  )
  if (!completed) {
    stepError.value = store.error || '步骤完成状态保存失败'
    return
  }

  const completion = store.lastStepCompletion
  if (!completion || completion.step_no !== stepNo) {
    stepError.value = '步骤完成状态保存失败'
    return
  }
  if (!completion.accepted) {
    stepCompletionErrors.value = {
      ...stepCompletionErrors.value,
      [stepNo]: completionFeedback(completion.reason)
    }
  } else {
    craftHeartbeat.reset()
  }
}

async function requestArGuidance() {
  const currentCraft = craft.value
  const normalizedLabel = projectLabel.value.trim()
  if (!currentCraft?.craft_key || !normalizedLabel) {
    return
  }
  arError.value = ''
  const segmentId = await arHeartbeat.flush()
  const generated = await store.generateArGuidance(
    currentCraft.craft_key,
    normalizedLabel,
    segmentId
  )
  if (!generated) {
    arError.value = 'AI 服务暂时不可用'
  } else {
    arHeartbeat.reset()
  }
}

function resumeLearning() {
  const stepNo = progress.value?.resume_step_no
  if (stepNo) {
    document
      .getElementById(`handcraft-step-${stepNo}`)
      ?.scrollIntoView?.({ block: 'start' })
  }
}

async function loadContent() {
  viewLoading.value = true
  loadError.value = ''
  stepError.value = ''
  stepCompletionErrors.value = {}
  arError.value = ''
  arHeartbeat.reset()
  craftHeartbeat.reset()
  store.arGuidance = null

  const [craftLoaded, progressLoaded, videosLoaded] = await Promise.all([
    store.loadCraft(props.craftKey),
    store.loadProgress(props.craftKey),
    store.loadVideos(props.craftKey)
  ])

  if (!craftLoaded || !progressLoaded || !videosLoaded) {
    loadError.value = store.error || '技艺内容加载失败'
  }
  viewLoading.value = false
}

watch(
  () => props.craftKey,
  () => {
    projectLabel.value = ''
    void loadContent()
  }
)

onMounted(() => {
  void loadContent()
})
</script>

<template>
  <main
    class="craft-learning"
    data-test="craft-learning"
    :aria-busy="viewLoading"
    @pointerdown="craftHeartbeat.touch"
    @keydown="craftHeartbeat.touch"
    @scroll.passive="craftHeartbeat.touch"
  >
    <header class="craft-learning__heading">
      <span class="craft-learning__code ark-data">
        05 / CRAFT LEARNING
      </span>
      <h1>{{ craft?.name || '技艺学习' }}</h1>
      <p v-if="craft?.introduction">{{ craft.introduction }}</p>
    </header>

    <div v-if="viewLoading" class="craft-learning__status" role="status">
      <RefreshCw class="spinning" :size="20" aria-hidden="true" />
      正在加载技艺内容
    </div>

    <div
      v-else-if="loadError"
      class="craft-learning__error"
      role="alert"
    >
      <span>{{ loadError }}</span>
      <button type="button" data-test="craft-retry" @click="loadContent">
        <RefreshCw :size="16" aria-hidden="true" />
        重新加载
      </button>
    </div>

    <p v-else-if="!craft" class="craft-learning__status">
      未找到该技艺
    </p>

    <section
      v-else-if="isUnavailable"
      class="craft-unavailable"
      data-test="craft-unavailable"
      role="alert"
    >
      <Circle :size="22" aria-hidden="true" />
      <div>
        <h2>暂不可学习</h2>
        <p>{{ unavailableReason }}</p>
      </div>
    </section>

    <template v-else>
      <section class="progress-panel" aria-labelledby="craft-progress-title">
        <div class="progress-panel__head">
          <div>
            <span class="ark-data">LEARNING PROGRESS</span>
            <h2 id="craft-progress-title">学习进度</h2>
          </div>
          <strong class="ark-data" data-test="completed-count">
            已完成 {{ completedCount }} / 6
          </strong>
        </div>
        <progress :value="completedPercent" max="100">
          {{ completedPercent }}%
        </progress>
        <button
          class="resume-action"
          type="button"
          data-test="resume-point"
          @click="resumeLearning"
        >
          <BookOpen :size="17" aria-hidden="true" />
          {{ resumeText }}
        </button>
      </section>

      <section aria-labelledby="craft-steps-title">
        <div class="section-heading">
          <div>
            <span class="ark-data">ORDERED STEPS / 01-06</span>
            <h2 id="craft-steps-title">六步学习</h2>
          </div>
          <span>按顺序完成</span>
        </div>

        <div
          v-if="stepError"
          class="inline-error"
          role="alert"
          data-test="step-error"
        >
          {{ stepError }}
        </div>

        <ol class="step-list">
          <li
            v-for="step in orderedSteps"
            :id="`handcraft-step-${step.step_no}`"
            :key="step.step_key"
            class="step-item"
            :class="{ 'is-complete': stepIsCompleted(step.step_no) }"
            data-test="craft-step"
          >
            <span class="step-item__number ark-data">
              {{ String(step.step_no).padStart(2, '0') }}
            </span>
            <div class="step-item__body">
              <header>
                <h3>{{ step.title }}</h3>
                <span
                  class="step-item__state"
                  :class="{ 'is-complete': stepIsCompleted(step.step_no) }"
                >
                  <CheckCircle2
                    v-if="stepIsCompleted(step.step_no)"
                    :size="16"
                    aria-hidden="true"
                  />
                  <Circle v-else :size="16" aria-hidden="true" />
                  {{ stepIsCompleted(step.step_no) ? '已完成' : '待学习' }}
                </span>
              </header>
              <p class="step-item__description">{{ step.description }}</p>
              <div v-if="step.tips.length" class="step-item__tips">
                <strong>实用技巧</strong>
                <ul>
                  <li v-for="tip in step.tips" :key="tip">{{ tip }}</li>
                </ul>
              </div>
              <p
                v-if="stepCompletionErrors[step.step_no]"
                class="step-completion-error"
                role="alert"
                :data-test="`step-completion-error-${step.step_no}`"
              >
                {{ stepCompletionErrors[step.step_no] }}
              </p>
              <button
                v-if="!stepIsCompleted(step.step_no)"
                type="button"
                class="step-complete"
                :disabled="stepIsDisabled(step.step_no)"
                :data-test="`complete-step-${step.step_no}`"
                @click="completeStep(step.step_no)"
              >
                <CheckCircle2 :size="17" aria-hidden="true" />
                {{ store.completingStep ? '保存中' : '完成此步骤' }}
              </button>
            </div>
          </li>
        </ol>
      </section>

      <section class="content-section" aria-labelledby="material-guide-title">
        <div class="section-heading">
          <div>
            <span class="ark-data">MATERIAL GUIDE</span>
            <h2 id="material-guide-title">材料指南</h2>
          </div>
          <span>{{ materialGuide.length }} 项</span>
        </div>

        <p v-if="materialGuide.length === 0" class="section-empty">
          暂无材料采购信息
        </p>
        <div v-else class="material-list">
          <article
            v-for="(material, index) in materialGuide"
            :key="`${material.name}-${index}`"
            class="material-item"
            data-test="material-item"
          >
            <h3>{{ material.name || '未命名材料' }}</h3>
            <dl>
              <div>
                <dt>参考价格</dt>
                <dd>{{ material.reference_price || '未提供' }}</dd>
              </div>
              <div>
                <dt>购买渠道</dt>
                <dd>{{ material.purchase_channel || '未提供' }}</dd>
              </div>
              <div>
                <dt>注意事项</dt>
                <dd>{{ material.precautions || '未提供' }}</dd>
              </div>
              <div>
                <dt>淘宝搜索关键词</dt>
                <dd>{{ material.taobao_keyword || '未提供' }}</dd>
              </div>
            </dl>
          </article>
        </div>
      </section>

      <section class="content-section" aria-labelledby="teaching-video-title">
        <div class="section-heading">
          <div>
            <span class="ark-data">APPROVED VIDEO</span>
            <h2 id="teaching-video-title">教学视频</h2>
          </div>
          <span>{{ approvedVideos.length }} 个</span>
        </div>

        <p
          v-if="approvedVideos.length === 0"
          class="section-empty"
          data-test="video-empty"
        >
          暂无已审核且可播放的教学视频
        </p>
        <div v-else class="video-list">
          <article
            v-for="item in approvedVideos"
            :key="item.video_id"
            class="video-item"
            data-test="craft-video"
            data-comment-capability="unavailable"
          >
            <header>
              <Video :size="18" aria-hidden="true" />
              <div>
                <h3>{{ item.title || '教学视频' }}</h3>
                <span>已审核 · 可播放</span>
              </div>
            </header>
            <video
              data-test="craft-video-player"
              controls
              playsinline
              preload="metadata"
              :aria-label="item.title || '教学视频'"
            >
              <source :src="item.playback_url || ''" type="video/mp4">
              当前浏览器不支持视频播放。
            </video>
            <ContentCommentThread
              :endpoint="`/api/handcraft-inheritance/videos/${encodeURIComponent(item.video_id)}/comments`"
              :title="`${item.title || '教学视频'}评论`"
            />
          </article>
        </div>
      </section>

      <section class="content-section ar-section" aria-labelledby="ar-title">
        <div class="section-heading">
          <div>
            <span class="ark-data">AI GUIDANCE</span>
            <h2 id="ar-title">AR 分步操作指引</h2>
          </div>
          <Sparkles :size="21" aria-hidden="true" />
        </div>

        <div
          class="ar-workspace"
          @pointerdown.stop="arHeartbeat.touch"
          @keydown.stop="arHeartbeat.touch"
          @scroll.passive.stop="arHeartbeat.touch"
        >
          <form
            class="ar-form"
            data-test="ar-form"
            @submit.prevent="requestArGuidance"
          >
            <label>
              <span>当前制作项目</span>
              <input
                v-model="projectLabel"
                data-test="ar-project-label"
                type="text"
                required
                autocomplete="off"
                placeholder="例如：绣制花瓣"
                :aria-invalid="Boolean(arError)"
                :aria-describedby="arError ? 'ar-error-message' : undefined"
              >
            </label>
            <button
              type="submit"
              :disabled="store.generatingGuidance"
              :aria-busy="store.generatingGuidance"
            >
              <Sparkles :size="17" aria-hidden="true" />
              {{
                store.generatingGuidance
                  ? '生成中'
                  : arError
                    ? '重新请求'
                    : '请求分步指引'
              }}
            </button>
            <div
              v-if="store.generatingGuidance"
              class="ar-status"
              data-test="ar-loading"
              role="status"
            >
              <RefreshCw class="spinning" :size="16" aria-hidden="true" />
              正在生成分步指引
            </div>
            <div
              v-if="arError"
              class="inline-error ar-error"
              role="alert"
            >
              <span id="ar-error-message" data-test="ar-error">
                {{ arError }}
              </span>
              <button
                type="button"
                class="ar-retry"
                data-test="ar-retry"
                :disabled="store.generatingGuidance"
                @click="requestArGuidance"
              >
                <RefreshCw :size="15" aria-hidden="true" />
                重试
              </button>
            </div>
          </form>

          <div
            v-if="store.arGuidance"
            class="ar-output"
            data-test="ar-output"
          >
            <section>
              <h3>工具准备</h3>
              <ul>
                <li v-for="item in store.arGuidance.tool_preparation" :key="item">
                  {{ item }}
                </li>
              </ul>
            </section>
            <section>
              <h3>操作要点</h3>
              <ul>
                <li v-for="item in store.arGuidance.operating_points" :key="item">
                  {{ item }}
                </li>
              </ul>
            </section>
            <section>
              <h3>常见错误</h3>
              <ul>
                <li v-for="item in store.arGuidance.common_errors" :key="item">
                  {{ item }}
                </li>
              </ul>
            </section>
            <section>
              <h3>分步指引</h3>
              <ol>
                <li v-for="item in store.arGuidance.steps" :key="item.step_no">
                  <strong>{{ item.step_no }}. {{ item.title }}</strong>
                  <p>{{ item.instruction }}</p>
                </li>
              </ol>
            </section>
          </div>
          <p v-else class="section-empty">
            填写制作项目后请求分步操作指引
          </p>
        </div>
      </section>

      <RouterLink
        class="course-entry"
        to="/student/handcraft-inheritance/courses"
        data-test="handcraft-course-link"
      >
        <BookOpen :size="21" aria-hidden="true" />
        <span>
          <span class="ark-data">HANDCRAFT COURSES</span>
          <strong>进入手工课程</strong>
          <small>查看推荐、继续学习进度并完成课后测验</small>
        </span>
      </RouterLink>
    </template>
  </main>
</template>

<style scoped>
.craft-learning {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
  overflow-x: clip;
}

.craft-learning__heading {
  padding-bottom: 24px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.craft-learning__code {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.craft-learning__heading h1 {
  margin: 9px 0 0;
  font-size: 3rem;
  line-height: 1.05;
  text-wrap: balance;
}

.craft-learning__heading p {
  max-width: 68ch;
  margin: 14px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.craft-learning__status,
.craft-learning__error,
.craft-unavailable {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 180px;
  margin-top: 20px;
  padding: 20px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
}

.craft-learning__error,
.craft-unavailable {
  justify-content: space-between;
  color: var(--ark-paper);
}

.craft-learning__error span,
.craft-unavailable p {
  min-width: 0;
  overflow-wrap: anywhere;
}

.craft-learning__error button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  min-height: 38px;
  padding: 0 11px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

.craft-unavailable {
  justify-content: flex-start;
  background: var(--ark-surface-1);
}

.craft-unavailable > svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.craft-unavailable h2 {
  margin: 0;
  font-size: 1.1rem;
}

.craft-unavailable p {
  margin: 5px 0 0;
}

.progress-panel {
  margin-top: 20px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.progress-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 16px 18px 12px;
}

.progress-panel__head > div {
  min-width: 0;
}

.progress-panel__head span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.progress-panel__head h2 {
  margin: 3px 0 0;
  font-size: 1rem;
}

.progress-panel__head strong {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.progress-panel progress {
  display: block;
  width: calc(100% - 36px);
  height: 10px;
  margin: 0 18px 14px;
  overflow: hidden;
  appearance: none;
  border: 1px solid var(--ark-line-strong);
  border-radius: 0;
  background: var(--ark-surface-2);
  color: var(--ark-signal);
}

.progress-panel progress::-webkit-progress-bar {
  background: var(--ark-surface-2);
}

.progress-panel progress::-webkit-progress-value {
  background: var(--ark-signal);
}

.progress-panel progress::-moz-progress-bar {
  background: var(--ark-signal);
}

.resume-action {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 44px;
  padding: 0 18px;
  border: 0;
  border-top: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  text-align: left;
}

.resume-action svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.section-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin: 30px 0 12px;
}

.section-heading > div {
  min-width: 0;
}

.section-heading > div > span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.section-heading h2 {
  margin: 3px 0 0;
  font-size: 1.1rem;
}

.section-heading > span,
.section-heading > svg {
  flex: 0 0 auto;
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.section-heading > svg {
  color: var(--ark-signal);
}

.inline-error {
  margin: 0 0 12px;
  padding: 10px 12px;
  border: 1px solid var(--ark-line-strong);
  border-top-color: var(--ark-signal);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  font-size: 0.82rem;
  overflow-wrap: anywhere;
}

.step-list {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  border-top: 1px solid var(--ark-line-strong);
  list-style: none;
}

.step-item {
  display: grid;
  grid-template-columns: 54px minmax(0, 1fr);
  min-width: 0;
  border-right: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  border-left: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.step-item.is-complete {
  background: var(--ark-surface-1);
}

.step-item__number {
  display: grid;
  place-items: start center;
  padding-top: 22px;
  border-right: 1px solid var(--ark-line);
  color: var(--ark-signal);
  font-size: 0.78rem;
}

.step-item__body {
  min-width: 0;
  padding: 20px;
}

.step-item__body header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.step-item h3 {
  min-width: 0;
  margin: 0;
  font-size: 1.05rem;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.step-item__state {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 5px;
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.step-item__state.is-complete {
  color: var(--ark-state);
}

.step-item__description,
.step-item__tips li,
.ar-output li,
.ar-output p {
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
}

.step-item__description {
  margin: 10px 0 0;
  color: var(--ark-muted);
}

.step-item__tips {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--ark-line);
}

.step-item__tips strong {
  color: var(--ark-signal);
  font-size: 0.78rem;
}

.step-item__tips ul,
.ar-output ul,
.ar-output ol {
  display: grid;
  gap: 6px;
  margin: 8px 0 0;
  padding-left: 20px;
}

.step-item__tips li,
.ar-output li {
  padding-left: 2px;
}

.step-complete {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 40px;
  margin-top: 16px;
  padding: 0 13px;
  border: 1px solid var(--ark-signal);
  background: transparent;
  color: var(--ark-signal);
}

.step-completion-error {
  margin: 14px 0 0;
  padding: 9px 11px;
  border: 1px solid var(--ark-line-strong);
  border-top-color: var(--ark-signal);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
}

.step-complete:hover:not(:disabled) {
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}

.step-complete:disabled {
  border-color: var(--ark-line-strong);
  background: var(--ark-surface-2);
  color: var(--ark-muted);
  opacity: 1;
}

.content-section {
  margin-top: 30px;
}

.material-list,
.video-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
  gap: 10px;
}

.material-item,
.video-item {
  min-width: 0;
  padding: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.material-item h3,
.video-item h3 {
  margin: 0;
  font-size: 1rem;
  overflow-wrap: anywhere;
}

.material-item dl {
  display: grid;
  gap: 10px;
  margin: 14px 0 0;
}

.material-item dl > div {
  min-width: 0;
  padding-top: 10px;
  border-top: 1px solid var(--ark-line);
}

.material-item dt {
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.material-item dd {
  margin: 3px 0 0;
  overflow-wrap: anywhere;
}

.video-item header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.video-item header > svg {
  flex: 0 0 auto;
  margin-top: 2px;
  color: var(--ark-signal);
}

.video-item header > div {
  min-width: 0;
}

.video-item header span {
  display: block;
  margin-top: 3px;
  color: var(--ark-state);
  font-size: 0.74rem;
}

.video-item video {
  display: block;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  min-height: 0;
  aspect-ratio: 16 / 9;
  margin-top: 14px;
  background: var(--ark-surface-2);
  object-fit: contain;
}

.ar-workspace {
  display: grid;
  grid-template-columns:
    minmax(min(100%, 260px), 0.72fr)
    minmax(0, 1.28fr);
  gap: 10px;
  align-items: start;
}

.ar-form,
.ar-output,
.ar-workspace > .section-empty {
  min-width: 0;
  padding: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.ar-form {
  display: grid;
  gap: 12px;
}

.ar-form label {
  display: grid;
  gap: 6px;
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.ar-form input {
  width: 100%;
  min-height: 42px;
  padding: 9px 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  outline: none;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.ar-form input:focus {
  border-color: var(--ark-focus);
  box-shadow: 0 0 0 2px var(--ark-surface-2);
}

.ar-form button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 42px;
  border: 1px solid var(--ark-signal);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}

.ar-form button:disabled {
  border-color: var(--ark-line-strong);
  background: var(--ark-surface-2);
  color: var(--ark-muted);
  opacity: 1;
}

.ar-form .inline-error {
  margin: 0;
}

.ar-status,
.ar-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.ar-status {
  color: var(--ark-muted);
  font-size: 0.82rem;
}

.ar-status > svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.ar-error > span {
  min-width: 0;
}

.ar-form .ar-retry {
  flex: 0 0 auto;
  min-height: 36px;
  padding-inline: 10px;
  border-color: var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

.ar-output {
  display: grid;
  gap: 18px;
}

.ar-output section {
  min-width: 0;
}

.ar-output h3 {
  margin: 0;
  color: var(--ark-signal);
  font-size: 0.9rem;
}

.ar-output p {
  margin: 5px 0 0;
  color: var(--ark-muted);
}

.section-empty {
  margin: 0;
  color: var(--ark-muted);
}

.course-entry {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  margin-top: 34px;
  padding: 20px 18px;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  color: var(--ark-paper);
  text-decoration: none;
}

.course-entry > svg {
  color: var(--ark-signal);
}

.course-entry > span {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.course-entry > span > span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.course-entry strong,
.course-entry small {
  overflow-wrap: anywhere;
}

.course-entry small {
  color: var(--ark-muted);
}

.course-entry:hover,
.course-entry:focus-visible {
  color: var(--ark-signal);
}

.craft-learning :is(a, button, input):focus-visible {
  outline: 2px solid var(--ark-focus);
  outline-offset: 3px;
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 760px), (orientation: portrait) {
  .craft-learning {
    padding: 28px 14px 56px;
  }

  .craft-learning__heading h1 {
    font-size: 2.35rem;
  }

  .progress-panel__head,
  .section-heading,
  .step-item__body header {
    align-items: flex-start;
    flex-direction: column;
  }

  .progress-panel__head strong {
    flex: initial;
  }

  .step-item {
    grid-template-columns: minmax(0, 1fr);
  }

  .step-item__number {
    place-items: start;
    padding: 14px 14px 0;
    border-right: 0;
  }

  .step-item__body {
    padding: 16px 14px;
  }

  .material-list,
  .video-list,
  .ar-workspace {
    grid-template-columns: minmax(0, 1fr);
  }

  .craft-learning__error {
    align-items: flex-start;
    flex-direction: column;
  }

  .ar-error {
    align-items: stretch;
    flex-direction: column;
  }

  .ar-form .ar-retry {
    width: 100%;
  }
}

@media (max-width: 420px) {
  .craft-learning {
    padding: 24px 12px 48px;
  }

  .craft-learning__heading h1 {
    font-size: 2rem;
  }

  .progress-panel__head,
  .section-heading {
    gap: 9px;
    padding-inline: 12px;
  }

  .step-item__body,
  .material-item,
  .video-item,
  .ar-form,
  .ar-output,
  .ar-workspace > .section-empty {
    padding-inline: 12px;
  }

  .resume-action,
  .step-complete,
  .ar-form button,
  .craft-learning__error button {
    width: 100%;
    justify-content: center;
  }

  .course-entry {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
