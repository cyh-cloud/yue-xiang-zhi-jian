import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type {
  DiagnosisAnswer,
  DiagnosisSession,
  DiagnosticSelfTest,
  SelfTestResult
} from '@/api/types'

type InputMode = 'text' | 'voice'
type FollowupOutcome = 'improved' | 'unchanged' | 'worsened'

export interface DiagnosisCreatePayload {
  product_key: string
  affected_part: string
  symptoms: string[]
}

type DiagnosisSessionPayload = Omit<DiagnosisSession, 'answers'> & {
  answers?: DiagnosisAnswer[] | string[]
  answer_records?: DiagnosisAnswer[]
  questions?: string[]
  pending_question?: string | null
  pending_question_round?: number | null
  ai_error?: string
}

interface AgriDiagnosisState {
  sessions: DiagnosisSession[]
  activeSession: DiagnosisSession | null
  loading: boolean
  saving: boolean
  error: string
  selfTest: DiagnosticSelfTest | null
  selfTestResult: SelfTestResult | null
}

const AI_UNAVAILABLE_MESSAGE = 'AI 服务暂时不可用'

function compareSessions(
  left: DiagnosisSession,
  right: DiagnosisSession
): number {
  const timeDifference =
    Date.parse(right.updated_at) - Date.parse(left.updated_at)
  return Number.isNaN(timeDifference)
    ? right.id - left.id
    : timeDifference || right.id - left.id
}

function normalizeSession(payload: DiagnosisSessionPayload): DiagnosisSession {
  const rawAnswers = Array.isArray(payload.answers) ? payload.answers : []
  const answerRecords = Array.isArray(payload.answer_records)
    ? payload.answer_records
    : rawAnswers.filter(
        (item): item is DiagnosisAnswer =>
          typeof item === 'object' && item !== null
      )
  const answers =
    answerRecords.length > 0
      ? answerRecords
      : rawAnswers.map((answer, index) => ({
          round_no: index + 1,
          question: payload.questions?.[index] ?? '',
          answer: String(answer),
          input_mode: 'text' as const,
          ai_status: 'follow_up_required' as const
        }))

  return {
    ...payload,
    answers
  } as DiagnosisSession
}

function pendingQuestion(session: DiagnosisSession | null): string {
  return (session as DiagnosisSessionPayload | null)?.pending_question?.trim() ?? ''
}

function sortFollowups(session: DiagnosisSession): DiagnosisSession {
  return {
    ...session,
    followups: [...session.followups].sort(
      (left, right) =>
        Date.parse(left.created_at) - Date.parse(right.created_at) ||
        left.id - right.id
    )
  }
}

export const useAgriDiagnosisStore = defineStore('agriDiagnosis', {
  state: (): AgriDiagnosisState => ({
    sessions: [],
    activeSession: null,
    loading: false,
    saving: false,
    error: '',
    selfTest: null,
    selfTestResult: null
  }),
  actions: {
    captureError(error: unknown, fallback: string) {
      if (error instanceof ApiError) {
        this.error =
          error.status === 503 ||
          error.message === AI_UNAVAILABLE_MESSAGE
            ? AI_UNAVAILABLE_MESSAGE
            : error.message || fallback
        return
      }
      this.error = error instanceof Error ? error.message : fallback
    },
    storeSession(payload: DiagnosisSessionPayload) {
      const normalized = sortFollowups(normalizeSession(payload))
      this.activeSession = normalized
      this.sessions = [
        normalized,
        ...this.sessions.filter(item => item.id !== normalized.id)
      ].sort(compareSessions)
    },
    async loadSessions() {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          diagnoses: DiagnosisSessionPayload[]
        }>('/api/agri-skills/diagnoses')
        this.sessions = response.diagnoses
          .map(normalizeSession)
          .sort(compareSessions)
      } catch (error) {
        this.captureError(error, '诊断记录加载失败')
      } finally {
        this.loading = false
      }
    },
    async createDiagnosis(payload: DiagnosisCreatePayload): Promise<boolean> {
      this.saving = true
      this.error = ''
      this.selfTest = null
      this.selfTestResult = null

      try {
        const response = await apiFetch<{
          success: true
          session: DiagnosisSessionPayload
        }>('/api/agri-skills/diagnoses', {
          method: 'POST',
          body: JSON.stringify(payload)
        })
        this.storeSession(response.session)

        const session = this.activeSession
        if (
          session?.status === 'in_progress' &&
          !pendingQuestion(session)
        ) {
          return await this.startDiagnosis()
        }

        const aiError = response.session.ai_error
        if (aiError) {
          this.error = AI_UNAVAILABLE_MESSAGE
          return false
        }
        return true
      } catch (error) {
        this.captureError(error, '诊断创建失败')
        return false
      } finally {
        this.saving = false
      }
    },
    async startDiagnosis(): Promise<boolean> {
      const session = this.activeSession
      if (!session || session.status !== 'in_progress') {
        return Boolean(session)
      }
      if (pendingQuestion(session)) {
        return true
      }

      this.saving = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          session: DiagnosisSessionPayload
        }>(`/api/agri-skills/diagnoses/${session.id}/start`, {
          method: 'POST'
        })
        this.storeSession(response.session)

        if (response.session.ai_error) {
          this.error = AI_UNAVAILABLE_MESSAGE
          return false
        }
        if (
          this.activeSession?.status === 'in_progress' &&
          !pendingQuestion(this.activeSession)
        ) {
          this.error = AI_UNAVAILABLE_MESSAGE
          return false
        }
        return true
      } catch (error) {
        this.captureError(error, AI_UNAVAILABLE_MESSAGE)
        return false
      } finally {
        this.saving = false
      }
    },
    async answerDiagnosis(
      answer: string,
      inputMode: InputMode
    ): Promise<boolean> {
      const normalizedAnswer = answer.trim()
      if (!normalizedAnswer) {
        this.error = '回答不能为空'
        return false
      }

      let session = this.activeSession
      if (!session || session.status !== 'in_progress') {
        this.error = '诊断会话不可继续'
        return false
      }
      if (!pendingQuestion(session)) {
        const started = await this.startDiagnosis()
        session = this.activeSession
        if (!started || !session || !pendingQuestion(session)) {
          return false
        }
      }

      this.saving = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          session: DiagnosisSessionPayload
        }>(`/api/agri-skills/diagnoses/${session.id}/answers`, {
          method: 'POST',
          body: JSON.stringify({
            answer: normalizedAnswer,
            input_mode: inputMode
          })
        })
        this.storeSession(response.session)
        return true
      } catch (error) {
        this.captureError(error, AI_UNAVAILABLE_MESSAGE)
        return false
      } finally {
        this.saving = false
      }
    },
    async abandonDiagnosis(): Promise<boolean> {
      const session = this.activeSession
      if (!session || session.status !== 'in_progress') {
        this.error = '诊断会话不可放弃'
        return false
      }

      this.saving = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          session: DiagnosisSessionPayload
        }>(`/api/agri-skills/diagnoses/${session.id}/abandon`, {
          method: 'POST'
        })
        this.storeSession(response.session)
        return true
      } catch (error) {
        this.captureError(error, '放弃诊断失败')
        return false
      } finally {
        this.saving = false
      }
    },
    async addFollowup(
      outcome: FollowupOutcome,
      note: string
    ): Promise<boolean> {
      const session = this.activeSession
      if (!session || session.status !== 'completed') {
        this.error = '仅已完成诊断可记录复诊'
        return false
      }

      this.saving = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          followup: DiagnosisSession['followups'][number]
        }>(`/api/agri-skills/diagnoses/${session.id}/followups`, {
          method: 'POST',
          body: JSON.stringify({
            outcome,
            note: note.trim()
          })
        })
        this.storeSession({
          ...session,
          followups: [...session.followups, response.followup],
          updated_at: response.followup.created_at
        })
        return true
      } catch (error) {
        this.captureError(error, '复诊记录保存失败')
        return false
      } finally {
        this.saving = false
      }
    },
    async repeatDiagnosis(followupId: number): Promise<boolean> {
      const session = this.activeSession
      if (!session) {
        this.error = '诊断记录不存在'
        return false
      }

      this.saving = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          session: DiagnosisSessionPayload
        }>(`/api/agri-skills/diagnoses/${session.id}/repeat`, {
          method: 'POST',
          body: JSON.stringify({ followup_id: followupId })
        })
        this.selfTest = null
        this.selfTestResult = null
        this.storeSession(response.session)
        return true
      } catch (error) {
        this.captureError(error, '再次诊断创建失败')
        return false
      } finally {
        this.saving = false
      }
    },
    async generateSelfTest(): Promise<boolean> {
      const session = this.activeSession
      if (!session || session.status !== 'completed') {
        this.error = '仅已完成诊断可生成自测'
        return false
      }

      this.saving = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          self_test: DiagnosticSelfTest
        }>(`/api/agri-skills/diagnoses/${session.id}/self-test`, {
          method: 'POST'
        })
        this.selfTest = response.self_test
        this.selfTestResult = null
        return true
      } catch (error) {
        this.captureError(error, AI_UNAVAILABLE_MESSAGE)
        return false
      } finally {
        this.saving = false
      }
    },
    async submitSelfTest(answers: Record<string, string>): Promise<boolean> {
      const selfTest = this.selfTest
      if (!selfTest) {
        this.error = '自测尚未生成'
        return false
      }

      this.saving = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          result: SelfTestResult
        }>(`/api/agri-skills/self-tests/${selfTest.id}/submit`, {
          method: 'POST',
          body: JSON.stringify({ answers })
        })
        this.selfTestResult = response.result
        return true
      } catch (error) {
        this.captureError(error, AI_UNAVAILABLE_MESSAGE)
        return false
      } finally {
        this.saving = false
      }
    }
  }
})
