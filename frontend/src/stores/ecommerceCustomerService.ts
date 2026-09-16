import { defineStore } from 'pinia'

import { apiFetch } from '@/api/client'
import type { CustomerScenario, CustomerSession } from '@/api/types'

const API_PREFIX = '/api/ecommerce-training/customer-service'
const AI_UNAVAILABLE_MESSAGE = 'AI 服务暂时不可用'

interface EcommerceCustomerServiceState {
  scenarios: CustomerScenario[]
  current: CustomerSession | null
  history: CustomerSession[]
  pendingReply: string
  loadingScenarios: boolean
  loadingHistory: boolean
  starting: boolean
  submitting: boolean
  advancing: boolean
  ending: boolean
  opening: boolean
  error: string
}

function lastTurn(session: CustomerSession | null) {
  if (!session?.turns.length) {
    return null
  }
  return session.turns[session.turns.length - 1]
}

function sortSessions(sessions: CustomerSession[]): CustomerSession[] {
  return [...sessions].sort((left, right) => right.id - left.id)
}

export const useEcommerceCustomerServiceStore = defineStore(
  'ecommerceCustomerService',
  {
    state: (): EcommerceCustomerServiceState => ({
      scenarios: [],
      current: null,
      history: [],
      pendingReply: '',
      loadingScenarios: false,
      loadingHistory: false,
      starting: false,
      submitting: false,
      advancing: false,
      ending: false,
      opening: false,
      error: ''
    }),
    getters: {
      isBusy(state): boolean {
        return (
          state.loadingScenarios ||
          state.loadingHistory ||
          state.starting ||
          state.submitting ||
          state.advancing ||
          state.ending ||
          state.opening
        )
      },
      canContinue(state): boolean {
        const turn = lastTurn(state.current)
        return Boolean(
          state.current &&
            state.current.status !== 'completed' &&
            !state.current.end_suggested &&
            !state.pendingReply &&
            turn?.student_reply &&
            turn.analysis?.goal_status === 'not_reached'
        )
      },
      canEnd(state): boolean {
        return Boolean(
          state.current &&
            state.current.status !== 'completed' &&
            state.current.end_suggested &&
            !state.pendingReply
        )
      },
      completedSessions(state): CustomerSession[] {
        return state.history.filter(session => session.status === 'completed')
      }
    },
    actions: {
      replaceSession(session: CustomerSession) {
        this.current = session
        if (
          session.status === 'completed' ||
          this.history.some(item => item.id === session.id)
        ) {
          this.history = sortSessions([
            session,
            ...this.history.filter(item => item.id !== session.id)
          ])
        }
      },
      async loadScenarios(): Promise<boolean> {
        if (this.loadingScenarios) {
          return false
        }

        this.loadingScenarios = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            scenarios: CustomerScenario[]
          }>(`${API_PREFIX}/scenarios`)
          this.scenarios = response.scenarios
          return true
        } catch {
          this.error = '客服场景加载失败'
          return false
        } finally {
          this.loadingScenarios = false
        }
      },
      async loadHistory(): Promise<boolean> {
        if (this.loadingHistory) {
          return false
        }

        this.loadingHistory = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            sessions: CustomerSession[]
          }>(`${API_PREFIX}/sessions`)
          this.history = sortSessions(
            Array.isArray(response.sessions) ? response.sessions : []
          )
          return true
        } catch {
          this.error = '客服训练记录加载失败'
          return false
        } finally {
          this.loadingHistory = false
        }
      },
      async openSession(id: number): Promise<boolean> {
        if (this.opening) {
          return false
        }

        this.opening = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            session: CustomerSession
          }>(`${API_PREFIX}/sessions/${id}`)
          this.replaceSession(response.session)
          this.pendingReply = ''
          return true
        } catch {
          this.error = '客服训练记录加载失败'
          return false
        } finally {
          this.opening = false
        }
      },
      async start(scenarioKey: string): Promise<boolean> {
        if (this.starting || !scenarioKey.trim()) {
          return false
        }

        this.starting = true
        this.error = ''
        this.pendingReply = ''
        try {
          const response = await apiFetch<{
            success: true
            session: CustomerSession
          }>(`${API_PREFIX}/sessions`, {
            method: 'POST',
            body: JSON.stringify({ scenario_key: scenarioKey })
          })
          this.replaceSession(response.session)
          return true
        } catch {
          this.error = AI_UNAVAILABLE_MESSAGE
          return false
        } finally {
          this.starting = false
        }
      },
      async submitReply(text: string): Promise<boolean> {
        const reply = text.trim()
        if (!this.current || !reply || this.submitting) {
          return false
        }

        this.pendingReply = reply
        this.submitting = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            session: CustomerSession
          }>(`${API_PREFIX}/sessions/${this.current.id}/replies`, {
            method: 'POST',
            body: JSON.stringify({ reply })
          })
          this.replaceSession(response.session)
          this.pendingReply = ''
          return true
        } catch {
          this.error = AI_UNAVAILABLE_MESSAGE
          return false
        } finally {
          this.submitting = false
        }
      },
      async nextMessage(): Promise<boolean> {
        if (!this.current || !this.canContinue || this.advancing) {
          return false
        }

        this.advancing = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            session: CustomerSession
          }>(`${API_PREFIX}/sessions/${this.current.id}/next-message`, {
            method: 'POST'
          })
          this.replaceSession(response.session)
          this.pendingReply = ''
          return true
        } catch {
          this.error = AI_UNAVAILABLE_MESSAGE
          return false
        } finally {
          this.advancing = false
        }
      },
      async confirmEnd(): Promise<boolean> {
        if (!this.current || !this.canEnd || this.ending) {
          return false
        }

        this.ending = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            session: CustomerSession
          }>(`${API_PREFIX}/sessions/${this.current.id}/end`, {
            method: 'POST'
          })
          this.replaceSession(response.session)
          this.pendingReply = ''
          return true
        } catch {
          this.error = AI_UNAVAILABLE_MESSAGE
          return false
        } finally {
          this.ending = false
        }
      }
    }
  }
)
