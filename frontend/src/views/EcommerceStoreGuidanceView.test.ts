import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type { StorePlan } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import EcommerceTrainingNav from '@/components/EcommerceTrainingNav.vue'
import { useEcommerceStoreGuidanceStore } from '@/stores/ecommerceStoreGuidance'

import EcommerceStoreGuidanceView from './EcommerceStoreGuidanceView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function storePlan(
  id: number,
  patch: Partial<StorePlan> = {}
): StorePlan {
  return {
    id,
    store_type: '农产品旗舰店',
    platform: 'taobao',
    style_preference: '温暖可靠',
    plan: {
      home_layout: ['顶部活动区', '商品分组'],
      color_scheme: {
        primary: '#E43D30',
        accent: '#F7C948'
      },
      detail_structure: ['卖点', '参数', '售后'],
      navigation: ['首页', '新品', '优惠', '客服']
    },
    created_at: '2026-09-17T08:30:00+08:00',
    ...patch
  }
}

function createTestRouter() {
  const paths = [
    '/',
    '/login',
    '/register',
    '/student/ecommerce-training',
    '/student/ecommerce-training/live-script',
    '/student/ecommerce-training/simulation',
    '/student/ecommerce-training/copy-training',
    '/student/ecommerce-training/store-guidance',
    '/student/ecommerce-training/customer-service',
    '/student/ecommerce-training/courses'
  ]

  return createRouter({
    history: createMemoryHistory(),
    routes: paths.map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}

function mountView() {
  const pinia = createPinia()
  const wrapper = mount(EcommerceStoreGuidanceView, {
    global: {
      plugins: [pinia, createTestRouter()]
    }
  })
  return { pinia, wrapper }
}

describe('EcommerceStoreGuidanceView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    mockedApiFetch.mockResolvedValue({
      success: true,
      plans: []
    } as never)
  })

  it('renders the required inputs and exactly three platform choices', async () => {
    const { wrapper } = mountView()
    await flushPromises()

    expect(wrapper.findComponent(AppHeader).exists()).toBe(true)
    expect(wrapper.findComponent(EcommerceTrainingNav).exists()).toBe(true)
    expect(
      wrapper.get('[data-test="store-guidance-store-type"]').attributes()
    ).toHaveProperty('required')
    expect(
      wrapper.get('[data-test="store-guidance-style"]').attributes()
    ).toHaveProperty('required')
    expect(
      wrapper
        .findAll('[data-test="store-guidance-platform"] option')
        .map(option => option.attributes('value'))
    ).toEqual(['taobao', 'pinduoduo', 'douyin_shop'])
  })

  it('renders all four labels and safely displays string, list and dict wire values', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      plan: storePlan(1, {
        plan: {
          home_layout: [
            {
              zone: '首屏',
              modules: [
                {
                  key: 'hero',
                  title: '主视觉',
                  position: { row: 1, column: 'left' },
                  visible: true
                }
              ]
            }
          ],
          color_scheme: {
            primary: '暖红',
            variants: [
              {
                name: '点缀金',
                tokens: { hex: '#F7C948', contrast: 4.5 }
              }
            ]
          },
          detail_structure: ['卖点', '参数', '售后'],
          navigation: {
            primary: {
              label: '首页',
              children: [
                { label: '新品', order: 1, active: true },
                { label: '优惠', order: 2, active: false }
              ]
            }
          }
        }
      })
    } as never)

    await wrapper
      .get('[data-test="store-guidance-store-type"]')
      .setValue('农产品旗舰店')
    await wrapper
      .get('[data-test="store-guidance-style"]')
      .setValue('温暖可靠')
    await wrapper.get('[data-test="store-guidance-form"]').trigger('submit')
    await flushPromises()

    const sections = wrapper.findAll('[data-test="store-guidance-section"]')
    expect(sections.map(item => item.get('h3').text())).toEqual([
      '首页布局',
      '色彩方案',
      '详情页结构',
      '导航分类'
    ])
    expect(sections[0].text()).toContain('zone')
    expect(sections[0].text()).toContain('首屏')
    expect(sections[0].text()).toContain('modules')
    expect(sections[0].text()).toContain('复杂内容')
    expect(sections[1].text()).toContain('variants')
    expect(sections[1].text()).toContain('点缀金')
    expect(sections[1].text()).toContain('tokens')
    expect(sections[1].text()).toContain('复杂内容')
    expect(sections[2].text()).toContain('参数')
    expect(sections[3].text()).toContain('children')
    expect(sections[3].text()).toContain('复杂内容')
    expect(wrapper.text()).not.toContain('[object Object]')

    const history = wrapper.get('[data-test="store-guidance-history"]')
    expect(history.text()).toContain('农产品旗舰店')
    expect(history.text()).toContain('淘宝')
    expect(history.text()).toContain('温暖可靠')
    expect(history.get('time').attributes('datetime')).toBe(
      '2026-09-17T08:30:00+08:00'
    )
  })

  it('opens a historical plan with its original input and complete output', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        plans: [storePlan(2, { platform: 'pinduoduo' })]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        plan: storePlan(2, {
          store_type: '陈皮专营店',
          platform: 'pinduoduo',
          style_preference: '朴实',
          plan: {
            home_layout: ['爆款入口'],
            color_scheme: { primary: '棕色' },
            detail_structure: ['产地', '规格', '售后'],
            navigation: ['全部商品', '店铺']
          }
        })
      } as never)
    const { wrapper } = mountView()
    await flushPromises()

    await wrapper
      .get('[data-test="store-guidance-history-item-2"]')
      .trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('陈皮专营店')
    expect(wrapper.text()).toContain('拼多多')
    expect(wrapper.text()).toContain('朴实')
    expect(wrapper.text()).toContain('爆款入口')
    expect(wrapper.text()).toContain('产地')
    expect(wrapper.text()).toContain('店铺')
  })

  it('blocks an unsupported platform without issuing a generation request', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    const store = useEcommerceStoreGuidanceStore(pinia)
    store.form = {
      store_type: '农产品旗舰店',
      platform: 'unknown' as never,
      style_preference: '温暖可靠'
    }

    expect(await store.generate()).toBe(false)
    await flushPromises()

    expect(
      mockedApiFetch.mock.calls.some(
        ([url, options]) =>
          url === '/api/ecommerce-training/store-plans' &&
          options?.method === 'POST'
      )
    ).toBe(false)
    expect(wrapper.get('[aria-live="assertive"]').text()).toContain(
      '请选择支持的店铺平台'
    )
    expect(store.current).toBeNull()
  })

  it('disables generation while any store operation is pending', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    const store = useEcommerceStoreGuidanceStore(pinia)
    const generateButton = wrapper.get(
      '[data-test="store-guidance-generate"]'
    )

    store.loading = true
    await wrapper.vm.$nextTick()
    expect(generateButton.attributes()).toHaveProperty('disabled')

    store.loading = false
    store.opening = true
    await wrapper.vm.$nextTick()
    expect(generateButton.attributes()).toHaveProperty('disabled')

    store.opening = false
    store.generating = true
    await wrapper.vm.$nextTick()
    expect(generateButton.attributes()).toHaveProperty('disabled')
  })

  it('shows the exact AI failure while preserving the form and omitting fabricated output', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    mockedApiFetch.mockRejectedValueOnce(new Error('provider timeout'))

    await wrapper
      .get('[data-test="store-guidance-store-type"]')
      .setValue('农产品旗舰店')
    await wrapper
      .get('[data-test="store-guidance-style"]')
      .setValue('温暖可靠')
    await wrapper.get('[data-test="store-guidance-form"]').trigger('submit')
    await flushPromises()

    const store = useEcommerceStoreGuidanceStore(pinia)
    expect(wrapper.get('[aria-live="assertive"]').text()).toBe(
      'AI 服务暂时不可用'
    )
    expect(
      wrapper.get<HTMLInputElement>(
        '[data-test="store-guidance-store-type"]'
      ).element.value
    ).toBe('农产品旗舰店')
    expect(
      wrapper.get<HTMLInputElement>(
        '[data-test="store-guidance-style"]'
      ).element.value
    ).toBe('温暖可靠')
    expect(store.current).toBeNull()
    expect(store.history).toEqual([])
    expect(wrapper.find('[data-test="store-guidance-current"]').exists()).toBe(
      false
    )
    expect(wrapper.text()).not.toMatch(/本地兜底|003|降级方案/i)
  })
})
