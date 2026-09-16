import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type {
  DiagnosisSession,
  DiagnosticSelfTest,
  SelfTestResult
} from '@/api/types'

import { useAgriDiagnosisStore } from './agriDiagnosis'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

type SessionFixture = DiagnosisSession & {
  pending_question?: string | null
  pending_question_round?: number | null
  ai_error?: string
}

const sessionFixture: SessionFixture = {
  id: 12,
  product: {
    key: 'litchi',
    name: '荔枝',
    sort_order: 1
  },
  product_key: 'litchi',
  affected_part: 'fruit',
  symptoms: ['虫蛀', '落果'],
  status: 'in_progress',
  round_count: 0,
  conclusion: null,
  limited: false,
  answers: [],
  followups: [],
  source_session_id: null,
  source_followup_id: null,
  source_available: true,
  created_at: '2026-09-16T01:00:00+00:00',
  updated_at: '2026-09-16T01:00:00+00:00',
  pending_question: '请补充症状出现时间',
  pending_question_round: 1
}

const selfTestFixture: DiagnosticSelfTest = {
  id: 3,
  diagnosis_session_id: 12,
  generation_attempts: 1,
  questions: [
    {
      id: 'q1',
      type: 'single_choice',
      prompt: '第一步应该做什么？',
      options: ['清理落果', '继续观察']
    }
  ]
}

const selfTestResultFixture: SelfTestResult = {
  attempt_id: 8,
  score: 100,
  questions: [
    {
      ...selfTestFixture.questions[0],
      correct: true,
      explanation: '清理落果可以减少虫源。'
    }
  ]
}

function session(patch: Partial<SessionFixture> = {}): SessionFixture {
  return {
    ...sessionFixture,
    product: { ...sessionFixture.product },
    symptoms: [...sessionFixture.symptoms],
    answers: [...sessionFixture.answers],
    followups: [...sessionFixture.followups],
    ...patch
  }
}

describe('agriDiagnosis store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('stores an in-progress response with the next question', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      session: session({
        round_count: 1,
        pending_question: '症状是否继续扩大',
        pending_question_round: 2
      })
    } as never)
    const store = useAgriDiagnosisStore()
    store.activeSession = session()

    const succeeded = await store.answerDiagnosis('两天前出现', 'text')

    expect(succeeded).toBe(true)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/diagnoses/12/answers',
      {
        method: 'POST',
        body: JSON.stringify({
          answer: '两天前出现',
          input_mode: 'text'
        })
      }
    )
    expect(store.activeSession?.status).toBe('in_progress')
    expect(
      (store.activeSession as SessionFixture | null)?.pending_question
    ).toBe('症状是否继续扩大')
  })

  it('stores a completed response and the exact limited marker', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      session: session({
        round_count: 5,
        status: 'completed',
        pending_question: null,
        pending_question_round: null,
        limited: true,
        conclusion: {
          cause: '疑似蒂蛀虫',
          treatment: '清理落果并规范用药'
        }
      })
    } as never)
    const store = useAgriDiagnosisStore()
    store.activeSession = session({ round_count: 4 })

    await store.answerDiagnosis('第五轮补充', 'text')

    expect(store.activeSession?.status).toBe('completed')
    expect(store.activeSession?.limited).toBe(true)
    expect(store.activeSession?.conclusion?.cause).toBe('疑似蒂蛀虫')
  })

  it('keeps selections when AI is unavailable during an answer', async () => {
    mockedApiFetch.mockRejectedValue(
      new ApiError('AI 服务暂时不可用', 503)
    )
    const store = useAgriDiagnosisStore()
    const current = session()
    store.activeSession = current

    const succeeded = await store.answerDiagnosis('仍未改善', 'text')

    expect(succeeded).toBe(false)
    expect(store.error).toBe('AI 服务暂时不可用')
    expect(store.activeSession).toMatchObject({
      id: current.id,
      product_key: 'litchi',
      affected_part: 'fruit',
      symptoms: ['虫蛀', '落果']
    })
  })

  it('calls start only when an in-progress session has no pending question', async () => {
    const store = useAgriDiagnosisStore()
    store.activeSession = session()

    await store.startDiagnosis()
    expect(mockedApiFetch).not.toHaveBeenCalled()

    mockedApiFetch.mockResolvedValue({
      success: true,
      session: session({
        round_count: 1,
        pending_question: '请描述落果比例',
        pending_question_round: 1
      })
    } as never)
    store.activeSession = session({
      pending_question: null,
      pending_question_round: null
    })

    await store.startDiagnosis()

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/diagnoses/12/start',
      { method: 'POST' }
    )
    expect(
      (store.activeSession as SessionFixture | null)?.pending_question
    ).toBe('请描述落果比例')
  })

  it('recovers a missing first question while preserving point selections', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/diagnoses') {
        return {
          success: true,
          session: session({
            pending_question: null,
            pending_question_round: null
          })
        } as never
      }
      if (path === '/api/agri-skills/diagnoses/12/start') {
        return {
          success: true,
          session: session({
            round_count: 1,
            pending_question: '请补充叶片病斑颜色',
            pending_question_round: 1
          })
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    const store = useAgriDiagnosisStore()
    store.selfTest = selfTestFixture
    store.selfTestResult = selfTestResultFixture

    const succeeded = await store.createDiagnosis({
      product_key: 'litchi',
      affected_part: 'fruit',
      symptoms: ['虫蛀', '落果']
    })

    expect(succeeded).toBe(true)
    expect(mockedApiFetch.mock.calls.map(([path]) => path)).toEqual([
      '/api/agri-skills/diagnoses',
      '/api/agri-skills/diagnoses/12/start'
    ])
    expect(store.activeSession).toMatchObject({
      product_key: 'litchi',
      affected_part: 'fruit',
      symptoms: ['虫蛀', '落果']
    })
    expect(store.selfTest).toBeNull()
    expect(store.selfTestResult).toBeNull()
  })

  it('appends every follow-up without overwriting earlier records', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        followup: {
          id: 7,
          outcome: 'improved',
          note: '叶片恢复',
          created_at: '2026-09-16T02:00:00+00:00'
        }
      } as never)
      .mockResolvedValueOnce({
        success: true,
        followup: {
          id: 8,
          outcome: 'unchanged',
          note: '继续观察',
          created_at: '2026-09-17T02:00:00+00:00'
        }
      } as never)
    const store = useAgriDiagnosisStore()
    store.activeSession = session({
      status: 'completed',
      pending_question: null,
      pending_question_round: null,
      conclusion: {
        cause: '疑似蒂蛀虫',
        treatment: '清理落果并规范用药'
      }
    })

    await store.addFollowup('improved', '叶片恢复')
    await store.addFollowup('unchanged', '继续观察')

    expect(store.activeSession?.followups).toHaveLength(2)
    expect(store.activeSession?.followups.map(item => item.id)).toEqual([7, 8])
  })

  it('creates an editable repeated diagnosis from a follow-up', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      session: session({
        id: 19,
        source_session_id: 12,
        source_followup_id: 7,
        pending_question: '复诊后症状是否变化',
        pending_question_round: 1
      })
    } as never)
    const store = useAgriDiagnosisStore()
    store.activeSession = session({ status: 'completed' })

    await store.repeatDiagnosis(7)

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/diagnoses/12/repeat',
      {
        method: 'POST',
        body: JSON.stringify({ followup_id: 7 })
      }
    )
    expect(store.activeSession?.source_followup_id).toBe(7)
    expect(store.activeSession?.product_key).toBe('litchi')
    expect(store.activeSession?.status).toBe('in_progress')
  })

  it('generates and grades a self-test without dropping the questions', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        self_test: selfTestFixture
      } as never)
      .mockResolvedValueOnce({
        success: true,
        result: selfTestResultFixture
      } as never)
    const store = useAgriDiagnosisStore()
    store.activeSession = session({ status: 'completed' })

    await store.generateSelfTest()
    expect(store.selfTest).toEqual(selfTestFixture)

    const succeeded = await store.submitSelfTest({ q1: '清理落果' })

    expect(succeeded).toBe(true)
    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      '/api/agri-skills/self-tests/3/submit',
      {
        method: 'POST',
        body: JSON.stringify({ answers: { q1: '清理落果' } })
      }
    )
    expect(store.selfTestResult?.score).toBe(100)
  })
})
