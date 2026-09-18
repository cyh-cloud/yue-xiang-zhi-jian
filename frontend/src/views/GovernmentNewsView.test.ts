import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type { GovernmentNews } from '@/api/types'
import GovernmentConsoleNav from '@/components/GovernmentConsoleNav.vue'
import governmentConsoleNavSource from '@/components/GovernmentConsoleNav.vue?raw'
import { useGovernmentConsoleStore } from '@/stores/governmentConsole'

import GovernmentNewsView from './GovernmentNewsView.vue'
import governmentNewsViewSource from './GovernmentNewsView.vue?raw'

const newsCategories = [
  ['news', '新闻'],
  ['disaster_warning', '灾害预警'],
  ['policy_update', '政策更新']
] as const

function newsFixture(
  patch: Partial<GovernmentNews> = {}
): GovernmentNews {
  return {
    id: 'news-1',
    title: '暴雨预警',
    content: '请提前防范',
    category_code: 'disaster_warning',
    category_label: '灾害预警',
    view_count: 7,
    version: 3,
    published_at: '2026-09-18T10:00:00+08:00',
    updated_at: '2026-09-18T10:00:00+08:00',
    ...patch
  }
}

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

async function mountView(news: GovernmentNews[] = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useGovernmentConsoleStore()
  store.news = news

  vi.spyOn(store, 'loadNews').mockResolvedValue(true)
  vi.spyOn(store, 'publishNews').mockResolvedValue(true)
  vi.spyOn(store, 'deleteNews').mockResolvedValue(true)

  const router = testRouter()
  await router.push('/government/news')
  await router.isReady()

  const wrapper = mount(GovernmentNewsView, {
    global: {
      plugins: [pinia, router]
    }
  })
  await flushPromises()

  return { wrapper, store }
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

describe('GovernmentNewsView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('publishes the three-category news form with a generated request id', async () => {
    const { wrapper, store } = await mountView()
    const randomUUID = vi
      .spyOn(globalThis.crypto, 'randomUUID')
      .mockReturnValue('00000000-0000-4000-8000-000000000001')

    const categoryOptions = wrapper
      .get('[data-test="news-category"]')
      .findAll('option')
      .map(option => [
        option.attributes('value'),
        option.text()
      ])
    expect(categoryOptions).toEqual(newsCategories)

    await wrapper.get('[data-test="news-title"]').setValue(' 暴雨预警 ')
    await wrapper.get('[data-test="news-content"]').setValue(' 请提前防范 ')
    await wrapper
      .get('[data-test="news-category"]')
      .setValue('disaster_warning')
    await wrapper.get('[data-test="news-form"]').trigger('submit')

    expect(store.publishNews).toHaveBeenCalledWith({
      request_id: '00000000-0000-4000-8000-000000000001',
      title: '暴雨预警',
      content: '请提前防范',
      category_code: 'disaster_warning'
    })
    expect(randomUUID).toHaveBeenCalledOnce()
  })

  it('reuses the request id when publication succeeds but refresh fails', async () => {
    const { wrapper, store } = await mountView()
    const randomUUID = vi
      .spyOn(globalThis.crypto, 'randomUUID')
      .mockReturnValueOnce('00000000-0000-4000-8000-000000000001')
      .mockReturnValueOnce('00000000-0000-4000-8000-000000000002')
    vi.mocked(store.publishNews)
      .mockReset()
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(true)

    await wrapper.get('[data-test="news-title"]').setValue('暴雨预警')
    await wrapper.get('[data-test="news-content"]').setValue('请提前防范')
    await wrapper.get('[data-test="news-form"]').trigger('submit')

    expect(store.publishNews).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        request_id: '00000000-0000-4000-8000-000000000001'
      })
    )

    await wrapper.get('[data-test="news-form"]').trigger('submit')

    expect(store.publishNews).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        request_id: '00000000-0000-4000-8000-000000000001'
      })
    )
    expect(randomUUID).toHaveBeenCalledTimes(1)

    await wrapper.get('[data-test="news-title"]').setValue('政策更新')
    await wrapper.get('[data-test="news-content"]').setValue('补贴申报开始')
    await wrapper.get('[data-test="news-form"]').trigger('submit')

    expect(store.publishNews).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        request_id: '00000000-0000-4000-8000-000000000002'
      })
    )
    expect(randomUUID).toHaveBeenCalledTimes(2)
  })

  it('filters the list by the three exact news categories', async () => {
    const warning = newsFixture()
    const policyUpdate = newsFixture({
      id: 'news-2',
      title: '补贴申报开始',
      category_code: 'policy_update',
      category_label: '政策更新'
    })
    const { wrapper } = await mountView([warning, policyUpdate])

    expect(wrapper.findAll('[data-test="news-row"]')).toHaveLength(2)

    await wrapper
      .get('[data-test="news-category-filter"]')
      .setValue('policy_update')

    expect(wrapper.findAll('[data-test="news-row"]')).toHaveLength(1)
    expect(wrapper.get('[data-test="news-row"]').text()).toContain(
      '补贴申报开始'
    )
  })

  it('renders the news fields with delete as the only row action', async () => {
    const news = newsFixture()
    const { wrapper } = await mountView([news])

    const row = wrapper.get('[data-test="news-row"]')
    expect(row.text()).toContain(news.title)
    expect(row.text()).toContain(news.category_label)
    expect(row.text()).toContain(String(news.view_count))
    expect(row.text()).toContain('2026-09-18 10:00')

    const remove = wrapper.get('[data-test="delete-news"]')
    expect(remove.attributes('aria-label')).toContain(news.title)
    expect(remove.attributes('title')).toBeTruthy()
    expect(wrapper.find('[data-test="unpublish-news"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="relist-news"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('下架')
    expect(wrapper.text()).not.toContain('重新上架')
  })

  it('requires an explicit confirmation before deleting news', async () => {
    const news = newsFixture()
    const { wrapper, store } = await mountView([news])

    await wrapper.get('[data-test="delete-news"]').trigger('click')
    expect(store.deleteNews).not.toHaveBeenCalled()

    const confirmation = wrapper.get(
      '[data-test="news-delete-confirmation"]'
    )
    expect(confirmation.text()).toContain(news.title)

    await wrapper
      .get('[data-test="confirm-delete-news"]')
      .trigger('click')

    expect(store.deleteNews).toHaveBeenCalledWith(
      news.id,
      news.version
    )
  })

  it('renders the empty state without a hidden restore path', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.get('[data-test="news-empty"]').text()).toContain(
      '暂无新闻'
    )
    expect(wrapper.find('[data-test="delete-news"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="unpublish-news"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="relist-news"]').exists()).toBe(false)
  })

  it('exposes the shared government workspace navigation', async () => {
    const { wrapper } = await mountView()
    const nav = wrapper.getComponent(GovernmentConsoleNav)

    expect(nav.get('nav').attributes('aria-label')).toBe('政务工作台导航')
    expect(nav.findAll('a').map(link => link.attributes('href'))).toEqual([
      '/government/policies',
      '/government/news',
      '/government/dashboard'
    ])
  })

  it('does not render review, AI, user or training controls', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.text()).not.toMatch(
      /审核|审批|AI|用户数据|培训数据|导出/
    )
    expect(wrapper.find('[data-test="news-review"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="news-ai"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="news-export"]').exists()).toBe(false)
  })

  it.each([
    {
      width: 320,
      layout: 'mobile',
      composeGrid: 'grid-template-columns: minmax(0, 1fr)',
      tableBody: 'display: grid',
      actions: 'grid-template-columns: minmax(0, 1fr)'
    },
    {
      width: 375,
      layout: 'mobile',
      composeGrid: 'grid-template-columns: minmax(0, 1fr)',
      tableBody: 'display: grid',
      actions: 'grid-template-columns: minmax(0, 1fr)'
    },
    {
      width: 1280,
      layout: 'desktop',
      composeGrid:
        'grid-template-columns: minmax(0, 1.55fr) minmax(190px, 0.75fr)',
      table: 'table-layout: fixed',
      actions: 'display: flex'
    }
  ] as const)(
    'binds typography and layout contracts at $width px',
    ({ width, layout, composeGrid, actions, ...expected }) => {
      const sources = [
        governmentNewsViewSource,
        governmentConsoleNavSource
      ]
      const mobileCss = mediaBlock(governmentNewsViewSource, 760)
      const narrowCss = mediaBlock(governmentNewsViewSource, 420)
      const desktopCss = governmentNewsViewSource.slice(
        0,
        governmentNewsViewSource.indexOf('@media')
      )

      expect(
        cssRule(desktopCss, '.government-news-page')
      ).toContain('overflow-x: clip')
      expect(
        cssRule(desktopCss, '.government-news')
      ).toContain('width: min(100%, 1180px)')
      expect(
        cssRule(desktopCss, '.government-news')
      ).toContain('min-width: 0')

      const typographyRules = [
        cssRule(desktopCss, '.news-hero__identity p'),
        cssRule(desktopCss, '.news-table td'),
        cssRule(desktopCss, '.news-delete-confirmation p')
      ]
      typographyRules.forEach(rule => {
        expect(rule).toContain('line-break: strict')
        expect(rule).toContain('word-break: keep-all')
        expect(rule).toContain('overflow-wrap: anywhere')
        expect(rule).toContain('text-wrap: pretty')
      })

      if (layout === 'mobile') {
        expect(width).toBeLessThanOrEqual(760)
        expect(
          cssRule(mobileCss, '.news-compose__grid')
        ).toContain(composeGrid)
        expect(
          cssRule(mobileCss, '.news-table tbody')
        ).toContain(expected.tableBody)
        expect(cssRule(narrowCss, '.news-actions')).toContain(
          actions
        )
        expect(governmentConsoleNavSource).toContain(
          '@media (max-width: 640px)'
        )
      } else {
        expect(width).toBeGreaterThan(760)
        expect(
          cssRule(desktopCss, '.news-compose__grid')
        ).toContain(composeGrid)
        expect(
          cssRule(desktopCss, '.news-table')
        ).toContain(expected.table)
        expect(
          cssRule(desktopCss, '.news-actions')
        ).toContain(actions)
      }

      expect(
        sources.every(
          source =>
            !source.includes(`min-width: ${width}px`) &&
            !source.includes(`width: ${width}px`)
        )
      ).toBe(true)
      expect(sources.join('\n')).not.toMatch(/#[0-9a-f]{3,8}|rgba?\(/i)
    }
  )
})
