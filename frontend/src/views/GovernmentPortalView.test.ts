import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import GovernmentPortalView from './GovernmentPortalView.vue'
import governmentPortalSource from './GovernmentPortalView.vue?raw'

const workspaceEntries = [
  {
    id: 'government-policy-publish',
    label: '政策管理',
    href: '/government/policies'
  },
  {
    id: 'government-news-publish',
    label: '新闻管理',
    href: '/government/news'
  },
  {
    id: 'government-dashboard',
    label: '数据看板',
    href: '/government/dashboard'
  },
  {
    id: 'government-messages',
    label: '消息中心',
    href: '/messages'
  }
] as const

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      '/government',
      ...workspaceEntries.map(entry => entry.href)
    ].map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}

function cssRule(css: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(
    new RegExp(`(?:^|\\n)\\s*${escaped}\\s*\\{([^{}]*)\\}`)
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

describe('GovernmentPortalView', () => {
  it('renders the console navigation and exact workspace entries', async () => {
    const router = testRouter()
    await router.push('/government')
    await router.isReady()

    const wrapper = mount(GovernmentPortalView, {
      global: { plugins: [router] }
    })

    expect(wrapper.find('.government-console-nav').exists()).toBe(true)
    expect(
      wrapper.findAll('[data-test="government-workspace-entry"]')
    ).toHaveLength(workspaceEntries.length)

    for (const expected of workspaceEntries) {
      const entry = wrapper.get(`#${expected.id}`)
      expect(entry.get('a').attributes('href')).toBe(expected.href)
      expect(entry.text()).toContain(expected.label)
      expect(entry.text()).toContain('进入')
      expect(entry.text()).not.toContain('后续开放')
    }
  })

  it('keeps Chinese portal copy intact at 320, 375, and 1280', () => {
    // jsdom does not calculate CSS layout; these assertions lock the
    // responsive and CJK wrapping contract for real-browser verification.
    const viewports = [320, 375, 1280]
    const page = cssRule(governmentPortalSource, '.government-portal-page')
    const main = cssRule(governmentPortalSource, '.government-portal')
    const heading = cssRule(
      governmentPortalSource,
      '.government-portal__heading p'
    )
    const entryCopy = cssRule(
      governmentPortalSource,
      '.government-portal-entry__copy p'
    )
    const mobile = mediaBlock(governmentPortalSource, 640)

    expect(page).toContain('min-width: 0')
    expect(page).toContain('overflow-x: clip')
    expect(main).toContain('width: min(100%, 1180px)')
    expect(main).toContain('min-width: 0')
    expect(cssRule(governmentPortalSource, '.government-portal__heading h1')).toContain(
      'text-wrap: balance'
    )

    for (const rule of [heading, entryCopy]) {
      expect(rule).toContain('line-break: strict')
      expect(rule).toContain('overflow-wrap: anywhere')
      expect(rule).toContain('text-wrap: pretty')
      expect(rule).toContain('word-break: keep-all')
    }

    expect(
      cssRule(mobile, '.government-portal__heading')
    ).toContain('grid-template-columns: minmax(0, 1fr)')
    expect(
      cssRule(mobile, '.government-portal-entry')
    ).toContain('grid-template-columns: minmax(0, 1fr)')
    expect(
      cssRule(governmentPortalSource, '.government-portal-entry__action')
    ).toContain('white-space: nowrap')

    for (const viewport of viewports) {
      expect(governmentPortalSource).not.toContain(`min-width: ${viewport}px`)
      expect(governmentPortalSource).not.toContain(`width: ${viewport}px`)
    }
    expect(governmentPortalSource).not.toMatch(/#[0-9a-f]{3,8}|rgba?\(/i)
  })
})
