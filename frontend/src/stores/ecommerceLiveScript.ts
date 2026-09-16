import { defineStore } from 'pinia'

import { apiFetch } from '@/api/client'
import type { LiveScriptVersion } from '@/api/types'

export const LIVE_SCRIPT_STYLES = [
  'enthusiastic',
  'professional',
  'humorous'
] as const

export type LiveScriptStyle = (typeof LIVE_SCRIPT_STYLES)[number]

export interface LiveScriptForm {
  product_name: string
  selling_points: string
  price_text: string
  style: LiveScriptStyle
}

interface EcommerceLiveScriptState {
  form: LiveScriptForm
  current: LiveScriptVersion | null
  history: LiveScriptVersion[]
  loading: boolean
  generating: boolean
  error: string
}

const AI_UNAVAILABLE_MESSAGE = 'AI 服务暂时不可用'

function createForm(): LiveScriptForm {
  return {
    product_name: '',
    selling_points: '',
    price_text: '',
    style: 'enthusiastic'
  }
}

function sortHistory(versions: LiveScriptVersion[]): LiveScriptVersion[] {
  return [...versions].sort((left, right) => right.id - left.id)
}

export const useEcommerceLiveScriptStore = defineStore(
  'ecommerceLiveScript',
  {
    state: (): EcommerceLiveScriptState => ({
      form: createForm(),
      current: null,
      history: [],
      loading: false,
      generating: false,
      error: ''
    }),
    actions: {
      resetForm() {
        this.form = createForm()
        this.error = ''
      },
      async generate(payload?: LiveScriptForm): Promise<boolean> {
        if (this.generating) {
          return false
        }

        if (payload) {
          this.form = { ...payload }
        }

        const request: LiveScriptForm = {
          product_name: this.form.product_name.trim(),
          selling_points: this.form.selling_points.trim(),
          price_text: this.form.price_text.trim(),
          style: this.form.style
        }

        if (
          !request.product_name ||
          !request.selling_points ||
          !request.price_text
        ) {
          this.error = '请填写商品名称、卖点和价格文案'
          return false
        }
        if (!LIVE_SCRIPT_STYLES.includes(request.style)) {
          this.error = '请选择支持的直播话术风格'
          return false
        }

        this.generating = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            version: LiveScriptVersion
          }>('/api/ecommerce-training/live-scripts', {
            method: 'POST',
            body: JSON.stringify(request)
          })
          const current = {
            ...response.version,
            is_current: true
          }
          this.current = current
          this.history = sortHistory([
            current,
            ...this.history
              .filter(item => item.id !== current.id)
              .map(item => ({ ...item, is_current: false }))
          ])
          return true
        } catch {
          this.error = AI_UNAVAILABLE_MESSAGE
          return false
        } finally {
          this.generating = false
        }
      },
      async loadHistory(): Promise<void> {
        this.loading = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            versions: LiveScriptVersion[]
          }>('/api/ecommerce-training/live-scripts')
          this.history = sortHistory(response.versions)
          const current = response.versions.find(item => item.is_current)
          if (current) {
            this.current = current
          } else if (!this.current) {
            this.current = this.history[0] ?? null
          }
        } catch {
          this.error = '直播话术记录加载失败'
        } finally {
          this.loading = false
        }
      },
      async openVersion(id: number): Promise<boolean> {
        this.loading = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            version: LiveScriptVersion
          }>(`/api/ecommerce-training/live-scripts/${id}`)
          this.current = response.version
          this.history = sortHistory([
            response.version,
            ...this.history.filter(item => item.id !== response.version.id)
          ])
          return true
        } catch {
          this.error = '直播话术版本加载失败'
          return false
        } finally {
          this.loading = false
        }
      }
    }
  }
)
