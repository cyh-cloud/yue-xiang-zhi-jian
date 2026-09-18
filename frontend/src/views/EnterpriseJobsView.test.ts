import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError, apiFetch } from '@/api/client'
import type { EnterpriseJob, InterestTag } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import EnterpriseConsoleNav from '@/components/EnterpriseConsoleNav.vue'
import enterpriseJobFormSource from '@/components/EnterpriseJobForm.vue?raw'
import { useEnterpriseConsoleStore } from '@/stores/enterpriseConsole'

import EnterpriseJobsView from './EnterpriseJobsView.vue'
import enterpriseJobsViewSource from './EnterpriseJobsView.vue?raw'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const jobTags = [
  { id: 9, group_key: 'job', name: '农业技术员' },
  { id: 12, group_key: 'job', name: '农产品电商运营' }
] satisfies InterestTag[]

const pendingJob: EnterpriseJob = {
  job_id: 'job-pending',
  enterprise_id: 7,
  title: '农业技术员',
  salary: '6000-8000 元/月',
  location: '广州市从化区',
  category_id: 9,
  category_name: '农业技术员',
  description: '负责荔枝种植基地的日常技术指导与质量记录。',
  review_status: 'pending',
  version: 1,
  rejection_opinion: null,
  published_at: null,
  deleted_at: null,
  created_at: '2026-09-18T09:00:00+08:00',
  updated_at: '2026-09-18T09:00:00+08:00'
}

const approvedJob: EnterpriseJob = {
  ...pendingJob,
  job_id: 'job-approved',
  title: '农产品电商运营助理',
  review_status: 'approved',
  version: 3,
  published_at: '2026-09-18T10:00:00+08:00'
}

const rejectedJob: EnterpriseJob = {
  ...pendingJob,
  job_id: 'job-rejected',
  title: '乡村品牌策划专员',
  review_status: 'rejected',
  version: 2,
  rejection_opinion: '请补充更具体的岗位职责与任职要求。'
}

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      '/',
      '/login',
      '/register',
      '/messages',
      '/enterprise',
      '/enterprise/jobs',
      '/enterprise/applications'
    ].map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}

async function mountView() {
  const pinia = createPinia()
  const router = testRouter()
  await router.push('/enterprise/jobs')
  await router.isReady()
  const wrapper = mount(EnterpriseJobsView, {
    global: {
      plugins: [pinia, router]
    }
  })
  await flushPromises()
  return { pinia, wrapper }
}

function mockInitialLoad(jobs: EnterpriseJob[] = [pendingJob]) {
  mockedApiFetch.mockImplementation(async (path: string) => {
    if (path === '/api/interest-tags') {
      return {
        success: true,
        tags: [
          ...jobTags,
          { id: 1, group_key: 'crop', name: '荔枝' },
          { id: 2, group_key: 'skill', name: '农业技术' }
        ]
      } as never
    }
    if (path === '/api/enterprise/jobs') {
      return { success: true, jobs } as never
    }
    throw new Error(`Unexpected request: ${path}`)
  })
}

function cssRule(css: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(
    new RegExp(
      `(?:^|[{}])\\s*[^{}]*?${escaped}[^{}]*?\\s*\\{([\\s\\S]*?)\\}`
    )
  )
  expect(match).not.toBeNull()
  return (match?.[1] ?? '').replace(/\s+/g, ' ').trim()
}

describe('EnterpriseJobsView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loads only job categories and renders reviewed status labels', async () => {
    mockInitialLoad([pendingJob, approvedJob, rejectedJob])
    const { pinia, wrapper } = await mountView()
    const store = useEnterpriseConsoleStore(pinia)

    expect(wrapper.findComponent(AppHeader).exists()).toBe(true)
    expect(wrapper.findComponent(EnterpriseConsoleNav).exists()).toBe(true)
    expect(wrapper.find('[data-test="job-form"]').exists()).toBe(false)
    await wrapper.get('[data-test="job-create-toggle"]').trigger('click')
    expect(store.jobCategories.map(tag => tag.name)).toEqual([
      '农业技术员',
      '农产品电商运营'
    ])
    expect(wrapper.get('[data-test="job-category-select"]').text()).toContain(
      '农业技术员'
    )
    expect(wrapper.get('[data-test="job-category-select"]').text()).not.toContain(
      '荔枝'
    )
    expect(wrapper.get('[data-test="job-status-pending"]').text()).toContain(
      '待审核'
    )
    expect(wrapper.get('[data-test="job-status-approved"]').text()).toContain(
      '已通过'
    )
    expect(wrapper.get('[data-test="job-status-rejected"]').text()).toContain(
      '已驳回'
    )
    expect(wrapper.get('[data-test="job-rejection-opinion"]').text()).toContain(
      '请补充更具体的岗位职责与任职要求。'
    )
    expect(mockedApiFetch).toHaveBeenCalledWith('/api/interest-tags')
    expect(mockedApiFetch).toHaveBeenCalledWith('/api/enterprise/jobs')
  })

  it('shows loading and empty states, then retries a failed job load', async () => {
    let jobsRequests = 0
    let rejectJobs: ((reason?: unknown) => void) | undefined
    mockedApiFetch.mockImplementation(async (path: string) => {
      if (path === '/api/interest-tags') {
        return { success: true, tags: jobTags } as never
      }
      if (path === '/api/enterprise/jobs') {
        jobsRequests += 1
        if (jobsRequests === 1) {
          return new Promise((_resolve, reject) => {
            rejectJobs = reject
          }) as never
        }
        return { success: true, jobs: [] } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const { wrapper } = await mountView()

    expect(wrapper.get('[data-test="jobs-loading"]').text()).toContain(
      '正在加载职位'
    )

    rejectJobs?.(new ApiError('职位列表暂不可用', 503))
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain(
      '职位列表暂不可用'
    )

    await wrapper.get('[data-test="jobs-refresh"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="jobs-empty"]').text()).toContain(
      '暂无职位'
    )
    expect(jobsRequests).toBe(2)
  })

  it('filters reviewed jobs through the store tabs', async () => {
    mockInitialLoad([pendingJob, approvedJob, rejectedJob])
    const { pinia, wrapper } = await mountView()
    const store = useEnterpriseConsoleStore(pinia)

    await wrapper.get('[data-test="job-filter-pending"]').trigger('click')
    await flushPromises()

    expect(store.jobReviewFilter).toBe('pending')
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/enterprise/jobs?review_status=pending'
    )
    expect(
      wrapper.get('[data-test="job-filter-pending"]').attributes('aria-pressed')
    ).toBe('true')
  })

  it('creates the exact payload and shows the returned pending status', async () => {
    mockInitialLoad([])
    const { wrapper } = await mountView()
    const createdJob = {
      ...pendingJob,
      title: '荔枝种植技术员',
      salary: '7000 元/月',
      location: '茂名市高州市',
      category_id: 12,
      category_name: '农产品电商运营',
      description: '负责果园数据记录、产品上架与订单协调。'
    }

    mockedApiFetch.mockImplementation(
      async (path: string, options?: RequestInit) => {
        if (path === '/api/enterprise/jobs' && options?.method === 'POST') {
          return { success: true, job: createdJob } as never
        }
        if (path === '/api/enterprise/dashboard') {
          return {
            success: true,
            dashboard: {
              active_job_count: 0,
              received_resume_count: 0
            }
          } as never
        }
        if (path === '/api/enterprise/jobs') {
          return { success: true, jobs: [createdJob] } as never
        }
        throw new Error(`Unexpected request: ${path}`)
      }
    )

    await wrapper.get('[data-test="job-create-toggle"]').trigger('click')
    await wrapper.get('[data-test="job-title"]').setValue('荔枝种植技术员')
    await wrapper.get('[data-test="job-salary"]').setValue('7000 元/月')
    await wrapper.get('[data-test="job-location"]').setValue('茂名市高州市')
    await wrapper
      .get('[data-test="job-category-select"]')
      .setValue('12')
    await wrapper
      .get('[data-test="job-description"]')
      .setValue('负责果园数据记录、产品上架与订单协调。')
    await wrapper.get('[data-test="job-form"]').trigger('submit')
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenCalledWith('/api/enterprise/jobs', {
      method: 'POST',
      body: JSON.stringify({
        title: '荔枝种植技术员',
        salary: '7000 元/月',
        location: '茂名市高州市',
        category_id: 12,
        description: '负责果园数据记录、产品上架与订单协调。'
      })
    })
    expect(wrapper.get('[data-test="job-status-pending"]').text()).toContain(
      '待审核'
    )
    expect(wrapper.find('[data-test="job-form"]').exists()).toBe(false)
  })

  it('edits an approved job with its current version and displays pending immediately', async () => {
    mockInitialLoad([approvedJob])
    const { wrapper } = await mountView()
    const pendingEditedJob = {
      ...approvedJob,
      title: '资深农产品电商运营',
      review_status: 'pending' as const,
      version: 4,
      published_at: null
    }

    mockedApiFetch.mockImplementation(
      async (path: string, options?: RequestInit) => {
        if (
          path === `/api/enterprise/jobs/${approvedJob.job_id}` &&
          options?.method === 'PUT'
        ) {
          return { success: true, job: pendingEditedJob } as never
        }
        if (path === '/api/enterprise/dashboard') {
          return {
            success: true,
            dashboard: {
              active_job_count: 0,
              received_resume_count: 0
            }
          } as never
        }
        if (path === '/api/enterprise/jobs') {
          return { success: true, jobs: [pendingEditedJob] } as never
        }
        throw new Error(`Unexpected request: ${path}`)
      }
    )

    await wrapper
      .get(`[data-test="job-edit-${approvedJob.job_id}"]`)
      .trigger('click')
    await wrapper
      .get('[data-test="job-title"]')
      .setValue('资深农产品电商运营')
    await wrapper.get('[data-test="job-form"]').trigger('submit')
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenCalledWith(
      `/api/enterprise/jobs/${approvedJob.job_id}`,
      {
        method: 'PUT',
        body: JSON.stringify({
          expected_version: 3,
          title: '资深农产品电商运营',
          salary: approvedJob.salary,
          location: approvedJob.location,
          category_id: approvedJob.category_id,
          description: approvedJob.description
        })
      }
    )
    expect(wrapper.get('[data-test="job-status-pending"]').text()).toContain(
      '待审核'
    )
  })

  it('confirms deletion and removes a successfully deleted job', async () => {
    mockInitialLoad([pendingJob])
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { wrapper } = await mountView()

    mockedApiFetch.mockImplementation(
      async (path: string, options?: RequestInit) => {
        if (
          path === `/api/enterprise/jobs/${pendingJob.job_id}` &&
          options?.method === 'DELETE'
        ) {
          return {
            success: true,
            deleted: { deleted: true, changed: true }
          } as never
        }
        if (path === '/api/enterprise/dashboard') {
          return {
            success: true,
            dashboard: {
              active_job_count: 0,
              received_resume_count: 0
            }
          } as never
        }
        if (path === '/api/enterprise/jobs') {
          return { success: true, jobs: [] } as never
        }
        throw new Error(`Unexpected request: ${path}`)
      }
    )

    await wrapper
      .get(`[data-test="job-delete-${pendingJob.job_id}"]`)
      .trigger('click')
    await flushPromises()

    expect(confirm).toHaveBeenCalled()
    expect(mockedApiFetch).toHaveBeenCalledWith(
      `/api/enterprise/jobs/${pendingJob.job_id}`,
      {
        method: 'DELETE',
        body: JSON.stringify({ expected_version: 1 })
      }
    )
    expect(wrapper.find(`[data-test="job-${pendingJob.job_id}"]`).exists()).toBe(
      false
    )
    expect(wrapper.text()).toContain('暂无职位')
    confirm.mockRestore()
  })

  it('renders field-specific errors and does not call the create API', async () => {
    mockInitialLoad([])
    const { wrapper } = await mountView()

    await wrapper.get('[data-test="job-create-toggle"]').trigger('click')
    await wrapper.get('[data-test="job-form"]').trigger('submit')

    expect(wrapper.get('[data-test="job-title-error"]').text()).toContain(
      '请填写职位标题'
    )
    expect(wrapper.get('[data-test="job-salary-error"]').text()).toContain(
      '请填写薪资'
    )
    expect(wrapper.get('[data-test="job-location-error"]').text()).toContain(
      '请填写工作地点'
    )
    expect(wrapper.get('[data-test="job-category-error"]').text()).toContain(
      '请选择职位类别'
    )
    expect(wrapper.get('[data-test="job-description-error"]').text()).toContain(
      '请填写职位描述'
    )
    expect(wrapper.get('[data-test="job-title"]').attributes('aria-describedby')).toBe(
      'job-title-error'
    )
    expect(mockedApiFetch).not.toHaveBeenCalledWith(
      '/api/enterprise/jobs',
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('shows a refresh action for a 409 conflict without optimistic mutation', async () => {
    mockInitialLoad([approvedJob])
    const { pinia, wrapper } = await mountView()
    const store = useEnterpriseConsoleStore(pinia)

    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('职位版本冲突，请刷新后重试', 409)
    )

    await wrapper
      .get(`[data-test="job-edit-${approvedJob.job_id}"]`)
      .trigger('click')
    await wrapper
      .get('[data-test="job-title"]')
      .setValue('不会乐观覆盖的标题')
    await wrapper.get('[data-test="job-form"]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain(
      '职位版本冲突，请刷新后重试'
    )
    expect(wrapper.get('[data-test="jobs-refresh"]').text()).toContain('刷新')
    expect(store.jobs).toEqual([approvedJob])
    expect(wrapper.get(`[data-test="job-${approvedJob.job_id}"]`).text()).toContain(
      '农产品电商运营助理'
    )
  })

  it('keeps CJK copy and actions stable at narrow and wide viewports', () => {
    const sources = [enterpriseJobFormSource, enterpriseJobsViewSource]
    const form = cssRule(
      enterpriseJobFormSource,
      '.enterprise-job-form__field'
    )
    const title = cssRule(
      enterpriseJobsViewSource,
      '.enterprise-jobs-heading h1'
    )
    const description = cssRule(
      enterpriseJobsViewSource,
      '.enterprise-jobs-heading > p'
    )
    const jobTitle = cssRule(
      enterpriseJobsViewSource,
      '.job-row__title'
    )
    const jobDescription = cssRule(
      enterpriseJobsViewSource,
      '.job-row__description'
    )
    const actions = cssRule(
      enterpriseJobsViewSource,
      '.job-row__actions button'
    )
    const filters = cssRule(
      enterpriseJobsViewSource,
      '.job-filter-tab'
    )

    expect(form).toContain('min-width: 0')
    expect(form).toContain('line-break: strict')
    expect(form).toContain('overflow-wrap: break-word')
    expect(form).toContain('word-break: normal')
    expect(title).toContain('line-break: strict')
    expect(title).toContain('text-wrap: balance')
    expect(title).toContain('word-break: normal')
    expect(description).toContain('text-wrap: pretty')
    expect(description).toContain('word-break: normal')
    expect(jobTitle).toContain('overflow-wrap: break-word')
    expect(jobTitle).toContain('word-break: normal')
    expect(jobDescription).toContain('line-break: strict')
    expect(jobDescription).toContain('word-break: normal')
    expect(actions).toContain('min-height: 40px')
    expect(actions).toContain('white-space: normal')
    expect(filters).toContain('min-height: 40px')
    expect(filters).toContain('white-space: normal')

    for (const source of sources) {
      expect(source).not.toContain('white-space: nowrap')
      expect(source).not.toMatch(
        /#[0-9a-f]{3,8}|rgba?\(|hsla?\(|\bcyan\b/i
      )
    }
    expect(enterpriseJobsViewSource).toContain('@media (max-width: 720px)')
  })
})
