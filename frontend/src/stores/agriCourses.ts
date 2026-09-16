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
  progressErrorsByCourse: Record<number, string>
  activeQuiz: CourseQuiz | null
  attempts: CourseQuizAttempt[]
  loading: boolean
  error: string
  recommendationError: string
}

function hasOwn(course: AgriCourse, key: keyof AgriCourse): boolean {
  return Object.prototype.hasOwnProperty.call(course, key)
}

interface MetadataState {
  present: boolean
  valid: boolean
}

function publicationMetadata(course: AgriCourse): MetadataState {
  if (hasOwn(course, 'status')) {
    return {
      present: true,
      valid: typeof course.status === 'string' && course.status === 'published'
    }
  }
  if (hasOwn(course, 'publication_status')) {
    return {
      present: true,
      valid:
        typeof course.publication_status === 'string' &&
        course.publication_status === 'published'
    }
  }
  if (hasOwn(course, 'is_published')) {
    return {
      present: true,
      valid: course.is_published === true
    }
  }
  return { present: false, valid: true }
}

function directionMetadata(course: AgriCourse): MetadataState {
  if (hasOwn(course, 'direction')) {
    return {
      present: true,
      valid:
        typeof course.direction === 'string' &&
        course.direction === 'agriculture'
    }
  }
  if (hasOwn(course, 'learning_direction')) {
    return {
      present: true,
      valid:
        typeof course.learning_direction === 'string' &&
        course.learning_direction === 'agriculture'
    }
  }
  return { present: false, valid: true }
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : fallback
}

function isEligibleCourse(course: AgriCourse): boolean {
  const publication = publicationMetadata(course)
  const direction = directionMetadata(course)
  return publication.valid && direction.present && direction.valid
}

function isEligibleRecommendation(course: AgriCourse): boolean {
  const publication = publicationMetadata(course)
  const direction = directionMetadata(course)
  return (
    Number.isInteger(course.id) &&
    course.id > 0 &&
    typeof course.title === 'string' &&
    course.title.trim() !== '' &&
    publication.valid &&
    direction.valid
  )
}

export const useAgriCoursesStore = defineStore('agriCourses', {
  state: (): AgriCoursesState => ({
    courses: [],
    recommendations: [],
    progressByCourse: {},
    progressErrorsByCourse: {},
    activeQuiz: null,
    attempts: [],
    loading: false,
    error: '',
    recommendationError: ''
  }),
  actions: {
    captureError(error: unknown, fallback: string) {
      this.error = errorMessage(error, fallback)
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

        this.progressErrorsByCourse = {}
        const progressErrors: Record<number, string> = {}
        const progressEntries = await Promise.all(
          courses.map(async course => {
            try {
              const progressResponse = await apiFetch<{
                success: true
                progress: CourseProgress
              }>(`/api/agri-skills/courses/${course.id}/progress`)
              return [course.id, progressResponse.progress] as const
            } catch (error) {
              progressErrors[course.id] = errorMessage(
                error,
                '学习进度加载失败'
              )
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
        this.progressErrorsByCourse = progressErrors
      } catch (error) {
        this.captureError(error, '课程加载失败')
      } finally {
        this.loading = false
      }
    },
    async loadProgress(courseId: number): Promise<boolean> {
      this.loading = true

      try {
        const response = await apiFetch<{
          success: true
          progress: CourseProgress
        }>(`/api/agri-skills/courses/${courseId}/progress`)
        this.progressByCourse[courseId] = response.progress
        delete this.progressErrorsByCourse[courseId]
        return true
      } catch (error) {
        this.progressErrorsByCourse[courseId] = errorMessage(
          error,
          '学习进度加载失败'
        )
        return false
      } finally {
        this.loading = false
      }
    },
    async loadRecommendations(): Promise<boolean> {
      this.loading = true
      this.recommendationError = ''

      try {
        const response = await apiFetch<{
          success: true
          courses: AgriCourse[]
        }>('/api/agri-skills/recommendations')
        this.recommendations = response.courses.filter(isEligibleRecommendation)
        return true
      } catch (error) {
        this.recommendationError = errorMessage(error, '推荐课程加载失败')
        return false
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
        delete this.progressErrorsByCourse[courseId]

        if (
          response.progress.completed_at !== null ||
          response.progress.progress_percent >= 80
        ) {
          this.recommendations = this.recommendations.filter(
            course => course.id !== courseId
          )
          return await this.loadRecommendations()
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
