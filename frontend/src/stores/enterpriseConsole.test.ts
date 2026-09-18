import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type {
  EnterpriseApplicationDetail,
  EnterpriseApplicationSummary,
  EnterpriseDashboard,
  EnterpriseJob,
  EnterpriseJobPayload,
  InterestTag
} from '@/api/types'

import { useEnterpriseConsoleStore } from './enterpriseConsole'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const dashboardFixture: EnterpriseDashboard = {
  active_job_count: 2,
  received_resume_count: 5
}

const jobPayload: EnterpriseJobPayload = {
  title: '农业技术员',
  salary: '6k-8k',
  location: '广州',
  category_id: 9,
  description: '负责田间管理'
}

const pendingJob: EnterpriseJob = {
  ...jobPayload,
  job_id: 'job-1',
  enterprise_id: 7,
  category_name: '农业技术员',
  review_status: 'pending',
  version: 1,
  rejection_opinion: null,
  published_at: null,
  deleted_at: null,
  created_at: '2026-09-18T09:00:00+08:00',
  updated_at: '2026-09-18T09:00:00+08:00'
}

const applicationSummary: EnterpriseApplicationSummary = {
  application_id: 'application-1',
  student_id: 11,
  student_name: '张三',
  job_id: 'job-1',
  job_title: '农业技术员',
  submitted_at: '2026-09-18T10:00:00+08:00',
  status: 'pending',
  status_label: '待处理',
  status_version: 1,
  position_closed: false,
  position_closed_at: null,
  effective_status: 'pending',
  effective_status_label: '待处理'
}

const applicationDetail: EnterpriseApplicationDetail = {
  ...applicationSummary,
  resume_snapshot: {
    education: '本科',
    skills: ['田间管理']
  },
  skill_profile: {
    items: [{ title: '农业技术竞赛' }]
  },
  skill_profile_attached: true,
  status_history: []
}

function rejectedApiError(message: string): ApiError {
  return new ApiError(message, 503)
}

describe('enterpriseConsole store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('loads dashboard, job categories and jobs', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        dashboard: dashboardFixture
      } as never)
      .mockResolvedValueOnce({
        success: true,
        tags: [
          { id: 9, group_key: 'job', name: '农业技术员' },
          { id: 1, group_key: 'crop', name: '荔枝' }
        ] satisfies InterestTag[]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        jobs: [pendingJob]
      } as never)

    const store = useEnterpriseConsoleStore()
    await store.loadDashboard()
    await store.loadJobCategories()
    await store.loadJobs('pending')

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/enterprise/dashboard'
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(2, '/api/interest-tags')
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/enterprise/jobs?review_status=pending'
    )
    expect(store.dashboard).toEqual(dashboardFixture)
    expect(store.jobReviewFilter).toBe('pending')
    expect(store.jobCategories).toEqual([
      { id: 9, group_key: 'job', name: '农业技术员' }
    ])
    expect(store.jobs).toEqual([pendingJob])
  })

  it('keeps dashboard when dashboard loading fails', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      rejectedApiError('企业看板暂不可用')
    )
    const store = useEnterpriseConsoleStore()
    store.dashboard = dashboardFixture

    expect(await store.loadDashboard()).toBe(false)
    expect(store.error).toBe('企业看板暂不可用')
    expect(store.dashboard).toEqual(dashboardFixture)
  })

  it('keeps job categories when category loading fails', async () => {
    const categories: InterestTag[] = [
      { id: 9, group_key: 'job', name: '农业技术员' }
    ]
    mockedApiFetch.mockRejectedValueOnce(
      rejectedApiError('职位类别暂不可用')
    )
    const store = useEnterpriseConsoleStore()
    store.jobCategories = categories

    expect(await store.loadJobCategories()).toBe(false)
    expect(store.error).toBe('职位类别暂不可用')
    expect(store.jobCategories).toEqual(categories)
  })

  it('creates only editable fields and refreshes jobs and dashboard', async () => {
    const createdJob = {
      ...pendingJob,
      job_id: 'job-created'
    }
    const payloadWithServerFields = {
      ...jobPayload,
      job_id: 'forged-job',
      version: 99
    }
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        job: createdJob
      } as never)
      .mockResolvedValueOnce({
        success: true,
        dashboard: dashboardFixture
      } as never)
      .mockResolvedValueOnce({
        success: true,
        jobs: [createdJob]
      } as never)

    const store = useEnterpriseConsoleStore()
    store.jobReviewFilter = 'pending'

    expect(await store.createJob(payloadWithServerFields)).toEqual(createdJob)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/enterprise/jobs',
      {
        method: 'POST',
        body: JSON.stringify(jobPayload)
      }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/enterprise/dashboard'
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/enterprise/jobs?review_status=pending'
    )
    expect(store.jobs).toEqual([createdJob])
  })

  it('does not add a job when creation fails', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      rejectedApiError('职位创建暂不可用')
    )
    const store = useEnterpriseConsoleStore()
    store.jobs = [pendingJob]

    expect(await store.createJob(jobPayload)).toBeNull()
    expect(store.error).toBe('职位创建暂不可用')
    expect(store.jobs).toEqual([pendingJob])
    expect(mockedApiFetch).toHaveBeenCalledTimes(1)
  })

  it('edits an encoded job id with expected_version and refreshes jobs', async () => {
    const jobId = 'job /一'
    const currentJob = {
      ...pendingJob,
      job_id: jobId,
      version: 3
    }
    const editedJob = {
      ...currentJob,
      title: '高级农业技术员',
      version: 4
    }
    const payload = {
      ...jobPayload,
      title: '高级农业技术员'
    }
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        job: editedJob
      } as never)
      .mockResolvedValueOnce({
        success: true,
        dashboard: dashboardFixture
      } as never)
      .mockResolvedValueOnce({
        success: true,
        jobs: [editedJob]
      } as never)

    const store = useEnterpriseConsoleStore()
    store.jobs = [currentJob]

    expect(await store.editJob(jobId, currentJob.version, payload)).toEqual(
      editedJob
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/enterprise/jobs/job%20%2F%E4%B8%80',
      {
        method: 'PUT',
        body: JSON.stringify({
          expected_version: 3,
          ...payload
        })
      }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/enterprise/dashboard'
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/enterprise/jobs'
    )
    expect(store.jobs).toEqual([editedJob])
  })

  it('does not mutate a job when editing fails', async () => {
    const currentJob = {
      ...pendingJob,
      title: '原职位标题',
      version: 3
    }
    mockedApiFetch.mockRejectedValueOnce(
      rejectedApiError('职位保存暂不可用')
    )
    const store = useEnterpriseConsoleStore()
    store.jobs = [currentJob]

    expect(
      await store.editJob(currentJob.job_id, currentJob.version, {
        ...jobPayload,
        title: '不会保存的标题'
      })
    ).toBeNull()
    expect(store.error).toBe('职位保存暂不可用')
    expect(store.jobs).toEqual([currentJob])
  })

  it('deletes with expected_version and refreshes jobs and dashboard', async () => {
    const jobId = 'job /一'
    const job = {
      ...pendingJob,
      job_id: jobId,
      version: 4
    }
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        deleted: {
          deleted: true,
          changed: true
        }
      } as never)
      .mockResolvedValueOnce({
        success: true,
        dashboard: dashboardFixture
      } as never)
      .mockResolvedValueOnce({
        success: true,
        jobs: []
      } as never)

    const store = useEnterpriseConsoleStore()
    store.jobReviewFilter = 'pending'
    store.jobs = [job]

    expect(await store.deleteJob(job)).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/enterprise/jobs/job%20%2F%E4%B8%80',
      {
        method: 'DELETE',
        body: JSON.stringify({ expected_version: 4 })
      }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/enterprise/dashboard'
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/enterprise/jobs?review_status=pending'
    )
    expect(store.jobs).toEqual([])
  })

  it('keeps a job when deletion fails', async () => {
    const job = {
      ...pendingJob,
      job_id: 'job-delete-failure',
      version: 4
    }
    mockedApiFetch.mockRejectedValueOnce(
      rejectedApiError('职位删除暂不可用')
    )
    const store = useEnterpriseConsoleStore()
    store.jobs = [job]

    expect(await store.deleteJob(job)).toBe(false)
    expect(store.error).toBe('职位删除暂不可用')
    expect(store.jobs).toEqual([job])
  })

  it('serializes application filters and omits blank values', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        applications: [applicationSummary]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        applications: []
      } as never)
      .mockResolvedValueOnce({
        success: true,
        applications: []
      } as never)

    const store = useEnterpriseConsoleStore()
    await store.loadApplications({
      job_id: 'job-1',
      status: 'intent',
      submitted_from: '2026-09-01',
      submitted_to: '2026-09-18',
      sort: 'submitted_desc'
    })

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/enterprise/applications?job_id=job-1&status=intent&submitted_from=2026-09-01&submitted_to=2026-09-18&sort=submitted_desc'
    )
    expect(store.applications).toEqual([applicationSummary])

    await store.loadApplications({
      job_id: '',
      status: undefined,
      submitted_from: '',
      submitted_to: '',
      sort: undefined
    })

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/enterprise/applications'
    )

    await store.loadApplications({ job_id: 'job /一?&' })

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/enterprise/applications?job_id=job%20%2F%E4%B8%80%3F%26'
    )
  })

  it('loads an encoded application id and resets a previous detail', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        application: applicationDetail
      } as never)
      .mockRejectedValueOnce(new ApiError('申请不存在', 404))

    const store = useEnterpriseConsoleStore()

    expect(await store.loadApplication('application /一')).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/enterprise/applications/application%20%2F%E4%B8%80'
    )
    expect(store.activeApplication).toEqual(applicationDetail)

    expect(await store.loadApplication('application-2')).toBe(false)
    expect(store.activeApplication).toBeNull()
    expect(store.error).toBe('申请不存在')
  })

  it('changes status with expected_version and refreshes active data', async () => {
    const changedApplication = {
      ...applicationSummary,
      status: 'intent',
      status_label: '意向沟通',
      status_version: 2,
      effective_status: 'intent',
      effective_status_label: '意向沟通'
    } satisfies EnterpriseApplicationSummary
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        application: changedApplication,
        changed: true
      } as never)
      .mockResolvedValueOnce({
        success: true,
        dashboard: dashboardFixture
      } as never)
      .mockResolvedValueOnce({
        success: true,
        applications: [changedApplication]
      } as never)

    const store = useEnterpriseConsoleStore()
    store.applicationFilters = {
      job_id: 'job-1',
      status: 'intent'
    }
    store.activeApplication = applicationDetail

    expect(await store.changeApplicationStatus('application-1', 1, 'intent')).toBe(
      true
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/enterprise/applications/application-1/status',
      {
        method: 'PATCH',
        body: JSON.stringify({
          expected_version: 1,
          status: 'intent'
        })
      }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/enterprise/dashboard'
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/enterprise/applications?job_id=job-1&status=intent'
    )
    expect(store.activeApplication?.status).toBe('intent')
    expect(store.activeApplication?.status_version).toBe(2)
    expect(store.activeApplication?.resume_snapshot).toEqual(
      applicationDetail.resume_snapshot
    )
    expect(store.applications).toEqual([changedApplication])
  })

  it('keeps loaded data when an API request fails', async () => {
    const store = useEnterpriseConsoleStore()
    store.dashboard = dashboardFixture
    store.jobs = [pendingJob]
    store.applications = [applicationSummary]
    store.activeApplication = applicationDetail

    mockedApiFetch
      .mockRejectedValueOnce(new ApiError('职位列表暂不可用', 503))
      .mockRejectedValueOnce(new ApiError('申请列表暂不可用', 503))

    expect(await store.loadJobs('approved')).toBe(false)
    expect(store.error).toBe('职位列表暂不可用')
    expect(store.dashboard).toEqual(dashboardFixture)
    expect(store.jobs).toEqual([pendingJob])

    expect(await store.loadApplications()).toBe(false)
    expect(store.error).toBe('申请列表暂不可用')
    expect(store.applications).toEqual([applicationSummary])
    expect(store.activeApplication).toEqual(applicationDetail)

    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('申请状态版本冲突', 409)
    )

    expect(
      await store.changeApplicationStatus('application-1', 1, 'viewed')
    ).toBe(false)
    expect(store.error).toBe('申请状态版本冲突')
    expect(store.activeApplication).toEqual(applicationDetail)
  })
})
