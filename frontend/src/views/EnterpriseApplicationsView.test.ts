import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError, apiFetch } from '@/api/client'
import type {
  EnterpriseApplicationDetail,
  EnterpriseApplicationSummary
} from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import EnterpriseApplicationStatusBadge from '@/components/EnterpriseApplicationStatusBadge.vue'
import enterpriseApplicationStatusBadgeSource from '@/components/EnterpriseApplicationStatusBadge.vue?raw'
import EnterpriseConsoleNav from '@/components/EnterpriseConsoleNav.vue'

import EnterpriseApplicationDetailView from './EnterpriseApplicationDetailView.vue'
import enterpriseApplicationDetailViewSource from './EnterpriseApplicationDetailView.vue?raw'
import EnterpriseApplicationsView from './EnterpriseApplicationsView.vue'
import enterpriseApplicationsViewSource from './EnterpriseApplicationsView.vue?raw'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const longStudentName =
  '欧阳娜娜阿依古丽·阿卜杜热合曼同学'
const longJobTitle =
  '农产品品牌数字化运营与乡村振兴内容策划专员'
const longResumeValue =
  '负责粤东西北农产品品牌故事整理、短视频内容策划与线上店铺运营数据分析'

const pendingApplication: EnterpriseApplicationSummary = {
  application_id: 'application-1',
  student_id: 11,
  student_name: longStudentName,
  job_id: 'job-1',
  job_title: longJobTitle,
  submitted_at: '2026-09-18T11:30:00+08:00',
  status: 'pending',
  status_label: '待处理',
  status_version: 2,
  position_closed: false,
  position_closed_at: null,
  effective_status: 'pending',
  effective_status_label: '待处理'
}

const intentApplication: EnterpriseApplicationSummary = {
  ...pendingApplication,
  application_id: 'application-2',
  student_id: 12,
  student_name: '陈晓彤',
  job_id: 'job-2',
  job_title: '农业技术推广助理',
  submitted_at: '2026-09-17T09:00:00+08:00',
  status: 'intent',
  status_label: '意向沟通',
  status_version: 3,
  effective_status: 'intent',
  effective_status_label: '意向沟通'
}

const applicationDetail: EnterpriseApplicationDetail = {
  ...pendingApplication,
  resume_snapshot: {
    education: '华南农业大学农业经济管理本科',
    experience: [
      {
        company: '广东乡村振兴实践基地',
        responsibility: longResumeValue
      }
    ],
    skills: ['品牌策划', '视频剪辑', '数据复盘']
  },
  skill_profile: {
    items: [
      {
        title: '荔枝品牌短视频策划',
        outcome: '获得校级实践项目优秀成果'
      }
    ]
  },
  skill_profile_attached: true,
  status_history: [
    {
      sequence_no: 1,
      previous_status: 'pending',
      new_status: 'viewed',
      actor_enterprise_id: 7,
      event_id: 'event-1',
      created_at: '2026-09-18T12:00:00+08:00'
    }
  ]
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
      '/enterprise/applications',
      '/enterprise/applications/:applicationId'
    ].map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}

async function mountApplicationsView() {
  const pinia = createPinia()
  const router = testRouter()
  await router.push('/enterprise/applications')
  await router.isReady()
  const wrapper = mount(EnterpriseApplicationsView, {
    global: {
      plugins: [pinia, router]
    }
  })
  await flushPromises()
  return { pinia, wrapper }
}

async function mountDetailView() {
  const pinia = createPinia()
  const router = testRouter()
  await router.push('/enterprise/applications/application-1')
  await router.isReady()
  const wrapper = mount(EnterpriseApplicationDetailView, {
    global: {
      plugins: [pinia, router]
    }
  })
  await flushPromises()
  return { pinia, wrapper }
}

function mockApplicationList(
  applications: EnterpriseApplicationSummary[]
) {
  mockedApiFetch.mockImplementation(async path => {
    if (
      path === '/api/enterprise/applications' ||
      path.startsWith('/api/enterprise/applications?')
    ) {
      return { success: true, applications } as never
    }
    throw new Error(`Unexpected request: ${path}`)
  })
}

function mockApplicationDetail(
  application: EnterpriseApplicationDetail =
    applicationDetail
) {
  mockedApiFetch.mockImplementation(async path => {
    if (path === '/api/enterprise/applications/application-1') {
      return { success: true, application } as never
    }
    throw new Error(`Unexpected request: ${path}`)
  })
}

function cssRule(css: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const boundary = /[a-zA-Z0-9_-]$/.test(selector) ? '(?![a-zA-Z0-9_-])' : ''
  const match = css.match(
    new RegExp(
      `(?:^|[{}])\\s*[^{}]*?${escaped}${boundary}[^{}]*?\\s*\\{([\\s\\S]*?)\\}`
    )
  )
  expect(match).not.toBeNull()
  return (match?.[1] ?? '').replace(/\s+/g, ' ').trim()
}

function mediaBlock(source: string, maxWidth: number): string {
  const marker = `@media (max-width: ${maxWidth}px)`
  const start = source.indexOf(marker)
  expect(start).toBeGreaterThanOrEqual(0)
  return source.slice(start)
}

function fixedPixelWidths(source: string): number[] {
  return Array.from(
    source.matchAll(/(?:^|[;{\n]\s*)(?:min-)?width:\s*(\d+)px/g),
    match => Number(match[1])
  )
}

describe('EnterpriseApplicationsView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders exact filters and requests the store query without reordering rows', async () => {
    mockApplicationList([intentApplication, pendingApplication])
    const { wrapper } = await mountApplicationsView()

    expect(wrapper.findComponent(AppHeader).exists()).toBe(true)
    expect(wrapper.findComponent(EnterpriseConsoleNav).exists()).toBe(true)
    expect(
      wrapper
        .findAll('[data-test^="application-row-"]')
        .map(row => row.attributes('data-test'))
    ).toEqual(['application-row-application-2', 'application-row-application-1'])

    const jobFilter = wrapper.get('[data-test="application-job-filter"]')
    expect(jobFilter.findAll('option').map(option => option.text())).toEqual([
      '全部职位',
      '农业技术推广助理',
      longJobTitle
    ])
    expect(
      wrapper
        .get('[data-test="application-status-filter"]')
        .findAll('option')
        .map(option => option.attributes('value'))
    ).toEqual(['', 'pending', 'viewed', 'intent', 'unsuitable'])
    expect(
      wrapper.get('[data-test="application-sort-filter"]').element
    ).toHaveProperty('value', 'submitted_desc')

    await jobFilter.setValue('job-1')
    await wrapper
      .get('[data-test="application-status-filter"]')
      .setValue('intent')
    await wrapper
      .get('[data-test="application-submitted-from"]')
      .setValue('2026-09-01')
    await wrapper
      .get('[data-test="application-submitted-to"]')
      .setValue('2026-09-18')
    await wrapper
      .get('[data-test="application-sort-filter"]')
      .setValue('submitted_desc')
    await wrapper.get('[data-test="application-filter-form"]').trigger('submit')
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/enterprise/applications?job_id=job-1&status=intent&submitted_from=2026-09-01&submitted_to=2026-09-18&sort=submitted_desc'
    )
    expect(
      wrapper
        .findAll('[data-test^="application-row-"]')
        .map(row => row.attributes('data-test'))
    ).toEqual(['application-row-application-2', 'application-row-application-1'])
  })

  it('renders the exact empty state without fabricating applications', async () => {
    mockApplicationList([])
    const { wrapper } = await mountApplicationsView()

    expect(wrapper.get('[data-test="applications-empty"]').text()).toBe(
      '暂无符合条件的申请'
    )
  })

  it('shows immutable resume data and an attached non-empty skill profile', async () => {
    mockApplicationDetail()
    const { wrapper } = await mountDetailView()

    const resume = wrapper.get('[data-test="resume-snapshot"]')
    expect(resume.text()).toContain('华南农业大学农业经济管理本科')
    expect(resume.text()).toContain('广东乡村振兴实践基地')
    expect(resume.text()).toContain(longResumeValue)
    expect(resume.text()).toContain('品牌策划, 视频剪辑, 数据复盘')

    const skillProfile = wrapper.get('[data-test="skill-profile"]')
    expect(skillProfile.text()).toContain('荔枝品牌短视频策划')
    expect(skillProfile.text()).toContain('获得校级实践项目优秀成果')
    expect(wrapper.find('[data-test="skill-profile-empty"]').exists()).toBe(
      false
    )
    expect(mockedApiFetch).toHaveBeenCalledTimes(1)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/enterprise/applications/application-1'
    )
  })

  it('shows the exact empty skill-profile state for missing or visible-empty snapshots', async () => {
    mockApplicationDetail({
      ...applicationDetail,
      skill_profile: null,
      skill_profile_attached: true
    })
    const first = await mountDetailView()

    expect(first.wrapper.get('[data-test="skill-profile-empty"]').text()).toBe(
      '未附带技能档案'
    )
    expect(first.wrapper.find('[data-test="skill-profile"]').exists()).toBe(
      false
    )
    expect(mockedApiFetch).toHaveBeenCalledTimes(1)

    mockedApiFetch.mockReset()
    mockApplicationDetail({
      ...applicationDetail,
      skill_profile: { items: [] },
      skill_profile_attached: true
    })
    const second = await mountDetailView()

    expect(second.wrapper.get('[data-test="skill-profile-empty"]').text()).toBe(
      '未附带技能档案'
    )
    expect(second.wrapper.find('[data-test="skill-profile"]').exists()).toBe(
      false
    )
    expect(mockedApiFetch).toHaveBeenCalledTimes(1)
  })

  it('renders status history in ascending sequence', async () => {
    mockApplicationDetail({
      ...applicationDetail,
      status: 'intent',
      status_label: '意向沟通',
      status_version: 3,
      effective_status: 'intent',
      effective_status_label: '意向沟通',
      status_history: [
        {
          sequence_no: 2,
          previous_status: 'viewed',
          new_status: 'intent',
          actor_enterprise_id: 7,
          event_id: 'event-2',
          created_at: '2026-09-18T13:00:00+08:00'
        },
        {
          sequence_no: 1,
          previous_status: 'pending',
          new_status: 'viewed',
          actor_enterprise_id: 7,
          event_id: 'event-1',
          created_at: '2026-09-18T12:00:00+08:00'
        }
      ]
    })
    const { wrapper } = await mountDetailView()

    expect(
      wrapper
        .findAll('[data-test="status-history-item"]')
        .map(item => item.text())
    ).toEqual([
      expect.stringContaining('待处理'),
      expect.stringContaining('意向沟通')
    ])
  })

  it('offers only the three manual status targets and refreshes detail and list after success', async () => {
    const updatedSummary: EnterpriseApplicationSummary = {
      ...pendingApplication,
      status: 'intent',
      status_label: '意向沟通',
      status_version: 3,
      effective_status: 'intent',
      effective_status_label: '意向沟通'
    }
    const refreshedDetail: EnterpriseApplicationDetail = {
      ...applicationDetail,
      ...updatedSummary,
      status_history: [
        ...applicationDetail.status_history,
        {
          sequence_no: 2,
          previous_status: 'pending',
          new_status: 'intent',
          actor_enterprise_id: 7,
          event_id: 'event-2',
          created_at: '2026-09-18T13:00:00+08:00'
        }
      ]
    }
    let detailReads = 0
    mockedApiFetch.mockImplementation(
      async (path, options?: RequestInit) => {
        if (
          path === '/api/enterprise/applications/application-1/status' &&
          options?.method === 'PATCH'
        ) {
          return {
            success: true,
            application: updatedSummary,
            changed: true
          } as never
        }
        if (path === '/api/enterprise/dashboard') {
          return {
            success: true,
            dashboard: {
              active_job_count: 1,
              received_resume_count: 2
            }
          } as never
        }
        if (path === '/api/enterprise/applications') {
          return {
            success: true,
            applications: [updatedSummary]
          } as never
        }
        if (path === '/api/enterprise/applications/application-1') {
          detailReads += 1
          return {
            success: true,
            application:
              detailReads === 1 ? applicationDetail : refreshedDetail
          } as never
        }
        throw new Error(`Unexpected request: ${path}`)
      }
    )

    const { wrapper } = await mountDetailView()
    const buttons = wrapper.findAll('[data-test^="application-status-"]')

    expect(buttons.map(button => button.text())).toEqual([
      '已查看',
      '意向沟通',
      '不合适'
    ])
    expect(buttons.map(button => button.attributes('data-status'))).toEqual([
      'viewed',
      'intent',
      'unsuitable'
    ])
    expect(buttons.map(button => button.text())).not.toContain('待处理')

    await wrapper.get('[data-test="application-status-intent"]').trigger('click')
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/enterprise/applications/application-1/status',
      {
        method: 'PATCH',
        body: JSON.stringify({
          expected_version: 2,
          status: 'intent'
        })
      }
    )
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/enterprise/applications'
    )
    expect(
      mockedApiFetch.mock.calls.filter(
        ([path]) => path === '/api/enterprise/applications/application-1'
      )
    ).toHaveLength(2)
    expect(wrapper.get('[data-test="current-application-status"]').text()).toBe(
      '意向沟通'
    )
    expect(wrapper.get('[data-test="status-history"]').text()).toContain(
      '意向沟通'
    )
  })

  it('keeps closed history visible and disables every status button', async () => {
    const closedDetail: EnterpriseApplicationDetail = {
      ...applicationDetail,
      status: 'viewed',
      status_label: '已查看',
      status_version: 4,
      position_closed: true,
      position_closed_at: '2026-09-18T14:00:00+08:00',
      effective_status: 'viewed',
      effective_status_label: '已查看',
      status_history: [
        {
          sequence_no: 1,
          previous_status: 'pending',
          new_status: 'viewed',
          actor_enterprise_id: 7,
          event_id: 'event-viewed',
          created_at: '2026-09-18T12:00:00+08:00'
        }
      ]
    }
    mockApplicationDetail(closedDetail)
    const { wrapper } = await mountDetailView()

    expect(
      wrapper.get('[data-test="current-application-status"]').text()
    ).toContain('已查看')
    expect(wrapper.get('[data-test="position-closed-badge"]').text()).toBe(
      '岗位已关闭'
    )
    expect(wrapper.get('[data-test="status-history"]').text()).toContain(
      '已查看'
    )
    for (const button of wrapper.findAll(
      '[data-test^="application-status-"]'
    )) {
      expect(button.attributes('disabled')).toBeDefined()
    }

    expect(wrapper.get('[data-test="message-applicant"]').text()).toBe(
      '私信沟通'
    )
    expect(
      wrapper.get('[data-test="message-applicant"]').attributes('href')
    ).toBe('/messages')
    expect(wrapper.text()).not.toMatch(
      /人才搜索|主动邀约|邀请面试|发起面试|电子签约|导出人才|入职管理/
    )
  })

  it('preserves the previous status after a 409 and offers a real refresh action', async () => {
    let detailReads = 0
    mockedApiFetch.mockImplementation(
      async (path, options?: RequestInit) => {
        if (path === '/api/enterprise/applications/application-1') {
          detailReads += 1
          return { success: true, application: applicationDetail } as never
        }
        if (
          path === '/api/enterprise/applications/application-1/status' &&
          options?.method === 'PATCH'
        ) {
          throw new ApiError('申请状态版本冲突，请刷新后重试', 409)
        }
        throw new Error(`Unexpected request: ${path}`)
      }
    )

    const { wrapper } = await mountDetailView()
    await wrapper.get('[data-test="application-status-intent"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain(
      '申请状态版本冲突，请刷新后重试'
    )
    expect(wrapper.get('[data-test="current-application-status"]').text()).toBe(
      '待处理'
    )
    const refresh = wrapper.get('[data-test="application-detail-refresh"]')
    expect(refresh.text()).toContain('刷新')

    await refresh.trigger('click')
    await flushPromises()

    expect(detailReads).toBe(2)
    expect(wrapper.get('[data-test="current-application-status"]').text()).toBe(
      '待处理'
    )
  })

  it('renders both labels for a closed application whose business status is still pending', () => {
    const wrapper = mount(EnterpriseApplicationStatusBadge, {
      props: {
        status: 'pending',
        positionClosed: true
      }
    })

    expect(wrapper.get('[data-test="effective-status-badge"]').text()).toBe(
      '待处理'
    )
    expect(wrapper.get('[data-test="position-closed-badge"]').text()).toBe(
      '岗位已关闭'
    )
  })

  it('keeps CJK fields and status actions tokenized and overflow-safe', () => {
    const sources = [
      enterpriseApplicationsViewSource,
      enterpriseApplicationDetailViewSource,
      enterpriseApplicationStatusBadgeSource
    ]

    expect(enterpriseApplicationsViewSource).toContain(
      'overflow-wrap: anywhere'
    )
    expect(enterpriseApplicationsViewSource).toContain('line-break: strict')
    expect(enterpriseApplicationDetailViewSource).toContain(
      'overflow-wrap: anywhere'
    )
    expect(enterpriseApplicationDetailViewSource).toContain(
      'line-break: strict'
    )

    const applicationName = cssRule(
      enterpriseApplicationsViewSource,
      '.application-row__student'
    )
    const jobTitle = cssRule(
      enterpriseApplicationsViewSource,
      '.application-row__job'
    )
    const resumeValue = cssRule(
      enterpriseApplicationDetailViewSource,
      '.resume-field dd'
    )
    const statusActions = cssRule(
      enterpriseApplicationDetailViewSource,
      '.application-status-controls button'
    )

    expect(applicationName).toContain('overflow-wrap: anywhere')
    expect(applicationName).toContain('word-break: normal')
    expect(applicationName).toContain('text-wrap: pretty')
    expect(jobTitle).toContain('overflow-wrap: anywhere')
    expect(jobTitle).toContain('word-break: normal')
    expect(resumeValue).toContain('overflow-wrap: anywhere')
    expect(resumeValue).toContain('word-break: normal')
    expect(statusActions).toContain('min-height: 40px')
    expect(statusActions).toContain('white-space: normal')
    expect(statusActions).toContain('word-break: normal')
    expect(statusActions).toContain('text-wrap: pretty')

    for (const source of sources) {
      expect(source).not.toMatch(
        /#[0-9a-f]{3,8}|rgba?\(|hsla?\(|\bcyan\b/i
      )
    }
    expect(enterpriseApplicationsViewSource).toContain(
      '@media (max-width: 720px)'
    )
    expect(enterpriseApplicationDetailViewSource).toContain(
      '@media (max-width: 720px)'
    )
  })

  it('locks the application list layout contract at 320, 375 and 1280', async () => {
    mockApplicationList([pendingApplication])
    const { wrapper } = await mountApplicationsView()
    const sources = [
      enterpriseApplicationsViewSource,
      enterpriseApplicationStatusBadgeSource
    ]
    const page = cssRule(
      enterpriseApplicationsViewSource,
      '.enterprise-applications-page'
    )
    const main = cssRule(
      enterpriseApplicationsViewSource,
      '.enterprise-applications-main'
    )
    const filter = cssRule(
      enterpriseApplicationsViewSource,
      '.application-filter-form'
    )
    const field = cssRule(
      enterpriseApplicationsViewSource,
      '.application-filter-field'
    )
    const content = cssRule(
      enterpriseApplicationsViewSource,
      '.applications-content'
    )
    const row = cssRule(
      enterpriseApplicationsViewSource,
      '.application-row'
    )
    const identity = cssRule(
      enterpriseApplicationsViewSource,
      '.application-row__identity'
    )
    const student = cssRule(
      enterpriseApplicationsViewSource,
      '.application-row__student'
    )
    const job = cssRule(
      enterpriseApplicationsViewSource,
      '.application-row__job'
    )
    const action = cssRule(
      enterpriseApplicationsViewSource,
      '.application-row__action'
    )
    const badge = cssRule(
      enterpriseApplicationStatusBadgeSource,
      '.application-status-badge'
    )
    const badgeStatus = cssRule(
      enterpriseApplicationStatusBadgeSource,
      '.application-status-badge__status'
    )

    expect(longStudentName.length).toBeGreaterThan(12)
    expect(longJobTitle.length).toBeGreaterThan(12)
    expect(wrapper.get('.application-row__student').text()).toBe(
      longStudentName
    )
    expect(wrapper.get('.application-row__job').text()).toBe(longJobTitle)
    expect(row).toContain('grid-template-columns')
    expect(row).toContain('minmax(0, 1.1fr)')
    expect(
      cssRule(
        mediaBlock(enterpriseApplicationsViewSource, 900),
        '.application-filter-form'
      )
    ).toContain('grid-template-columns: repeat(2, minmax(0, 1fr))')
    expect(
      cssRule(
        mediaBlock(enterpriseApplicationsViewSource, 720),
        '.application-row'
      )
    ).toContain('grid-template-columns: minmax(0, 1fr)')
    expect(
      cssRule(
        mediaBlock(enterpriseApplicationsViewSource, 720),
        '.application-row__action'
      )
    ).toContain('width: 100%')

    ;[320, 375, 1280].forEach(viewport => {
      expect(page).toContain('min-width: 0')
      expect(main).toContain('min-width: 0')
      expect(filter).toContain('min-width: 0')
      expect(field).toContain('min-width: 0')
      expect(content).toContain('min-width: 0')
      expect(row).toContain('min-width: 0')
      expect(identity).toContain('min-width: 0')
      expect(student).toContain('line-break: strict')
      expect(student).toContain('overflow-wrap: anywhere')
      expect(student).toContain('word-break: normal')
      expect(job).toContain('line-break: strict')
      expect(job).toContain('overflow-wrap: anywhere')
      expect(job).toContain('word-break: normal')
      expect(action).toContain('overflow-wrap: anywhere')
      expect(action).toContain('white-space: normal')
      expect(action).toContain('word-break: normal')
      expect(badge).toContain('min-width: 0')
      expect(badgeStatus).toContain('line-break: strict')
      expect(badgeStatus).toContain('overflow-wrap: anywhere')
      expect(badgeStatus).toContain('word-break: normal')
      expect(
        sources.every(source =>
          fixedPixelWidths(source).every(width => width <= viewport)
        )
      ).toBe(true)
      expect(sources.join('\n')).not.toContain('white-space: nowrap')
      expect(sources.join('\n')).not.toMatch(
        /#[0-9a-f]{3,8}|rgba?\(|hsla?\(|\bcyan\b/i
      )
    })
  })

  it('locks the application detail layout contract at 320, 375 and 1280', async () => {
    mockApplicationDetail()
    const { wrapper } = await mountDetailView()
    const sources = [
      enterpriseApplicationDetailViewSource,
      enterpriseApplicationStatusBadgeSource
    ]
    const page = cssRule(
      enterpriseApplicationDetailViewSource,
      '.application-detail-page'
    )
    const main = cssRule(
      enterpriseApplicationDetailViewSource,
      '.application-detail-main'
    )
    const content = cssRule(
      enterpriseApplicationDetailViewSource,
      '.application-detail-content'
    )
    const profile = cssRule(
      enterpriseApplicationDetailViewSource,
      '.application-profile'
    )
    const profileCopy = cssRule(
      enterpriseApplicationDetailViewSource,
      '.application-profile__copy'
    )
    const detailGrid = cssRule(
      enterpriseApplicationDetailViewSource,
      '.application-detail-grid'
    )
    const resumeField = cssRule(
      enterpriseApplicationDetailViewSource,
      '.resume-field'
    )
    const resumeValue = cssRule(
      enterpriseApplicationDetailViewSource,
      '.resume-field dd'
    )
    const statusControls = cssRule(
      enterpriseApplicationDetailViewSource,
      '.application-status-controls'
    )
    const statusButton = cssRule(
      enterpriseApplicationDetailViewSource,
      '.application-status-controls button'
    )
    const badge = cssRule(
      enterpriseApplicationStatusBadgeSource,
      '.application-status-badge'
    )
    const badgeStatus = cssRule(
      enterpriseApplicationStatusBadgeSource,
      '.application-status-badge__status'
    )

    expect(longStudentName.length).toBeGreaterThan(12)
    expect(longJobTitle.length).toBeGreaterThan(12)
    expect(longResumeValue.length).toBeGreaterThan(20)
    expect(wrapper.get('.application-profile h1').text()).toBe(
      longStudentName
    )
    expect(wrapper.get('.application-profile__copy p').text()).toBe(
      longJobTitle
    )
    expect(wrapper.get('[data-test="resume-snapshot"]').text()).toContain(
      longResumeValue
    )
    expect(
      wrapper
        .findAll('.application-status-controls button')
        .map(button => button.text())
    ).toEqual(['已查看', '意向沟通', '不合适'])
    expect(detailGrid).toContain('grid-template-columns: minmax(0, 1.2fr)')
    expect(
      cssRule(
        mediaBlock(enterpriseApplicationDetailViewSource, 900),
        '.application-detail-grid'
      )
    ).toContain('grid-template-columns: minmax(0, 1fr)')
    expect(
      cssRule(
        mediaBlock(enterpriseApplicationDetailViewSource, 720),
        '.application-profile'
      )
    ).toContain('grid-template-columns: minmax(0, 1fr)')
    expect(
      cssRule(
        mediaBlock(enterpriseApplicationDetailViewSource, 720),
        '.resume-field'
      )
    ).toContain('grid-template-columns: minmax(0, 1fr)')
    expect(
      cssRule(
        mediaBlock(enterpriseApplicationDetailViewSource, 720),
        '.application-status-controls button'
      )
    ).toContain('flex-basis: 100%')

    ;[320, 375, 1280].forEach(viewport => {
      expect(page).toContain('min-width: 0')
      expect(main).toContain('min-width: 0')
      expect(content).toContain('min-width: 0')
      expect(profile).toContain('min-width: 0')
      expect(profileCopy).toContain('min-width: 0')
      expect(profileCopy).toContain('line-break: strict')
      expect(profileCopy).toContain('overflow-wrap: anywhere')
      expect(profileCopy).toContain('word-break: normal')
      expect(detailGrid).toContain('minmax(0, 1.2fr)')
      expect(resumeField).toContain('min-width: 0')
      expect(resumeValue).toContain('line-break: strict')
      expect(resumeValue).toContain('overflow-wrap: anywhere')
      expect(resumeValue).toContain('word-break: normal')
      expect(statusControls).toContain('min-width: 0')
      expect(statusButton).toContain('min-height: 40px')
      expect(statusButton).toContain('overflow-wrap: anywhere')
      expect(statusButton).toContain('text-wrap: pretty')
      expect(statusButton).toContain('white-space: normal')
      expect(statusButton).toContain('word-break: normal')
      expect(badge).toContain('min-width: 0')
      expect(badgeStatus).toContain('line-break: strict')
      expect(badgeStatus).toContain('overflow-wrap: anywhere')
      expect(badgeStatus).toContain('word-break: normal')
      expect(
        sources.every(source =>
          fixedPixelWidths(source).every(width => width <= viewport)
        )
      ).toBe(true)
      expect(sources.join('\n')).not.toContain('white-space: nowrap')
      expect(sources.join('\n')).not.toMatch(
        /#[0-9a-f]{3,8}|rgba?\(|hsla?\(|\bcyan\b/i
      )
    })
  })
})
