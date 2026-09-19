import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type {
  TeacherAnnouncement,
  TeacherAnnouncementPayload,
  TeacherComment,
  TeacherCommentFilters,
  TeacherCourse,
  TeacherCourseFilters,
  TeacherCoursePayload,
  TeacherDashboard,
  TeacherMedia,
  TeacherQuiz,
  TeacherQuizGeneratePayload,
  TeacherQuizSavePayload,
  TeacherReport
} from '@/api/types'

const API_PREFIX = '/api/teacher'

interface TeacherCourseResponse {
  success: true
  course: TeacherCourse
}

interface TeacherQuizResponse {
  success: true
  quiz: TeacherQuiz
}

interface TeacherConsoleState {
  courses: TeacherCourse[]
  quizDraft: TeacherQuiz | null
  lastUploadedMedia: TeacherMedia | null
  announcements: TeacherAnnouncement[]
  comments: TeacherComment[]
  dashboard: TeacherDashboard | null
  reports: TeacherReport[]
  loading: boolean
  reportLoading: boolean
  error: string
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : fallback
}

function replaceCourse(
  courses: TeacherCourse[],
  course: TeacherCourse
): TeacherCourse[] {
  return [course, ...courses.filter(item => item.id !== course.id)]
}

function replaceAnnouncement(
  announcements: TeacherAnnouncement[],
  announcement: TeacherAnnouncement
): TeacherAnnouncement[] {
  return [
    announcement,
    ...announcements.filter(
      item => item.announcement_id !== announcement.announcement_id
    )
  ]
}

function replaceComment(
  comments: TeacherComment[],
  comment: TeacherComment
): TeacherComment[] {
  const existingIndex = comments.findIndex(
    item => item.comment_id === comment.comment_id
  )
  if (existingIndex === -1) {
    return [...comments, comment]
  }
  return comments.map(item =>
    item.comment_id === comment.comment_id ? comment : item
  )
}

function replaceReport(
  reports: TeacherReport[],
  report: TeacherReport
): TeacherReport[] {
  return [
    report,
    ...reports.filter(item => item.report_id !== report.report_id)
  ]
}

export const useTeacherConsoleStore = defineStore('teacherConsole', {
  state: (): TeacherConsoleState => ({
    courses: [],
    quizDraft: null,
    lastUploadedMedia: null,
    announcements: [],
    comments: [],
    dashboard: null,
    reports: [],
    loading: false,
    reportLoading: false,
    error: ''
  }),
  actions: {
    captureError(error: unknown, fallback: string) {
      this.error = errorMessage(error, fallback)
    },
    async loadCourses(
      filters: TeacherCourseFilters = {}
    ): Promise<TeacherCourse[]> {
      this.loading = true
      this.error = ''
      try {
        const query = new URLSearchParams()
        if (filters.direction) {
          query.set('direction', filters.direction)
        }
        if (filters.status) {
          query.set('status', filters.status)
        }
        const suffix = query.toString() ? `?${query.toString()}` : ''
        const response = await apiFetch<{
          success: true
          courses: TeacherCourse[]
        }>(`${API_PREFIX}/courses${suffix}`)
        this.courses = response.courses
        return this.courses
      } catch (error) {
        this.captureError(error, '课程列表加载失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async createCourse(
      payload: TeacherCoursePayload
    ): Promise<TeacherCourse> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<TeacherCourseResponse>(
          `${API_PREFIX}/courses`,
          {
            method: 'POST',
            body: JSON.stringify(payload)
          }
        )
        this.courses = replaceCourse(this.courses, response.course)
        return response.course
      } catch (error) {
        this.captureError(error, '课程创建失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async saveCourse(
      courseId: number,
      payload: TeacherCoursePayload
    ): Promise<TeacherCourse> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<TeacherCourseResponse>(
          `${API_PREFIX}/courses/${courseId}`,
          {
            method: 'PUT',
            body: JSON.stringify(payload)
          }
        )
        this.courses = replaceCourse(this.courses, response.course)
        return response.course
      } catch (error) {
        this.captureError(error, '课程保存失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async submitCourse(
      courseId: number,
      expectedVersion: number
    ): Promise<TeacherCourse> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<TeacherCourseResponse>(
          `${API_PREFIX}/courses/${courseId}/submit`,
          {
            method: 'POST',
            body: JSON.stringify({
              expected_version: expectedVersion
            })
          }
        )
        this.courses = replaceCourse(this.courses, response.course)
        return response.course
      } catch (error) {
        this.captureError(error, '课程提交失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async offlineCourse(
      courseId: number,
      expectedVersion: number
    ): Promise<TeacherCourse> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<TeacherCourseResponse>(
          `${API_PREFIX}/courses/${courseId}/offline`,
          {
            method: 'POST',
            body: JSON.stringify({
              expected_version: expectedVersion
            })
          }
        )
        this.courses = replaceCourse(this.courses, response.course)
        return response.course
      } catch (error) {
        this.captureError(error, '课程下架失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async relistCourse(
      courseId: number,
      expectedVersion: number
    ): Promise<TeacherCourse> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<TeacherCourseResponse>(
          `${API_PREFIX}/courses/${courseId}/relist`,
          {
            method: 'POST',
            body: JSON.stringify({
              expected_version: expectedVersion
            })
          }
        )
        this.courses = replaceCourse(this.courses, response.course)
        return response.course
      } catch (error) {
        this.captureError(error, '课程重新上架失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async uploadVideo(file: File): Promise<TeacherMedia> {
      this.loading = true
      this.error = ''
      try {
        const body = new FormData()
        body.append('file', file)
        const response = await apiFetch<{
          success: true
          media: TeacherMedia
        }>(`${API_PREFIX}/uploads/video`, {
          method: 'POST',
          body
        })
        this.lastUploadedMedia = response.media
        return response.media
      } catch (error) {
        this.captureError(error, '视频上传失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async generateQuiz(
      courseId: number,
      payload: TeacherQuizGeneratePayload
    ): Promise<TeacherQuiz> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<TeacherQuizResponse>(
          `${API_PREFIX}/courses/${courseId}/quiz/generate`,
          {
            method: 'POST',
            body: JSON.stringify(payload)
          }
        )
        this.quizDraft = response.quiz
        return response.quiz
      } catch (error) {
        this.captureError(error, '测验生成失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async loadQuiz(courseId: number): Promise<TeacherQuiz | null> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<{
          success: true
          quiz: TeacherQuiz | null
        }>(`${API_PREFIX}/courses/${courseId}/quiz`)
        this.quizDraft = response.quiz
        return response.quiz
      } catch (error) {
        this.captureError(error, '测验加载失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async saveQuiz(
      courseId: number,
      payload: TeacherQuizSavePayload
    ): Promise<TeacherQuiz> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<TeacherQuizResponse>(
          `${API_PREFIX}/courses/${courseId}/quiz`,
          {
            method: 'POST',
            body: JSON.stringify(payload)
          }
        )
        this.quizDraft = response.quiz
        return response.quiz
      } catch (error) {
        this.captureError(error, '测验保存失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async loadAnnouncements(): Promise<TeacherAnnouncement[]> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<{
          success: true
          announcements: TeacherAnnouncement[]
        }>(`${API_PREFIX}/announcements`)
        this.announcements = response.announcements
        return this.announcements
      } catch (error) {
        this.captureError(error, '公告加载失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async publishAnnouncement(
      payload: TeacherAnnouncementPayload
    ): Promise<TeacherAnnouncement> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<{
          success: true
          announcement: TeacherAnnouncement
        }>(`${API_PREFIX}/announcements`, {
          method: 'POST',
          body: JSON.stringify(payload)
        })
        this.announcements = replaceAnnouncement(
          this.announcements,
          response.announcement
        )
        return response.announcement
      } catch (error) {
        this.captureError(error, '公告发布失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async loadComments(
      filters: TeacherCommentFilters = {}
    ): Promise<TeacherComment[]> {
      this.loading = true
      this.error = ''
      try {
        const query = new URLSearchParams()
        if (filters.content_type) {
          query.set('content_type', filters.content_type)
        }
        if (filters.content_id) {
          query.set('content_id', filters.content_id)
        }
        const suffix = query.toString() ? `?${query.toString()}` : ''
        const response = await apiFetch<{
          success: true
          comments: TeacherComment[]
        }>(`${API_PREFIX}/comments${suffix}`)
        this.comments = response.comments
        return this.comments
      } catch (error) {
        this.captureError(error, '评论加载失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async replyComment(
      commentId: string,
      body: string
    ): Promise<TeacherComment> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<{
          success: true
          comment: TeacherComment
        }>(
          `${API_PREFIX}/comments/${encodeURIComponent(
            commentId
          )}/replies`,
          {
            method: 'POST',
            body: JSON.stringify({ body })
          }
        )
        this.comments = replaceComment(this.comments, response.comment)
        return response.comment
      } catch (error) {
        this.captureError(error, '评论回复失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async loadDashboard(): Promise<TeacherDashboard> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<{
          success: true
          dashboard: TeacherDashboard
        }>(`${API_PREFIX}/dashboard`)
        this.dashboard = response.dashboard
        return response.dashboard
      } catch (error) {
        this.captureError(error, '教师看板加载失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async loadReports(): Promise<TeacherReport[]> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<{
          success: true
          reports: TeacherReport[]
        }>(`${API_PREFIX}/reports`)
        this.reports = response.reports
        return this.reports
      } catch (error) {
        this.captureError(error, '学情报告加载失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async generateReport(): Promise<TeacherReport> {
      this.reportLoading = true
      this.error = ''
      try {
        const response = await apiFetch<{
          success: true
          report: TeacherReport
        }>(`${API_PREFIX}/reports`, { method: 'POST' })
        this.reports = replaceReport(this.reports, response.report)
        return response.report
      } catch (error) {
        this.captureError(error, '学情报告生成失败')
        throw error
      } finally {
        this.reportLoading = false
      }
    }
  }
})
