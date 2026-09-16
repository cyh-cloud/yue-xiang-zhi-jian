import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError, apiFetch } from '@/api/client'
import type { LiveScriptVersion } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import EcommerceTrainingNav from '@/components/EcommerceTrainingNav.vue'
import { useEcommerceLiveScriptStore } from '@/stores/ecommerceLiveScript'

import EcommerceLiveScriptView from './EcommerceLiveScriptView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function version(
  id: number,
  patch: Partial<LiveScriptVersion> = {}
): LiveScriptVersion {
  return {
    id,
    product_name: '荔枝干',
    selling_points: ['香甜', '耐储存'],
    price_text: '39.9 元',
    style: 'enthusiastic',
    script: {
      opening: '欢迎来到直播间',
      product_intro: '来自广东的香甜荔枝干',
      interaction: '喜欢的朋友扣一',
      closing: '现在下单更划算'
    },
    is_current: false,
    created_at: `2026-09-17T0${id}:00:00+00:00`,
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
  const wrapper = mount(EcommerceLiveScriptView, {
    global: {
      plugins: [pinia, createTestRouter()]
    }
  })
  return { pinia, wrapper }
}

describe('EcommerceLiveScriptView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    mockedApiFetch.mockResolvedValue({
      success: true,
      versions: []
    } as never)
  })

  it('renders required inputs and exactly three ordered style choices', async () => {
    const { wrapper } = mountView()
    await flushPromises()

    expect(wrapper.findComponent(AppHeader).exists()).toBe(true)
    expect(wrapper.findComponent(EcommerceTrainingNav).exists()).toBe(true)
    expect(wrapper.get('[data-test="live-script-product-name"]').attributes()).toHaveProperty(
      'required'
    )
    expect(wrapper.get('[data-test="live-script-selling-points"]').attributes()).toHaveProperty(
      'required'
    )

    const styles = wrapper.findAll('[data-test="live-script-style"]')
    expect(styles).toHaveLength(3)
    expect(styles.map(item => item.text())).toEqual(['热情', '专业', '幽默'])
    expect(styles.map(item => item.get('input').element.value)).toEqual([
      'enthusiastic',
      'professional',
      'humorous'
    ])
  })

  it('submits the form, renders four ordered sections and keeps history', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    const store = useEcommerceLiveScriptStore(pinia)
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      version: version(1, { is_current: true })
    } as never)

    await wrapper.get('[data-test="live-script-product-name"]').setValue('荔枝干')
    await wrapper
      .get('[data-test="live-script-selling-points"]')
      .setValue('香甜、耐储存')
    await wrapper.get('[data-test="live-script-price"]').setValue('39.9 元')
    await wrapper.get('[data-test="live-script-form"]').trigger('submit')
    await flushPromises()

    expect(store.form).toMatchObject({
      product_name: '荔枝干',
      selling_points: '香甜、耐储存',
      price_text: '39.9 元',
      style: 'enthusiastic'
    })
    const sections = wrapper.findAll('[data-test="live-script-section"]')
    expect(sections.map(item => item.get('h3').text())).toEqual([
      '开场白',
      '产品介绍',
      '互动话术',
      '促单话术'
    ])
    expect(wrapper.get('[data-test="live-script-history"]').text()).toContain(
      '荔枝干'
    )
    expect(wrapper.find('[data-test="live-script-regenerate"]').exists()).toBe(
      true
    )
  })

  it('opens a historical version with its original input and complete output', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        versions: [version(2, { is_current: true }), version(1)]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        version: version(1, {
          product_name: '陈皮',
          style: 'humorous'
        })
      } as never)
    const { pinia, wrapper } = mountView()
    await flushPromises()
    const store = useEcommerceLiveScriptStore(pinia)
    store.current = version(2, { is_current: true })
    await wrapper.vm.$nextTick()

    await wrapper.get('[data-test="live-script-history-item-1"]').trigger('click')
    await flushPromises()

    expect(store.current?.id).toBe(1)
    expect(wrapper.get('[data-test="live-script-current"]').text()).toContain(
      '陈皮'
    )
    expect(wrapper.findAll('[data-test="live-script-section"]')).toHaveLength(4)
  })

  it('shows the exact AI message and preserves the form after failure', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    const store = useEcommerceLiveScriptStore(pinia)
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('provider timeout', 503)
    )

    await wrapper.get('[data-test="live-script-product-name"]').setValue('荔枝干')
    await wrapper
      .get('[data-test="live-script-selling-points"]')
      .setValue('香甜、耐储存')
    await wrapper.get('[data-test="live-script-price"]').setValue('39.9 元')
    await wrapper.get('[data-test="live-script-form"]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[aria-live="polite"]').text()).toBe(
      'AI 服务暂时不可用'
    )
    expect(store.form.product_name).toBe('荔枝干')
    expect(store.current).toBeNull()
    expect(wrapper.text()).not.toMatch(/音频|录音|流式|token/i)
  })
})
