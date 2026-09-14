<script setup lang="ts">
import { ArrowLeft, BookOpen, RefreshCw } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import type { CourseSummary, LearningDirection } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import { useAuthStore } from '@/stores/auth'
import { useStudentStore } from '@/stores/student'

type CourseDirection = Exclude<LearningDirection, 'comprehensive'>

const directionTabs: Array<{
  value: CourseDirection
  label: string
}> = [
  { value: 'agriculture', label: '农业' },
  { value: 'ecommerce', label: '电商' },
  { value: 'handcraft', label: '手工' }
]

const auth = useAuthStore()
const student = useStudentStore()
const router = useRouter()
const activeDirection = ref<CourseDirection>('agriculture')

function formatPublishedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(date)
}

function courseKey(course: CourseSummary): string {
  return `${course.id}-${course.direction}`
}

async function selectDirection(direction: CourseDirection) {
  if (direction === activeDirection.value) {
    return
  }

  activeDirection.value = direction
  await student.loadCourses(direction)
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void student.loadCourses(activeDirection.value)
})
</script>

<template>
  <div class="catalog-page">
    <AppHeader
      source="live"
      :loading="student.loadingCourses"
      :user-name="auth.user?.name"
      @logout="logout"
    />

    <main class="catalog-main">
      <RouterLink class="back-link" to="/student">
        <ArrowLeft :size="16" aria-hidden="true" />
        返回学员门户
      </RouterLink>

      <header class="catalog-heading">
        <div>
          <h1>课程聚合</h1>
          <p>浏览已上架课程。匹配兴趣标签的课程优先展示，方向切换时重新读取课程数据。</p>
        </div>
        <div class="catalog-state">
          <BookOpen :size="18" aria-hidden="true" />
          <span class="ark-data">{{ student.courses.length }}</span>
          <small>门课程</small>
        </div>
      </header>

      <div
        class="direction-tabs"
        role="tablist"
        aria-label="课程方向"
      >
        <button
          v-for="tab in directionTabs"
          :key="tab.value"
          type="button"
          role="tab"
          :aria-selected="activeDirection === tab.value"
          :class="{ active: activeDirection === tab.value }"
          :data-test="`direction-${tab.value}`"
          @click="selectDirection(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>

      <section
        class="catalog-results"
        :aria-busy="student.loadingCourses"
        :aria-labelledby="`catalog-${activeDirection}-title`"
      >
        <h2 :id="`catalog-${activeDirection}-title`" class="ark-sr-only">
          {{ directionTabs.find(tab => tab.value === activeDirection)?.label }}课程
        </h2>

        <div v-if="student.loadingCourses" class="course-skeletons" role="status">
          <span class="ark-sr-only">正在加载课程</span>
          <div v-for="index in 3" :key="index" class="course-skeleton" aria-hidden="true">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>

        <div v-else-if="student.error" class="catalog-error" role="alert">
          <p>{{ student.error }}</p>
          <button type="button" @click="student.loadCourses(activeDirection)">
            <RefreshCw :size="16" aria-hidden="true" />
            重新加载
          </button>
        </div>

        <p v-else-if="student.courses.length === 0" class="catalog-empty">
          暂无课程
        </p>

        <div v-else class="course-list">
          <article
            v-for="course in student.courses"
            :key="courseKey(course)"
            class="course-row"
          >
            <div class="course-marker" aria-hidden="true">
              <span>{{ String(course.id).padStart(2, '0') }}</span>
            </div>
            <div class="course-copy">
              <header>
                <h3>{{ course.title }}</h3>
                <span v-if="course.interest_match" class="recommendation-marker">
                  推荐
                </span>
              </header>
              <p>{{ course.summary }}</p>
            </div>
            <dl class="course-meta">
              <div>
                <dt>授课教师</dt>
                <dd>{{ course.teacher_name || '待定' }}</dd>
              </div>
              <div>
                <dt>上架时间</dt>
                <dd>
                  <time :datetime="course.published_at">
                    {{ formatPublishedAt(course.published_at) }}
                  </time>
                </dd>
              </div>
            </dl>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.catalog-page {
  min-height: 100svh;
  background:
    linear-gradient(rgb(244 246 246 / 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgb(244 246 246 / 0.028) 1px, transparent 1px),
    var(--ark-ink);
  background-size: 72px 72px;
}

.catalog-main {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 38px 24px 72px;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  color: var(--ark-muted);
  font-size: 0.8rem;
  text-decoration: none;
}

.back-link:hover,
.back-link:focus-visible {
  color: var(--ark-signal);
}

.catalog-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 28px;
  margin-top: 18px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.catalog-heading h1 {
  margin: 0;
  font-size: 3rem;
  line-height: 1.02;
}

.catalog-heading p {
  max-width: 66ch;
  margin: 14px 0 0;
  color: #c4cdcf;
}

.catalog-state {
  display: grid;
  grid-template-columns: auto auto;
  gap: 2px 9px;
  align-items: center;
  min-width: 112px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line);
  background: rgb(5 6 7 / 0.78);
  color: var(--ark-signal);
}

.catalog-state span {
  font-size: 1.35rem;
  font-weight: 700;
  line-height: 1;
}

.catalog-state small {
  grid-column: 2;
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.direction-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  margin-top: 22px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.direction-tabs button {
  min-height: 48px;
  border: 0;
  background: rgb(5 6 7 / 0.88);
  color: var(--ark-muted);
  font-size: 0.9rem;
}

.direction-tabs button:hover {
  color: var(--ark-paper);
}

.direction-tabs button.active {
  background: rgb(24 209 255 / 0.1);
  color: var(--ark-signal);
  box-shadow: inset 0 -2px 0 var(--ark-signal);
}

.catalog-results {
  min-height: 360px;
  margin-top: 12px;
  border: 1px solid var(--ark-line-strong);
  background: rgb(5 6 7 / 0.84);
}

.course-list {
  display: grid;
}

.course-row {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr) minmax(220px, 0.34fr);
  min-height: 148px;
  border-bottom: 1px solid var(--ark-line);
}

.course-row:last-child {
  border-bottom: 0;
}

.course-marker {
  display: grid;
  place-items: start center;
  padding-top: 24px;
  border-right: 1px solid var(--ark-line);
}

.course-marker span {
  color: var(--ark-muted);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.74rem;
  font-variant-numeric: tabular-nums;
}

.course-copy {
  min-width: 0;
  padding: 22px 24px;
}

.course-copy header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.course-copy h3 {
  margin: 0;
  font-size: 1.18rem;
  line-height: 1.3;
}

.course-copy p {
  max-width: 66ch;
  margin: 12px 0 0;
  color: var(--ark-muted);
  font-size: 0.88rem;
}

.recommendation-marker {
  display: inline-flex;
  align-items: center;
  min-height: 25px;
  padding: 0 7px;
  border: 1px solid var(--ark-signal);
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.course-meta {
  display: grid;
  align-content: center;
  gap: 16px;
  margin: 0;
  padding: 22px 24px;
  border-left: 1px solid var(--ark-line);
}

.course-meta div {
  min-width: 0;
}

.course-meta dt {
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.course-meta dd {
  margin: 4px 0 0;
  color: var(--ark-paper);
  font-size: 0.84rem;
}

.course-meta time {
  font-variant-numeric: tabular-nums;
}

.catalog-empty,
.catalog-error {
  display: grid;
  place-items: center;
  min-height: 360px;
  margin: 0;
  color: var(--ark-muted);
}

.catalog-error {
  align-content: center;
  gap: 14px;
}

.catalog-error p {
  margin: 0;
  color: #ff9c9c;
}

.catalog-error button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 38px;
  padding: 0 13px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

.catalog-error button:hover {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.course-skeletons {
  display: grid;
}

.course-skeleton {
  display: grid;
  grid-template-columns: 42% 24% 18%;
  gap: 9%;
  min-height: 148px;
  padding: 34px 24px;
  border-bottom: 1px solid var(--ark-line);
}

.course-skeleton:last-child {
  border-bottom: 0;
}

.course-skeleton span {
  display: block;
  height: 14px;
  background: linear-gradient(
    90deg,
    rgb(244 246 246 / 0.08),
    rgb(244 246 246 / 0.16),
    rgb(244 246 246 / 0.08)
  );
  background-size: 200% 100%;
  animation: skeleton-shift 1.4s linear infinite;
}

.course-skeleton span:nth-child(2) {
  width: 82%;
}

.course-skeleton span:nth-child(3) {
  width: 72%;
}

@keyframes skeleton-shift {
  to {
    background-position: -200% 0;
  }
}

@media (max-width: 760px) {
  .catalog-main {
    padding: 28px 14px 48px;
  }

  .catalog-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .catalog-heading h1 {
    font-size: 2.25rem;
  }

  .direction-tabs button {
    min-width: 0;
    padding: 0 8px;
  }

  .course-row {
    grid-template-columns: 44px minmax(0, 1fr);
  }

  .course-marker {
    grid-row: 1 / span 2;
  }

  .course-copy {
    padding: 18px 16px 14px;
  }

  .course-meta {
    grid-column: 2;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    padding: 0 16px 18px;
    border-left: 0;
  }

  .course-skeleton {
    grid-template-columns: 1fr;
    gap: 14px;
  }
}
</style>
