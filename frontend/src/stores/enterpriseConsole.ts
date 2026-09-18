import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type {
  ApplicationStatus,
  EnterpriseApplicationDetail,
  EnterpriseApplicationFilters,
  EnterpriseApplicationSummary,
  EnterpriseDashboard,
  EnterpriseJob,
  EnterpriseJobPayload,
  InterestTag,
  JobReviewStatus
} from '@/api/types'

const API_PREFIX = '/api/enterprise'

interface EnterpriseConsoleState {
  dashboard: EnterpriseDashboard
  jobs: EnterpriseJob[]
  jobReviewFilter: JobReviewStatus | 'all'
  jobCategories: InterestTag[]
  applications: EnterpriseApplicationSummary[]
  applicationFilters: EnterpriseApplicationFilters
  activeApplication: EnterpriseApplicationDetail | null
  loading: boolean
  saving: boolean
  error: string
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : fallback
}

export const useEnterpriseConsoleStore = defineStore(
  'enterpriseConsole',
  {
    state: (): EnterpriseConsoleState => ({
      dashboard: {
        active_job_count: 0,
        received_resume_count: 0
      },
      jobs: [],
      jobReviewFilter: 'all',
      jobCategories: [],
      applications: [],
      applicationFilters: {},
      activeApplication: null,
      loading: false,
      saving: false,
      error: ''
    }),
    actions: {
      async loadDashboard(): Promise<boolean> {
        this.loading = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            dashboard: EnterpriseDashboard
          }>(`${API_PREFIX}/dashboard`)
          this.dashboard = response.dashboard
          return true
        } catch (error) {
          this.error = errorMessage(error, '企业看板加载失败')
          return false
        } finally {
          this.loading = false
        }
      },
      async loadJobCategories(): Promise<boolean> {
        this.loading = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            tags: InterestTag[]
          }>('/api/interest-tags')
          this.jobCategories = response.tags.filter(
            tag => tag.group_key === 'job'
          )
          return true
        } catch (error) {
          this.error = errorMessage(error, '职位类别加载失败')
          return false
        } finally {
          this.loading = false
        }
      },
      async loadJobs(
        reviewStatus: JobReviewStatus | 'all' = 'all'
      ): Promise<boolean> {
        this.jobReviewFilter = reviewStatus
        this.loading = true
        this.error = ''
        try {
          const path =
            reviewStatus === 'all'
              ? `${API_PREFIX}/jobs`
              : `${API_PREFIX}/jobs?review_status=${encodeURIComponent(
                  reviewStatus
                )}`
          const response = await apiFetch<{
            success: true
            jobs: EnterpriseJob[]
          }>(path)
          this.jobs = response.jobs
          return true
        } catch (error) {
          this.error = errorMessage(error, '职位列表加载失败')
          return false
        } finally {
          this.loading = false
        }
      },
      async createJob(
        payload: EnterpriseJobPayload
      ): Promise<EnterpriseJob | null> {
        this.saving = true
        this.error = ''
        try {
          const {
            title,
            salary,
            location,
            category_id,
            description
          } = payload
          const response = await apiFetch<{
            success: true
            job: EnterpriseJob
          }>(`${API_PREFIX}/jobs`, {
            method: 'POST',
            body: JSON.stringify({
              title,
              salary,
              location,
              category_id,
              description
            })
          })
          await this.loadDashboard()
          await this.loadJobs(this.jobReviewFilter)
          return response.job
        } catch (error) {
          this.error = errorMessage(error, '职位创建失败')
          return null
        } finally {
          this.saving = false
        }
      },
      async editJob(
        jobId: string,
        expectedVersion: number,
        payload: EnterpriseJobPayload
      ): Promise<EnterpriseJob | null> {
        this.saving = true
        this.error = ''
        try {
          const {
            title,
            salary,
            location,
            category_id,
            description
          } = payload
          const response = await apiFetch<{
            success: true
            job: EnterpriseJob
          }>(
            `${API_PREFIX}/jobs/${encodeURIComponent(jobId)}`,
            {
              method: 'PUT',
              body: JSON.stringify({
                expected_version: expectedVersion,
                title,
                salary,
                location,
                category_id,
                description
              })
            }
          )
          await this.loadDashboard()
          await this.loadJobs(this.jobReviewFilter)
          return response.job
        } catch (error) {
          this.error = errorMessage(error, '职位保存失败')
          return null
        } finally {
          this.saving = false
        }
      },
      async deleteJob(job: EnterpriseJob): Promise<boolean> {
        this.saving = true
        this.error = ''
        try {
          await apiFetch<{
            success: true
            deleted: Record<string, unknown>
          }>(
            `${API_PREFIX}/jobs/${encodeURIComponent(job.job_id)}`,
            {
              method: 'DELETE',
              body: JSON.stringify({
                expected_version: job.version
              })
            }
          )
          await this.loadDashboard()
          await this.loadJobs(this.jobReviewFilter)
          return true
        } catch (error) {
          this.error = errorMessage(error, '职位删除失败')
          return false
        } finally {
          this.saving = false
        }
      },
      async loadApplications(
        filters: EnterpriseApplicationFilters = {}
      ): Promise<boolean> {
        this.applicationFilters = filters
        this.loading = true
        this.error = ''
        try {
          const query: string[] = []
          if (filters.job_id?.trim()) {
            query.push(
              `job_id=${encodeURIComponent(filters.job_id.trim())}`
            )
          }
          if (filters.status) {
            query.push(
              `status=${encodeURIComponent(filters.status)}`
            )
          }
          if (filters.submitted_from?.trim()) {
            query.push(
              `submitted_from=${encodeURIComponent(
                filters.submitted_from.trim()
              )}`
            )
          }
          if (filters.submitted_to?.trim()) {
            query.push(
              `submitted_to=${encodeURIComponent(
                filters.submitted_to.trim()
              )}`
            )
          }
          if (filters.sort) {
            query.push(`sort=${encodeURIComponent(filters.sort)}`)
          }
          const suffix = query.length ? `?${query.join('&')}` : ''
          const response = await apiFetch<{
            success: true
            applications: EnterpriseApplicationSummary[]
          }>(`${API_PREFIX}/applications${suffix}`)
          this.applications = response.applications
          return true
        } catch (error) {
          this.error = errorMessage(error, '申请列表加载失败')
          return false
        } finally {
          this.loading = false
        }
      },
      async loadApplication(applicationId: string): Promise<boolean> {
        if (
          this.activeApplication?.application_id !== applicationId
        ) {
          this.activeApplication = null
        }
        this.loading = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            application: EnterpriseApplicationDetail
          }>(
            `${API_PREFIX}/applications/${encodeURIComponent(
              applicationId
            )}`
          )
          this.activeApplication = response.application
          return true
        } catch (error) {
          this.error = errorMessage(error, '申请详情加载失败')
          return false
        } finally {
          this.loading = false
        }
      },
      async changeApplicationStatus(
        applicationId: string,
        expectedVersion: number,
        status: Exclude<ApplicationStatus, 'pending'>
      ): Promise<boolean> {
        this.saving = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            application: EnterpriseApplicationSummary
            changed: boolean
          }>(
            `${API_PREFIX}/applications/${encodeURIComponent(
              applicationId
            )}/status`,
            {
              method: 'PATCH',
              body: JSON.stringify({
                expected_version: expectedVersion,
                status
              })
            }
          )
          if (
            this.activeApplication?.application_id === applicationId
          ) {
            this.activeApplication = {
              ...this.activeApplication,
              ...response.application
            }
          }
          await this.loadDashboard()
          await this.loadApplications(this.applicationFilters)
          return true
        } catch (error) {
          this.error = errorMessage(error, '申请状态更新失败')
          return false
        } finally {
          this.saving = false
        }
      }
    }
  }
)
