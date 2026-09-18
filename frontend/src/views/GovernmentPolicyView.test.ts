import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type { GovernmentPolicy } from '@/api/types'
import GovernmentConsoleNav from '@/components/GovernmentConsoleNav.vue'
import governmentConsoleNavSource from '@/components/GovernmentConsoleNav.vue?raw'
import { useGovernmentConsoleStore } from '@/stores/governmentConsole'

import GovernmentPolicyView from './GovernmentPolicyView.vue'
import governmentPolicyViewSource from './GovernmentPolicyView.vue?raw'

const policyCategories = [
  ['subsidy', '补贴'],
  ['ecommerce', '电商'],
  ['heritage', '非遗'],
  ['training', '培训'],
  ['certification', '认证'],
  ['general', '综合'],
  ['entrepreneurship', '创业支持']
] as const

function policyFixture(
  patch: Partial<GovernmentPolicy> = {}
): GovernmentPolicy {
  return {
    id: 'policy-1',
    title: '创业支持政策',
    content: '政策正文',
    category_code: 'entrepreneurship',
    category_label: '创业支持',
    status: 'active',
    view_count: 12,
    version: 3,
    published_at: '2026-09-18T09:30:00+08:00',
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

async function mountView(policies: GovernmentPolicy[] = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useGovernmentConsoleStore()
  store.policies = policies

  vi.spyOn(store, 'loadPolicies').mockResolvedValue(true)
  vi.spyOn(store, 'publishPolicy').mockResolvedValue(true)
  vi.spyOn(store, 'unpublishPolicy').mockResolvedValue(true)
  vi.spyOn(store, 'relistPolicy').mockResolvedValue(true)
  vi.spyOn(store, 'deletePolicy').mockResolvedValue(true)

  const router = testRouter()
  await router.push('/government/policies')
  await router.isReady()

  const wrapper = mount(GovernmentPolicyView, {
    global: {
      plugins: [pinia, router]
    }
  })
  await flushPromises()

  return { wrapper, store }
}

function cssRule(css: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(
    new RegExp(
      `(?:^|\\n)\\s*${escaped}\\s*\\{([\\s\\S]*?)\\}`
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

describe('GovernmentPolicyView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('publishes the seven-category policy form with a generated request id', async () => {
    const { wrapper, store } = await mountView()
    const randomUUID = vi
      .spyOn(globalThis.crypto, 'randomUUID')
      .mockReturnValue('00000000-0000-4000-8000-000000000001')

    const categoryOptions = wrapper
      .get('[data-test="policy-category"]')
      .findAll('option')
      .map(option => [
        option.attributes('value'),
        option.text()
      ])
    expect(categoryOptions).toEqual(policyCategories)

    await wrapper.get('[data-test="policy-title"]').setValue(' 创业补贴 ')
    await wrapper.get('[data-test="policy-content"]').setValue(' 正文 ')
    await wrapper
      .get('[data-test="policy-category"]')
      .setValue('entrepreneurship')
    await wrapper.get('[data-test="policy-form"]').trigger('submit')

    expect(store.publishPolicy).toHaveBeenCalledWith({
      request_id: '00000000-0000-4000-8000-000000000001',
      title: '创业补贴',
      content: '正文',
      category_code: 'entrepreneurship'
    })
    expect(randomUUID).toHaveBeenCalledOnce()
  })

  it('filters the registry by category and active or unpublished status', async () => {
    const active = policyFixture()
    const unpublished = policyFixture({
      id: 'policy-2',
      title: '电商培训政策',
      category_code: 'ecommerce',
      category_label: '电商',
      status: 'unpublished',
      version: 2
    })
    const { wrapper } = await mountView([active, unpublished])

    expect(wrapper.findAll('[data-test="policy-row"]')).toHaveLength(2)

    await wrapper
      .get('[data-test="policy-category-filter"]')
      .setValue('ecommerce')
    expect(wrapper.findAll('[data-test="policy-row"]')).toHaveLength(1)
    expect(wrapper.get('[data-test="policy-row"]').text()).toContain(
      '电商培训政策'
    )

    await wrapper
      .get('[data-test="policy-status-filter"]')
      .setValue('active')
    expect(wrapper.find('[data-test="policy-row"]').exists()).toBe(false)
    expect(wrapper.get('[data-test="policy-empty"]').text()).toContain(
      '暂无符合条件的政策'
    )
  })

  it('uses the current version for unpublish and relist actions', async () => {
    const active = policyFixture()
    const unpublished = policyFixture({
      id: 'policy-2',
      title: '非遗保护政策',
      category_code: 'heritage',
      category_label: '非遗',
      status: 'unpublished',
      version: 5
    })
    const { wrapper, store } = await mountView([active, unpublished])

    await wrapper.get('[data-test="unpublish-policy"]').trigger('click')
    await wrapper.get('[data-test="relist-policy"]').trigger('click')

    expect(store.unpublishPolicy).toHaveBeenCalledWith(
      active.id,
      active.version
    )
    expect(store.relistPolicy).toHaveBeenCalledWith(
      unpublished.id,
      unpublished.version
    )
  })

  it('requires an explicit confirmation before deleting a policy', async () => {
    const policy = policyFixture()
    const { wrapper, store } = await mountView([policy])

    await wrapper.get('[data-test="delete-policy"]').trigger('click')
    expect(store.deletePolicy).not.toHaveBeenCalled()

    const confirmation = wrapper.get(
      '[data-test="policy-delete-confirmation"]'
    )
    expect(confirmation.text()).toContain(policy.title)
    await wrapper
      .get('[data-test="confirm-delete-policy"]')
      .trigger('click')

    expect(store.deletePolicy).toHaveBeenCalledWith(
      policy.id,
      policy.version
    )
  })

  it('renders the policy table fields and accessible lifecycle controls', async () => {
    const policy = policyFixture()
    const { wrapper } = await mountView([policy])

    expect(wrapper.get('[data-test="policy-row"]').text()).toContain(
      policy.title
    )
    expect(wrapper.get('[data-test="policy-row"]').text()).toContain(
      policy.category_label
    )
    expect(wrapper.get('[data-test="policy-row"]').text()).toContain('在架')
    expect(wrapper.get('[data-test="policy-row"]').text()).toContain(
      String(policy.view_count)
    )
    expect(wrapper.get('[data-test="policy-row"]').text()).toContain(
      '版本 3'
    )

    const unpublish = wrapper.get('[data-test="unpublish-policy"]')
    const remove = wrapper.get('[data-test="delete-policy"]')
    expect(unpublish.attributes('aria-label')).toContain(policy.title)
    expect(unpublish.attributes('title')).toBeTruthy()
    expect(remove.attributes('aria-label')).toContain(policy.title)
    expect(remove.attributes('title')).toBeTruthy()
  })

  it('exposes the three government workspace links through the shared nav', async () => {
    const { wrapper } = await mountView()
    const nav = wrapper.getComponent(GovernmentConsoleNav)

    expect(nav.get('nav').attributes('aria-label')).toBe('政务工作台导航')
    expect(nav.findAll('a').map(link => link.attributes('href'))).toEqual([
      '/government/policies',
      '/government/news',
      '/government/dashboard'
    ])
    expect(nav.text()).toContain('政策管理')
    expect(nav.text()).toContain('新闻管理')
    expect(nav.text()).toContain('数据看板')
  })

  it('does not render review, approval, export, editing or user-data controls', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.text()).not.toMatch(
      /审核|审批|导出|编辑|补贴申请|用户数据/
    )
    expect(wrapper.find('[data-test="policy-edit"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="policy-review"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="policy-export"]').exists()).toBe(false)
  })

  it('locks typography and layout contracts for 320, 375 and 1280 widths', () => {
    const viewports = [320, 375, 1280]
    const sources = [governmentPolicyViewSource, governmentConsoleNavSource]

    expect(
      cssRule(governmentPolicyViewSource, '.government-policy-page')
    ).toContain('overflow-x: clip')
    expect(
      cssRule(governmentPolicyViewSource, '.government-policy')
    ).toContain('width: min(100%, 1180px)')
    expect(
      cssRule(governmentPolicyViewSource, '.government-policy')
    ).toContain('min-width: 0')
    expect(
      cssRule(governmentPolicyViewSource, '.policy-table')
    ).toContain('table-layout: fixed')
    expect(governmentPolicyViewSource).toContain('line-break: strict')
    expect(governmentPolicyViewSource).toContain('word-break: keep-all')
    expect(governmentPolicyViewSource).toContain('text-wrap: pretty')
    expect(
      cssRule(
        mediaBlock(governmentPolicyViewSource, 760),
        '.policy-compose__grid'
      )
    ).toContain('grid-template-columns: minmax(0, 1fr)')
    expect(
      cssRule(
        mediaBlock(governmentPolicyViewSource, 760),
        '.policy-table tbody'
      )
    ).toContain('display: grid')
    expect(
      cssRule(
        mediaBlock(governmentPolicyViewSource, 420),
        '.policy-actions'
      )
    ).toContain('grid-template-columns: minmax(0, 1fr)')
    expect(governmentConsoleNavSource).toContain(
      '@media (max-width: 640px)'
    )

    viewports.forEach(viewport => {
      expect(
        sources.every(
          source =>
            !source.includes(`min-width: ${viewport}px`) &&
            !source.includes(`width: ${viewport}px`)
        )
      ).toBe(true)
    })
    expect(sources.join('\n')).not.toMatch(/#[0-9a-f]{3,8}|rgba?\(/i)
  })
})
