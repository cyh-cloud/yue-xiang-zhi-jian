import { defineStore } from 'pinia'

import { apiFetch } from '@/api/client'
import type { StorePlan } from '@/api/types'

export const STORE_PLATFORMS = [
  'taobao',
  'pinduoduo',
  'douyin_shop'
] as const

export type StorePlatform = (typeof STORE_PLATFORMS)[number]

export interface StoreGuidanceForm {
  store_type: string
  platform: StorePlatform
  style_preference: string
}

export type StorePlanSectionKey = keyof StorePlan['plan']

export type StorePlanWire = StorePlan

interface EcommerceStoreGuidanceState {
  form: StoreGuidanceForm
  current: StorePlanWire | null
  history: StorePlanWire[]
  loading: boolean
  generating: boolean
  opening: boolean
  error: string
}

const API_PREFIX = '/api/ecommerce-training/store-plans'
const AI_UNAVAILABLE_MESSAGE = 'AI 服务暂时不可用'

function createForm(): StoreGuidanceForm {
  return {
    store_type: '',
    platform: 'taobao',
    style_preference: ''
  }
}

function sortHistory(plans: StorePlanWire[]): StorePlanWire[] {
  return [...plans].sort((left, right) => right.id - left.id)
}

function replaceHistoryItem(
  plans: StorePlanWire[],
  plan: StorePlanWire
): StorePlanWire[] {
  return sortHistory([
    plan,
    ...plans.filter(item => item.id !== plan.id)
  ])
}

export const useEcommerceStoreGuidanceStore = defineStore(
  'ecommerceStoreGuidance',
  {
    state: (): EcommerceStoreGuidanceState => ({
      form: createForm(),
      current: null,
      history: [],
      loading: false,
      generating: false,
      opening: false,
      error: ''
    }),
    getters: {
      isBusy(state): boolean {
        return state.loading || state.generating || state.opening
      }
    },
    actions: {
      resetForm() {
        this.form = createForm()
        this.error = ''
      },
      applyPlan(plan: StorePlanWire) {
        this.current = plan
        this.history = replaceHistoryItem(this.history, plan)
      },
      async generate(): Promise<boolean> {
        if (this.isBusy) {
          return false
        }

        const request: StoreGuidanceForm = {
          store_type: this.form.store_type.trim(),
          platform: this.form.platform,
          style_preference: this.form.style_preference.trim()
        }

        if (!request.store_type || !request.style_preference) {
          this.error = '请填写店铺类型和风格偏好'
          return false
        }
        if (!STORE_PLATFORMS.includes(request.platform)) {
          this.error = '请选择支持的店铺平台'
          return false
        }

        this.generating = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            plan: StorePlanWire
          }>(API_PREFIX, {
            method: 'POST',
            body: JSON.stringify(request)
          })
          this.applyPlan(response.plan)
          return true
        } catch {
          this.error = AI_UNAVAILABLE_MESSAGE
          return false
        } finally {
          this.generating = false
        }
      },
      async loadHistory(): Promise<boolean> {
        if (this.isBusy) {
          return false
        }

        this.loading = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            plans: StorePlanWire[]
          }>(API_PREFIX)
          this.history = sortHistory(response.plans)
          return true
        } catch {
          this.error = '店铺装修记录加载失败'
          return false
        } finally {
          this.loading = false
        }
      },
      async openPlan(id: number): Promise<boolean> {
        if (this.isBusy) {
          return false
        }

        this.opening = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            plan: StorePlanWire
          }>(`${API_PREFIX}/${id}`)
          this.current = response.plan
          this.history = replaceHistoryItem(this.history, response.plan)
          return true
        } catch {
          this.error = '店铺装修方案加载失败'
          return false
        } finally {
          this.opening = false
        }
      }
    }
  }
)
