import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type {
  ApiFieldErrors,
  JobFavorite,
  JobMatchingJob,
  ResumeOptimizationOffer,
  ResumePayload,
  SkillProfile,
  StudentApplication,
  StudentResume
} from '@/api/types'

const API_PREFIX = '/api/job-matching'

interface SaveResumePayload extends ResumePayload {
  expected_version: number
}

interface FavoriteRemoval {
  job_id: string
  favorited: false
}

interface JobMatchingState {
  resume: StudentResume | null
  optimizationOffer: ResumeOptimizationOffer | null
  skillProfile: SkillProfile | null
  jobs: JobMatchingJob[]
  recommendedJobs: JobMatchingJob[]
  activeJob: JobMatchingJob | null
  applications: StudentApplication[]
  favorites: JobFavorite[]
  loading: boolean
  saving: boolean
  error: string
  errorCode: string
  fieldErrors: ApiFieldErrors
}

export const useJobMatchingStore = defineStore('jobMatching', {
  state: (): JobMatchingState => ({
    resume: null,
    optimizationOffer: null,
    skillProfile: null,
    jobs: [],
    recommendedJobs: [],
    activeJob: null,
    applications: [],
    favorites: [],
    loading: false,
    saving: false,
    error: '',
    errorCode: '',
    fieldErrors: {}
  }),
  actions: {
    captureError(error: unknown, fallback = '就业对接请求失败') {
      if (error instanceof ApiError) {
        this.error = error.message
        this.errorCode = error.code ?? ''
        this.fieldErrors = error.errors
        return
      }
      this.error = error instanceof Error ? error.message : fallback
      this.errorCode = ''
      this.fieldErrors = {}
    },
    async loadResume() {
      this.loading = true
      this.error = ''
      this.errorCode = ''
      this.fieldErrors = {}
      try {
        const response = await apiFetch<{
          success: true
          resume: StudentResume
        }>(`${API_PREFIX}/resume`)
        this.resume = response.resume
        return this.resume
      } catch (error) {
        this.captureError(error)
        return null
      } finally {
        this.loading = false
      }
    },
    async saveResume(payload: SaveResumePayload) {
      this.saving = true
      this.error = ''
      this.errorCode = ''
      this.fieldErrors = {}
      try {
        const response = await apiFetch<{
          success: true
          resume: StudentResume
        }>(`${API_PREFIX}/resume`, {
          method: 'PUT',
          body: JSON.stringify({
            expected_version: payload.expected_version,
            education_experiences: payload.education_experiences,
            work_experiences: payload.work_experiences,
            skills: payload.skills
          })
        })
        this.resume = response.resume
        return this.resume
      } catch (error) {
        this.captureError(error)
        return null
      } finally {
        this.saving = false
      }
    },
    async optimizeResume(expectedVersion: number) {
      this.saving = true
      this.error = ''
      this.errorCode = ''
      this.fieldErrors = {}
      try {
        const response = await apiFetch<{
          success: true
          offer: ResumeOptimizationOffer
        }>(`${API_PREFIX}/resume/optimize`, {
          method: 'POST',
          body: JSON.stringify({ expected_version: expectedVersion })
        })
        this.optimizationOffer = response.offer
        return this.optimizationOffer
      } catch (error) {
        this.captureError(error)
        return null
      } finally {
        this.saving = false
      }
    },
    async adoptOptimization(offerId: string, expectedVersion: number) {
      this.saving = true
      this.error = ''
      this.errorCode = ''
      this.fieldErrors = {}
      try {
        const response = await apiFetch<{
          success: true
          resume: StudentResume
        }>(
          `${API_PREFIX}/resume/optimizations/${encodeURIComponent(
            offerId
          )}/adopt`,
          {
            method: 'POST',
            body: JSON.stringify({
              expected_version: expectedVersion
            })
          }
        )
        this.resume = response.resume
        if (this.optimizationOffer?.offer_id === offerId) {
          this.optimizationOffer = {
            ...this.optimizationOffer,
            status: 'adopted'
          }
        }
        return this.resume
      } catch (error) {
        this.captureError(error)
        return null
      } finally {
        this.saving = false
      }
    },
    async discardOptimization(offerId: string) {
      this.saving = true
      this.error = ''
      this.errorCode = ''
      this.fieldErrors = {}
      try {
        const response = await apiFetch<{
          success: true
          offer: ResumeOptimizationOffer
        }>(
          `${API_PREFIX}/resume/optimizations/${encodeURIComponent(
            offerId
          )}/discard`,
          { method: 'POST' }
        )
        this.optimizationOffer = response.offer
        return this.optimizationOffer
      } catch (error) {
        this.captureError(error)
        return null
      } finally {
        this.saving = false
      }
    },
    async loadSkillProfile() {
      this.loading = true
      this.error = ''
      this.errorCode = ''
      this.fieldErrors = {}
      try {
        const response = await apiFetch<{
          success: true
          profile: SkillProfile
        }>(`${API_PREFIX}/skill-profile`)
        this.skillProfile = response.profile
        return this.skillProfile
      } catch (error) {
        this.captureError(error)
        return null
      } finally {
        this.loading = false
      }
    },
    async saveSkillVisibility(visibleItemIds: string[]) {
      this.saving = true
      this.error = ''
      this.errorCode = ''
      this.fieldErrors = {}
      try {
        const response = await apiFetch<{
          success: true
          profile: SkillProfile
        }>(`${API_PREFIX}/skill-profile/visibility`, {
          method: 'PUT',
          body: JSON.stringify({
            visible_item_ids: visibleItemIds
          })
        })
        this.skillProfile = response.profile
        return this.skillProfile
      } catch (error) {
        this.captureError(error)
        return null
      } finally {
        this.saving = false
      }
    },
    async loadJobs() {
      this.loading = true
      this.error = ''
      this.errorCode = ''
      this.fieldErrors = {}
      try {
        const response = await apiFetch<{
          success: true
          jobs: JobMatchingJob[]
          recommended_jobs: JobMatchingJob[]
        }>(`${API_PREFIX}/jobs`)
        this.jobs = response.jobs
        this.recommendedJobs = response.recommended_jobs
        return true
      } catch (error) {
        this.captureError(error)
        return false
      } finally {
        this.loading = false
      }
    },
    async loadJob(jobId: string) {
      if (this.activeJob?.job_id !== jobId) {
        this.activeJob = null
      }
      this.loading = true
      this.error = ''
      this.errorCode = ''
      this.fieldErrors = {}
      try {
        const response = await apiFetch<{
          success: true
          job: JobMatchingJob
        }>(`${API_PREFIX}/jobs/${encodeURIComponent(jobId)}`)
        this.activeJob = response.job
        return this.activeJob
      } catch (error) {
        this.captureError(error)
        return null
      } finally {
        this.loading = false
      }
    },
    async submitApplication(
      jobId: string,
      attachSkillProfile: boolean
    ) {
      this.saving = true
      this.error = ''
      this.errorCode = ''
      this.fieldErrors = {}
      try {
        const response = await apiFetch<{
          success: true
          application: StudentApplication
        }>(
          `${API_PREFIX}/jobs/${encodeURIComponent(
            jobId
          )}/applications`,
          {
            method: 'POST',
            body: JSON.stringify({
              attach_skill_profile: attachSkillProfile
            })
          }
        )
        return response.application
      } catch (error) {
        this.captureError(error)
        return null
      } finally {
        this.saving = false
      }
    },
    async loadApplications() {
      this.loading = true
      this.error = ''
      this.errorCode = ''
      this.fieldErrors = {}
      try {
        const response = await apiFetch<{
          success: true
          applications: StudentApplication[]
        }>(`${API_PREFIX}/applications`)
        this.applications = response.applications
        return true
      } catch (error) {
        this.captureError(error)
        return false
      } finally {
        this.loading = false
      }
    },
    async loadFavorites() {
      this.loading = true
      this.error = ''
      this.errorCode = ''
      this.fieldErrors = {}
      try {
        const response = await apiFetch<{
          success: true
          favorites: JobFavorite[]
        }>(`${API_PREFIX}/favorites`)
        this.favorites = response.favorites
        return true
      } catch (error) {
        this.captureError(error)
        return false
      } finally {
        this.loading = false
      }
    },
    async addFavorite(jobId: string) {
      this.saving = true
      this.error = ''
      this.errorCode = ''
      this.fieldErrors = {}
      try {
        const response = await apiFetch<{
          success: true
          favorite: JobFavorite
        }>(
          `${API_PREFIX}/favorites/${encodeURIComponent(jobId)}`,
          { method: 'POST' }
        )
        const existingIndex = this.favorites.findIndex(
          favorite => favorite.job_id === response.favorite.job_id
        )
        if (existingIndex === -1) {
          this.favorites = [response.favorite, ...this.favorites]
        } else {
          this.favorites.splice(existingIndex, 1, response.favorite)
        }
        return response.favorite
      } catch (error) {
        this.captureError(error)
        return null
      } finally {
        this.saving = false
      }
    },
    async removeFavorite(jobId: string) {
      this.saving = true
      this.error = ''
      this.errorCode = ''
      this.fieldErrors = {}
      try {
        const response = await apiFetch<{
          success: true
          favorite: FavoriteRemoval
        }>(
          `${API_PREFIX}/favorites/${encodeURIComponent(jobId)}`,
          { method: 'DELETE' }
        )
        this.favorites = this.favorites.filter(
          favorite => favorite.job_id !== response.favorite.job_id
        )
        return true
      } catch (error) {
        this.captureError(error)
        return false
      } finally {
        this.saving = false
      }
    }
  }
})
