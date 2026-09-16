import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type { AgriProduct, FarmingCalendar } from '@/api/types'
import AgriSkillsNav from '@/components/AgriSkillsNav.vue'
import AppHeader from '@/components/AppHeader.vue'
import { useAgriCalendarStore } from '@/stores/agriCalendar'

import AgriCalendarView from './AgriCalendarView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const litchi: AgriProduct = {
  key: 'litchi',
  name: '荔枝',
  sort_order: 1
}

const calendar: FarmingCalendar = {
  product: litchi,
  month: 4,
  tasks: ['疏花疏果'],
  management: ['保持果园排水'],
  solar_terms: ['清明'],
  reminder: '关注花期天气',
  empty_state: null
}

function createTestRouter() {
  const paths = [
    '/',
    '/login',
    '/register',
    '/messages',
    '/student',
    '/student/agri-skills',
    '/student/agri-skills/calendar',
    '/student/agri-skills/qa',
    '/student/agri-skills/diagnosis',
    '/student/agri-skills/courses'
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
  const wrapper = mount(AgriCalendarView, {
    global: {
      plugins: [pinia, createTestRouter()]
    }
  })
  return { pinia, wrapper }
}

function mockCalendarApi(
  products: AgriProduct[] = [litchi],
  calendarResponse: FarmingCalendar = calendar
) {
  mockedApiFetch.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path === '/api/agri-skills/products') {
      return { success: true, products } as never
    }
    if (path.startsWith('/api/agri-skills/calendar?')) {
      return {
        success: true,
        calendar: products.length
          ? calendarResponse
          : { ...calendarResponse, empty_state: '暂无该产品农时数据' }
      } as never
    }
    if (
      path.startsWith('/api/agri-skills/subscriptions/') &&
      (options?.method === 'POST' || options?.method === 'DELETE')
    ) {
      return { success: true } as never
    }
    throw new Error(`Unexpected request: ${path}`)
  })
}

describe('AgriCalendarView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders the shared header and agricultural navigation', () => {
    mockCalendarApi()
    const { wrapper } = mountView()

    expect(wrapper.findComponent(AppHeader).exists()).toBe(true)
    expect(wrapper.findComponent(AgriSkillsNav).exists()).toBe(true)
  })

  it('renders the exact calendar sections', async () => {
    mockCalendarApi()
    const { wrapper } = mountView()
    await flushPromises()

    expect(wrapper.get('[data-test="calendar-tasks"]').text()).toContain('疏花疏果')
    expect(wrapper.get('[data-test="calendar-management"]').text()).toContain(
      '保持果园排水'
    )
    expect(wrapper.get('[data-test="calendar-solar-terms"]').text()).toContain('清明')
    expect(wrapper.get('[data-test="calendar-reminder"]').text()).toContain(
      '关注花期天气'
    )
  })

  it('shows product-level empty state without calendar cards', async () => {
    mockCalendarApi([])
    const { wrapper } = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('暂无该产品农时数据')
    expect(wrapper.find('[data-test="calendar-tasks"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="product-select"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="month-previous"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="month-next"]').exists()).toBe(true)
  })

  it('keeps selected product and month controls in the month empty state', async () => {
    mockCalendarApi([litchi], {
      ...calendar,
      tasks: [],
      management: [],
      solar_terms: [],
      reminder: '',
      empty_state: '当月无该产品农时'
    })
    const { wrapper } = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('当月无该产品农时')
    expect(wrapper.find('[data-test="calendar-tasks"]').exists()).toBe(false)
    expect(
      (wrapper.get('[data-test="product-select"]').element as HTMLSelectElement)
        .value
    ).toBe('litchi')
    expect(wrapper.find('[data-test="month-previous"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="month-next"]').exists()).toBe(true)
  })

  it('toggles subscription immediately', async () => {
    mockCalendarApi()
    const { pinia, wrapper } = mountView()
    await flushPromises()

    const button = wrapper.get('[data-test="subscribe-litchi"]')
    expect(button.attributes('aria-pressed')).toBe('false')

    await button.trigger('click')
    await flushPromises()

    expect(button.attributes('aria-pressed')).toBe('true')
    expect(useAgriCalendarStore(pinia).subscriptions).toContain('litchi')
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/subscriptions/litchi',
      { method: 'POST' }
    )
  })
})
