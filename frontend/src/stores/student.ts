import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type {
  ApiFieldErrors,
  CourseSummary,
  LearningDirection,
  StudentProfile
} from '@/api/types'

interface ProfileResponse {
  success: true
  profile: StudentProfile
}

interface CoursesResponse {
  success: true
  courses: CourseSummary[]
}

interface StudentState {
  profile: StudentProfile | null
  courses: CourseSummary[]
  loadingProfile: boolean
  savingProfile: boolean
  loadingCourses: boolean
  error: string
  fieldErrors: ApiFieldErrors
  courseRequestId: number
}

export const useStudentStore = defineStore('student', {
  state: (): StudentState => ({
    profile: null,
    courses: [],
    loadingProfile: false,
    savingProfile: false,
    loadingCourses: false,
    error: '',
    fieldErrors: {},
    courseRequestId: 0
  }),
  actions: {
    captureError(error: unknown, fallback: string) {
      if (error instanceof ApiError) {
        this.error = error.message
        this.fieldErrors = error.errors
        return
      }

      this.error = error instanceof Error ? error.message : fallback
      this.fieldErrors = {}
    },
    async loadProfile() {
      this.loadingProfile = true
      this.error = ''
      this.fieldErrors = {}

      try {
        const response = await apiFetch<ProfileResponse>('/api/student/profile')
        this.profile = response.profile
        return response.profile
      } catch (error) {
        this.captureError(error, '个人资料加载失败')
        return null
      } finally {
        this.loadingProfile = false
      }
    },
    async saveProfile(payload: StudentProfile) {
      this.savingProfile = true
      this.error = ''
      this.fieldErrors = {}

      try {
        const response = await apiFetch<ProfileResponse>('/api/student/profile', {
          method: 'PUT',
          body: JSON.stringify(payload)
        })
        this.profile = response.profile
        return response.profile
      } catch (error) {
        this.captureError(error, '个人资料保存失败')
        return null
      } finally {
        this.savingProfile = false
      }
    },
    async loadCourses(direction: Exclude<LearningDirection, 'comprehensive'>) {
      const requestId = this.courseRequestId + 1
      this.courseRequestId = requestId
      this.loadingCourses = true
      this.error = ''
      this.fieldErrors = {}
      this.courses = []

      try {
        const response = await apiFetch<CoursesResponse>(
          `/api/student/courses?direction=${encodeURIComponent(direction)}`
        )
        if (requestId === this.courseRequestId) {
          this.courses = response.courses
        }
        return response.courses
      } catch (error) {
        if (requestId === this.courseRequestId) {
          this.captureError(error, '课程加载失败')
        }
        return null
      } finally {
        if (requestId === this.courseRequestId) {
          this.loadingCourses = false
        }
      }
    }
  }
})
