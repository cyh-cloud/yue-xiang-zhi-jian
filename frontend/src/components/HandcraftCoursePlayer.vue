<script setup lang="ts">
import { Pause, Play, RefreshCw } from 'lucide-vue-next'
import { computed, onBeforeUnmount, ref } from 'vue'

import type { CourseProgress, HandcraftCourse } from '@/api/types'
import { useActiveLearningHeartbeat } from '@/composables/activeLearningHeartbeat'
import { useCourseLearningStore } from '@/stores/courseLearning'

const props = defineProps<{
  course: HandcraftCourse
}>()

const coursesStore = useCourseLearningStore()
const mediaUrl = computed(() => props.course.media_url?.trim() ?? '')
const currentPosition = ref(0)
const duration = ref(
  Math.max(0, Number(props.course.duration_seconds) || 0)
)
const playing = ref(false)
const playerError = ref('')
let saveTimer: ReturnType<typeof setInterval> | null = null

const heartbeat = useActiveLearningHeartbeat(
  payload => coursesStore.heartbeatCourse(props.course.id, payload),
  {
    onError(error) {
      playerError.value =
        error instanceof Error ? error.message : '学习时长同步失败'
    }
  }
)

const displayedProgress = computed<CourseProgress | undefined>(
  () => coursesStore.progressByCourse[props.course.id]
)

function formatTime(seconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(safeSeconds / 60)
  const remainingSeconds = safeSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(
    remainingSeconds
  ).padStart(2, '0')}`
}

function clearSaveTimer() {
  if (saveTimer !== null) {
    clearInterval(saveTimer)
    saveTimer = null
  }
}

async function savePosition() {
  if (!mediaUrl.value) return
  const segmentId = await heartbeat.flush()
  await coursesStore.saveProgress(
    props.course.id,
    Math.max(0, Math.floor(currentPosition.value)),
    0,
    segmentId
  )
}

function handleLoadedMetadata(event: Event) {
  const video = event.currentTarget as HTMLVideoElement
  if (Number.isFinite(video.duration) && video.duration > 0) {
    duration.value = video.duration
  }
}

function handleTimeUpdate(event: Event) {
  if (playing.value) {
    heartbeat.touch()
  }
  const video = event.currentTarget as HTMLVideoElement
  currentPosition.value = Number.isFinite(video.currentTime)
    ? video.currentTime
    : 0
}

function handlePlay() {
  playing.value = true
  playerError.value = ''
  heartbeat.touch()
  clearSaveTimer()
  saveTimer = setInterval(() => {
    void savePosition()
  }, 30_000)
}

async function handlePause() {
  playing.value = false
  clearSaveTimer()
  await savePosition()
  heartbeat.stop()
}

async function handleEnded() {
  await handlePause()
}

async function handleSeeked() {
  await savePosition()
}

onBeforeUnmount(() => {
  clearSaveTimer()
  void savePosition()
  heartbeat.stop()
})
</script>

<template>
  <section
    v-if="mediaUrl"
    class="handcraft-course-player"
    data-test="handcraft-course-player"
    :aria-label="`${course.title}课程播放器`"
  >
    <video
      controls
      playsinline
      preload="metadata"
      :src="mediaUrl"
      @loadedmetadata="handleLoadedMetadata"
      @timeupdate="handleTimeUpdate"
      @play="handlePlay"
      @pause="handlePause"
      @ended="handleEnded"
      @seeked="handleSeeked"
    >
      当前浏览器不支持视频播放。
    </video>
    <div class="handcraft-course-player__status">
      <span>
        <Play v-if="!playing" :size="15" aria-hidden="true" />
        <Pause v-else :size="15" aria-hidden="true" />
        {{ playing ? '正在学习' : '已暂停' }}
      </span>
      <span class="ark-data">
        {{ formatTime(currentPosition) }} /
        {{ formatTime(duration || course.duration_seconds || 0) }}
      </span>
      <strong class="ark-data">
        {{ displayedProgress?.progress_percent ?? 0 }}%
      </strong>
    </div>
    <p v-if="playerError" class="handcraft-course-player__error" role="alert">
      <RefreshCw :size="15" aria-hidden="true" />
      {{ playerError }}
    </p>
  </section>
  <p
    v-else
    class="handcraft-course-player__unavailable"
    data-test="course-media-unavailable"
  >
    课程视频暂不可用
  </p>
</template>

<style scoped>
.handcraft-course-player {
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.handcraft-course-player video {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: var(--ark-ink);
  object-fit: contain;
}

.handcraft-course-player video:focus-visible {
  outline: 2px solid var(--ark-focus);
  outline-offset: 3px;
}

.handcraft-course-player__status {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  min-height: 42px;
  padding: 8px 12px;
  border-top: 1px solid var(--ark-line);
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.handcraft-course-player__status > span:first-child {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  gap: 6px;
}

.handcraft-course-player__status strong {
  color: var(--ark-signal);
}

.handcraft-course-player__error,
.handcraft-course-player__unavailable {
  margin: 0;
  padding: 12px;
  border-top: 1px solid var(--ark-line);
  color: var(--ark-signal);
  font-size: 0.78rem;
}

.handcraft-course-player__error {
  display: flex;
  align-items: center;
  gap: 7px;
}

.handcraft-course-player__unavailable {
  margin-top: 18px;
  border: 1px solid var(--ark-line);
  color: var(--ark-muted);
}

@media (orientation: portrait), (max-width: 520px) {
  .handcraft-course-player__status {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .handcraft-course-player__status strong {
    grid-column: 1 / -1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .handcraft-course-player video {
    animation: none;
    transition: none;
  }
}
</style>
