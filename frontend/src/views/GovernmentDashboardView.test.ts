import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type { GovernmentDashboard } from '@/api/types'
import { useGovernmentConsoleStore } from '@/stores/governmentConsole'

import GovernmentDashboardView from './GovernmentDashboardView.vue'
import governmentDashboardViewSource from './GovernmentDashboardView.vue?raw'

const dashboardFixture = {
  employment: {
    active_job_count: 12,
    cumulative_application_count: 34,
    available: true
  },
  policy: {
    active_count: 5,
    unpublished_count: 6,
    total_count: 11,
    view_count: 78
  },
  news: {
    total_count: 9,
    view_count: 123
  }
} satisfies GovernmentDashboard

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      '/',
      '/government/policies',
      '/government/news',
      '/government/dashboard',
      '/:pathMatch(.*)*'
    ].map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}

async function mountView(
  dashboard: GovernmentDashboard | null = dashboardFixture
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useGovernmentConsoleStore()
  store.dashboard = dashboard

  const loadDashboard = vi
    .spyOn(store, 'loadDashboard')
    .mockResolvedValue(true)

  const router = testRouter()
  await router.push('/government/dashboard')
  await router.isReady()

  const wrapper = mount(GovernmentDashboardView, {
    global: {
      plugins: [pinia, router]
    }
  })
  await flushPromises()

  return { wrapper, store, loadDashboard }
}

function cssRule(css: string, selector: string): string {
  const matches = Array.from(
    css.matchAll(/(?:^|\n)\s*([^{}\n]+?)\s*\{([\s\S]*?)\}/g)
  ).filter(candidate => candidate[1].trim() === selector)
  const match = matches[matches.length - 1]
  expect(match).not.toBeUndefined()
  return (match?.[2] ?? '').replace(/\s+/g, ' ').trim()
}

function mediaBlock(source: string, maxWidth: number): string {
  const marker = `@media (max-width: ${maxWidth}px)`
  const start = source.indexOf(marker)
  expect(start).toBeGreaterThanOrEqual(0)
  return source.slice(start)
}

function mediaRule(
  source: string,
  maxWidth: number,
  selector: string
): string {
  const block = mediaBlock(source, maxWidth)
  const bodyStart = block.indexOf('{') + 1
  const bodyEnd = block.lastIndexOf('}')
  return cssRule(block.slice(bodyStart, bodyEnd), selector)
}

describe('GovernmentDashboardView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders only the seven allowed metrics with their values', async () => {
    const { wrapper } = await mountView()

    expect(
      wrapper
        .findAll('[data-test="metric-label"]')
        .map(label => label.text())
    ).toEqual([
      '在招岗位数',
      '累计投递量',
      '在架政策数',
      '下架政策数',
      '政策累计点击浏览量',
      '新闻总数',
      '新闻累计点击浏览量'
    ])
    expect(wrapper.get('[data-test="metric-active-job-count"]').text()).toContain(
      '12'
    )
    expect(
      wrapper
        .get('[data-test="metric-cumulative-application-count"]')
        .text()
    ).toContain('34')
    expect(wrapper.get('[data-test="metric-policy-active"]').text()).toContain(
      '5'
    )
    expect(
      wrapper.get('[data-test="metric-policy-unpublished"]').text()
    ).toContain('6')
    expect(wrapper.get('[data-test="metric-policy-views"]').text()).toContain(
      '78'
    )
    expect(wrapper.get('[data-test="metric-news-total"]').text()).toContain(
      '9'
    )
    expect(wrapper.get('[data-test="metric-news-views"]').text()).toContain(
      '123'
    )
  })

  it('does not render forbidden user, training, export or mutation controls', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.text()).not.toMatch(
      /总用户数|角色分布|地区分布|方向分布|用户详情|课程数|学习行为量|进度|完课率|证书数|导出|审核|审批|AI/
    )
    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.find('[data-test="dashboard-export"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="dashboard-review"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="dashboard-ai"]').exists()).toBe(false)
  })

  it('shows unavailable employment without zero values or hiding content metrics', async () => {
    const { wrapper } = await mountView({
      ...dashboardFixture,
      employment: {
        active_job_count: null,
        cumulative_application_count: null,
        available: false
      }
    })

    const unavailable = wrapper.findAll(
      '[data-test="employment-unavailable"]'
    )
    expect(unavailable).toHaveLength(2)
    unavailable.forEach(metric => {
      expect(metric.element.parentElement?.textContent).toContain('--')
      expect(metric.text()).toContain('就业数据暂不可用')
    })
    expect(wrapper.text()).not.toContain('0')
    expect(wrapper.get('[data-test="metric-policy-views"]').text()).toContain(
      '78'
    )
    expect(wrapper.get('[data-test="metric-news-views"]').text()).toContain(
      '123'
    )
  })

  it('keeps the load error recoverable without adding a mutation', async () => {
    const { wrapper, store, loadDashboard } = await mountView(null)
    store.error = '数据看板加载失败'
    await wrapper.vm.$nextTick()

    expect(wrapper.get('[data-test="dashboard-error"]').text()).toContain(
      '数据看板加载失败'
    )

    await wrapper.get('[data-test="dashboard-retry"]').trigger('click')

    expect(loadDashboard).toHaveBeenCalledTimes(2)
  })

  it.each([
    {
      width: 320,
      layout: 'mobile',
      groups: 'grid-template-columns: minmax(0, 1fr)',
      padding: 'padding: 28px 14px 48px'
    },
    {
      width: 375,
      layout: 'mobile',
      groups: 'grid-template-columns: minmax(0, 1fr)',
      padding: 'padding: 28px 14px 48px'
    },
    {
      width: 1280,
      layout: 'desktop',
      groups: 'grid-template-columns: repeat(3, minmax(0, 1fr))',
      padding: 'padding: 40px 24px 72px'
    }
  ] as const)(
    'binds CJK typography and layout contracts at $width px',
    ({ width, layout, groups, padding }) => {
      const desktopCss = governmentDashboardViewSource.slice(
        0,
        governmentDashboardViewSource.indexOf('@media')
      )

      expect(
        cssRule(desktopCss, '.government-dashboard-page')
      ).toContain('overflow-x: clip')
      expect(cssRule(desktopCss, '.government-dashboard')).toContain(
        'width: min(100%, 1180px)'
      )
      expect(cssRule(desktopCss, '.government-dashboard')).toContain(
        'min-width: 0'
      )
      if (layout === 'desktop') {
        expect(cssRule(desktopCss, '.government-dashboard')).toContain(padding)
      }

      const typographyRules = [
        cssRule(desktopCss, '.dashboard-hero__identity p'),
        cssRule(desktopCss, '.dashboard-metric dt'),
        cssRule(desktopCss, '.dashboard-empty')
      ]
      typographyRules.forEach(rule => {
        expect(rule).toContain('line-break: strict')
        expect(rule).toContain('word-break: keep-all')
        expect(rule).toContain('overflow-wrap: anywhere')
      })
      expect(
        cssRule(desktopCss, '.dashboard-metric dt')
      ).toContain('white-space: nowrap')

      if (layout === 'mobile') {
        expect(
          mediaRule(governmentDashboardViewSource, 760, '.dashboard-groups')
        ).toContain(groups)
        expect(
          mediaRule(
            governmentDashboardViewSource,
            760,
            '.government-dashboard'
          )
        ).toContain(padding)
      } else {
        expect(cssRule(desktopCss, '.dashboard-groups')).toContain(groups)
      }

      expect(governmentDashboardViewSource).not.toContain(
        `min-width: ${width}px`
      )
      expect(governmentDashboardViewSource).not.toContain(`width: ${width}px`)
      expect(governmentDashboardViewSource).not.toMatch(
        /#[0-9a-f]{3,8}|rgba?\(/i
      )
    }
  )
})
