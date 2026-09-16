<script setup lang="ts">
import {
  Activity,
  CheckCircle2,
  ClipboardCheck,
  History,
  MessageSquareText,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldCheck,
  Stethoscope,
  XCircle
} from 'lucide-vue-next'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type { DiagnosisSession } from '@/api/types'
import AgriSkillsNav from '@/components/AgriSkillsNav.vue'
import AppHeader from '@/components/AppHeader.vue'
import VoiceInputButton from '@/components/VoiceInputButton.vue'
import { useAgriCalendarStore } from '@/stores/agriCalendar'
import {
  useAgriDiagnosisStore,
  type DiagnosisCreatePayload
} from '@/stores/agriDiagnosis'
import { useAuthStore } from '@/stores/auth'

type SessionView = DiagnosisSession & {
  pending_question?: string | null
  pending_question_round?: number | null
}

const diagnosisStore = useAgriDiagnosisStore()
const calendarStore = useAgriCalendarStore()
const auth = useAuthStore()
const router = useRouter()

const affectedParts = [
  { value: 'leaf', label: '叶片' },
  { value: 'fruit', label: '果实' },
  { value: 'stem', label: '枝干' },
  { value: 'root', label: '根部' }
] as const

const symptoms = ['斑点', '虫蛀', '落果', '霉层'] as const

const diagnosisForm = reactive<DiagnosisCreatePayload>({
  product_key: '',
  affected_part: '',
  symptoms: []
})

const answerDraft = ref('')
const answerInputMode = ref<'text' | 'voice'>('text')
const recording = ref(false)
const transcribing = ref(false)
const followupOutcome = ref<'improved' | 'unchanged' | 'worsened'>('improved')
const followupNote = ref('')
const selfTestAnswers = reactive<Record<string, string>>({})

const activeSessionView = computed(
  () => diagnosisStore.activeSession as SessionView | null
)

const pendingQuestion = computed(
  () => activeSessionView.value?.pending_question?.trim() ?? ''
)

const orderedSessions = computed(() =>
  [...diagnosisStore.sessions].sort((left, right) => {
    const difference = Date.parse(right.updated_at) - Date.parse(left.updated_at)
    return Number.isNaN(difference)
      ? right.id - left.id
      : difference || right.id - left.id
  })
)

const orderedFollowups = computed(() =>
  [...(diagnosisStore.activeSession?.followups ?? [])].sort(
    (left, right) =>
      Date.parse(left.created_at) - Date.parse(right.created_at) ||
      left.id - right.id
  )
)

const orderedAnswers = computed(() =>
  [...(diagnosisStore.activeSession?.answers ?? [])].sort(
    (left, right) =>
      left.round_no - right.round_no ||
      left.question.localeCompare(right.question)
  )
)

const canStartDiagnosis = computed(
  () =>
    Boolean(diagnosisForm.product_key) &&
    Boolean(diagnosisForm.affected_part) &&
    diagnosisForm.symptoms.length > 0 &&
    !diagnosisStore.saving
)

const voiceError = computed(() =>
  diagnosisStore.error === '未能识别，请重试或改用文字输入'
    ? diagnosisStore.error
    : ''
)

const selfTestComplete = computed(
  () =>
    Boolean(diagnosisStore.selfTest?.questions.length) &&
    diagnosisStore.selfTest!.questions.every(question =>
      Boolean(selfTestAnswers[question.id])
    )
)

function partLabel(value: string): string {
  return affectedParts.find(part => part.value === value)?.label ?? value
}

function outcomeLabel(value: 'improved' | 'unchanged' | 'worsened'): string {
  return {
    improved: '好转',
    unchanged: '无变化',
    worsened: '恶化'
  }[value]
}

function formatTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}

function resetAnswerDraft() {
  answerDraft.value = ''
  answerInputMode.value = 'text'
  recording.value = false
}

function selectSession(session: DiagnosisSession) {
  diagnosisStore.activeSession = session
  diagnosisStore.error = ''
  diagnosisStore.selfTest = null
  diagnosisStore.selfTestResult = null
  Object.keys(selfTestAnswers).forEach(key => {
    delete selfTestAnswers[key]
  })
  resetAnswerDraft()
}

function createMultipartBoundary(): string {
  const randomPart =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `----agri-diagnosis-${randomPart}`
}

async function transcribe(blob: Blob, filename: string): Promise<string> {
  transcribing.value = true
  diagnosisStore.error = ''

  try {
    const boundary = createMultipartBoundary()
    const safeFilename =
      filename.replace(/[\r\n"]/g, '').trim() || 'answer.webm'
    const contentType = blob.type || 'application/octet-stream'
    const body = new Blob([
      `--${boundary}\r\n`,
      `Content-Disposition: form-data; name="audio"; filename="${safeFilename}"\r\n`,
      `Content-Type: ${contentType}\r\n\r\n`,
      blob,
      `\r\n--${boundary}--\r\n`
    ])
    const response = await apiFetch<{
      success: true
      text: string
    }>('/api/agri-skills/speech/transcriptions', {
      method: 'POST',
      headers: {
        'Content-Type': `multipart/form-data; boundary=${boundary}`
      },
      body
    })
    const text = response.text.trim()
    if (!text) {
      diagnosisStore.error = '未能识别，请重试或改用文字输入'
      return ''
    }
    return text
  } catch {
    diagnosisStore.error = '未能识别，请重试或改用文字输入'
    return ''
  } finally {
    transcribing.value = false
  }
}

function handleTextInput() {
  answerInputMode.value = 'text'
  diagnosisStore.error = ''
}

function handleRecordingChange(value: boolean) {
  recording.value = value
}

async function handleRecorded(blob: Blob, filename: string) {
  answerInputMode.value = 'voice'
  const text = await transcribe(blob, filename)
  if (text) {
    answerDraft.value = text
  }
}

function handlePermissionDenied() {
  recording.value = false
  diagnosisStore.error = '未能识别，请重试或改用文字输入'
}

async function startDiagnosis() {
  if (!canStartDiagnosis.value) {
    return
  }
  const succeeded = await diagnosisStore.createDiagnosis({
    product_key: diagnosisForm.product_key,
    affected_part: diagnosisForm.affected_part,
    symptoms: [...diagnosisForm.symptoms]
  })
  if (succeeded) {
    diagnosisForm.affected_part = ''
    diagnosisForm.symptoms = []
    resetAnswerDraft()
  }
}

async function resumeDiagnosis() {
  const succeeded = await diagnosisStore.startDiagnosis()
  if (succeeded && pendingQuestion.value) {
    resetAnswerDraft()
  }
}

async function submitAnswer() {
  const answer = answerDraft.value.trim()
  if (!answer || !pendingQuestion.value || diagnosisStore.saving) {
    return
  }
  const succeeded = await diagnosisStore.answerDiagnosis(
    answer,
    answerInputMode.value
  )
  if (succeeded) {
    resetAnswerDraft()
  }
}

async function submitFollowup() {
  const succeeded = await diagnosisStore.addFollowup(
    followupOutcome.value,
    followupNote.value
  )
  if (succeeded) {
    followupOutcome.value = 'improved'
    followupNote.value = ''
  }
}

async function repeatDiagnosis(followupId: number) {
  const succeeded = await diagnosisStore.repeatDiagnosis(followupId)
  if (succeeded) {
    resetAnswerDraft()
  }
}

async function submitSelfTest() {
  if (!selfTestComplete.value || diagnosisStore.saving) {
    return
  }
  await diagnosisStore.submitSelfTest({ ...selfTestAnswers })
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(async () => {
  await Promise.all([
    diagnosisStore.loadSessions(),
    calendarStore.loadProducts()
  ])
  if (!diagnosisForm.product_key && calendarStore.products.length > 0) {
    diagnosisForm.product_key = calendarStore.products[0].key
  }
})
</script>

<template>
  <div class="diagnosis-page">
    <AppHeader
      source="live"
      :loading="diagnosisStore.loading || diagnosisStore.saving || transcribing"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <AgriSkillsNav />

    <main class="diagnosis-main">
      <header class="diagnosis-heading">
        <span class="diagnosis-heading__code ark-data">
          03 / PEST DIAGNOSIS
        </span>
        <h1>病虫害诊断</h1>
        <p>按农产品、发病部位和症状点选，逐轮补充信息并形成诊断结论。</p>
      </header>

      <div
        v-if="diagnosisStore.error && !voiceError"
        class="diagnosis-error"
        role="alert"
      >
        {{ diagnosisStore.error }}
      </div>

      <div class="diagnosis-workspace">
        <aside class="diagnosis-history" aria-labelledby="diagnosis-history-title">
          <div class="diagnosis-history__head">
            <div>
              <span class="ark-data">SESSION ARCHIVE</span>
              <h2 id="diagnosis-history-title">诊断记录</h2>
            </div>
            <button
              type="button"
              :disabled="diagnosisStore.loading"
              aria-label="刷新诊断记录"
              @click="diagnosisStore.loadSessions"
            >
              <RefreshCw
                :size="16"
                :class="{ spinning: diagnosisStore.loading }"
                aria-hidden="true"
              />
            </button>
          </div>

          <div v-if="orderedSessions.length" class="diagnosis-history__list">
            <button
              v-for="session in orderedSessions"
              :key="session.id"
              type="button"
              :class="{
                'is-active': session.id === diagnosisStore.activeSession?.id
              }"
              @click="selectSession(session)"
            >
              <strong>{{ session.product.name }}</strong>
              <span>{{ partLabel(session.affected_part) }}</span>
              <small class="ark-data">
                {{ formatTime(session.updated_at) }}
              </small>
            </button>
          </div>
          <p v-else class="diagnosis-history__empty">暂无诊断记录</p>
        </aside>

        <section class="diagnosis-stage" aria-live="polite">
          <form
            v-if="diagnosisStore.activeSession?.status !== 'in_progress'"
            class="diagnosis-start"
            data-test="diagnosis-start-form"
            @submit.prevent="startDiagnosis"
          >
            <header class="diagnosis-section-head">
              <div>
                <span class="ark-data">NEW DIAGNOSIS</span>
                <h2>新建诊断</h2>
              </div>
              <Stethoscope :size="22" aria-hidden="true" />
            </header>

            <div class="diagnosis-start__grid">
              <label>
                <span>农产品</span>
                <select
                  v-model="diagnosisForm.product_key"
                  data-test="diagnosis-product"
                  :disabled="calendarStore.loading"
                >
                  <option value="" disabled>请选择农产品</option>
                  <option
                    v-for="product in calendarStore.products"
                    :key="product.key"
                    :value="product.key"
                  >
                    {{ product.name }}
                  </option>
                </select>
              </label>

              <label>
                <span>发病部位</span>
                <select
                  v-model="diagnosisForm.affected_part"
                  data-test="diagnosis-part"
                >
                  <option value="" disabled>请选择发病部位</option>
                  <option
                    v-for="part in affectedParts"
                    :key="part.value"
                    :value="part.value"
                  >
                    {{ part.label }}
                  </option>
                </select>
              </label>
            </div>

            <fieldset class="symptom-fieldset">
              <legend>症状表现（可多选）</legend>
              <div class="symptom-options">
                <label
                  v-for="(symptom, index) in symptoms"
                  :key="symptom"
                >
                  <input
                    v-model="diagnosisForm.symptoms"
                    type="checkbox"
                    :value="symptom"
                    :data-test="`diagnosis-symptom-${index}`"
                  >
                  <span>{{ symptom }}</span>
                </label>
              </div>
            </fieldset>

            <button
              class="diagnosis-primary"
              type="submit"
              :disabled="!canStartDiagnosis"
            >
              <Stethoscope :size="17" aria-hidden="true" />
              开始诊断
            </button>
          </form>

          <template v-if="diagnosisStore.activeSession">
            <section class="diagnosis-selection">
              <div>
                <span class="ark-data">DIAGNOSIS #{{ diagnosisStore.activeSession.id }}</span>
                <h2>{{ diagnosisStore.activeSession.product.name }}</h2>
              </div>
              <div class="diagnosis-selection__facts">
                <span>{{ partLabel(diagnosisStore.activeSession.affected_part) }}</span>
                <span
                  v-for="symptom in diagnosisStore.activeSession.symptoms"
                  :key="symptom"
                >
                  {{ symptom }}
                </span>
              </div>
            </section>

            <template v-if="diagnosisStore.activeSession.status === 'in_progress'">
              <section class="in-progress-panel">
                <header class="diagnosis-section-head">
                  <div>
                    <span class="ark-data">
                      ROUND {{ diagnosisStore.activeSession.round_count }} / 5
                    </span>
                    <h2>诊断进行中</h2>
                  </div>
                  <Activity :size="22" aria-hidden="true" />
                </header>

                <div class="in-progress-panel__actions">
                  <button
                    type="button"
                    data-test="resume-diagnosis"
                    :disabled="diagnosisStore.saving"
                    @click="resumeDiagnosis"
                  >
                    <RotateCcw :size="16" aria-hidden="true" />
                    继续诊断
                  </button>
                  <button
                    type="button"
                    data-test="abandon-diagnosis"
                    :disabled="diagnosisStore.saving"
                    @click="diagnosisStore.abandonDiagnosis"
                  >
                    <XCircle :size="16" aria-hidden="true" />
                    放弃并重开
                  </button>
                </div>

                <div
                  v-if="pendingQuestion"
                  class="pending-question"
                  data-test="pending-question"
                >
                  <span>当前追问</span>
                  <p>{{ pendingQuestion }}</p>
                </div>
                <div v-else class="diagnosis-empty">
                  <RefreshCw :size="20" aria-hidden="true" />
                  <p>首次追问暂未生成。继续诊断不会丢失已选信息。</p>
                </div>

                <form
                  v-if="pendingQuestion"
                  class="answer-composer"
                  data-test="diagnosis-answer-form"
                  @submit.prevent="submitAnswer"
                >
                  <label for="diagnosis-answer">补充回答</label>
                  <div class="answer-composer__row">
                    <textarea
                      id="diagnosis-answer"
                      v-model="answerDraft"
                      data-test="diagnosis-answer"
                      rows="4"
                      placeholder="请描述症状变化、出现时间或使用过的处理方式"
                      :disabled="diagnosisStore.saving || transcribing"
                      @input="handleTextInput"
                    />
                    <div class="answer-composer__actions">
                      <VoiceInputButton
                        :recording="recording"
                        :disabled="diagnosisStore.saving || transcribing"
                        :error="voiceError"
                        @update:recording="handleRecordingChange"
                        @recorded="handleRecorded"
                        @permission-denied="handlePermissionDenied"
                      />
                      <button
                        class="diagnosis-primary"
                        type="submit"
                        :disabled="
                          !answerDraft.trim() ||
                          diagnosisStore.saving ||
                          transcribing
                        "
                      >
                        <Send :size="16" aria-hidden="true" />
                        提交回答
                      </button>
                    </div>
                  </div>
                </form>
              </section>
            </template>

            <template v-else-if="diagnosisStore.activeSession.status === 'completed'">
              <section class="conclusion-panel">
                <header class="diagnosis-section-head">
                  <div>
                    <span class="ark-data">CONCLUSION / COMPLETED</span>
                    <h2>诊断结论</h2>
                  </div>
                  <CheckCircle2 :size="22" aria-hidden="true" />
                </header>

                <span
                  v-if="diagnosisStore.activeSession.limited"
                  class="limited-marker"
                  data-test="limited-marker"
                >
                  信息有限
                </span>

                <div class="conclusion-grid">
                  <article>
                    <h3>病因分析</h3>
                    <p data-test="diagnosis-cause">
                      {{ diagnosisStore.activeSession.conclusion?.cause }}
                    </p>
                  </article>
                  <article>
                    <h3>防治方案</h3>
                    <p data-test="diagnosis-treatment">
                      {{ diagnosisStore.activeSession.conclusion?.treatment }}
                    </p>
                  </article>
                </div>
              </section>

              <section class="followup-panel">
                <header class="diagnosis-section-head">
                  <div>
                    <span class="ark-data">FOLLOW-UP RECORDS</span>
                    <h2>复诊记录</h2>
                  </div>
                  <History :size="22" aria-hidden="true" />
                </header>

                <div v-if="orderedFollowups.length" class="followup-list">
                  <article
                    v-for="(followup, index) in orderedFollowups"
                    :key="followup.id"
                    :data-test="`followup-${index}`"
                  >
                    <div>
                      <strong>{{ outcomeLabel(followup.outcome) }}</strong>
                      <time class="ark-data">{{ formatTime(followup.created_at) }}</time>
                    </div>
                    <p>{{ followup.note || '未填写备注' }}</p>
                    <button
                      type="button"
                      :disabled="diagnosisStore.saving"
                      @click="repeatDiagnosis(followup.id)"
                    >
                      <RotateCcw :size="15" aria-hidden="true" />
                      基于此记录再次诊断
                    </button>
                  </article>
                </div>
                <p v-else class="diagnosis-empty">暂无复诊记录</p>

                <form class="followup-form" @submit.prevent="submitFollowup">
                  <label>
                    <span>防治效果</span>
                    <select v-model="followupOutcome">
                      <option value="improved">好转</option>
                      <option value="unchanged">无变化</option>
                      <option value="worsened">恶化</option>
                    </select>
                  </label>
                  <label>
                    <span>备注（可选）</span>
                    <textarea
                      v-model="followupNote"
                      rows="2"
                      placeholder="记录叶片、果实或植株状态变化"
                    />
                  </label>
                  <button
                    class="diagnosis-primary"
                    type="submit"
                    :disabled="diagnosisStore.saving"
                  >
                    <MessageSquareText :size="16" aria-hidden="true" />
                    记录本次复诊
                  </button>
                </form>
              </section>

              <section class="self-test-panel" data-test="self-test">
                <header class="diagnosis-section-head">
                  <div>
                    <span class="ark-data">AI SELF-TEST</span>
                    <h2>诊断自测</h2>
                  </div>
                  <ClipboardCheck :size="22" aria-hidden="true" />
                </header>

                <button
                  v-if="!diagnosisStore.selfTest"
                  class="diagnosis-primary"
                  type="button"
                  :disabled="diagnosisStore.saving"
                  @click="diagnosisStore.generateSelfTest"
                >
                  <ShieldCheck :size="17" aria-hidden="true" />
                  生成自测
                </button>

                <form
                  v-else-if="!diagnosisStore.selfTestResult"
                  class="self-test-form"
                  @submit.prevent="submitSelfTest"
                >
                  <fieldset
                    v-for="(question, questionIndex) in diagnosisStore.selfTest.questions"
                    :key="question.id"
                  >
                    <legend>
                      {{ questionIndex + 1 }}. {{ question.prompt }}
                    </legend>
                    <label
                      v-for="(option, optionIndex) in question.options"
                      :key="option"
                    >
                      <input
                        v-model="selfTestAnswers[question.id]"
                        type="radio"
                        :name="`self-test-${question.id}`"
                        :value="option"
                        :data-test="`self-test-${questionIndex}-${optionIndex}`"
                      >
                      <span>{{ option }}</span>
                    </label>
                  </fieldset>
                  <button
                    class="diagnosis-primary"
                    type="submit"
                    :disabled="!selfTestComplete || diagnosisStore.saving"
                  >
                    <CheckCircle2 :size="17" aria-hidden="true" />
                    提交自测
                  </button>
                </form>

                <div v-else class="self-test-result">
                  <div class="self-test-result__score">
                    <span>本次得分</span>
                    <strong class="ark-data" data-test="self-test-score">
                      {{ diagnosisStore.selfTestResult.score }} 分
                    </strong>
                  </div>
                  <article
                    v-for="(question, index) in diagnosisStore.selfTestResult.questions"
                    :key="question.id"
                  >
                    <span
                      :class="{
                        'is-correct': question.correct,
                        'is-wrong': !question.correct
                      }"
                    >
                      {{ question.correct ? '正确' : '错误' }}
                    </span>
                    <h3>{{ index + 1 }}. {{ question.prompt }}</h3>
                    <p :data-test="`self-test-explanation-${index}`">
                      {{ question.explanation }}
                    </p>
                  </article>
                </div>
              </section>
            </template>

            <section v-else class="abandoned-panel">
              <XCircle :size="22" aria-hidden="true" />
              <h2>诊断已放弃</h2>
              <p>历史点选信息仍可查看，重新诊断将创建独立会话。</p>
            </section>

            <section
              v-if="orderedAnswers.length"
              class="answer-history"
              aria-labelledby="answer-history-title"
            >
              <header class="diagnosis-section-head">
                <div>
                  <span class="ark-data">ANSWER TRACE</span>
                  <h2 id="answer-history-title">追问记录</h2>
                </div>
                <History :size="21" aria-hidden="true" />
              </header>
              <ol>
                <li v-for="answer in orderedAnswers" :key="answer.round_no">
                  <span class="ark-data">ROUND {{ answer.round_no }}</span>
                  <p class="answer-history__question">{{ answer.question }}</p>
                  <p>{{ answer.answer }}</p>
                  <small>{{ answer.input_mode === 'voice' ? '语音转文字' : '文字输入' }}</small>
                </li>
              </ol>
            </section>
          </template>

          <div v-else class="diagnosis-stage__empty">
            <Stethoscope :size="26" aria-hidden="true" />
            <p>完成点选后，系统将在这里生成第一轮追问。</p>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.diagnosis-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
}

.diagnosis-main {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.diagnosis-heading {
  padding-bottom: 24px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.diagnosis-heading__code {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.diagnosis-heading h1 {
  margin: 9px 0 0;
  font-size: 3rem;
  line-height: 1;
}

.diagnosis-heading p {
  max-width: 62ch;
  margin: 15px 0 0;
  color: var(--ark-muted);
}

.diagnosis-error {
  margin-top: 18px;
  padding: 11px 13px;
  border-left: 3px solid var(--ark-signal);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  overflow-wrap: anywhere;
}

.diagnosis-workspace {
  display: grid;
  grid-template-columns: minmax(210px, 260px) minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  margin-top: 22px;
}

.diagnosis-history,
.diagnosis-stage {
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.diagnosis-history__head,
.diagnosis-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  min-height: 62px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--ark-line);
}

.diagnosis-history__head span,
.diagnosis-section-head span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.diagnosis-history__head h2,
.diagnosis-section-head h2 {
  margin: 3px 0 0;
  font-size: 1rem;
}

.diagnosis-history__head button {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 34px;
  height: 34px;
  padding: 0;
  border: 1px solid var(--ark-line);
  background: transparent;
  color: var(--ark-paper);
}

.diagnosis-history__head button:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.diagnosis-history__list {
  display: grid;
}

.diagnosis-history__list button {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 4px 10px;
  width: 100%;
  min-width: 0;
  padding: 13px 15px;
  border: 0;
  border-bottom: 1px solid var(--ark-line);
  background: transparent;
  color: var(--ark-paper);
  text-align: left;
}

.diagnosis-history__list button:last-child {
  border-bottom: 0;
}

.diagnosis-history__list button:hover,
.diagnosis-history__list button.is-active {
  background: var(--ark-surface-1);
}

.diagnosis-history__list button.is-active {
  box-shadow: inset 3px 0 0 var(--ark-signal);
}

.diagnosis-history__list strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.diagnosis-history__list span,
.diagnosis-history__list small,
.diagnosis-history__empty {
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.diagnosis-history__list small {
  grid-column: 1 / -1;
}

.diagnosis-history__empty {
  margin: 0;
  padding: 22px 15px;
}

.diagnosis-stage {
  display: grid;
}

.diagnosis-stage__empty {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 12px;
  min-height: 360px;
  padding: 28px;
  color: var(--ark-muted);
  text-align: center;
}

.diagnosis-stage__empty p {
  max-width: 34ch;
  margin: 0;
}

.diagnosis-start {
  display: grid;
  gap: 22px;
  padding-bottom: 22px;
}

.diagnosis-start__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 22px 22px 0;
}

.diagnosis-start label,
.followup-form label {
  display: grid;
  min-width: 0;
  gap: 7px;
}

.diagnosis-start label > span,
.followup-form label > span {
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.diagnosis-start select,
.followup-form select,
.followup-form textarea {
  width: 100%;
  min-width: 0;
  min-height: 42px;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: 0;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.followup-form textarea {
  padding-block: 10px;
  line-height: 1.55;
  resize: vertical;
}

.symptom-fieldset,
.self-test-form fieldset {
  min-width: 0;
  margin: 0;
  padding: 0 22px;
  border: 0;
}

.symptom-fieldset legend,
.self-test-form legend {
  margin-bottom: 10px;
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.symptom-options {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.symptom-options label,
.self-test-form label {
  display: flex;
  align-items: center;
  min-height: 42px;
  gap: 9px;
  padding: 8px 10px;
  border: 1px solid var(--ark-line);
  color: var(--ark-paper);
  cursor: pointer;
}

.symptom-options input,
.self-test-form input {
  flex: 0 0 auto;
  accent-color: var(--ark-signal);
}

.diagnosis-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: fit-content;
  min-height: 42px;
  margin-inline: 22px;
  padding: 0 16px;
  border: 1px solid var(--ark-signal);
  border-radius: 0;
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}

.diagnosis-primary:hover:not(:disabled) {
  border-color: var(--ark-paper);
  background: var(--ark-paper);
}

.diagnosis-selection {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 18px;
  padding: 20px 22px;
  border-bottom: 1px solid var(--ark-line);
}

.diagnosis-selection h2 {
  margin: 4px 0 0;
  font-size: 1.5rem;
}

.diagnosis-selection__facts {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 7px;
}

.diagnosis-selection__facts span,
.limited-marker {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-signal);
  font-size: 0.75rem;
}

.in-progress-panel,
.conclusion-panel,
.followup-panel,
.self-test-panel,
.answer-history,
.abandoned-panel {
  min-width: 0;
  border-bottom: 1px solid var(--ark-line);
}

.in-progress-panel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 18px 22px 0;
}

.in-progress-panel__actions button,
.followup-list button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 38px;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: 0;
  background: transparent;
  color: var(--ark-paper);
}

.in-progress-panel__actions button:hover:not(:disabled),
.followup-list button:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.pending-question {
  margin: 18px 22px;
  padding: 16px;
  border-left: 3px solid var(--ark-signal);
  background: var(--ark-surface-1);
}

.pending-question > span {
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.pending-question p {
  margin: 7px 0 0;
  color: var(--ark-paper);
  font-size: 1.1rem;
  font-weight: 700;
  overflow-wrap: anywhere;
}

.diagnosis-empty,
.abandoned-panel {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  min-height: 130px;
  margin: 0;
  padding: 22px;
  color: var(--ark-muted);
  text-align: center;
}

.diagnosis-empty p,
.abandoned-panel p {
  max-width: 44ch;
  margin: 0;
}

.abandoned-panel h2 {
  margin: 0;
  color: var(--ark-paper);
  font-size: 1.1rem;
}

.answer-composer {
  display: grid;
  gap: 8px;
  padding: 0 22px 22px;
}

.answer-composer > label {
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.answer-composer__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
}

.answer-composer textarea {
  width: 100%;
  min-width: 0;
  min-height: 104px;
  padding: 11px 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: 0;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-height: 1.55;
  resize: vertical;
}

.answer-composer textarea::placeholder,
.followup-form textarea::placeholder {
  color: var(--ark-muted);
}

.answer-composer__actions {
  display: grid;
  grid-template-columns: 46px;
  align-content: start;
  gap: 8px;
}

.answer-composer__actions .diagnosis-primary {
  width: 100%;
  margin: 0;
  white-space: nowrap;
}

.conclusion-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.conclusion-grid article {
  min-width: 0;
  padding: 22px;
  border-right: 1px solid var(--ark-line);
}

.conclusion-grid article:last-child {
  border-right: 0;
}

.conclusion-grid h3,
.self-test-result article h3 {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.conclusion-grid p {
  margin: 13px 0 0;
  overflow-wrap: anywhere;
}

.limited-marker {
  margin: 18px 22px 0;
  border-color: var(--ark-signal);
}

.followup-list {
  display: grid;
}

.followup-list article {
  display: grid;
  gap: 12px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--ark-line);
}

.followup-list article > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.followup-list strong {
  color: var(--ark-signal);
}

.followup-list time {
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.followup-list p {
  margin: 0;
  overflow-wrap: anywhere;
}

.followup-list button {
  width: fit-content;
}

.followup-form {
  display: grid;
  gap: 14px;
  padding: 22px;
}

.followup-form .diagnosis-primary {
  width: fit-content;
  margin: 0;
}

.self-test-form {
  display: grid;
  gap: 18px;
  padding-block: 22px;
}

.self-test-form fieldset {
  display: grid;
  gap: 8px;
  padding-inline: 22px;
}

.self-test-form .diagnosis-primary {
  margin-inline: 22px;
}

.self-test-result {
  display: grid;
}

.self-test-result__score {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--ark-line);
}

.self-test-result__score span {
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.self-test-result__score strong {
  color: var(--ark-signal);
  font-size: 2rem;
}

.self-test-result article {
  display: grid;
  gap: 7px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--ark-line);
}

.self-test-result article:last-child {
  border-bottom: 0;
}

.self-test-result article > span {
  width: fit-content;
  padding: 2px 7px;
  border: 1px solid var(--ark-line-strong);
  font-size: 0.7rem;
}

.self-test-result article > span.is-correct {
  border-color: var(--ark-state);
  color: var(--ark-state);
}

.self-test-result article > span.is-wrong {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.self-test-result article p {
  margin: 0;
  color: var(--ark-muted);
  overflow-wrap: anywhere;
}

.answer-history ol {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.answer-history li {
  display: grid;
  gap: 8px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--ark-line);
}

.answer-history li:last-child {
  border-bottom: 0;
}

.answer-history li > span,
.answer-history small {
  color: var(--ark-muted);
  font-size: 0.7rem;
}

.answer-history p {
  margin: 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.answer-history__question {
  color: var(--ark-muted);
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 760px) {
  .diagnosis-main {
    padding: 28px 14px 48px;
  }

  .diagnosis-heading h1 {
    font-size: 2.25rem;
  }

  .diagnosis-workspace {
    grid-template-columns: minmax(0, 1fr);
  }

  .diagnosis-history__list {
    grid-auto-columns: minmax(190px, 72%);
    grid-auto-flow: column;
    overflow-x: auto;
    scrollbar-width: thin;
  }

  .diagnosis-history__list button {
    border-right: 1px solid var(--ark-line);
    border-bottom: 0;
  }

  .diagnosis-start__grid,
  .conclusion-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .symptom-options {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .diagnosis-selection {
    align-items: flex-start;
    flex-direction: column;
    padding-inline: 16px;
  }

  .diagnosis-selection__facts {
    justify-content: flex-start;
  }

  .diagnosis-history__head,
  .diagnosis-section-head,
  .diagnosis-start__grid,
  .symptom-fieldset,
  .answer-composer,
  .followup-form,
  .self-test-form fieldset {
    padding-inline: 16px;
  }

  .diagnosis-primary {
    margin-inline: 16px;
  }

  .self-test-form .diagnosis-primary {
    margin-inline: 16px;
  }

  .in-progress-panel__actions,
  .pending-question {
    margin-inline: 16px;
  }

  .in-progress-panel__actions {
    padding-inline: 0;
  }

  .pending-question {
    margin-inline: 16px;
  }

  .answer-composer__row {
    grid-template-columns: minmax(0, 1fr);
  }

  .answer-composer__actions {
    grid-template-columns: 46px minmax(0, 1fr);
  }

  .conclusion-grid article {
    border-right: 0;
    border-bottom: 1px solid var(--ark-line);
  }

  .conclusion-grid article:last-child {
    border-bottom: 0;
  }

  .limited-marker {
    margin-inline: 16px;
  }

  .followup-list article,
  .self-test-result article,
  .self-test-result__score,
  .answer-history li {
    padding-inline: 16px;
  }
}
</style>
