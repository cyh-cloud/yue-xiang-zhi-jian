import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type {
  AiCompanionAnswerResponse,
  AiCompanionConversation,
  AiCompanionMessage,
  LocalDialectCode
} from '@/api/types'

const MESSAGES_PATH = '/api/ai-companion/messages'
const CONVERSATIONS_PATH = '/api/ai-companion/conversations'
const TRANSCRIPTIONS_PATH = '/api/ai-companion/speech/transcriptions'
const DRAFT_STORAGE_KEY = 'ai-companion:draft'
const MAX_QUESTION_LENGTH = 2000
const EMPTY_QUESTION_MESSAGE = '问题不能为空'
const QUESTION_TOO_LONG_MESSAGE = '问题过长，请缩短后重试'
const RECOGNITION_FAILURE_MESSAGE = '未能识别，请重说或改用文字'
const AI_UNAVAILABLE_MESSAGE = 'AI 服务暂时不可用'

interface PendingRequest {
  question: string
  clientRequestId: string
  conversationId: string | null
}

interface AiCompanionState {
  panelOpen: boolean
  activeView: 'chat' | 'history'
  conversationId: string | null
  messages: AiCompanionMessage[]
  conversations: AiCompanionConversation[]
  draft: string
  dialectCode: LocalDialectCode | null
  recording: boolean
  recognizedText: string
  loading: boolean
  loadingHistory: boolean
  error: string
  pendingRequest: PendingRequest | null
}

interface ConversationsResponse {
  success: true
  conversations: AiCompanionConversation[]
}

interface ConversationDetailResponse {
  success: true
  // 后端把 messages 嵌在 conversation 记录内，store 归一后按 DTO 语义写入 state。
  conversation: AiCompanionConversation & { messages: AiCompanionMessage[] }
}

interface TranscriptionResponse {
  success: true
  text: string
}

function readStoredDraft(): string {
  try {
    if (typeof sessionStorage === 'undefined') {
      return ''
    }
    return sessionStorage.getItem(DRAFT_STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

function writeStoredDraft(value: string): void {
  try {
    if (typeof sessionStorage === 'undefined') {
      return
    }
    sessionStorage.setItem(DRAFT_STORAGE_KEY, value)
  } catch {
    // 存储不可用时草稿只留在内存，不打断输入。
  }
}

function removeStoredDraft(): void {
  try {
    if (typeof sessionStorage === 'undefined') {
      return
    }
    sessionStorage.removeItem(DRAFT_STORAGE_KEY)
  } catch {
    // 同上：清理失败不影响内存状态。
  }
}

function createClientRequestId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function createMultipartBoundary(): string {
  return `----ai-companion-${createClientRequestId()}`
}

function resolveRequestError(error: unknown): string {
  if (error instanceof ApiError && error.status !== 503) {
    return error.message
  }
  return AI_UNAVAILABLE_MESSAGE
}

function resolveTranscriptionError(error: unknown): string {
  if (error instanceof ApiError && error.status === 422) {
    return RECOGNITION_FAILURE_MESSAGE
  }
  return resolveRequestError(error)
}

export const useAiCompanionStore = defineStore('aiCompanion', {
  state: (): AiCompanionState => ({
    panelOpen: false,
    activeView: 'chat',
    conversationId: null,
    messages: [],
    conversations: [],
    draft: readStoredDraft(),
    dialectCode: null,
    recording: false,
    recognizedText: '',
    loading: false,
    loadingHistory: false,
    error: '',
    pendingRequest: null
  }),
  actions: {
    open() {
      this.panelOpen = true
    },
    close() {
      this.panelOpen = false
    },
    setDraft(value: string) {
      this.draft = value
      writeStoredDraft(value)
    },
    clearDraft() {
      this.draft = ''
      this.recognizedText = ''
      removeStoredDraft()
    },
    async sendQuestion(question: string): Promise<boolean> {
      const normalizedQuestion = question.trim()
      if (!normalizedQuestion) {
        this.error = EMPTY_QUESTION_MESSAGE
        return false
      }
      if (normalizedQuestion.length > MAX_QUESTION_LENGTH) {
        this.error = QUESTION_TOO_LONG_MESSAGE
        return false
      }

      // 重试同一问题时沿用同一请求标识，服务端据此幂等重放而不是重复生成。
      const pending = this.pendingRequest
      const clientRequestId =
        pending !== null &&
        pending.question === normalizedQuestion &&
        pending.conversationId === this.conversationId
          ? pending.clientRequestId
          : createClientRequestId()
      this.pendingRequest = {
        question: normalizedQuestion,
        clientRequestId,
        conversationId: this.conversationId
      }
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<AiCompanionAnswerResponse>(MESSAGES_PATH, {
          method: 'POST',
          body: JSON.stringify({
            question: normalizedQuestion,
            client_request_id: clientRequestId,
            conversation_id: this.conversationId
          })
        })
        this.conversationId = response.conversation_id
        this.messages.push(response.user_message, response.assistant_message)
        this.draft = ''
        removeStoredDraft()
        this.pendingRequest = null
        return true
      } catch (error) {
        this.error = resolveRequestError(error)
        return false
      } finally {
        this.loading = false
      }
    },
    async loadConversations(): Promise<AiCompanionConversation[]> {
      this.loadingHistory = true
      this.error = ''

      try {
        const response = await apiFetch<ConversationsResponse>(CONVERSATIONS_PATH)
        this.conversations = response.conversations
        return this.conversations
      } catch (error) {
        this.error = resolveRequestError(error)
        return this.conversations
      } finally {
        this.loadingHistory = false
      }
    },
    async openConversation(conversationId: string): Promise<AiCompanionMessage[]> {
      this.loadingHistory = true
      this.error = ''

      try {
        const response = await apiFetch<ConversationDetailResponse>(
          `${CONVERSATIONS_PATH}/${encodeURIComponent(conversationId)}`
        )
        const { messages, ...conversation } = response.conversation
        this.conversationId = conversation.conversation_id
        this.messages = messages
        this.activeView = 'chat'
        return this.messages
      } catch (error) {
        this.error = resolveRequestError(error)
        return this.messages
      } finally {
        this.loadingHistory = false
      }
    },
    async transcribe(audio: Blob, filename: string): Promise<string> {
      this.loading = true
      this.error = ''
      this.recording = false

      try {
        const boundary = createMultipartBoundary()
        const safeFilename =
          filename.replace(/[\r\n"]/g, '').trim() || 'question.webm'
        const contentType = audio.type || 'application/octet-stream'
        const body = new Blob([
          `--${boundary}\r\n`,
          `Content-Disposition: form-data; name="audio"; filename="${safeFilename}"\r\n`,
          `Content-Type: ${contentType}\r\n\r\n`,
          audio,
          `\r\n--${boundary}--\r\n`
        ])
        const response = await apiFetch<TranscriptionResponse>(
          TRANSCRIPTIONS_PATH,
          {
            method: 'POST',
            headers: {
              'Content-Type': `multipart/form-data; boundary=${boundary}`
            },
            body
          }
        )
        const text = response.text.trim()
        if (!text) {
          this.error = RECOGNITION_FAILURE_MESSAGE
          return ''
        }
        this.recognizedText = text
        return text
      } catch (error) {
        this.error = resolveTranscriptionError(error)
        return ''
      } finally {
        this.loading = false
        this.recording = false
      }
    }
  }
})
