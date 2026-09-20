import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  LocalResourcePolicy,
  PolicyCategorySubscription
} from '@/api/types'
import { ApiError, apiFetch } from '@/api/client'
import { useLocalResourcesStore } from '@/stores/localResources'

import LocalResourcePoliciesView from './LocalResourcePoliciesView.vue'
import LocalResourcePolicyDetailView from './LocalResourcePolicyDetailView.vue'
import localResourcePoliciesSource from './LocalResourcePoliciesView.vue?raw'
import localResourcePolicyDetailSource from './LocalResourcePolicyDetailView.vue?raw'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return { ...actual, apiFetch: vi.fn() }
})

const mockedApiFetch = vi.mocked(apiFetch)

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { policyId: 'policy-1' } }),
  RouterLink: {
    props: ['to'],
    template: '<a :href="String(to)"><slot /></a>'
  }
}))

const categoryRows = [
  ['subsidy', '补贴'],
  ['ecommerce', '电商'],
  ['heritage', '非遗'],
  ['training', '培训'],
  ['certification', '认证'],
  ['general', '综合'],
  ['entrepreneurship', '创业支持']
] as const

const policyFixture: LocalResourcePolicy = {
  id: 'policy-1',
  title: '创业支持政策',
  content: '政策正文包含足够长的中文内容，用于验证窄屏下的稳定换行。',
  category_code: 'entrepreneurship',
  category_label: '创业支持',
  published_at: '2026-09-19T10:00:00+08:00',
  updated_at: '2026-09-19T10:00:00+08:00',
  version: 1
}

function subscriptionState(): PolicyCategorySubscription[] {
  return categoryRows.map(([code, label]) => ({
    code,
    label,
    subscribed: code === 'ecommerce',
    recommended: code === 'entrepreneurship'
  }))
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, reject, resolve }
}

function mountList() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useLocalResourcesStore()
  store.policies = [policyFixture]
  store.subscriptions = {
    categories: subscriptionState(),
    recommended_category_codes: ['entrepreneurship']
  }
  const loadSubscriptions = vi
    .spyOn(store, 'loadSubscriptions')
    .mockResolvedValue(true)
  const loadPolicies = vi.spyOn(store, 'loadPolicies').mockResolvedValue(true)
  const subscribe = vi
    .spyOn(store, 'subscribePolicyCategory')
    .mockResolvedValue(true)
  const unsubscribe = vi
    .spyOn(store, 'unsubscribePolicyCategory')
    .mockResolvedValue(true)
  const wrapper = mount(LocalResourcePoliciesView, {
    global: {
      plugins: [pinia],
      stubs: { AppHeader: true, LocalResourcesNav: true }
    }
  })
  return {
    loadPolicies,
    loadSubscriptions,
    subscribe,
    unsubscribe,
    wrapper
  }
}

function mountDetail() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useLocalResourcesStore()
  store.policyDetail = policyFixture
  const openPolicy = vi.spyOn(store, 'openPolicy').mockResolvedValue(true)
  const recordPolicyView = vi
    .spyOn(store, 'recordPolicyView')
    .mockResolvedValue(undefined)
  const wrapper = mount(LocalResourcePolicyDetailView, {
    global: {
      plugins: [pinia],
      stubs: { AppHeader: true, LocalResourcesNav: true }
    }
  })
  return { openPolicy, recordPolicyView, store, wrapper }
}

describe('local-resource policy views', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    mockedApiFetch.mockReset()
  })

  it('renders exactly seven policy categories and subscription state', async () => {
    const { subscribe, wrapper } = mountList()
    await flushPromises()

    const categories = wrapper.findAll('[data-test="policy-category"]')
    expect(categories).toHaveLength(7)
    expect(categories.map(category => category.text())).toEqual([
      '补贴',
      '电商',
      '非遗',
      '培训',
      '认证',
      '综合',
      '创业支持 推荐'
    ])
    expect(wrapper.get('[data-category="ecommerce"]').classes()).toContain(
      'is-subscribed'
    )
    expect(
      wrapper.get('[data-category="entrepreneurship"]').text()
    ).toContain('推荐')
    expect(subscribe).not.toHaveBeenCalled()
  })

  it('selects categories and toggles each subscription through store actions', async () => {
    const { loadPolicies, subscribe, unsubscribe, wrapper } = mountList()
    await flushPromises()

    const categories = wrapper.findAll('[data-test="policy-category"]')
    const toggles = wrapper.findAll(
      '[data-test="policy-subscription-toggle"]'
    )
    expect(toggles).toHaveLength(7)

    await categories[2].trigger('click')
    expect(loadPolicies).toHaveBeenLastCalledWith('heritage')

    await toggles[1].trigger('click')
    expect(unsubscribe).toHaveBeenCalledWith('ecommerce')
    expect(subscribe).not.toHaveBeenCalled()

    await toggles[6].trigger('click')
    expect(subscribe).toHaveBeenCalledWith('entrepreneurship')
  })

  it('shows a failed subscription change without hiding content or false success', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLocalResourcesStore()
    store.policies = [policyFixture]
    store.subscriptions = {
      categories: subscriptionState(),
      recommended_category_codes: ['entrepreneurship']
    }
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        subscriptions: store.subscriptions
      } as never)
      .mockResolvedValueOnce({
        success: true,
        policies: [policyFixture]
      } as never)
    const subscriptionRequest = deferred<never>()
    mockedApiFetch.mockReturnValueOnce(subscriptionRequest.promise)
    const wrapper = mount(LocalResourcePoliciesView, {
      global: {
        plugins: [pinia],
        stubs: { AppHeader: true, LocalResourcesNav: true }
      }
    })
    await flushPromises()

    const toggle = wrapper.get(
      '[data-category="ecommerce"] [data-test="policy-subscription-toggle"]'
    )
    expect(toggle.attributes('disabled')).toBeUndefined()
    await toggle.trigger('click')

    expect(toggle.attributes('disabled')).toBeDefined()
    expect(toggle.text()).toContain('已订阅')

    subscriptionRequest.reject(
      new ApiError('政策订阅更新失败', 503)
    )
    await flushPromises()

    expect(toggle.attributes('disabled')).toBeUndefined()
    expect(
      wrapper.get('[data-test="policy-subscription-feedback"]').text()
    ).toContain('政策订阅更新失败')
    expect(toggle.text()).toContain('已订阅')
    expect(wrapper.find('[data-test="policy-link"]').exists()).toBe(true)
  })

  it('loads subscriptions and all policies, then renders stable detail links', async () => {
    const { loadPolicies, loadSubscriptions, wrapper } = mountList()
    await flushPromises()

    expect(loadSubscriptions).toHaveBeenCalledTimes(1)
    expect(loadPolicies).toHaveBeenCalledWith()
    const link = wrapper.get('[data-test="policy-link"]')
    expect(link.attributes('href')).toBe(
      '/student/local-resources/policies/policy-1'
    )
    expect(link.text()).toContain(policyFixture.title)
    expect(link.text()).toContain(policyFixture.category_label)
    expect(link.text()).not.toContain('浏览量')
  })

  it('records a view only after openPolicy succeeds and renders detail fields', async () => {
    const { openPolicy, recordPolicyView, wrapper } = mountDetail()

    expect(openPolicy).toHaveBeenCalledWith('policy-1')
    expect(recordPolicyView).not.toHaveBeenCalled()

    await flushPromises()

    expect(recordPolicyView).toHaveBeenCalledWith('policy-1')
    expect(wrapper.text()).toContain(policyFixture.title)
    expect(wrapper.text()).toContain(policyFixture.category_label)
    expect(wrapper.text()).toContain(policyFixture.published_at)
    expect(wrapper.text()).toContain(policyFixture.content)
  })

  it('does not record a view when openPolicy returns false', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLocalResourcesStore()
    store.policyDetail = policyFixture
    const openPolicy = vi.spyOn(store, 'openPolicy').mockResolvedValue(false)
    const recordPolicyView = vi
      .spyOn(store, 'recordPolicyView')
      .mockResolvedValue(undefined)
    const wrapper = mount(LocalResourcePolicyDetailView, {
      global: {
        plugins: [pinia],
        stubs: { AppHeader: true, LocalResourcesNav: true }
      }
    })

    await flushPromises()

    expect(openPolicy).toHaveBeenCalledWith('policy-1')
    expect(recordPolicyView).not.toHaveBeenCalled()
    expect(
      wrapper.find('[data-test="policy-detail-unavailable"]').exists()
    ).toBe(true)
  })

  it('keeps policy content visible when view recording fails', async () => {
    const { store, wrapper } = mountDetail()
    store.viewNotice = '浏览量暂未记录'
    await flushPromises()

    expect(wrapper.get('[data-test="policy-body"]').text()).toContain(
      policyFixture.content
    )
    expect(wrapper.get('[data-test="policy-view-notice"]').text()).toBe(
      '浏览量暂未记录'
    )
  })

  it('renders no policy management actions in the detail view', async () => {
    const { wrapper } = mountDetail()
    await flushPromises()

    expect(wrapper.findAll('button, form, input, textarea, select')).toHaveLength(
      0
    )
    expect(wrapper.text()).not.toMatch(/创建|编辑|删除|下架|重新上架/)
    expect(localResourcePolicyDetailSource).not.toContain('view_count')
  })

  it('uses token-only light surfaces and CJK-safe wrapping at narrow widths', () => {
    const css = [
      localResourcePoliciesSource,
      localResourcePolicyDetailSource
    ].join('\n')

    expect(css).toContain('background: var(--ark-surface-0)')
    expect(css).toContain('@media (max-width: 640px)')
    expect(css.match(/line-break: strict/g)?.length).toBeGreaterThanOrEqual(6)
    expect(css.match(/word-break: keep-all/g)?.length).toBeGreaterThanOrEqual(6)
    expect(css).toContain('overflow-wrap: anywhere')
    expect(css).not.toMatch(/#[0-9a-f]{3,8}|rgba?\(|hsla?\(/i)
    expect(css).not.toMatch(/linear-gradient|radial-gradient/i)
    expect(css).not.toMatch(/letter-spacing:\s*-/)
    expect(css).not.toMatch(/\d(?:vw|vmin|vmax)/i)
  })
})
