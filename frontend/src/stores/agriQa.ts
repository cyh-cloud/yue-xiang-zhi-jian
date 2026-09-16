import { defineStore } from 'pinia'

import { ApiError, apiFetch, apiStream } from '@/api/client'
import type { QaConversation, QaTurn } from '@/api/types'

type InputMode = 'text' | 'voice'
type AnswerMode = 'ai' | 'local_kb'

interface QaStreamPayload {
  content?: string
  turn?: QaTurn
  message?: string
  suggestion_error?: string | null
}

interface AgriQaState {
  conversations: QaConversation[]
  activeConversationId: number | null
  turns: QaTurn[]
  streamingText: string
  suggestions: string[]
  suggestionError: string
  answerMode: AnswerMode
  loading: boolean
  recording: boolean
  error: string
}

function compareConversations(
  left: QaConversation,
  right: QaConversation
): number {
  const timeDifference =
    Date.parse(right.updated_at) - Date.parse(left.updated_at)
  return Number.isNaN(timeDifference)
    ? right.id - left.id
    : timeDifference || right.id - left.id
}

function createMultipartBoundary(): string {
  const randomPart =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `----agri-qa-${randomPart}`
}

export const useAgriQaStore = defineStore('agriQa', {
  state: (): AgriQaState => ({
    conversations: [],
    activeConversationId: null,
    turns: [],
    streamingText: '',
    suggestions: [],
    suggestionError: '',
    answerMode: 'ai',
    loading: false,
    recording: false,
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
    applyTurn(turn: QaTurn, suggestionError = '') {
      this.turns.push(turn)
      this.streamingText = ''
      this.answerMode = turn.answer_mode
      this.suggestions = turn.suggestions
      this.suggestionError = suggestionError

      const conversation = this.conversations.find(
        item => item.id === this.activeConversationId
      )
      if (conversation) {
        const updated = { ...conversation, updated_at: turn.created_at }
        this.conversations = [
          updated,
          ...this.conversations.filter(item => item.id !== conversation.id)
        ].sort(compareConversations)
      }
    },
    async loadConversations() {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          conversations: QaConversation[]
        }>('/api/agri-skills/qa/conversations')
        this.conversations = [...response.conversations].sort(
          compareConversations
        )
      } catch (error) {
        this.captureError(error, '问答记录加载失败')
      } finally {
        this.loading = false
      }
    },
    async openConversation(id: number) {
      this.loading = true
      this.error = ''
      this.streamingText = ''
      this.suggestions = []
      this.suggestionError = ''

      try {
        const response = await apiFetch<{
          success: true
          conversation: QaConversation
          turns: QaTurn[]
        }>(`/api/agri-skills/qa/conversations/${id}`)
        const orderedTurns = [...response.turns].sort(
          (left, right) =>
            Date.parse(left.created_at) - Date.parse(right.created_at) ||
            left.id - right.id
        )
        const latestTurn = orderedTurns[orderedTurns.length - 1]

        this.activeConversationId = response.conversation.id
        this.turns = orderedTurns
        this.answerMode = latestTurn?.answer_mode ?? 'ai'
        this.suggestions =
          latestTurn?.answer_mode === 'ai' ? latestTurn.suggestions : []
        this.conversations = [
          response.conversation,
          ...this.conversations.filter(
            item => item.id !== response.conversation.id
          )
        ].sort(compareConversations)
      } catch (error) {
        this.captureError(error, '问答记录打开失败')
      } finally {
        this.loading = false
      }
    },
    async ask(question: string, inputMode: InputMode): Promise<boolean> {
      const normalizedQuestion = question.trim()
      if (!normalizedQuestion) {
        this.error = '问题不能为空'
        return false
      }

      this.loading = true
      this.error = ''
      this.streamingText = ''
      this.suggestions = []
      this.suggestionError = ''
      this.answerMode = 'ai'

      let conversationId = this.activeConversationId
      let receivedChunk = false
      let settled = false
      let streamErrorMessage = ''

      try {
        if (conversationId === null) {
          const created = await apiFetch<{
            success: true
            conversation: QaConversation
          }>('/api/agri-skills/qa/conversations', {
            method: 'POST',
            body: JSON.stringify({
              question: normalizedQuestion,
              input_mode: inputMode
            })
          })
          conversationId = created.conversation.id
          this.activeConversationId = conversationId
          this.conversations = [
            created.conversation,
            ...this.conversations.filter(
              item => item.id !== created.conversation.id
            )
          ].sort(compareConversations)
        }

        const requestBody = JSON.stringify({
          question: normalizedQuestion,
          input_mode: inputMode
        })
        await apiStream<QaStreamPayload>(
          `/api/agri-skills/qa/conversations/${conversationId}/messages/stream`,
          {
            method: 'POST',
            body: requestBody
          },
          event => {
            if (event.event === 'chunk') {
              receivedChunk = true
              this.streamingText += event.data.content ?? ''
            } else if (event.event === 'complete' && event.data.turn) {
              settled = true
              this.applyTurn(
                event.data.turn,
                event.data.suggestion_error ?? ''
              )
            } else if (event.event === 'replace' && event.data.turn) {
              settled = true
              this.applyTurn(event.data.turn)
            } else if (event.event === 'error') {
              streamErrorMessage =
                event.data.message ?? '暂无法回答，建议稍后再试'
            }
          }
        )

        if (streamErrorMessage) {
          this.streamingText = ''
          this.error = streamErrorMessage
          return false
        }

        if (!settled) {
          this.streamingText = ''
          this.error = '暂无法回答，建议稍后再试'
          return false
        }

        return true
      } catch (error) {
        if (streamErrorMessage) {
          this.streamingText = ''
          this.error = streamErrorMessage
          return false
        }

        if (settled) {
          return true
        }

        if (receivedChunk && !settled && this.answerMode === 'ai') {
          try {
            const fallback = await apiFetch<{
              success: true
              turn: QaTurn
            }>(
              `/api/agri-skills/qa/conversations/${conversationId}/messages`,
              {
                method: 'POST',
                body: JSON.stringify({
                  question: normalizedQuestion,
                  input_mode: inputMode
                })
              }
            )
            this.applyTurn(fallback.turn)
            return true
          } catch (fallbackError) {
            this.streamingText = ''
            this.captureError(fallbackError, '问答请求失败')
            return false
          }
        }

        this.streamingText = ''
        this.captureError(error, '问答请求失败')
        return false
      } finally {
        this.loading = false
      }
    },
    async transcribe(blob: Blob, filename: string): Promise<string> {
      this.loading = true
      this.error = ''
      this.recording = false

      try {
        const boundary = createMultipartBoundary()
        const safeFilename =
          filename.replace(/[\r\n"]/g, '').trim() || 'question.webm'
        const contentType = blob.type || 'application/octet-stream'
        const body = new Blob([
          `--${boundary}\r\n`,
          `Content-Disposition: form-data; name="audio"; filename="${safeFilename}"\r\n`,
          `Content-Type: ${contentType}\r\n\r\n`,
          blob,
          `\r\n--${boundary}--\r\n`
        ])
        const response = await apiFetch<{
          success: true
          text: string
        }>('/api/agri-skills/speech/transcriptions', {
          method: 'POST',
          headers: {
            'Content-Type': `multipart/form-data; boundary=${boundary}`
          },
          body
        })
        const text = response.text.trim()
        if (!text) {
          this.error = '未能识别，请重试或改用文字输入'
          return ''
        }
        return text
      } catch (error) {
        this.captureError(error, '未能识别，请重试或改用文字输入')
        return ''
      } finally {
        this.loading = false
      }
    },
    useSuggestion(text: string): Promise<boolean> {
      return this.ask(text, 'text')
    }
  }
})
