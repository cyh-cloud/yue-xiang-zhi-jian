import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'
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

  it('uses the server-resolved product when no product is supplied', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      calendar: {
        ...monthEmptyCalendar,
        month: 2
      }
    } as never)
    const store = useAgriCalendarStore()

    await store.loadCalendar(undefined, 2)

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/calendar?product_key=&month=2'
    )
    expect(store.selectedProductKey).toBe('litchi')
    expect(store.month).toBe(2)
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
