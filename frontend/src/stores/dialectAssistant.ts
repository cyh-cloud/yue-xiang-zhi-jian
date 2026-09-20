import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type { LocalDialectCode } from '@/api/types'

const ASR_PATH = '/api/agri-skills/speech/transcriptions'
const TURN_PATH = '/api/local-resources/dialect-assistant/turns'
const ASR_FAILURE = '未能识别，请重说或改用文字'
const AI_UNAVAILABLE = 'AI 服务暂时不可用'

export interface DialectTurn {
  id: string
  dialect_code: LocalDialectCode
  dialect_label: string
  recognized_text: string
  dialect_answer: string
  mandarin_answer: string
  status: 'completed'
  created_at: string
}

interface DialectAssistantState {
  dialectCode: LocalDialectCode
  recognizedText: string
  lastTurn: DialectTurn | null
  audioUrl: string | null
  recording: boolean
  loading: boolean
  error: string
}

function createMultipartBoundary(): string {
  const randomPart =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `----dialect-assistant-${randomPart}`
}

function normalizeAsrError(error: unknown): string {
  if (
    error instanceof ApiError &&
    (error.status === 400 || error.status === 422)
  ) {
    return ASR_FAILURE
  }
  if (
    error instanceof DOMException &&
    ['AbortError', 'NotAllowedError', 'NotFoundError', 'NotReadableError'].includes(
      error.name
    )
  ) {
    return ASR_FAILURE
  }
  return AI_UNAVAILABLE
}

function decodeAudio(
  base64: string,
  contentType: string
): Blob {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return new Blob([bytes.buffer], { type: contentType })
}

export const useDialectAssistantStore = defineStore('dialectAssistant', {
  state: (): DialectAssistantState => ({
    dialectCode: 'yue',
    recognizedText: '',
    lastTurn: null,
    audioUrl: null,
    recording: false,
    loading: false,
    error: ''
  }),
  actions: {
    clearError() {
      this.error = ''
    },
    disposeAudio() {
      if (this.audioUrl) {
        URL.revokeObjectURL(this.audioUrl)
      }
      this.audioUrl = null
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
        }>(ASR_PATH, {
          method: 'POST',
          headers: {
            'Content-Type': `multipart/form-data; boundary=${boundary}`
          },
          body
        })
        const text = response.text.trim()
        if (!text) {
          this.error = ASR_FAILURE
          return ''
        }
        return text
      } catch (error) {
        this.error = normalizeAsrError(error)
        return ''
      } finally {
        this.loading = false
        this.recording = false
      }
    },
    async submitTurn(question: string): Promise<boolean> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<{
          success: true
          turn: DialectTurn
          audio_base64: string
          audio_content_type: string
        }>(TURN_PATH, {
          method: 'POST',
          body: JSON.stringify({
            dialect_code: this.dialectCode,
            question: question.trim()
          })
        })
        const audio = decodeAudio(
          response.audio_base64,
          response.audio_content_type
        )
        if (audio.size === 0) {
          throw new Error('TTS returned empty audio')
        }
        const nextAudioUrl = URL.createObjectURL(audio)
        if (this.audioUrl) {
          URL.revokeObjectURL(this.audioUrl)
        }
        this.audioUrl = nextAudioUrl
        this.lastTurn = response.turn
        return true
      } catch {
        this.error = AI_UNAVAILABLE
        return false
      } finally {
        this.loading = false
      }
    }
  }
})
