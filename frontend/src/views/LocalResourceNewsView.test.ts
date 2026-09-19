import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { LocalResourceNews } from '@/api/types'
import { useLocalResourcesStore } from '@/stores/localResources'

import LocalResourceNewsDetailView from './LocalResourceNewsDetailView.vue'
import LocalResourceNewsView from './LocalResourceNewsView.vue'
import localResourceNewsDetailSource from './LocalResourceNewsDetailView.vue?raw'
import localResourceNewsSource from './LocalResourceNewsView.vue?raw'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { newsId: 'news-1' } }),
  RouterLink: {
    props: ['to'],
    template: '<a :href="String(to)"><slot /></a>'
  }
}))

const categoryRows = [
  ['news', '新闻'],
  ['disaster_warning', '灾害预警'],
  ['policy_update', '政策更新']
] as const

const newsFixture: LocalResourceNews = {
  id: 'news-1',
  title: '本地新闻标题',
  content: '新闻正文包含足够长的中文内容，用于验证窄屏下的稳定换行。',
  category_code: 'news',
  category_label: '新闻',
  published_at: '2026-09-19T10:00:00+08:00',
  updated_at: '2026-09-19T10:00:00+08:00',
  version: 1
}

function mountList(
  news: LocalResourceNews[] = [newsFixture],
  loadResult: boolean | Promise<boolean> = true
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useLocalResourcesStore()
  store.news = news
  const loadNews = vi
    .spyOn(store, 'loadNews')
    .mockReturnValue(Promise.resolve(loadResult))
  const wrapper = mount(LocalResourceNewsView, {
    global: {
      plugins: [pinia],
      stubs: { AppHeader: true, LocalResourcesNav: true }
    }
  })
  return { loadNews, store, wrapper }
}

function mountDetail(options?: {
  detail?: LocalResourceNews | null
  openResult?: boolean
  recordError?: Error
}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useLocalResourcesStore()
  store.newsDetail =
    options && 'detail' in options
      ? (options.detail ?? null)
      : newsFixture
  const openNews = vi
    .spyOn(store, 'openNews')
    .mockResolvedValue(options?.openResult ?? true)
  const recordNewsView = vi.spyOn(store, 'recordNewsView')
  if (options?.recordError) {
    recordNewsView.mockRejectedValue(options.recordError)
  } else {
    recordNewsView.mockResolvedValue(undefined)
  }
  const wrapper = mount(LocalResourceNewsDetailView, {
    global: {
      plugins: [pinia],
      stubs: { AppHeader: true, LocalResourcesNav: true }
    }
  })
  return { openNews, recordNewsView, store, wrapper }
}

describe('local-resource news views', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('loads news and renders exactly three categories in fixed order', async () => {
    const { loadNews, wrapper } = mountList()
    await flushPromises()

    expect(loadNews).toHaveBeenCalledTimes(1)
    expect(loadNews).toHaveBeenCalledWith()
    expect(
      wrapper
        .findAll('[data-test="news-category"]')
        .map(category => category.text())
    ).toEqual(categoryRows.map(([, label]) => label))
  })

  it('selects each category through loadNews and links to the exact detail route', async () => {
    const { loadNews, wrapper } = mountList()
    await flushPromises()
    const categories = wrapper.findAll('[data-test="news-category"]')

    for (const [index, [code]] of categoryRows.entries()) {
      await categories[index].trigger('click')
      await flushPromises()
      expect(loadNews).toHaveBeenLastCalledWith(code)
      expect(categories[index].attributes('aria-pressed')).toBe('true')
    }

    const link = wrapper.get('[data-test="news-link"]')
    expect(link.attributes('href')).toBe(
      '/student/local-resources/news/news-1'
    )
    expect(link.text()).toContain(newsFixture.title)
    expect(link.text()).toContain(newsFixture.category_label)
    expect(link.text()).toContain(newsFixture.published_at)
  })

  it('renders deleted item disappearance without subscription or policy controls', async () => {
    const { store, wrapper } = mountList()
    await flushPromises()

    store.news = []
    await wrapper.vm.$nextTick()

    expect(wrapper.get('[data-test="news-empty"]').text()).toBe('暂无新闻')
    expect(wrapper.find('[data-test="news-link"]').exists()).toBe(false)
    expect(wrapper.findAll('button')).toHaveLength(3)
    expect(wrapper.text()).not.toMatch(
      /订阅|取消订阅|政策推送|删除|下架|重新上架|恢复/
    )
  })

  it('records a view only after openNews returns content and renders detail fields', async () => {
    const { openNews, recordNewsView, wrapper } = mountDetail()

    expect(openNews).toHaveBeenCalledWith('news-1')
    expect(recordNewsView).not.toHaveBeenCalled()

    await flushPromises()

    expect(recordNewsView).toHaveBeenCalledWith('news-1')
    expect(wrapper.get('[data-test="news-content"]').text()).toContain(
      newsFixture.content
    )
    expect(wrapper.text()).toContain(newsFixture.title)
    expect(wrapper.text()).toContain(newsFixture.category_label)
    expect(wrapper.text()).toContain(newsFixture.published_at)
  })

  it('does not record when openNews fails or leaves content absent', async () => {
    const failed = mountDetail({ openResult: false })
    await flushPromises()

    expect(failed.recordNewsView).not.toHaveBeenCalled()
    expect(failed.wrapper.find('[data-test="news-content"]').exists()).toBe(
      false
    )
    expect(
      failed.wrapper.get('[data-test="news-detail-unavailable"]').text()
    ).toBe('新闻数据暂不可用')

    const absent = mountDetail({ detail: null, openResult: true })
    await flushPromises()

    expect(absent.recordNewsView).not.toHaveBeenCalled()
    expect(absent.wrapper.find('[data-test="news-content"]').exists()).toBe(
      false
    )
  })

  it('renders deleted target as not found without hiding view-record failure', async () => {
    const { store, wrapper } = mountDetail()
    store.viewNotice = '浏览量暂未记录'
    await flushPromises()

    expect(wrapper.get('[data-test="news-content"]').text()).toContain(
      newsFixture.content
    )
    expect(wrapper.get('[data-test="news-view-notice"]').text()).toBe(
      '浏览量暂未记录'
    )

    store.newsDetail = null
    store.error = '新闻不存在'
    await wrapper.vm.$nextTick()

    expect(wrapper.get('[data-test="news-not-found"]').text()).toBe(
      '新闻不存在'
    )
    expect(wrapper.find('[data-test="news-content"]').exists()).toBe(false)
  })

  it('keeps content visible when recordNewsView rejects', async () => {
    const { wrapper } = mountDetail({
      recordError: new Error('view unavailable')
    })
    await flushPromises()

    expect(wrapper.get('[data-test="news-content"]').text()).toContain(
      newsFixture.content
    )
    expect(wrapper.get('[data-test="news-view-notice"]').text()).toBe(
      '浏览量暂未记录'
    )
  })

  it('renders no news management or restore controls', async () => {
    const list = mountList()
    const detail = mountDetail()
    await flushPromises()

    for (const wrapper of [list.wrapper, detail.wrapper]) {
      expect(
        wrapper.findAll('form, input, textarea, select')
      ).toHaveLength(0)
      expect(wrapper.text()).not.toMatch(
        /订阅|取消订阅|政策推送|删除|下架|重新上架|恢复|创建|编辑|发布/
      )
    }
    expect(
      detail.wrapper.findAll('button')
    ).toHaveLength(0)
  })

  it('uses token-only light surfaces and CJK-safe wrapping at narrow widths', () => {
    const css = [
      localResourceNewsSource,
      localResourceNewsDetailSource
    ].join('\n')

    expect(css).toContain('background: var(--ark-surface-0)')
    expect(css).toContain('width: min(100%, 1180px)')
    expect(css).toContain('@media (max-width: 640px)')
    expect(css.match(/line-break: strict/g)?.length).toBeGreaterThanOrEqual(6)
    expect(css.match(/word-break: keep-all/g)?.length).toBeGreaterThanOrEqual(6)
    expect(css).toContain('overflow-wrap: anywhere')
    expect(css).not.toMatch(/#[0-9a-f]{3,8}|rgba?\(|hsla?\(/i)
    expect(css).not.toMatch(/linear-gradient|radial-gradient/i)
    expect(css).not.toMatch(/orb|bokeh/i)
    expect(css).not.toMatch(/box-shadow|border-radius/i)
    expect(css).not.toMatch(/letter-spacing:\s*-/)
    expect(css).not.toMatch(/\d(?:vw|vmin|vmax)/i)
  })
})
