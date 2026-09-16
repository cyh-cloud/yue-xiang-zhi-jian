import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type { CustomerScenario, CustomerSession } from '@/api/types'

const API_PREFIX = '/api/ecommerce-training/customer-service'
const AI_UNAVAILABLE_MESSAGE = 'AI 服务暂时不可用'
const GENERIC_ACTION_ERROR = '操作失败，请稍后重试'

export type EcommerceCustomerServiceSession = Omit<
  CustomerSession,
  'turns' | 'summary'
> & {
  turns: Array<
    Omit<CustomerSession['turns'][number], 'analysis'> & {
      analysis: {
        problem: unknown
        evidence: unknown
        suggestion: unknown
        criteria: Record<string, unknown>
        goal_status: 'reached' | 'not_reached'
      } | null
    }
  >
  summary: {
    overall_performance: unknown
    main_problems: unknown
    prioritized_improvements: unknown
    goal_completion: unknown
  } | null
}

interface EcommerceCustomerServiceState {
  scenarios: CustomerScenario[]
  current: EcommerceCustomerServiceSession | null
  history: EcommerceCustomerServiceSession[]
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

function lastTurn(session: EcommerceCustomerServiceSession | null) {
  if (!session?.turns.length) {
    return null
  }
  return session.turns[session.turns.length - 1]
}

function sortSessions(
  sessions: EcommerceCustomerServiceSession[]
): EcommerceCustomerServiceSession[] {
  const timestamp = (session: EcommerceCustomerServiceSession): number => {
    const updatedAt = Date.parse(session.updated_at)
    if (!Number.isNaN(updatedAt)) {
      return updatedAt
    }
    const createdAt = Date.parse(session.created_at)
    return Number.isNaN(createdAt) ? 0 : createdAt
  }

  return [...sessions].sort(
    (left, right) =>
      timestamp(right) - timestamp(left) || right.id - left.id
  )
}

function toStoreSession(
  session: CustomerSession
): EcommerceCustomerServiceSession {
  return session
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.status === 401) {
    return ''
  }
  if (
    error instanceof ApiError &&
    (error.status === 503 || error.message === AI_UNAVAILABLE_MESSAGE)
  ) {
    return AI_UNAVAILABLE_MESSAGE
  }
  return fallback
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
      completedSessions(state): EcommerceCustomerServiceSession[] {
        return state.history.filter(session => session.status === 'completed')
      }
    },
    actions: {
      replaceSession(session: CustomerSession) {
        const storedSession = toStoreSession(session)
        this.current = storedSession
        this.history = sortSessions([
          storedSession,
          ...this.history.filter(item => item.id !== storedSession.id)
        ])
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
        } catch (error) {
          this.error = errorMessage(error, '客服场景加载失败')
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
            Array.isArray(response.sessions)
              ? response.sessions.map(toStoreSession)
              : []
          )
          return true
        } catch (error) {
          this.error = errorMessage(error, '客服训练记录加载失败')
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
        } catch (error) {
          this.error = errorMessage(error, '客服训练记录加载失败')
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
        } catch (error) {
          this.error = errorMessage(error, GENERIC_ACTION_ERROR)
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
        } catch (error) {
          this.error = errorMessage(error, GENERIC_ACTION_ERROR)
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
        } catch (error) {
          this.error = errorMessage(error, GENERIC_ACTION_ERROR)
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
        } catch (error) {
          this.error = errorMessage(error, GENERIC_ACTION_ERROR)
          return false
        } finally {
          this.ending = false
        }
      }
    }
  }
)
