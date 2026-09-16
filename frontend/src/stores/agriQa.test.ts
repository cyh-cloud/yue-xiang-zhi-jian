import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch, apiStream } from '@/api/client'
import type { QaConversation, QaTurn } from '@/api/types'

import { useAgriQaStore } from './agriQa'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn(),
    apiStream: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)
const mockedApiStream = vi.mocked(apiStream)

const conversation: QaConversation = {
  id: 7,
  title: '荔枝蒂蛀虫',
  created_at: '2026-09-16T01:00:00+00:00',
  updated_at: '2026-09-16T01:00:00+00:00'
}

const aiTurn: QaTurn = {
  id: 11,
  question: '荔枝如何保果',
  answer: '春季保果',
  input_mode: 'text',
  answer_mode: 'ai',
  suggestions: ['如何施肥', '如何排水', '如何防虫'],
  created_at: '2026-09-16T01:01:00+00:00'
}

describe('agriQa store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
    mockedApiStream.mockReset()
  })

  it('creates the first conversation and persists a complete streamed turn', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      conversation
    } as never)
    mockedApiStream.mockImplementation(async (_path, _options, onEvent) => {
      onEvent({ event: 'chunk', data: { content: '春季' } } as never)
      onEvent({ event: 'chunk', data: { content: '保果' } } as never)
      onEvent({ event: 'complete', data: { turn: aiTurn } } as never)
    })
    const store = useAgriQaStore()

    await store.ask('荔枝如何保果', 'text')

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/qa/conversations',
      {
        method: 'POST',
        body: JSON.stringify({
          question: '荔枝如何保果',
          input_mode: 'text'
        })
      }
    )
    expect(mockedApiStream).toHaveBeenCalledWith(
      '/api/agri-skills/qa/conversations/7/messages/stream',
      {
        method: 'POST',
        body: JSON.stringify({
          question: '荔枝如何保果',
          input_mode: 'text'
        })
      },
      expect.any(Function)
    )
    expect(store.turns).toEqual([aiTurn])
    expect(store.streamingText).toBe('')
    expect(store.suggestions).toEqual(aiTurn.suggestions)
    expect(store.answerMode).toBe('ai')
  })

  it('replaces partial AI text with a labeled local answer', async () => {
    const localTurn: QaTurn = {
      ...aiTurn,
      id: 12,
      question: '荔枝蒂蛀虫',
      answer: '离线知识库回答\n荔枝蒂蛀虫：及时清理落果',
      answer_mode: 'local_kb',
      suggestions: []
    }
    mockedApiStream.mockImplementation(async (_path, _options, onEvent) => {
      onEvent({ event: 'chunk', data: { content: '部分' } } as never)
      onEvent({ event: 'replace', data: { turn: localTurn } } as never)
    })
    const store = useAgriQaStore()
    store.activeConversationId = conversation.id

    await store.ask('荔枝蒂蛀虫', 'text')

    expect(store.streamingText).toBe('')
    expect(store.answerMode).toBe('local_kb')
    expect(store.turns[0].answer).toContain('离线知识库回答')
    expect(store.suggestions).toEqual([])
    expect(store.suggestionError).toBe('')
  })

  it('forces local-KB semantics for a malformed replace event', async () => {
    const malformedTurn = {
      ...aiTurn,
      id: 14,
      question: '荔枝蒂蛀虫',
      answer: '离线知识库回答\n荔枝蒂蛀虫：及时清理落果',
      answer_mode: 'ai',
      suggestions: ['不应显示的建议']
    } as QaTurn
    mockedApiStream.mockImplementation(async (_path, _options, onEvent) => {
      onEvent({ event: 'chunk', data: { content: '部分' } } as never)
      onEvent({ event: 'replace', data: { turn: malformedTurn } } as never)
    })
    const store = useAgriQaStore()
    store.activeConversationId = conversation.id

    await store.ask('荔枝蒂蛀虫', 'text')

    expect(store.streamingText).toBe('')
    expect(store.answerMode).toBe('local_kb')
    expect(store.turns).toHaveLength(1)
    expect(store.turns[0]).toMatchObject({
      id: 14,
      answer_mode: 'local_kb',
      suggestions: []
    })
    expect(store.suggestions).toEqual([])
    expect(store.suggestionError).toBe('')
  })

  it('uses the non-streaming local fallback after a streamed AI response is interrupted', async () => {
    const localTurn: QaTurn = {
      ...aiTurn,
      id: 13,
      question: '荔枝蒂蛀虫导致落果',
      answer: '离线知识库回答\n荔枝蒂蛀虫：及时清理落果',
      answer_mode: 'local_kb',
      suggestions: []
    }
    mockedApiStream.mockImplementation(async (_path, _options, onEvent) => {
      onEvent({ event: 'chunk', data: { content: '不完整' } } as never)
      throw new Error('stream interrupted')
    })
    mockedApiFetch.mockResolvedValue({
      success: true,
      turn: localTurn
    } as never)
    const store = useAgriQaStore()
    store.activeConversationId = conversation.id

    await store.ask('荔枝蒂蛀虫导致落果', 'text')

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/qa/conversations/7/messages',
      {
        method: 'POST',
        body: JSON.stringify({
          question: '荔枝蒂蛀虫导致落果',
          input_mode: 'text'
        })
      }
    )
    expect(store.streamingText).toBe('')
    expect(store.answerMode).toBe('local_kb')
    expect(store.turns).toEqual([localTurn])
  })

  it('shows a streamed error event without creating a turn', async () => {
    mockedApiStream.mockImplementation(async (_path, _options, onEvent) => {
      onEvent({
        event: 'error',
        data: { message: '暂无法回答，建议稍后再试' }
      } as never)
      throw new Error('connection closed')
    })
    const store = useAgriQaStore()
    store.activeConversationId = conversation.id

    const succeeded = await store.ask('完全无关的问题', 'text')

    expect(succeeded).toBe(false)
    expect(store.error).toBe('暂无法回答，建议稍后再试')
    expect(store.turns).toHaveLength(0)
  })

  it('does not expose a raw streamed error message', async () => {
    mockedApiStream.mockImplementation(async (_path, _options, onEvent) => {
      onEvent({
        event: 'error',
        data: { message: 'upstream socket reset' }
      } as never)
    })
    const store = useAgriQaStore()
    store.activeConversationId = conversation.id

    await store.ask('荔枝如何保果', 'text')

    expect(store.error).toBe('AI 服务暂时不可用')
    expect(store.turns).toHaveLength(0)
  })

  it('does not expose a raw suggestion error from a completed turn', async () => {
    mockedApiStream.mockImplementation(async (_path, _options, onEvent) => {
      onEvent({
        event: 'complete',
        data: {
          turn: aiTurn,
          suggestion_error: 'backend implementation detail'
        }
      } as never)
    })
    const store = useAgriQaStore()
    store.activeConversationId = conversation.id

    await store.ask('荔枝如何保果', 'text')

    expect(store.suggestionError).toBe('AI 服务暂时不可用')
    expect(store.turns).toEqual([aiTurn])
  })

  it('shows the exact AI-unavailable message when the stream fails', async () => {
    mockedApiStream.mockRejectedValue(new Error('network connection closed'))
    const store = useAgriQaStore()
    store.activeConversationId = conversation.id

    const succeeded = await store.ask('荔枝如何保果', 'text')

    expect(succeeded).toBe(false)
    expect(store.error).toBe('AI 服务暂时不可用')
    expect(store.turns).toHaveLength(0)
  })

  it('shows the exact AI-unavailable message when non-stream fallback fails', async () => {
    mockedApiStream.mockImplementation(async (_path, _options, onEvent) => {
      onEvent({ event: 'chunk', data: { content: '不完整' } } as never)
      throw new Error('stream disconnected')
    })
    mockedApiFetch.mockRejectedValue(new Error('database unavailable'))
    const store = useAgriQaStore()
    store.activeConversationId = conversation.id

    const succeeded = await store.ask('荔枝蒂蛀虫导致落果', 'text')

    expect(succeeded).toBe(false)
    expect(store.error).toBe('AI 服务暂时不可用')
    expect(store.turns).toHaveLength(0)
  })

  it('loads conversations newest-first and opens every retained turn', async () => {
    const olderConversation = {
      ...conversation,
      id: 6,
      updated_at: '2026-09-15T01:00:00+00:00'
    }
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/qa/conversations') {
        return {
          success: true,
          conversations: [olderConversation, conversation]
        } as never
      }
      if (path === '/api/agri-skills/qa/conversations/7') {
        return {
          success: true,
          conversation,
          turns: [aiTurn]
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    const store = useAgriQaStore()

    await store.loadConversations()
    await store.openConversation(7)

    expect(store.conversations.map(item => item.id)).toEqual([7, 6])
    expect(store.activeConversationId).toBe(7)
    expect(store.turns).toEqual([aiTurn])
    expect(store.suggestions).toEqual(aiTurn.suggestions)
  })

  it('displays recognition failure without creating a turn', async () => {
    mockedApiFetch.mockRejectedValue(
      new ApiError('未能识别，请重试或改用文字输入', 422)
    )
    const store = useAgriQaStore()

    const text = await store.transcribe(new Blob(['x']), 'question.webm')

    expect(text).toBe('')
    expect(store.error).toBe('未能识别，请重试或改用文字输入')
    expect(store.turns).toHaveLength(0)
  })

  it('maps network-level transcription failures to the recognition message', async () => {
    mockedApiFetch.mockRejectedValue(new TypeError('Failed to fetch'))
    const store = useAgriQaStore()

    const text = await store.transcribe(
      new Blob(['audio'], { type: 'audio/webm' }),
      'question.webm'
    )

    expect(text).toBe('')
    expect(store.error).toBe('未能识别，请重试或改用文字输入')
    expect(store.turns).toHaveLength(0)
  })

  it('returns recognized text from the speech endpoint for editing', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      text: '荔枝蒂蛀虫怎么防'
    } as never)
    const store = useAgriQaStore()

    const text = await store.transcribe(
      new Blob(['audio'], { type: 'audio/webm' }),
      'question.webm'
    )

    expect(text).toBe('荔枝蒂蛀虫怎么防')
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/speech/transcriptions',
      expect.objectContaining({ method: 'POST' })
    )
    expect(store.turns).toHaveLength(0)
  })
})
