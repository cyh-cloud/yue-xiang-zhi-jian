import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type { AgriProduct, FarmingCalendar } from '@/api/types'

function currentMonth(): number {
  const value = new Intl.DateTimeFormat('en-US', {
    month: 'numeric',
    timeZone: 'Asia/Shanghai'
  }).format(new Date())
  const month = Number(value)
  return Number.isInteger(month) && month >= 1 && month <= 12 ? month : 1
}

interface AgriCalendarState {
  products: AgriProduct[]
  selectedProductKey: string
  month: number
  calendar: FarmingCalendar | null
  subscriptions: string[]
  loading: boolean
  saving: boolean
  error: string
}

export const useAgriCalendarStore = defineStore('agriCalendar', {
  state: (): AgriCalendarState => ({
    products: [],
    selectedProductKey: '',
    month: currentMonth(),
    calendar: null,
    subscriptions: [],
    loading: false,
    saving: false,
    error: ''
  }),
  actions: {
    captureError(error: unknown, fallback: string) {
      this.error =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : fallback
    },
    async loadProducts() {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          products: AgriProduct[]
        }>('/api/agri-skills/products')
        this.products = response.products
      } catch (error) {
        this.captureError(error, '农产品目录加载失败')
      } finally {
        this.loading = false
      }
    },
    async loadCalendar(productKey?: string, month?: number) {
      const targetProductKey = productKey ?? this.selectedProductKey
      const targetMonth = month ?? this.month
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          calendar: FarmingCalendar
        }>(
          `/api/agri-skills/calendar?product_key=${encodeURIComponent(targetProductKey)}&month=${targetMonth}`
        )
        this.selectedProductKey =
          response.calendar.product?.key || targetProductKey
        this.month = targetMonth
        this.calendar = response.calendar
      } catch (error) {
        this.captureError(error, '农时日历加载失败')
      } finally {
        this.loading = false
      }
    },
    async selectProduct(key: string) {
      this.saving = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          product_key: string
        }>('/api/agri-skills/calendar/selection', {
          method: 'PUT',
          body: JSON.stringify({ product_key: key })
        })
        this.selectedProductKey = response.product_key || key
      } catch (error) {
        this.captureError(error, '产品选择保存失败')
        return
      } finally {
        this.saving = false
      }

      await this.loadCalendar(this.selectedProductKey, this.month)
    },
    async changeMonth(delta: number) {
      const month = ((((this.month - 1 + delta) % 12) + 12) % 12) + 1
      await this.loadCalendar(this.selectedProductKey, month)
    },
    async subscribe(productKey: string) {
      this.saving = true
      this.error = ''

      try {
        await apiFetch(
          `/api/agri-skills/subscriptions/${encodeURIComponent(productKey)}`,
          {
            method: 'POST'
          }
        )
        this.subscriptions = [...new Set([...this.subscriptions, productKey])]
      } catch (error) {
        this.captureError(error, '订阅失败')
      } finally {
        this.saving = false
      }
    },
    async unsubscribe(productKey: string) {
      this.saving = true
      this.error = ''

      try {
        await apiFetch(
          `/api/agri-skills/subscriptions/${encodeURIComponent(productKey)}`,
          {
            method: 'DELETE'
          }
        )
        this.subscriptions = this.subscriptions.filter(key => key !== productKey)
      } catch (error) {
        this.captureError(error, '取消订阅失败')
      } finally {
        this.saving = false
      }
    }
  }
})
