import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError, apiFetch } from '@/api/client'
import enterpriseDashboardCardsSource from '@/components/EnterpriseDashboardCards.vue?raw'
import enterpriseConsoleNavSource from '@/components/EnterpriseConsoleNav.vue?raw'

import EnterprisePortalView from './EnterprisePortalView.vue'
import enterprisePortalViewSource from './EnterprisePortalView.vue?raw'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

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

function mediaBlock(source: string, maxWidth: number): string {
  const marker = `@media (max-width: ${maxWidth}px)`
  const start = source.indexOf(marker)
  expect(start).toBeGreaterThanOrEqual(0)
  return source.slice(start)
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

async function mountPortal() {
  const router = testRouter()
  await router.push('/enterprise')
  await router.isReady()

  const wrapper = mount(EnterprisePortalView, {
    global: {
      plugins: [createPinia(), router]
    }
  })
  await flushPromises()
  return wrapper
}

describe('EnterprisePortalView', () => {
  beforeEach(() => {
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
            active_job_count: 2,
            received_resume_count: 5
          }
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })
  })

  it('shows the two real dashboard metrics and enterprise navigation links', async () => {
    const wrapper = await mountPortal()

    expect(
      wrapper.get('[data-test="active-job-count"]').text()
    ).toContain('2')
    expect(
      wrapper.get('[data-test="received-resume-count"]').text()
    ).toContain('5')
    expect(
      wrapper.get('[data-test="enterprise-nav-dashboard"]').attributes('href')
    ).toBe('/enterprise')
    expect(
      wrapper.get('[data-test="enterprise-nav-jobs"]').attributes('href')
    ).toBe('/enterprise/jobs')
    expect(
      wrapper
        .get('[data-test="enterprise-nav-applications"]')
        .attributes('href')
    ).toBe('/enterprise/applications')
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/enterprise/dashboard'
    )
  })

  it('keeps navigation visible and retries after dashboard loading fails', async () => {
    let dashboardRequests = 0
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/onboarding/enterprise') {
        return {
          success: true,
          required: false,
          portal: 'enterprise'
        } as never
      }
      if (path === '/api/enterprise/dashboard') {
        dashboardRequests += 1
        if (dashboardRequests === 1) {
          throw new ApiError('企业看板暂不可用', 503)
        }
        return {
          success: true,
          dashboard: {
            active_job_count: 2,
            received_resume_count: 5
          }
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = await mountPortal()

    expect(
      wrapper.get('[data-test="enterprise-nav-jobs"]').attributes('href')
    ).toBe('/enterprise/jobs')
    expect(wrapper.get('[role="alert"]').text()).toContain(
      '企业看板暂不可用'
    )

    await wrapper.get('[data-test="dashboard-retry"]').trigger('click')
    await flushPromises()

    expect(dashboardRequests).toBe(2)
    expect(
      wrapper.get('[data-test="active-job-count"]').text()
    ).toContain('2')
    expect(
      wrapper.get('[data-test="received-resume-count"]').text()
    ).toContain('5')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('locks CJK wrapping, responsive breakpoints and light-theme token contracts', () => {
    const sources = [
      enterpriseConsoleNavSource,
      enterpriseDashboardCardsSource,
      enterprisePortalViewSource
    ]
    const nav = cssRule(
      enterpriseConsoleNavSource,
      '.enterprise-console-nav'
    )
    const navInner = cssRule(
      enterpriseConsoleNavSource,
      '.enterprise-console-nav__inner'
    )
    const navLink = cssRule(
      enterpriseConsoleNavSource,
      '.enterprise-console-nav a'
    )
    const card = cssRule(
      enterpriseDashboardCardsSource,
      '.enterprise-dashboard-card'
    )
    const cardCopy = cssRule(
      enterpriseDashboardCardsSource,
      '.enterprise-dashboard-card__copy'
    )
    const view = cssRule(
      enterprisePortalViewSource,
      '.enterprise-portal-dashboard'
    )

    expect(nav).toContain('min-width: 0')
    expect(nav).toContain('overflow-x: clip')
    expect(navInner).toContain('overflow-x: auto')
    expect(navInner).toContain('overscroll-behavior-inline: contain')
    expect(navLink).toContain('white-space: nowrap')

    expect(card).toContain('min-width: 0')
    expect(cardCopy).toContain('line-break: strict')
    expect(cardCopy).toContain('overflow-wrap: break-word')
    expect(cardCopy).toContain('text-wrap: pretty')
    expect(cardCopy).toContain('word-break: normal')
    expect(
      cssRule(
        mediaBlock(enterpriseDashboardCardsSource, 720),
        '.enterprise-dashboard-cards'
      )
    ).toContain('grid-template-columns: minmax(0, 1fr)')

    expect(view).toContain('width: min(100%, 1180px)')
    expect(view).toContain('min-width: 0')
    expect(view).toContain('overflow-x: clip')
    expect(enterprisePortalViewSource).toContain(
      '@media (max-width: 720px)'
    )

    ;[320, 375, 1280].forEach(viewport => {
      expect(
        sources.every(
          source =>
            !source.includes(`min-width: ${viewport}px`) &&
            !source.includes(`width: ${viewport}px`)
        )
      ).toBe(true)
    })
    expect(sources.join('\n')).not.toMatch(
      /#[0-9a-f]{3,8}|rgba?\(|hsla?\(/i
    )
  })
})
