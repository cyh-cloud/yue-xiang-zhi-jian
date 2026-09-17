<script setup lang="ts">
import {
  BookOpen,
  CheckCircle2,
  ExternalLink,
  RefreshCw,
  Sparkles,
  Trophy,
  XCircle
} from 'lucide-vue-next'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import type { CourseProgress, CourseQuizAttempt } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import {
  useCourseLearningStore,
  type CourseLearningCourse
} from '@/stores/courseLearning'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  direction: 'agriculture' | 'ecommerce'
  moduleCode: string
  title: string
  description: string
  apiPrefix: string
}>()

const coursesStore = useCourseLearningStore()
const auth = useAuthStore()
const router = useRouter()
const quizAnswers = reactive<Record<string, string>>({})
const retakingCourseId = ref<number | null>(null)
const attemptTimestampFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23'
})

const orderedCourses = computed(() => coursesStore.courses)
const orderedRecommendations = computed(() => coursesStore.recommendations)

function progressFor(courseId: number): CourseProgress | undefined {
  return coursesStore.progressByCourse[courseId]
}

function progressPercent(courseId: number): number | undefined {
  const value = progressFor(courseId)?.progress_percent
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return undefined
  }
  return Math.min(100, Math.max(0, value))
}

function canOpenQuiz(courseId: number): boolean {
  const progress = progressFor(courseId)
  const percent = progressPercent(courseId)
  return (
    percent !== undefined &&
    percent >= 80 &&
    progress?.quiz_available === true
  )
}

function quizGateMessage(courseId: number): string {
  if (coursesStore.progressErrorsByCourse[courseId]) {
    return '进度加载失败，重试后再参加测验'
  }
  const progress = progressFor(courseId)
  if (!progress) {
    return '学习进度加载中'
  }
  const percent = progressPercent(courseId)
  if (percent === undefined) {
    return '学习进度加载中'
  }
  if (percent < 80) {
    return '达到 80% 后开放'
  }
  return '暂无可用测验'
}

function commentReturnTo(course: CourseLearningCourse): string {
  return (
    course.return_to ??
    course.returnTo ??
    course.comment_url ??
    ''
  )
}

function latestAttempt(courseId: number): CourseQuizAttempt | undefined {
  return coursesStore.attempts.find(
    attempt => attempt.course_id === courseId
  )
}

function showsLatestResult(courseId: number): boolean {
  return Boolean(
    latestAttempt(courseId) && retakingCourseId.value !== courseId
  )
}

function justSubmitted(courseId: number): boolean {
  return coursesStore.justSubmittedCourseId === courseId
}

function resultLabel(courseId: number): string {
  return justSubmitted(courseId) ? '本次成绩' : '最近成绩'
}

function feedbackLabel(courseId: number): string {
  return justSubmitted(courseId) ? '本次解析' : '上次解析'
}

function attemptsFor(courseId: number): CourseQuizAttempt[] {
  return coursesStore.attempts.filter(
    attempt => attempt.course_id === courseId
  )
}

function quizIsComplete(courseId: number): boolean {
  const quiz = coursesStore.activeQuiz
  return Boolean(
    quiz &&
      quiz.course_id === courseId &&
      quiz.questions.length > 0 &&
      quiz.questions.every(question => Boolean(quizAnswers[question.id]))
  )
}

function formatTime(seconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(safeSeconds / 3600)
  const minutes = Math.floor((safeSeconds % 3600) / 60)
  const remainingSeconds = safeSeconds % 60
  const minuteText = String(minutes).padStart(2, '0')
  const secondText = String(remainingSeconds).padStart(2, '0')
  return hours > 0
    ? `${hours}:${minuteText}:${secondText}`
    : `${minuteText}:${secondText}`
}

function formatPublishedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(date)
}

function formatAttemptTimestamp(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  const values = Object.fromEntries(
    attemptTimestampFormatter
      .formatToParts(date)
      .filter(part => part.type !== 'literal')
      .map(part => [part.type, part.value])
  )
  return [
    values.year,
    values.month,
    values.day
  ].join('-') + ` ${values.hour}:${values.minute}:${values.second}`
}

async function openQuiz(courseId: number) {
  retakingCourseId.value = null
  Object.keys(quizAnswers).forEach(key => {
    delete quizAnswers[key]
  })
  await coursesStore.loadQuiz(courseId)
}

function startRetake(courseId: number) {
  Object.keys(quizAnswers).forEach(key => {
    delete quizAnswers[key]
  })
  retakingCourseId.value = courseId
}

async function submitQuiz(courseId: number) {
  if (!quizIsComplete(courseId) || coursesStore.loading) {
    return
  }
  const submitted = await coursesStore.submitQuiz(courseId, {
    ...quizAnswers
  })
  if (submitted) {
    retakingCourseId.value = null
  }
}

async function retryAll() {
  await Promise.all([
    coursesStore.loadCourses(),
    coursesStore.loadRecommendations()
  ])
}

async function retryProgress(courseId: number) {
  await coursesStore.loadProgress(courseId)
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  coursesStore.configure(props.apiPrefix, props.direction)
  void Promise.all([
    coursesStore.loadCourses(),
    coursesStore.loadRecommendations()
  ])
})
</script>

<template>
  <div class="agri-courses-page">
    <AppHeader
      source="live"
      :loading="coursesStore.loading"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <slot name="nav" />

    <main class="agri-courses-main">
      <header class="agri-courses-heading">
        <span class="agri-courses-heading__code ark-data">
          {{ props.moduleCode }} /
          {{ props.direction === 'agriculture' ? 'AGRICULTURAL' : 'E-COMMERCE' }}
          COURSES
        </span>
        <h1>{{ props.title }}</h1>
        <p>{{ props.description }}</p>
      </header>

      <div
        v-if="coursesStore.error"
        class="agri-courses-error"
        role="alert"
      >
        <span>{{ coursesStore.error }}</span>
        <button type="button" @click="retryAll">
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </div>

      <section
        class="recommendation-section"
        aria-labelledby="course-recommendations-title"
      >
        <header class="section-heading">
          <div>
            <span class="ark-data">PERSONALIZED QUEUE</span>
            <h2 id="course-recommendations-title">为你推荐</h2>
          </div>
          <Sparkles :size="21" aria-hidden="true" />
        </header>

        <div
          v-if="coursesStore.recommendationError"
          class="section-error"
          role="alert"
        >
          <p data-test="recommendation-error">
            {{ coursesStore.recommendationError }}
          </p>
          <button
            type="button"
            data-test="recommendation-retry"
            @click="coursesStore.loadRecommendations"
          >
            <RefreshCw :size="15" aria-hidden="true" />
            重试推荐
          </button>
        </div>
        <p
          v-else-if="orderedRecommendations.length === 0"
          class="section-empty"
          data-test="recommendation-empty"
        >
          暂无推荐
        </p>
        <div
          v-if="orderedRecommendations.length"
          class="recommendation-list"
        >
          <article
            v-for="course in orderedRecommendations"
            :key="course.id"
            class="recommendation-item"
            :data-test="`recommendation-${course.id}`"
          >
            <span class="ark-data">
              {{ String(course.id).padStart(2, '0') }}
            </span>
            <div>
              <h3>{{ course.title }}</h3>
              <p>{{ course.summary }}</p>
            </div>
          </article>
        </div>
      </section>

      <section
        class="course-section"
        aria-labelledby="course-list-title"
        :aria-busy="coursesStore.loading"
      >
        <header class="section-heading">
          <div>
            <span class="ark-data">PUBLISHED COURSE INDEX</span>
            <h2 id="course-list-title">全部课程</h2>
          </div>
          <BookOpen :size="21" aria-hidden="true" />
        </header>

        <div
          v-if="coursesStore.loading && orderedCourses.length === 0"
          class="course-loading"
          role="status"
        >
          <RefreshCw class="spinning" :size="20" aria-hidden="true" />
          <span>正在加载课程</span>
        </div>
        <p
          v-else-if="orderedCourses.length === 0"
          class="section-empty"
          data-test="course-empty"
        >
          暂无课程
        </p>
        <div v-else class="course-list">
          <article
            v-for="course in orderedCourses"
            :key="course.id"
            class="course-card"
            :data-test="`course-${course.id}`"
          >
            <header class="course-card__head">
              <div>
                <span class="course-card__index ark-data">
                  COURSE {{ String(course.id).padStart(2, '0') }}
                </span>
                <h3>{{ course.title }}</h3>
              </div>
              <time class="ark-data" :datetime="course.published_at">
                {{ formatPublishedAt(course.published_at) }}
              </time>
            </header>

            <p class="course-card__summary">{{ course.summary }}</p>

            <dl class="course-card__meta">
              <div>
                <dt>授课教师</dt>
                <dd>{{ course.teacher_name || '待定' }}</dd>
              </div>
              <div>
                <dt>课程时长</dt>
                <dd>
                  {{
                    course.duration_seconds
                      ? formatTime(course.duration_seconds)
                      : '时长待补充'
                  }}
                </dd>
              </div>
            </dl>

            <div v-if="progressFor(course.id)" class="course-progress">
              <div class="course-progress__head">
                <span>学习进度</span>
                <strong class="ark-data">
                  {{ progressPercent(course.id) ?? 0 }}%
                </strong>
              </div>
              <progress
                :data-test="`course-progress-${course.id}`"
                :value="progressPercent(course.id) ?? 0"
                max="100"
              >
                {{ progressPercent(course.id) ?? 0 }}%
              </progress>
              <div class="course-progress__facts">
                <span :data-test="`course-resume-${course.id}`">
                  续播
                  {{ formatTime(progressFor(course.id)?.resume_position_seconds ?? 0) }}
                </span>
                <span>
                  累计
                  {{ formatTime(progressFor(course.id)?.watched_seconds ?? 0) }}
                </span>
              </div>
            </div>
            <div
              v-else-if="coursesStore.progressErrorsByCourse[course.id]"
              class="course-progress course-progress--error"
              :data-test="`course-progress-error-${course.id}`"
              role="alert"
            >
              <div>
                <strong>学习进度加载失败</strong>
                <p>{{ coursesStore.progressErrorsByCourse[course.id] }}</p>
              </div>
              <button
                type="button"
                :data-test="`course-progress-retry-${course.id}`"
                @click="retryProgress(course.id)"
              >
                <RefreshCw :size="15" aria-hidden="true" />
                重试
              </button>
            </div>
            <div v-else class="course-progress course-progress--pending">
              正在读取学习进度
            </div>

            <div class="course-card__actions">
              <a
                v-if="commentReturnTo(course)"
                class="course-comments-link"
                :href="commentReturnTo(course)"
                :data-test="`course-comments-${course.id}`"
              >
                课程评论区
                <ExternalLink :size="15" aria-hidden="true" />
              </a>
              <button
                class="quiz-entry"
                type="button"
                :data-test="`quiz-entry-${course.id}`"
                :disabled="!canOpenQuiz(course.id) || coursesStore.loading"
                @click="openQuiz(course.id)"
              >
                <Trophy :size="17" aria-hidden="true" />
                课后测验
              </button>
              <small
                v-if="!canOpenQuiz(course.id)"
                :data-test="`quiz-gate-${course.id}`"
              >
                {{ quizGateMessage(course.id) }}
              </small>
            </div>

            <section
              v-if="coursesStore.activeQuiz?.course_id === course.id"
              class="quiz-panel"
              :data-test="`quiz-${course.id}`"
            >
              <header class="quiz-panel__head">
                <div>
                  <span class="ark-data">AI COURSE QUIZ</span>
                  <h4>课后测验</h4>
                </div>
                <Trophy :size="21" aria-hidden="true" />
              </header>

              <section
                v-if="attemptsFor(course.id).length"
                class="quiz-history"
                :data-test="`quiz-history-${course.id}`"
              >
                <header>
                  <span>测验记录</span>
                  <strong class="ark-data">
                    {{ attemptsFor(course.id).length }} 次
                  </strong>
                </header>
                <article
                  v-for="attempt in attemptsFor(course.id)"
                  :key="attempt.id"
                  :data-test="`quiz-history-${attempt.id}`"
                >
                  <div>
                    <time
                      class="ark-data"
                      :datetime="attempt.created_at"
                    >
                      {{ formatAttemptTimestamp(attempt.created_at) }}
                    </time>
                    <span>
                      {{
                        attempt.is_current || attempt.is_formal
                          ? '正式成绩'
                          : '历史成绩'
                      }}
                    </span>
                    <span v-if="attempt.is_latest">最新提交</span>
                  </div>
                  <strong class="ark-data">{{ attempt.score }} 分</strong>
                </article>
              </section>

              <form
                v-if="!showsLatestResult(course.id)"
                class="quiz-form"
                :data-test="`quiz-form-${course.id}`"
                @submit.prevent="submitQuiz(course.id)"
              >
                <fieldset
                  v-for="(question, questionIndex) in coursesStore.activeQuiz.questions"
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
                      v-model="quizAnswers[question.id]"
                      type="radio"
                      :name="`course-${course.id}-${question.id}`"
                      :value="option"
                      :data-test="`quiz-option-${questionIndex}-${optionIndex}`"
                    >
                    <span>{{ option }}</span>
                  </label>
                </fieldset>
                <button
                  class="quiz-submit"
                  type="submit"
                  :data-test="`quiz-submit-${course.id}`"
                  :disabled="!quizIsComplete(course.id) || coursesStore.loading"
                >
                  <CheckCircle2 :size="17" aria-hidden="true" />
                  提交测验
                </button>
              </form>

              <div
                v-if="showsLatestResult(course.id)"
                class="quiz-result"
                :data-test="`quiz-result-${course.id}`"
              >
                <div class="quiz-result__score">
                  <span data-test="quiz-result-label">
                    {{ resultLabel(course.id) }}
                  </span>
                  <strong
                    class="ark-data"
                    :data-test="`quiz-score-${course.id}`"
                  >
                    {{ latestAttempt(course.id)?.score }} 分
                  </strong>
                </div>
                <div class="quiz-result__actions">
                  <button
                    class="quiz-submit quiz-retake"
                    type="button"
                    :data-test="`quiz-retake-${course.id}`"
                    @click="startRetake(course.id)"
                  >
                    <RefreshCw :size="17" aria-hidden="true" />
                    再次测验
                  </button>
                </div>
                <div
                  class="quiz-result__feedback-heading"
                  data-test="quiz-feedback-label"
                >
                  {{ feedbackLabel(course.id) }}
                </div>
                <article
                  v-for="(question, index) in latestAttempt(course.id)?.questions"
                  :key="question.id"
                >
                  <span
                    class="quiz-result__marker"
                    :class="{
                      'is-correct': question.correct,
                      'is-wrong': !question.correct
                    }"
                    :data-test="`quiz-result-${index}`"
                  >
                    <CheckCircle2
                      v-if="question.correct"
                      :size="14"
                      aria-hidden="true"
                    />
                    <XCircle v-else :size="14" aria-hidden="true" />
                    {{ question.correct ? '正确' : '错误' }}
                  </span>
                  <h5>{{ index + 1 }}. {{ question.prompt }}</h5>
                  <p :data-test="`quiz-explanation-${index}`">
                    {{ question.explanation }}
                  </p>
                </article>
              </div>
            </section>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.agri-courses-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
}

.agri-courses-main {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.agri-courses-heading {
  padding-bottom: 24px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.agri-courses-heading__code {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.agri-courses-heading h1 {
  margin: 9px 0 0;
  font-size: 3rem;
  line-height: 1;
}

.agri-courses-heading p {
  max-width: 64ch;
  margin: 15px 0 0;
  color: var(--ark-muted);
}

.agri-courses-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 18px;
  padding: 12px 14px;
  border-left: 3px solid var(--ark-signal);
  background: var(--ark-surface-0);
}

.agri-courses-error span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.agri-courses-error button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  padding: 0 11px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

.recommendation-section,
.course-section {
  margin-top: 22px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 66px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.section-heading span,
.quiz-panel__head span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.section-heading h2,
.quiz-panel__head h4 {
  margin: 3px 0 0;
  font-size: 1rem;
}

.section-heading > svg,
.quiz-panel__head > svg {
  color: var(--ark-signal);
}

.section-empty {
  min-height: 0;
  margin: 0;
  padding: 32px 18px;
  color: var(--ark-muted);
  text-align: center;
}

.section-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 13px 16px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.section-error p {
  margin: 0;
  overflow-wrap: anywhere;
}

.section-error button,
.course-progress--error button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 36px;
  padding: 0 11px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

.section-error button:hover,
.course-progress--error button:hover {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.recommendation-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
  gap: 10px;
  padding: 12px;
}

.recommendation-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  min-width: 0;
  padding: 17px 18px;
  border: 1px solid var(--ark-line);
}

.recommendation-item > span {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.recommendation-item h3 {
  margin: 0;
  font-size: 0.94rem;
  text-wrap: balance;
}

.recommendation-item p {
  display: -webkit-box;
  min-width: 0;
  margin: 7px 0 0;
  overflow: hidden;
  overflow-wrap: anywhere;
  color: var(--ark-muted);
  font-size: 0.78rem;
  text-wrap: balance;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.course-loading {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  min-height: 260px;
  color: var(--ark-muted);
}

.course-list {
  display: grid;
}

.course-card {
  min-width: 0;
  padding: 22px 20px;
  border-bottom: 1px solid var(--ark-line);
}

.course-card:last-child {
  border-bottom: 0;
}

.course-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.course-card__index {
  color: var(--ark-signal);
  font-size: 0.69rem;
}

.course-card__head h3 {
  margin: 5px 0 0;
  font-size: 1.28rem;
  line-height: 1.3;
  text-wrap: balance;
}

.course-card__head time {
  flex: 0 0 auto;
  color: var(--ark-muted);
  font-size: 0.74rem;
}

.course-card__summary {
  min-width: 0;
  max-width: 78ch;
  margin: 13px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: balance;
}

.course-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 34px;
  margin: 17px 0 0;
}

.course-card__meta div {
  display: grid;
  gap: 2px;
}

.course-card__meta dt {
  color: var(--ark-muted);
  font-size: 0.7rem;
}

.course-card__meta dd {
  margin: 0;
  font-size: 0.84rem;
}

.course-progress {
  margin-top: 20px;
  padding: 14px;
  background: var(--ark-surface-1);
}

.course-progress__head,
.course-progress__facts {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.course-progress__head span,
.course-progress__facts {
  color: var(--ark-muted);
  font-size: 0.74rem;
}

.course-progress__head strong {
  color: var(--ark-signal);
  font-size: 1rem;
}

.course-progress progress {
  display: block;
  width: 100%;
  height: 10px;
  margin: 10px 0;
  overflow: hidden;
  appearance: none;
  border: 1px solid var(--ark-line-strong);
  border-radius: 0;
  background: var(--ark-surface-2);
  color: var(--ark-signal);
  accent-color: var(--ark-signal);
}

.course-progress progress::-webkit-progress-bar {
  background: var(--ark-surface-2);
}

.course-progress progress::-webkit-progress-value {
  background: var(--ark-signal);
}

.course-progress progress::-moz-progress-bar {
  background: var(--ark-signal);
}

.course-progress--error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.course-progress--error > div {
  min-width: 0;
}

.course-progress--error strong {
  font-size: 0.84rem;
}

.course-progress--error p {
  margin: 4px 0 0;
  color: var(--ark-muted);
  font-size: 0.76rem;
  overflow-wrap: anywhere;
}

.course-progress--pending {
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.course-card__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
}

.course-card__actions button,
.course-card__actions a {
  display: inline-flex;
  min-width: 0;
  max-width: 100%;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 40px;
  padding: 0 13px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
  font-size: 0.82rem;
  text-decoration: none;
  white-space: normal;
}

.course-card__actions a:hover,
.course-card__actions a:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.course-card__actions .quiz-entry {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.course-card__actions .quiz-entry:hover:not(:disabled) {
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}

.course-card__actions button:disabled {
  border-color: var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-muted);
  cursor: not-allowed;
  opacity: 1;
}

.course-card__actions small {
  flex: 1 0 100%;
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-height: 1.5;
  text-wrap: balance;
}

.quiz-panel {
  margin-top: 20px;
  border: 1px solid var(--ark-line-strong);
}

.quiz-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  min-height: 60px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.quiz-form {
  display: grid;
  gap: 20px;
  padding: 20px 16px;
}

.quiz-history {
  border-bottom: 1px solid var(--ark-line);
}

.quiz-history > header,
.quiz-history article,
.quiz-history article > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.quiz-history > header {
  padding: 12px 16px;
  background: var(--ark-surface-1);
}

.quiz-history > header span,
.quiz-history article span,
.quiz-history article time {
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.quiz-history article {
  padding: 12px 16px;
  border-top: 1px solid var(--ark-line);
}

.quiz-history article > div {
  flex-wrap: wrap;
  justify-content: flex-start;
}

.quiz-history article > strong {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.quiz-form fieldset {
  display: grid;
  gap: 8px;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.quiz-form legend {
  margin-bottom: 10px;
  color: var(--ark-paper);
  font-weight: 700;
  overflow-wrap: anywhere;
}

.quiz-form label {
  display: flex;
  align-items: center;
  min-height: 42px;
  gap: 9px;
  padding: 8px 10px;
  border: 1px solid var(--ark-line);
  cursor: pointer;
}

.quiz-form input {
  flex: 0 0 auto;
  accent-color: var(--ark-signal);
}

.quiz-submit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  width: fit-content;
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--ark-signal);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}

.quiz-submit:hover:not(:disabled) {
  border-color: var(--ark-paper);
  background: var(--ark-paper);
}

.quiz-submit:disabled {
  border-color: var(--ark-line-strong);
  background: var(--ark-surface-2);
  color: var(--ark-paper);
  cursor: not-allowed;
  opacity: 1;
}

.quiz-result {
  display: grid;
  border-top: 1px solid var(--ark-line);
}

.quiz-result__score {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 16px;
  background: var(--ark-surface-1);
}

.quiz-result__score span {
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.quiz-result__score strong {
  color: var(--ark-signal);
  font-size: 1.55rem;
}

.quiz-result__actions {
  display: flex;
  justify-content: flex-end;
  padding: 12px 16px;
  border-top: 1px solid var(--ark-line);
}

.quiz-result__feedback-heading {
  padding: 10px 16px;
  border-top: 1px solid var(--ark-line);
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.quiz-result article {
  display: grid;
  gap: 7px;
  padding: 16px;
  border-top: 1px solid var(--ark-line);
}

.quiz-result__marker {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  gap: 5px;
  padding: 2px 7px;
  border: 1px solid var(--ark-line-strong);
  font-size: 0.7rem;
}

.quiz-result__marker.is-correct {
  border-color: var(--ark-state);
  color: var(--ark-state);
}

.quiz-result__marker.is-wrong {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.quiz-result h5 {
  margin: 0;
  font-size: 0.86rem;
}

.quiz-result p {
  margin: 0;
  color: var(--ark-muted);
  overflow-wrap: anywhere;
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
  .agri-courses-main {
    padding: 28px 14px 48px;
  }

  .agri-courses-heading h1 {
    font-size: 2.25rem;
  }

  .recommendation-list {
    grid-template-columns: minmax(0, 1fr);
  }

  .course-card {
    padding: 18px 14px;
  }

  .course-card__head,
  .agri-courses-error {
    align-items: flex-start;
    flex-direction: column;
  }

  .section-error,
  .course-progress--error {
    align-items: flex-start;
    flex-direction: column;
  }

  .course-card__actions {
    align-items: stretch;
  }

  .course-card__actions button,
  .course-card__actions a {
    flex: 1 1 160px;
  }

  .quiz-submit {
    width: 100%;
  }
}
</style>
