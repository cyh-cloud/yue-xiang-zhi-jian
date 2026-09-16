import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError, apiFetch } from '@/api/client'
import type { DiagnosisSession, DiagnosticSelfTest } from '@/api/types'
import AgriSkillsNav from '@/components/AgriSkillsNav.vue'
import AppHeader from '@/components/AppHeader.vue'
import VoiceInputButton from '@/components/VoiceInputButton.vue'
import { useAgriDiagnosisStore } from '@/stores/agriDiagnosis'

import AgriDiagnosisView from './AgriDiagnosisView.vue'

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
    },
    {
      id: 'q2',
      type: 'true_false',
      prompt: '药剂应按登记说明使用。',
      options: ['正确', '错误']
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

function createTestRouter() {
  const paths = [
    '/',
    '/login',
    '/messages',
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
  const wrapper = mount(AgriDiagnosisView, {
    global: {
      plugins: [pinia, createTestRouter()]
    }
  })
  return { pinia, wrapper }
}

describe('AgriDiagnosisView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/diagnoses') {
        return { success: true, diagnoses: [] } as never
      }
      if (path === '/api/agri-skills/products') {
        return {
          success: true,
          products: [sessionFixture.product]
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })
  })

  it('renders the shell and point-selection controls in product, part, symptom order', async () => {
    const { wrapper } = mountView()
    await flushPromises()

    expect(wrapper.findComponent(AppHeader).exists()).toBe(true)
    expect(wrapper.findComponent(AgriSkillsNav).exists()).toBe(true)

    const form = wrapper.get('[data-test="diagnosis-start-form"]')
    const controls = Array.from(
      form.element.querySelectorAll('select, input[type="checkbox"]')
    )
    expect(controls.map(element => element.getAttribute('data-test'))).toEqual([
      'diagnosis-product',
      'diagnosis-part',
      'diagnosis-symptom-0',
      'diagnosis-symptom-1',
      'diagnosis-symptom-2',
      'diagnosis-symptom-3'
    ])
  })

  it('submits product, part and multiple symptoms as one diagnosis payload', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    const store = useAgriDiagnosisStore(pinia)
    const createDiagnosis = vi
      .spyOn(store, 'createDiagnosis')
      .mockResolvedValue(true)

    await wrapper.get('[data-test="diagnosis-product"]').setValue('litchi')
    await wrapper.get('[data-test="diagnosis-part"]').setValue('fruit')
    await wrapper.get('[data-test="diagnosis-symptom-0"]').setValue(true)
    await wrapper.get('[data-test="diagnosis-symptom-1"]').setValue(true)
    await wrapper.get('[data-test="diagnosis-start-form"]').trigger('submit')

    expect(createDiagnosis).toHaveBeenCalledWith({
      product_key: 'litchi',
      affected_part: 'fruit',
      symptoms: ['斑点', '虫蛀']
    })
  })

  it('shows one pending question with resume and abandon controls', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    const store = useAgriDiagnosisStore(pinia)
    const startDiagnosis = vi
      .spyOn(store, 'startDiagnosis')
      .mockResolvedValue(true)
    store.activeSession = session()
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('[data-test="pending-question"]')).toHaveLength(1)
    expect(wrapper.get('[data-test="pending-question"]').text()).toContain(
      '请补充症状出现时间'
    )
    expect(wrapper.find('[data-test="resume-diagnosis"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="abandon-diagnosis"]').exists()).toBe(true)

    await wrapper.get('[data-test="resume-diagnosis"]').trigger('click')
    expect(startDiagnosis).toHaveBeenCalledOnce()
  })

  it('renders a limited conclusion, chronological follow-ups and self-test feedback', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    const store = useAgriDiagnosisStore(pinia)
    store.activeSession = session({
      status: 'completed',
      round_count: 5,
      pending_question: null,
      pending_question_round: null,
      limited: true,
      conclusion: {
        cause: '疑似蒂蛀虫',
        treatment: '清理落果并规范用药'
      },
      followups: [
        {
          id: 8,
          outcome: 'unchanged',
          note: '继续观察',
          created_at: '2026-09-17T02:00:00+00:00'
        },
        {
          id: 7,
          outcome: 'improved',
          note: '叶片恢复',
          created_at: '2026-09-16T02:00:00+00:00'
        }
      ]
    })
    store.selfTest = selfTestFixture
    store.selfTestResult = {
      attempt_id: 8,
      score: 100,
      questions: [
        {
          ...selfTestFixture.questions[0],
          correct: true,
          explanation: '清理落果可以减少虫源。'
        },
        {
          ...selfTestFixture.questions[1],
          correct: true,
          explanation: '必须按登记说明使用。'
        }
      ]
    }
    await wrapper.vm.$nextTick()

    expect(wrapper.get('[data-test="limited-marker"]').text()).toBe('信息有限')
    expect(wrapper.get('[data-test="diagnosis-cause"]').text()).toContain(
      '疑似蒂蛀虫'
    )
    expect(wrapper.get('[data-test="diagnosis-treatment"]').text()).toContain(
      '清理落果并规范用药'
    )

    const followups = wrapper.findAll('[data-test^="followup-"]')
    expect(followups.map(item => item.text())).toEqual([
      expect.stringContaining('好转'),
      expect.stringContaining('无变化')
    ])
    expect(followups[0].text()).toContain('叶片恢复')
    expect(wrapper.get('[data-test="self-test-score"]').text()).toContain('100')
    expect(wrapper.findAll('[data-test^="self-test-explanation-"]')).toHaveLength(
      2
    )
  })

  it('keeps the answer draft and point selections after a 503', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/diagnoses') {
        return { success: true, diagnoses: [] } as never
      }
      if (path === '/api/agri-skills/products') {
        return {
          success: true,
          products: [sessionFixture.product]
        } as never
      }
      if (path === '/api/agri-skills/diagnoses/12/answers') {
        throw new ApiError('AI 服务暂时不可用', 503)
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    const { pinia, wrapper } = mountView()
    await flushPromises()
    const store = useAgriDiagnosisStore(pinia)
    store.activeSession = session()
    await wrapper.vm.$nextTick()

    const input = wrapper.get('[data-test="diagnosis-answer"]')
    await input.setValue('症状已经持续三天')
    await wrapper.get('[data-test="diagnosis-answer-form"]').trigger('submit')
    await flushPromises()

    expect((input.element as HTMLTextAreaElement).value).toBe(
      '症状已经持续三天'
    )
    expect(store.activeSession).toMatchObject({
      product_key: 'litchi',
      affected_part: 'fruit',
      symptoms: ['虫蛀', '落果']
    })
    expect(wrapper.get('[role="alert"]').text()).toContain('AI 服务暂时不可用')
  })

  it('inserts confirmed speech text without auto-submitting the answer', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/diagnoses') {
        return { success: true, diagnoses: [] } as never
      }
      if (path === '/api/agri-skills/products') {
        return {
          success: true,
          products: [sessionFixture.product]
        } as never
      }
      if (path === '/api/agri-skills/speech/transcriptions') {
        return { success: true, text: '果实上有虫孔' } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    const { pinia, wrapper } = mountView()
    await flushPromises()
    const store = useAgriDiagnosisStore(pinia)
    store.activeSession = session()
    const answerDiagnosis = vi
      .spyOn(store, 'answerDiagnosis')
      .mockResolvedValue(true)
    await wrapper.vm.$nextTick()

    wrapper.findComponent(VoiceInputButton).vm.$emit(
      'recorded',
      new Blob(['audio'], { type: 'audio/webm' }),
      'answer.webm'
    )
    await flushPromises()

    expect(
      (
        wrapper.get('[data-test="diagnosis-answer"]')
          .element as HTMLTextAreaElement
      ).value
    ).toBe('果实上有虫孔')
    expect(answerDiagnosis).not.toHaveBeenCalled()
  })
})
