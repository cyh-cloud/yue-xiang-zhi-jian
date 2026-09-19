import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Component } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type {
  EnterpriseApplicationSummary,
  EnterpriseJob
} from '@/api/types'
import enterpriseDashboardCardsSource from '@/components/EnterpriseDashboardCards.vue?raw'
import enterpriseConsoleNavSource from '@/components/EnterpriseConsoleNav.vue?raw'
import { useAuthStore } from '@/stores/auth'

import EnterpriseApplicationsView from './EnterpriseApplicationsView.vue'
import enterpriseApplicationsSource from './EnterpriseApplicationsView.vue?raw'
import EnterpriseJobsView from './EnterpriseJobsView.vue'
import enterpriseJobsSource from './EnterpriseJobsView.vue?raw'
import EnterprisePortalView from './EnterprisePortalView.vue'
import enterprisePortalSource from './EnterprisePortalView.vue?raw'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)
const widths = [320, 375, 1280]
const longChinese =
  '欧阳娜娜阿依古丽·阿卜杜热合曼同学申请农产品品牌数字化运营与乡村振兴内容策划专员'
const longDescription =
  '负责粤东西北农产品品牌故事整理、短视频内容策划、直播运营、线上店铺管理、数据分析与跨部门协作。'.repeat(
    3
  )

const jobFixture: EnterpriseJob = {
  job_id: 'job-responsive',
  enterprise_id: 7,
  title: longChinese,
  salary: '8000-12000 元/月',
  location: '广州市从化区乡村振兴产业园',
  category_id: 9,
  category_name: '农业技术员',
  description: longDescription,
  review_status: 'approved',
  version: 2,
  rejection_opinion: null,
  published_at: '2026-09-19T10:00:00+08:00',
  deleted_at: null,
  created_at: '2026-09-19T09:00:00+08:00',
  updated_at: '2026-09-19T10:00:00+08:00'
}

const applicationFixture: EnterpriseApplicationSummary = {
  application_id: 'application-responsive',
  student_id: 11,
  student_name: longChinese,
  job_id: jobFixture.job_id,
  job_title: longChinese,
  submitted_at: '2026-09-19T11:30:00+08:00',
  status: 'pending',
  status_label: '待处理',
  status_version: 1,
  position_closed: false,
  position_closed_at: null,
  effective_status: 'pending',
  effective_status_label: '待处理'
}

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      '/',
      '/login',
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

function testPinia() {
  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  auth.sessionState = 'active'
  auth.user = {
    id: 7,
    username: 'enterprise_demo',
    name: longChinese,
    role: 'enterprise'
  }
  return pinia
}

function mockApi(componentName: string) {
  mockedApiFetch.mockReset()
  mockedApiFetch.mockImplementation(async path => {
    if (path === '/api/onboarding/enterprise') {
      return {
        success: true,
        required: false,
        portal: 'enterprise'
      } as never
    }
    if (path === '/api/enterprise/dashboard') {
      return {
        success: true,
        dashboard: {
          active_job_count: 1,
          received_resume_count: 1
        }
      } as never
    }
    if (path === '/api/interest-tags') {
      return {
        success: true,
        tags: [
          {
            id: 9,
            group_key: 'job',
            name: '农业技术员'
          }
        ]
      } as never
    }
    if (path === '/api/enterprise/jobs') {
      return { success: true, jobs: [jobFixture] } as never
    }
    if (
      path === '/api/enterprise/applications' ||
      path.startsWith('/api/enterprise/applications?')
    ) {
      return {
        success: true,
        applications: [applicationFixture]
      } as never
    }
    throw new Error(`${componentName} unexpected request: ${path}`)
  })
}

function mountedOffenders(wrapper: ReturnType<typeof mount>): string[] {
  return wrapper
    .findAll('*')
    .filter(element => {
      const computed = window.getComputedStyle(element.element)
      const hasText = Boolean(element.text().trim())
      return computed.position === 'fixed' && hasText
    })
    .map(element => element.element.tagName)
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

async function mountConsoleView(
  name: string,
  component: Component,
  path: string
) {
  mockApi(name)
  const router = testRouter()
  await router.push(path)
  await router.isReady()
  const wrapper = mount(component, {
    global: {
      plugins: [testPinia(), router]
    }
  })
  await flushPromises()
  return wrapper
}

describe('enterprise console responsive contracts', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('declares containment, wrapping, breakpoint and theme-token contracts', () => {
    const sources = [
      enterpriseConsoleNavSource,
      enterpriseDashboardCardsSource,
      enterprisePortalSource,
      enterpriseJobsSource,
      enterpriseApplicationsSource
    ]

    expect(
      cssRule(enterprisePortalSource, '.enterprise-portal-dashboard')
    ).toContain('overflow-x: clip')
    expect(
      cssRule(enterpriseDashboardCardsSource, '.enterprise-dashboard-cards')
    ).toContain('grid-template-columns: repeat(2, minmax(0, 1fr))')
    expect(
      cssRule(enterpriseDashboardCardsSource, '.enterprise-dashboard-cards')
    ).toContain('min-width: 0')
    expect(
      cssRule(
        mediaBlock(enterpriseDashboardCardsSource, 720),
        '.enterprise-dashboard-cards'
      )
    ).toContain('grid-template-columns: minmax(0, 1fr)')

    expect(cssRule(enterpriseJobsSource, '.enterprise-jobs-page')).toContain(
      'min-width: 0'
    )
    expect(cssRule(enterpriseJobsSource, '.enterprise-jobs-page')).toContain(
      'overflow-x: clip'
    )
    expect(
      cssRule(
        mediaBlock(enterpriseJobsSource, 720),
        '.job-row'
      )
    ).toContain('grid-template-columns: minmax(0, 1fr)')
    expect(enterpriseJobsSource).not.toContain('white-space: nowrap')

    expect(
      cssRule(enterpriseApplicationsSource, '.enterprise-applications-page')
    ).toContain('overflow-x: clip')
    expect(
      cssRule(
        enterpriseApplicationsSource,
        '.application-row__student'
      )
    ).toContain('overflow-wrap: anywhere')
    expect(
      cssRule(
        mediaBlock(enterpriseApplicationsSource, 720),
        '.application-row'
      )
    ).toContain('grid-template-columns: minmax(0, 1fr)')

    expect(sources.join('\n')).not.toMatch(
      /#[0-9a-f]{3,8}|rgba?\(|hsla?\(|\bcyan\b/i
    )
  })

  describe.each(widths)('at %dpx', width => {
    it('mounts the dashboard, jobs and applications with real long CJK DOM', async () => {
      vi.stubGlobal('innerWidth', width)
      const cases = [
        {
          name: 'dashboard',
          component: EnterprisePortalView,
          path: '/enterprise',
          expectedText: longChinese
        },
        {
          name: 'jobs',
          component: EnterpriseJobsView,
          path: '/enterprise/jobs',
          expectedText: longDescription
        },
        {
          name: 'applications',
          component: EnterpriseApplicationsView,
          path: '/enterprise/applications',
          expectedText: longChinese
        }
      ] as const

      for (const view of cases) {
        const wrapper = await mountConsoleView(
          view.name,
          view.component,
          view.path
        )

        expect(wrapper.text()).toContain(view.expectedText)
        expect(mountedOffenders(wrapper)).toEqual([])
        expect(wrapper.element.querySelectorAll('button, a, select, input').length)
          .toBeGreaterThan(0)

        const sources =
          view.name === 'dashboard'
            ? [
                enterpriseConsoleNavSource,
                enterpriseDashboardCardsSource,
                enterprisePortalSource
              ]
            : view.name === 'jobs'
              ? [enterpriseJobsSource]
              : [enterpriseApplicationsSource]
        expect(
          sources.every(source =>
            fixedPixelWidths(source).every(value => value <= width)
          )
        ).toBe(true)

        wrapper.unmount()
      }
    })
  })
})
