<script setup lang="ts">
import {
  CircleAlert,
  RefreshCw,
  Save,
  Sparkles,
  Trash2,
  X
} from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import type {
  CourseDirection,
  TeacherQuiz,
  TeacherQuizQuestion
} from '@/api/types'
import { useTeacherConsoleStore } from '@/stores/teacherConsole'

const props = withDefaults(
  defineProps<{
    courseId: number
    summary?: string
    direction?: CourseDirection
    expectedVersion?: number
    initialQuestions?: TeacherQuizQuestion[]
    initialEnabled?: boolean
    scoringRule?: string
  }>(),
  {
    summary: '',
    direction: 'agriculture',
    expectedVersion: 1,
    initialQuestions: () => [],
    initialEnabled: undefined,
    scoringRule: 'all_correct'
  }
)

const emit = defineEmits<{
  close: []
  draftChange: [quiz: TeacherQuiz]
}>()

const store = useTeacherConsoleStore()
const questions = ref<TeacherQuizQuestion[]>(cloneQuestions(props.initialQuestions))
const enabled = ref(
  props.initialEnabled ?? props.initialQuestions.length > 0
)
const actionError = ref('')
const actionMessage = ref('')

const isBusy = computed(() => store.loading)
const questionCountLabel = computed(() => `${questions.value.length} 道题`)
const canSave = computed(() => !isBusy.value)

watch(
  () => props.initialQuestions,
  nextQuestions => {
    questions.value = cloneQuestions(nextQuestions)
  }
)

watch(
  () => props.initialEnabled,
  nextEnabled => {
    if (nextEnabled !== undefined) {
      enabled.value = nextEnabled
    }
  }
)

function cloneQuestions(
  source: TeacherQuizQuestion[]
): TeacherQuizQuestion[] {
  return source.map(question => ({
    ...question,
    options: [...question.options]
  }))
}

function updateOption(
  question: TeacherQuizQuestion,
  index: number,
  value: string
) {
  const previousOption = question.options[index]
  question.options[index] = value
  if (question.answer === previousOption) {
    question.answer = value
  }
}

function removeQuestion(questionId: string) {
  actionError.value = ''
  actionMessage.value = ''
  questions.value = questions.value.filter(
    question => question.id !== questionId
  )
}

function validateQuestions(): boolean {
  actionError.value = ''
  actionMessage.value = ''

  if (!enabled.value) {
    return true
  }
  if (questions.value.length < 3) {
    actionError.value = '测验至少需要 3 道题'
    return false
  }
  if (questions.value.length > 5) {
    actionError.value = '测验最多需要 5 道题'
    return false
  }
  return true
}

async function generate() {
  actionError.value = ''
  actionMessage.value = ''
  if (isBusy.value) {
    return
  }
  if (!props.summary.trim()) {
    actionError.value = '请先填写课程简介/知识点要点'
    return
  }

  try {
    const quiz = await store.generateQuiz(props.courseId, {
      summary: props.summary.trim(),
      direction: props.direction
    })
    questions.value = cloneQuestions(quiz.questions)
    enabled.value = quiz.enabled ?? true
    actionMessage.value = '测验已生成，请预览并保存'
    emit('draftChange', quiz)
  } catch (error) {
    actionError.value =
      error instanceof ApiError
        ? error.message
        : store.error || '测验生成失败'
  }
}

async function save() {
  if (!validateQuestions() || isBusy.value) {
    return
  }

  const quizQuestions = enabled.value
    ? cloneQuestions(questions.value)
    : []
  try {
    const quiz = await store.saveQuiz(props.courseId, {
      expected_version: props.expectedVersion,
      enabled: enabled.value,
      scoring_rule: props.scoringRule,
      questions: quizQuestions
    })
    questions.value = cloneQuestions(quiz.questions)
    enabled.value = quiz.enabled ?? enabled.value
    actionMessage.value = enabled.value
      ? '测验已保存'
      : '测验已关闭'
    emit('draftChange', quiz)
  } catch (error) {
    actionError.value =
      error instanceof ApiError
        ? error.message
        : store.error || '测验保存失败'
  }
}

async function close() {
  actionError.value = ''
  actionMessage.value = ''
  if (isBusy.value) {
    return
  }

  try {
    const quiz = await store.saveQuiz(props.courseId, {
      expected_version: props.expectedVersion,
      enabled: false,
      scoring_rule: props.scoringRule,
      questions: []
    })
    questions.value = []
    enabled.value = quiz.enabled ?? false
    actionMessage.value = '测验已关闭'
    emit('draftChange', quiz)
    emit('close')
  } catch (error) {
    actionError.value =
      error instanceof ApiError
        ? error.message
        : store.error || '测验关闭失败'
  }
}
</script>

<template>
  <section class="quiz-editor" aria-labelledby="quiz-editor-title">
    <header class="quiz-editor__heading">
      <div>
        <span class="ark-data">QUIZ PREVIEW</span>
        <h3 id="quiz-editor-title">AI 课后测验</h3>
      </div>
      <span class="ark-data">{{ questionCountLabel }}</span>
    </header>

    <div class="quiz-editor__body">
      <div class="quiz-controls">
        <label class="quiz-toggle">
          <input
            v-model="enabled"
            data-test="quiz-enabled"
            type="checkbox"
          />
          <span>开启 AI 课后测验</span>
        </label>
        <p>开启后保留 3 至 5 道题，保存前仅教师可见。</p>
      </div>

      <div class="quiz-actions">
        <button
          class="generate-action"
          type="button"
          data-test="generate-quiz"
          :disabled="isBusy"
          @click="generate"
        >
          <RefreshCw
            v-if="isBusy"
            class="spinning"
            :size="17"
            aria-hidden="true"
          />
          <Sparkles v-else :size="17" aria-hidden="true" />
          生成课后测验
        </button>

        <button
          class="close-action"
          type="button"
          data-test="close-quiz"
          :disabled="isBusy"
          @click="close"
        >
          <X :size="17" aria-hidden="true" />
          关闭测验
        </button>
      </div>

      <p v-if="actionError" class="quiz-message is-error" role="alert">
        <CircleAlert :size="16" aria-hidden="true" />
        <span>{{ actionError }}</span>
      </p>
      <p
        v-if="actionMessage"
        class="quiz-message is-success"
        role="status"
      >
        <span>{{ actionMessage }}</span>
      </p>

      <div v-if="questions.length" class="question-list">
        <article
          v-for="(question, questionIndex) in questions"
          :key="question.id"
          class="question-card"
        >
          <header class="question-card__heading">
            <div>
              <span class="ark-data">
                QUESTION {{ String(questionIndex + 1).padStart(2, '0') }}
              </span>
              <strong>
                {{ question.type === 'true_false' ? '判断题' : '选择题' }}
              </strong>
            </div>
            <button
              type="button"
              :data-test="`delete-${question.id}`"
              :disabled="isBusy"
              @click="removeQuestion(question.id)"
            >
              <Trash2 :size="16" aria-hidden="true" />
              删除题目
            </button>
          </header>

          <label class="question-field">
            <span>题干</span>
            <textarea
              :value="question.prompt"
              :data-test="`question-${question.id}-prompt`"
              rows="3"
              @input="
                question.prompt = ($event.target as HTMLTextAreaElement).value
              "
            />
          </label>

          <fieldset class="option-field">
            <legend>选项</legend>
            <label
              v-for="(option, optionIndex) in question.options"
              :key="`${question.id}-${optionIndex}`"
              class="option-row"
            >
              <span class="option-index">{{ optionIndex + 1 }}</span>
              <input
                :value="option"
                :data-test="`question-${question.id}-option-${optionIndex}`"
                type="text"
                @input="
                  updateOption(
                    question,
                    optionIndex,
                    ($event.target as HTMLInputElement).value
                  )
                "
              />
              <span
                v-if="question.answer === option"
                class="correct-marker"
              >
                正确选项
              </span>
            </label>
          </fieldset>
        </article>
      </div>

      <p v-else class="quiz-empty">
        尚未生成题目。可先填写课程简介，再生成 3 至 5 道课后测验。
      </p>

      <footer class="quiz-footer">
        <p>
          {{
            enabled
              ? '保存后题库随课程进入审核，学员不会看到未保存的修改。'
              : '关闭状态下保存会清空学员可见题库。'
          }}
        </p>
        <button
          class="save-action"
          type="button"
          data-test="save-quiz"
          :disabled="!canSave"
          @click="save"
        >
          <RefreshCw
            v-if="isBusy"
            class="spinning"
            :size="17"
            aria-hidden="true"
          />
          <Save v-else :size="17" aria-hidden="true" />
          {{ isBusy ? '处理中' : '保存测验' }}
        </button>
      </footer>
    </div>
  </section>
</template>

<style scoped>
.quiz-editor {
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.quiz-editor__heading {
  display: flex;
  min-width: 0;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 13px 16px;
  border-bottom: 1px solid var(--ark-line);
}

.quiz-editor__heading > div {
  min-width: 0;
}

.quiz-editor__heading span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.quiz-editor__heading h3 {
  margin: 3px 0 0;
  font-size: 1rem;
  line-height: 1.35;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.quiz-editor__body {
  display: grid;
  min-width: 0;
  gap: 14px;
  padding: 16px;
}

.quiz-controls {
  display: grid;
  min-width: 0;
  gap: 6px;
}

.quiz-toggle {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 9px;
  color: var(--ark-paper);
  font-weight: 700;
  line-break: strict;
  text-wrap: pretty;
  word-break: normal;
}

.quiz-toggle input {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  margin: 0;
  accent-color: var(--ark-signal);
}

.quiz-controls p,
.quiz-footer p,
.quiz-empty,
.quiz-message {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.76rem;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.quiz-actions,
.quiz-footer {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.quiz-actions button,
.save-action,
.question-card__heading button {
  display: inline-flex;
  min-width: 0;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: var(--ark-radius);
  background: none;
  line-break: strict;
  text-wrap: pretty;
  white-space: normal;
  word-break: normal;
}

.generate-action,
.save-action {
  padding: 0 15px;
  border: 1px solid var(--ark-signal);
  color: var(--ark-signal);
  font-weight: 700;
}

.close-action,
.question-card__heading button {
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-paper);
  font-size: 0.78rem;
}

.generate-action:hover:not(:disabled),
.save-action:hover:not(:disabled) {
  background: var(--ark-surface-1);
}

.close-action:hover:not(:disabled),
.question-card__heading button:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.quiz-message {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  padding: 10px 11px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.quiz-message svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.question-list {
  display: grid;
  min-width: 0;
  gap: 1px;
  background: var(--ark-line);
}

.question-card {
  display: grid;
  min-width: 0;
  gap: 14px;
  padding: 15px;
  background: var(--ark-surface-0);
}

.question-card__heading {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.question-card__heading > div {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.question-card__heading span {
  color: var(--ark-muted);
  font-size: 0.66rem;
}

.question-card__heading strong {
  font-size: 0.86rem;
}

.question-card__heading button {
  flex: 0 0 auto;
}

.question-field,
.option-field {
  display: grid;
  min-width: 0;
  gap: 7px;
  margin: 0;
  padding: 0;
  border: 0;
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.question-field > span,
.option-field legend {
  padding: 0;
  line-break: strict;
  text-wrap: pretty;
  word-break: normal;
}

.question-field textarea,
.option-row input {
  width: 100%;
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: break-word;
  word-break: normal;
}

.question-field textarea {
  min-height: 88px;
  padding: 10px 11px;
  resize: vertical;
}

.option-field {
  gap: 8px;
}

.option-row {
  display: grid;
  min-width: 0;
  grid-template-columns: 28px minmax(0, 1fr);
  align-items: center;
  gap: 7px 9px;
}

.option-index {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-muted);
  font-variant-numeric: tabular-nums;
}

.option-row input {
  min-height: 42px;
  padding: 8px 10px;
}

.correct-marker {
  grid-column: 2;
  color: var(--ark-signal);
  font-size: 0.68rem;
  line-break: strict;
  text-wrap: pretty;
  word-break: normal;
}

.quiz-empty {
  min-height: 86px;
  padding: 20px 12px;
  border: 1px dashed var(--ark-line-strong);
  background: var(--ark-surface-1);
  text-align: center;
}

.quiz-footer {
  padding-top: 2px;
}

.save-action {
  flex: 0 0 auto;
  min-width: 124px;
}

.quiz-editor :is(button, input, textarea):focus-visible {
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

@media (max-width: 640px), (orientation: portrait) {
  .quiz-editor__heading,
  .question-card__heading,
  .quiz-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .quiz-editor__heading > span {
    width: 100%;
  }

  .quiz-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }

  .quiz-actions button,
  .question-card__heading button,
  .save-action {
    width: 100%;
  }

  .question-card__heading button {
    align-self: stretch;
  }
}

@media (max-width: 360px) {
  .quiz-editor__body,
  .question-card {
    padding-inline: 12px;
  }

  .quiz-editor__heading {
    padding-inline: 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
