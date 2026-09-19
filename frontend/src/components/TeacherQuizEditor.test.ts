import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type { TeacherQuiz, TeacherQuizQuestion } from '@/api/types'

import TeacherQuizEditor from './TeacherQuizEditor.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function question(id: string, prompt = `题目 ${id}`): TeacherQuizQuestion {
  return {
    id,
    type: 'single_choice',
    prompt,
    options: ['A', 'B'],
    answer: 'A'
  }
}

const fourQuestions = [
  question('q1'),
  question('q2'),
  question('q3'),
  question('q4')
]

function quiz(
  questions: TeacherQuizQuestion[],
  enabled = true
): TeacherQuiz {
  return {
    enabled,
    scoring_rule: 'all_correct',
    questions
  }
}

function mountEditor(
  initialQuestions: TeacherQuizQuestion[],
  overrides: Record<string, unknown> = {}
) {
  return mount(TeacherQuizEditor, {
    props: {
      courseId: 1,
      summary: '课程简介与知识点要点',
      direction: 'agriculture',
      expectedVersion: 1,
      initialQuestions,
      ...overrides
    },
    global: { plugins: [createPinia()] }
  })
}

describe('TeacherQuizEditor', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('edits and deletes preview questions before save', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      quiz: quiz(fourQuestions.slice(0, 3))
    } as never)
    const wrapper = mountEditor(fourQuestions)

    await wrapper
      .get('[data-test="question-q1-prompt"]')
      .setValue('新题干')
    await wrapper
      .get('[data-test="question-q1-option-0"]')
      .setValue('新选项')
    await wrapper.get('[data-test="delete-q2"]').trigger('click')
    await wrapper.get('[data-test="save-quiz"]').trigger('click')
    await flushPromises()

    const request = mockedApiFetch.mock.calls[0]
    const payload = JSON.parse(request[1]?.body as string)
    expect(request[0]).toBe('/api/teacher/courses/1/quiz')
    expect(payload.questions).toHaveLength(3)
    expect(payload.questions[0].prompt).toBe('新题干')
    expect(payload.questions[0].options[0]).toBe('新选项')
    expect(payload.questions[0].answer).toBe('新选项')
  })

  it('blocks save when deletion leaves fewer than three questions', async () => {
    const wrapper = mountEditor(fourQuestions.slice(0, 3))

    await wrapper.get('[data-test="delete-q2"]').trigger('click')
    await wrapper.get('[data-test="save-quiz"]').trigger('click')

    expect(wrapper.text()).toContain('测验至少需要 3 道题')
    expect(mockedApiFetch).not.toHaveBeenCalled()
  })

  it('blocks save when the preview has more than five questions', async () => {
    const wrapper = mountEditor([
      ...fourQuestions,
      question('q5'),
      question('q6')
    ])

    await wrapper.get('[data-test="save-quiz"]').trigger('click')

    expect(wrapper.text()).toContain('测验最多需要 5 道题')
    expect(mockedApiFetch).not.toHaveBeenCalled()
  })

  it('shows exact AI unavailable copy and keeps manual controls usable', async () => {
    mockedApiFetch.mockRejectedValue(
      new ApiError('AI 服务暂时不可用', 503)
    )
    const wrapper = mountEditor([])

    await wrapper.get('[data-test="generate-quiz"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('AI 服务暂时不可用')
    expect(wrapper.find('[data-test="close-quiz"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="generate-quiz"]').exists()).toBe(true)
  })

  it('generates from the current summary and direction', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      quiz: quiz(fourQuestions.slice(0, 3))
    } as never)
    const wrapper = mountEditor([])

    await wrapper.get('[data-test="generate-quiz"]').trigger('click')
    await flushPromises()

    const request = mockedApiFetch.mock.calls[0]
    expect(request[0]).toBe('/api/teacher/courses/1/quiz/generate')
    expect(JSON.parse(request[1]?.body as string)).toEqual({
      summary: '课程简介与知识点要点',
      direction: 'agriculture'
    })
    expect(wrapper.findAll('[data-test$="-prompt"]')).toHaveLength(3)
  })

  it('closes by saving a disabled empty quiz without calling AI', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      quiz: quiz([], false)
    } as never)
    const wrapper = mountEditor(fourQuestions)

    await wrapper.get('[data-test="close-quiz"]').trigger('click')
    await flushPromises()

    const request = mockedApiFetch.mock.calls[0]
    const payload = JSON.parse(request[1]?.body as string)
    expect(request[0]).toBe('/api/teacher/courses/1/quiz')
    expect(payload.enabled).toBe(false)
    expect(payload.questions).toEqual([])
    expect(
      mockedApiFetch.mock.calls.some(call =>
        String(call[0]).endsWith('/quiz/generate')
      )
    ).toBe(false)
    expect(wrapper.findAll('[data-test$="-prompt"]')).toHaveLength(0)
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
