import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useLocalResourcesStore } from '@/stores/localResources'

import LocalResourceCaseDetailView from './LocalResourceCaseDetailView.vue'
import LocalResourceCasesView from './LocalResourceCasesView.vue'
import localResourceCaseDetailSource from './LocalResourceCaseDetailView.vue?raw'
import localResourceCasesSource from './LocalResourceCasesView.vue?raw'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { caseId: 'case-1' } }),
  RouterLink: {
    props: ['to'],
    template: '<a :href="String(to)"><slot /></a>'
  }
}))

const caseSummary = {
  id: 'case-1',
  title: '案例一',
  summary: '从本地资源起步，逐步建立稳定经营模式。',
  published_at: '2026-09-19T10:00:00+08:00',
  updated_at: '2026-09-19T10:00:00+08:00',
  is_demo: true
}

const caseDetail = {
  ...caseSummary,
  background: '创业背景',
  journey: '创业历程',
  lessons: '经验启示'
}

function mountList(
  cases = [caseSummary],
  loadResult: boolean | Promise<boolean> = true
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useLocalResourcesStore()
  store.cases = cases
  const loadCases = vi
    .spyOn(store, 'loadCases')
    .mockReturnValue(Promise.resolve(loadResult))
  const wrapper = mount(LocalResourceCasesView, {
    global: {
      plugins: [pinia],
      stubs: { AppHeader: true, LocalResourcesNav: true }
    }
  })
  return { loadCases, store, wrapper }
}

function mountDetail() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useLocalResourcesStore()
  store.caseDetail = caseDetail
  const openCase = vi.spyOn(store, 'openCase').mockResolvedValue(true)
  const wrapper = mount(LocalResourceCaseDetailView, {
    global: {
      plugins: [pinia],
      stubs: { AppHeader: true, LocalResourcesNav: true }
    }
  })
  return { openCase, wrapper }
}

describe('success-case views', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('loads cases and renders stable detail links with their summary and demo label', async () => {
    const { loadCases, wrapper } = mountList()
    await flushPromises()

    expect(loadCases).toHaveBeenCalledTimes(1)
    const link = wrapper.get('[data-test="case-link"]')
    expect(link.attributes('href')).toBe(
      '/student/local-resources/cases/case-1'
    )
    expect(link.text()).toContain('案例一')
    expect(link.text()).toContain(caseSummary.summary)
    expect(link.text()).toContain('演示数据')
  })

  it('distinguishes an empty list from unavailable data', async () => {
    const empty = mountList([])
    await flushPromises()
    expect(empty.wrapper.get('[data-test="cases-empty"]').text()).toBe(
      '暂无成功案例'
    )
    expect(
      empty.wrapper.find('[data-test="cases-unavailable"]').exists()
    ).toBe(false)

    const unavailable = mountList([], false)
    await flushPromises()
    expect(
      unavailable.wrapper.get('[data-test="cases-unavailable"]').text()
    ).toBe('案例数据暂不可用')
    expect(
      unavailable.wrapper.find('[data-test="cases-empty"]').exists()
    ).toBe(false)
  })

  it('keeps current store state visible while the mount refresh is pending', async () => {
    let finishLoading: (loaded: boolean) => void = () => undefined
    const pendingLoad = new Promise<boolean>(resolve => {
      finishLoading = resolve
    })
    const { store, wrapper } = mountList([caseSummary], pendingLoad)

    expect(wrapper.text()).toContain(caseSummary.title)

    store.cases = []
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('暂无成功案例')

    finishLoading(true)
    await flushPromises()
  })

  it('opens the route case and renders all three exact detail sections', async () => {
    const { openCase, wrapper } = mountDetail()
    await flushPromises()

    expect(openCase).toHaveBeenCalledWith('case-1')
    expect(wrapper.get('[data-test="case-background"]').text()).toContain(
      '创业背景'
    )
    expect(wrapper.get('[data-test="case-journey"]').text()).toContain(
      '创业历程'
    )
    expect(wrapper.get('[data-test="case-lessons"]').text()).toContain(
      '经验启示'
    )
    expect(wrapper.text()).toContain(caseDetail.title)
    expect(wrapper.text()).toContain(caseDetail.summary)
    expect(wrapper.text()).toContain('演示数据')
  })

  it('renders an existing detail before openCase finishes', () => {
    const { wrapper } = mountDetail()

    expect(wrapper.find('[data-test="case-background"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="case-detail-loading"]').exists()).toBe(
      false
    )
  })

  it('renders no user-write controls', async () => {
    const list = mountList()
    const detail = mountDetail()
    await flushPromises()

    for (const wrapper of [list.wrapper, detail.wrapper]) {
      expect(
        wrapper.findAll('button, form, input, textarea, select')
      ).toHaveLength(0)
      expect(wrapper.text()).not.toMatch(
        /创建|编辑|删除|提交|收藏|评论|分享|排行/
      )
    }
  })

  it('uses token-only light surfaces and CJK-safe wrapping at narrow widths', () => {
    const sources = [localResourceCasesSource, localResourceCaseDetailSource]
    const css = sources.join('\n')

    expect(css).toContain('background: var(--ark-surface-0)')
    expect(css).toContain('@media (max-width: 640px)')
    expect(css.match(/line-break: strict/g)?.length).toBeGreaterThanOrEqual(4)
    expect(css.match(/word-break: keep-all/g)?.length).toBeGreaterThanOrEqual(4)
    expect(css).toContain('overflow-wrap: anywhere')
    expect(css).not.toMatch(/#[0-9a-f]{3,8}|rgba?\(|hsla?\(/i)
    expect(css).not.toMatch(/linear-gradient|radial-gradient/i)
    expect(css).not.toMatch(/letter-spacing:\s*-/)
    expect(css).not.toMatch(/\d(?:vw|vmin|vmax)/i)
  })
})
