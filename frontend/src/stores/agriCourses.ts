import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type {
  AgriculturalCourse,
  CourseProgress,
  CourseQuiz,
  CourseQuizAttempt
} from '@/api/types'

export interface AgriCourse extends AgriculturalCourse {
  status?: string
  publication_status?: string
  is_published?: boolean
  direction?: string
  learning_direction?: string
  return_to?: string
  returnTo?: string
  comment_url?: string
}

interface AgriCoursesState {
  courses: AgriCourse[]
  recommendations: AgriCourse[]
  progressByCourse: Record<number, CourseProgress>
  activeQuiz: CourseQuiz | null
  attempts: CourseQuizAttempt[]
  loading: boolean
  error: string
}

function normalizedStatus(course: AgriCourse): string | undefined {
  if (typeof course.status === 'string') {
    return course.status
  }
  if (typeof course.publication_status === 'string') {
    return course.publication_status
  }
  if (course.is_published === true) {
    return 'published'
  }
  if (course.is_published === false) {
    return 'offline'
  }
  return undefined
}

function normalizedDirection(course: AgriCourse): string | undefined {
  return course.direction ?? course.learning_direction
}

function isEligibleCourse(course: AgriCourse): boolean {
  const status = normalizedStatus(course)
  const direction = normalizedDirection(course)
  return (
    (status === undefined || status === 'published') &&
    (direction === undefined || direction === 'agriculture')
  )
}

function isEligibleRecommendation(course: AgriCourse): boolean {
  return isEligibleCourse(course)
}

export const useAgriCoursesStore = defineStore('agriCourses', {
  state: (): AgriCoursesState => ({
    courses: [],
    recommendations: [],
    progressByCourse: {},
    activeQuiz: null,
    attempts: [],
    loading: false,
    error: ''
  }),
  actions: {
    captureError(error: unknown, fallback: string) {
      this.error =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : fallback
    },
    async loadCourses() {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          courses: AgriCourse[]
        }>('/api/agri-skills/courses')
        const courses = response.courses.filter(isEligibleCourse)
        this.courses = courses

        const progressEntries = await Promise.all(
          courses.map(async course => {
            try {
              const progressResponse = await apiFetch<{
                success: true
                progress: CourseProgress
              }>(`/api/agri-skills/courses/${course.id}/progress`)
              return [course.id, progressResponse.progress] as const
            } catch {
              return null
            }
          })
        )
        this.progressByCourse = Object.fromEntries(
          progressEntries.filter(
            (
              entry
            ): entry is readonly [number, CourseProgress] => entry !== null
          )
        )
      } catch (error) {
        this.captureError(error, '课程加载失败')
      } finally {
        this.loading = false
      }
    },
    async loadRecommendations() {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          courses: AgriCourse[]
        }>('/api/agri-skills/recommendations')
        this.recommendations = response.courses.filter(isEligibleRecommendation)
      } catch (error) {
        this.captureError(error, '推荐课程加载失败')
      } finally {
        this.loading = false
      }
    },
    async saveProgress(
      courseId: number,
      positionSeconds: number,
      watchedDeltaSeconds: number
    ): Promise<boolean> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          progress: CourseProgress
        }>(`/api/agri-skills/courses/${courseId}/progress`, {
          method: 'PUT',
          body: JSON.stringify({
            position_seconds: positionSeconds,
            watched_delta_seconds: watchedDeltaSeconds
          })
        })
        this.progressByCourse[courseId] = response.progress

        if (
          response.progress.completed_at !== null ||
          response.progress.progress_percent >= 80
        ) {
          await this.loadRecommendations()
        }
        return true
      } catch (error) {
        this.captureError(error, '学习进度保存失败')
        return false
      } finally {
        this.loading = false
      }
    },
    async loadQuiz(courseId: number): Promise<boolean> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          quiz: CourseQuiz
        }>(`/api/agri-skills/courses/${courseId}/quiz`)
        this.activeQuiz = response.quiz
        return true
      } catch (error) {
        this.activeQuiz = null
        this.captureError(error, '课后测验加载失败')
        return false
      } finally {
        this.loading = false
      }
    },
    async submitQuiz(
      courseId: number,
      answers: Record<string, string>
    ): Promise<boolean> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          attempt: CourseQuizAttempt
        }>(`/api/agri-skills/courses/${courseId}/quiz`, {
          method: 'POST',
          body: JSON.stringify({ answers })
        })
        const attempt = { ...response.attempt, is_formal: true }
        this.attempts = [
          ...this.attempts.map(item =>
            item.course_id === courseId
              ? { ...item, is_formal: false }
              : item
          ),
          attempt
        ]
        return true
      } catch (error) {
        this.captureError(error, '课后测验提交失败')
        return false
      } finally {
        this.loading = false
      }
    }
  }
})
