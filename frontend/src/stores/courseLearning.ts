import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type {
  CourseDirection,
  CourseProgress,
  CourseQuiz,
  CourseQuizAttempt,
  EcommerceCourse,
  HandcraftCourse
} from '@/api/types'

const DEFAULT_API_PREFIX = '/api/agri-skills'
const DEFAULT_DIRECTION = 'agriculture' as const

export type CourseLearningCourse = EcommerceCourse | HandcraftCourse

interface CourseLearningState {
  requestEpoch: number
  apiPrefix: string
  direction: CourseDirection
  courses: CourseLearningCourse[]
  recommendations: CourseLearningCourse[]
  progressByCourse: Record<number, CourseProgress>
  progressErrorsByCourse: Record<number, string>
  activeQuiz: CourseQuiz | null
  attempts: CourseQuizAttempt[]
  justSubmittedCourseId: number | null
  loading: boolean
  error: string
  recommendationError: string
}

function hasOwn(
  course: CourseLearningCourse,
  key: keyof CourseLearningCourse
): boolean {
  return Object.prototype.hasOwnProperty.call(course, key)
}

interface MetadataState {
  present: boolean
  valid: boolean
}

function publicationMetadata(
  course: CourseLearningCourse
): MetadataState {
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

function directionMetadata(
  course: CourseLearningCourse,
  direction: CourseDirection
): MetadataState {
  if (hasOwn(course, 'direction')) {
    return {
      present: true,
      valid:
        typeof course.direction === 'string' && course.direction === direction
    }
  }
  if (hasOwn(course, 'learning_direction')) {
    return {
      present: true,
      valid:
        typeof course.learning_direction === 'string' &&
        course.learning_direction === direction
    }
  }
  return { present: false, valid: true }
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.status === 401 && error.redirect) {
    return fallback
  }
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : fallback
}

function isEligibleCourse(
  course: CourseLearningCourse,
  direction: CourseDirection
): boolean {
  const publication = publicationMetadata(course)
  const courseDirection = directionMetadata(course, direction)
  return publication.valid && courseDirection.present && courseDirection.valid
}

function isEligibleRecommendation(
  course: CourseLearningCourse,
  direction: CourseDirection
): boolean {
  const publication = publicationMetadata(course)
  const courseDirection = directionMetadata(course, direction)
  return (
    Number.isInteger(course.id) &&
    course.id > 0 &&
    typeof course.title === 'string' &&
    course.title.trim() !== '' &&
    publication.valid &&
    courseDirection.valid
  )
}

export const useCourseLearningStore = defineStore('courseLearning', {
  state: (): CourseLearningState => ({
    requestEpoch: 0,
    apiPrefix: DEFAULT_API_PREFIX,
    direction: DEFAULT_DIRECTION,
    courses: [],
    recommendations: [],
    progressByCourse: {},
    progressErrorsByCourse: {},
    activeQuiz: null,
    attempts: [],
    justSubmittedCourseId: null,
    loading: false,
    error: '',
    recommendationError: ''
  }),
  actions: {
    configure(apiPrefix: string, direction: CourseDirection) {
      if (this.apiPrefix === apiPrefix && this.direction === direction) return
      this.requestEpoch += 1
      this.apiPrefix = apiPrefix
      this.direction = direction
      this.courses = []
      this.recommendations = []
      this.progressByCourse = {}
      this.progressErrorsByCourse = {}
      this.activeQuiz = null
      this.attempts = []
      this.justSubmittedCourseId = null
      this.loading = false
      this.error = ''
      this.recommendationError = ''
    },
    captureError(error: unknown, fallback: string) {
      this.error = errorMessage(error, fallback)
    },
    async loadCourses() {
      const epoch = this.requestEpoch
      const direction = this.direction
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          courses: CourseLearningCourse[]
        }>(`${this.apiPrefix}/courses`)
        if (this.requestEpoch !== epoch) return false
        const courses = response.courses.filter(course =>
          isEligibleCourse(course, direction)
        )
        this.courses = courses

        this.progressErrorsByCourse = {}
        const progressErrors: Record<number, string> = {}
        const progressEntries = await Promise.all(
          courses.map(async course => {
            try {
              const progressResponse = await apiFetch<{
                success: true
                progress: CourseProgress
              }>(`${this.apiPrefix}/courses/${course.id}/progress`)
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
        if (this.requestEpoch !== epoch) return false
        this.progressByCourse = Object.fromEntries(
          progressEntries.filter(
            (
              entry
            ): entry is readonly [number, CourseProgress] => entry !== null
          )
        )
        this.progressErrorsByCourse = progressErrors
        return true
      } catch (error) {
        if (this.requestEpoch === epoch) {
          this.captureError(error, '课程加载失败')
        }
        return false
      } finally {
        if (this.requestEpoch === epoch) {
          this.loading = false
        }
      }
    },
    async loadProgress(courseId: number): Promise<boolean> {
      const epoch = this.requestEpoch
      this.loading = true

      try {
        const response = await apiFetch<{
          success: true
          progress: CourseProgress
        }>(`${this.apiPrefix}/courses/${courseId}/progress`)
        if (this.requestEpoch !== epoch) return false
        this.progressByCourse[courseId] = response.progress
        delete this.progressErrorsByCourse[courseId]
        return true
      } catch (error) {
        if (this.requestEpoch !== epoch) return false
        this.progressErrorsByCourse[courseId] = errorMessage(
          error,
          '学习进度加载失败'
        )
        return false
      } finally {
        if (this.requestEpoch === epoch) {
          this.loading = false
        }
      }
    },
    async loadRecommendations(): Promise<boolean> {
      const epoch = this.requestEpoch
      const direction = this.direction
      this.loading = true
      this.recommendationError = ''

      try {
        const response = await apiFetch<{
          success: true
          courses: CourseLearningCourse[]
        }>(`${this.apiPrefix}/recommendations`)
        if (this.requestEpoch !== epoch) return false
        this.recommendations = response.courses.filter(course =>
          isEligibleRecommendation(course, direction)
        )
        return true
      } catch (error) {
        if (this.requestEpoch !== epoch) return false
        this.recommendationError = errorMessage(error, '推荐课程加载失败')
        return false
      } finally {
        if (this.requestEpoch === epoch) {
          this.loading = false
        }
      }
    },
    async saveProgress(
      courseId: number,
      positionSeconds: number,
      watchedDeltaSeconds: number
    ): Promise<boolean> {
      const epoch = this.requestEpoch
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          progress: CourseProgress
        }>(`${this.apiPrefix}/courses/${courseId}/progress`, {
          method: 'PUT',
          body: JSON.stringify({
            position_seconds: positionSeconds,
            watched_delta_seconds: watchedDeltaSeconds
          })
        })
        if (this.requestEpoch !== epoch) return false
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
        if (this.requestEpoch !== epoch) return false
        this.captureError(error, '学习进度保存失败')
        return false
      } finally {
        if (this.requestEpoch === epoch) {
          this.loading = false
        }
      }
    },
    async loadQuiz(courseId: number): Promise<boolean> {
      const epoch = this.requestEpoch
      this.loading = true
      this.error = ''
      this.justSubmittedCourseId = null

      try {
        const response = await apiFetch<{
          success: true
          quiz: CourseQuiz
        }>(`${this.apiPrefix}/courses/${courseId}/quiz`)
        if (this.requestEpoch !== epoch) return false
        this.activeQuiz = response.quiz
        const attemptsResponse = await apiFetch<{
          success: true
          attempts: CourseQuizAttempt[]
        }>(`${this.apiPrefix}/courses/${courseId}/quiz/attempts`)
        if (this.requestEpoch !== epoch) return false
        this.attempts = [
          ...this.attempts.filter(
            attempt => attempt.course_id !== courseId
          ),
          ...attemptsResponse.attempts
        ]
        return true
      } catch (error) {
        if (this.requestEpoch !== epoch) return false
        this.activeQuiz = null
        this.captureError(error, '课后测验加载失败')
        return false
      } finally {
        if (this.requestEpoch === epoch) {
          this.loading = false
        }
      }
    },
    async submitQuiz(
      courseId: number,
      answers: Record<string, string>
    ): Promise<boolean> {
      const epoch = this.requestEpoch
      this.loading = true
      this.error = ''
      this.justSubmittedCourseId = null

      try {
        const response = await apiFetch<{
          success: true
          attempt: CourseQuizAttempt
        }>(`${this.apiPrefix}/courses/${courseId}/quiz`, {
          method: 'POST',
          body: JSON.stringify({ answers })
        })
        if (this.requestEpoch !== epoch) return false
        const attempt = {
          ...response.attempt,
          is_formal: true,
          is_current: true,
          is_latest: true
        }
        this.attempts = [
          attempt,
          ...this.attempts.map(item =>
            item.course_id === courseId
              ? {
                  ...item,
                  is_formal: false,
                  is_current: false,
                  is_latest: false
                }
              : item
          )
        ]
        this.justSubmittedCourseId = courseId
        return true
      } catch (error) {
        if (this.requestEpoch !== epoch) return false
        this.captureError(error, '课后测验提交失败')
        return false
      } finally {
        if (this.requestEpoch === epoch) {
          this.loading = false
        }
      }
    }
  }
})
