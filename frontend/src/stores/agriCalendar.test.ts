import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type { AgriProduct, FarmingCalendar } from '@/api/types'

import { useAgriCalendarStore } from './agriCalendar'

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

const longan: AgriProduct = {
  key: 'longan',
  name: '龙眼',
  sort_order: 2
}

const monthEmptyCalendar: FarmingCalendar = {
  product: litchi,
  month: 2,
  tasks: [],
  management: [],
  solar_terms: [],
  reminder: '',
  empty_state: '当月无该产品农时'
}

describe('useAgriCalendarStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('keeps product controls when a month has no data', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      calendar: monthEmptyCalendar
    } as never)
    const store = useAgriCalendarStore()

    await store.loadCalendar('litchi', 2)

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/calendar?product_key=litchi&month=2'
    )
    expect(store.calendar?.empty_state).toBe('当月无该产品农时')
    expect(store.selectedProductKey).toBe('litchi')
    expect(store.month).toBe(2)
  })

  it('loads the product catalog from the Task 12 endpoint', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      products: [litchi]
    } as never)
    const store = useAgriCalendarStore()

    await store.loadProducts()

    expect(mockedApiFetch).toHaveBeenCalledWith('/api/agri-skills/products')
    expect(store.products).toEqual([litchi])
  })

  it('restores the server-resolved selection during reinitialization', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      calendar: {
        ...monthEmptyCalendar,
        product: longan,
        month: 2
      }
    } as never)
    const store = useAgriCalendarStore()

    await store.loadCalendar(undefined, 2)

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/calendar?product_key=&month=2'
    )
    expect(store.selectedProductKey).toBe('longan')
    expect(store.month).toBe(2)
  })

  it('keeps the product key when an empty calendar omits product details', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      calendar: {
        product_key: 'longan',
        month: 9,
        tasks: [],
        management: [],
        solar_terms: [],
        reminder: '',
        empty_state: '暂无该产品农时数据'
      }
    } as never)
    const store = useAgriCalendarStore()

    await store.loadCalendar(undefined, 9)

    expect(store.selectedProductKey).toBe('longan')
    expect(store.calendar?.empty_state).toBe('暂无该产品农时数据')
    expect(store.month).toBe(9)
  })

  it('persists a product selection before loading its calendar', async () => {
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (
        path === '/api/agri-skills/calendar/selection' &&
        options?.method === 'PUT'
      ) {
        return { success: true, product_key: 'longan' } as never
      }
      if (
        path ===
        '/api/agri-skills/calendar?product_key=longan&month=2'
      ) {
        return {
          success: true,
          calendar: {
            ...monthEmptyCalendar,
            product: longan
          }
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    const store = useAgriCalendarStore()
    store.selectedProductKey = 'litchi'
    store.month = 2

    await store.selectProduct('longan')

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/agri-skills/calendar/selection',
      {
        method: 'PUT',
        body: JSON.stringify({ product_key: 'longan' })
      }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/agri-skills/calendar?product_key=longan&month=2'
    )
    expect(store.selectedProductKey).toBe('longan')
    expect(store.calendar?.product.key).toBe('longan')
  })

  it('preserves the current state when selection persistence fails', async () => {
    const originalCalendar = { ...monthEmptyCalendar }
    mockedApiFetch.mockRejectedValue(
      new ApiError('产品选择保存失败', 503)
    )
    const store = useAgriCalendarStore()
    store.products = [litchi, longan]
    store.selectedProductKey = 'litchi'
    store.month = 2
    store.calendar = originalCalendar

    await store.selectProduct('longan')

    expect(mockedApiFetch).toHaveBeenCalledTimes(1)
    expect(store.selectedProductKey).toBe('litchi')
    expect(store.products).toEqual([litchi, longan])
    expect(store.calendar).toEqual(originalCalendar)
    expect(store.error).toBe('产品选择保存失败')
    expect(store.saving).toBe(false)
  })

  it('preserves the current calendar when reloading the new selection fails', async () => {
    const originalCalendar = { ...monthEmptyCalendar }
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (
        path === '/api/agri-skills/calendar/selection' &&
        options?.method === 'PUT'
      ) {
        return { success: true, product_key: 'longan' } as never
      }
      throw new ApiError('农时日历加载失败', 503)
    })
    const store = useAgriCalendarStore()
    store.products = [litchi, longan]
    store.selectedProductKey = 'litchi'
    store.month = 2
    store.calendar = originalCalendar

    await store.selectProduct('longan')

    expect(store.selectedProductKey).toBe('longan')
    expect(store.products).toEqual([litchi, longan])
    expect(store.calendar).toEqual(originalCalendar)
    expect(store.error).toBe('农时日历加载失败')
  })

  it('loads the selected product and wraps month navigation', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      calendar: {
        ...monthEmptyCalendar,
        month: 1,
        empty_state: null
      }
    } as never)
    const store = useAgriCalendarStore()
    store.selectedProductKey = 'litchi'
    store.month = 12

    await store.changeMonth(1)

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/calendar?product_key=litchi&month=1'
    )
    expect(store.month).toBe(1)
  })

  it('toggles subscriptions through the product endpoint', async () => {
    mockedApiFetch.mockResolvedValue({ success: true } as never)
    const store = useAgriCalendarStore()

    await store.subscribe('litchi')
    await store.subscribe('litchi')

    expect(store.subscriptions).toEqual(['litchi'])
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/agri-skills/subscriptions/litchi',
      { method: 'POST' }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/agri-skills/subscriptions/litchi',
      { method: 'POST' }
    )

    await store.unsubscribe('litchi')

    expect(store.subscriptions).toEqual([])
    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      '/api/agri-skills/subscriptions/litchi',
      { method: 'DELETE' }
    )
  })
})
