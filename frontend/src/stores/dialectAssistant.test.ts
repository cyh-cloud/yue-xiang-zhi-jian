import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'

import { useDialectAssistantStore } from './dialectAssistant'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return { ...actual, apiFetch: vi.fn() }
})

const mockedApiFetch = vi.mocked(apiFetch)

function readBlobAsText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsText(blob)
  })
}

const completedTurn = {
  id: 'dialect-1',
  dialect_code: 'yue',
  dialect_label: '粤语',
  recognized_text: '问题',
  dialect_answer: '方言回答',
  mandarin_answer: '普通话回答',
  status: 'completed',
  created_at: '2026-09-19T10:00:00+08:00'
} as const

describe('dialectAssistant store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
    vi.restoreAllMocks()
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:audio-1'),
      revokeObjectURL: vi.fn()
    })
  })

  it('reuses the exact 003 ASR route and maps its failure copy', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('未能识别，请重试或改用文字输入', 422)
    )
    const store = useDialectAssistantStore()

    const result = await store.transcribe(
      new Blob(['original-audio-bytes'], { type: 'audio/webm' }),
      'question.webm'
    )

    expect(result).toBe('')
    expect(mockedApiFetch.mock.calls[0][0]).toBe(
      '/api/agri-skills/speech/transcriptions'
    )
    const options = mockedApiFetch.mock.calls[0][1]!
    expect(options.headers).toMatchObject({
      'Content-Type': expect.stringContaining(
        'multipart/form-data; boundary='
      )
    })
    const multipart = await readBlobAsText(options.body as Blob)
    expect(multipart).toContain('name="audio"')
    expect(multipart).toContain('filename="question.webm"')
    expect(multipart).toContain('original-audio-bytes')
    expect(multipart).not.toContain('dialect_code')
    expect(store.error).toBe('未能识别，请重说或改用文字')
  })

  it('returns recognized text from the exact ASR route', async () => {
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      text: '  几时种荔枝？  '
    } as never)
    const store = useDialectAssistantStore()

    const result = await store.transcribe(
      new Blob(['audio'], { type: 'audio/webm' }),
      'question.webm'
    )

    expect(result).toBe('几时种荔枝？')
    expect(store.error).toBe('')
    expect(store.loading).toBe(false)
    expect(store.recording).toBe(false)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/speech/transcriptions',
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('maps blank ASR output to the recognition failure copy', async () => {
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      text: '   '
    } as never)
    const store = useDialectAssistantStore()

    const result = await store.transcribe(
      new Blob(['audio'], { type: 'audio/webm' }),
      'question.webm'
    )

    expect(result).toBe('')
    expect(store.error).toBe('未能识别，请重说或改用文字')
  })

  it('maps ASR validation and permission failures to the recognition copy', async () => {
    const store = useDialectAssistantStore()
    const audio = new Blob(['audio'], { type: 'audio/webm' })

    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('音频为空', 400)
    )
    expect(await store.transcribe(audio, 'question.webm')).toBe('')
    expect(store.error).toBe('未能识别，请重说或改用文字')

    mockedApiFetch.mockRejectedValueOnce(
      new DOMException('Permission denied', 'NotAllowedError')
    )
    expect(await store.transcribe(audio, 'question.webm')).toBe('')
    expect(store.error).toBe('未能识别，请重说或改用文字')
  })

  it('maps an upstream ASR failure to the AI-unavailable copy', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('speech upstream unavailable', 503)
    )
    const store = useDialectAssistantStore()

    const result = await store.transcribe(
      new Blob(['audio'], { type: 'audio/webm' }),
      'question.webm'
    )

    expect(result).toBe('')
    expect(store.error).toBe('AI 服务暂时不可用')
  })

  it('maps native transport and other server failures to the AI-unavailable copy', async () => {
    const cases: unknown[] = [
      new TypeError('Failed to fetch'),
      new ApiError('Internal Server Error', 500),
      new ApiError('Bad Gateway', 502)
    ]
    const store = useDialectAssistantStore()
    const audio = new Blob(['audio'], { type: 'audio/webm' })

    for (const error of cases) {
      mockedApiFetch.mockRejectedValueOnce(error)
      expect(await store.transcribe(audio, 'question.webm')).toBe('')
      expect(store.error).toBe('AI 服务暂时不可用')
    }
  })

  it('submits dialect and decodes returned audio without storing it', async () => {
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      turn: completedTurn,
      audio_base64: 'SUQz',
      audio_content_type: 'audio/mpeg'
    } as never)
    const store = useDialectAssistantStore()
    store.dialectCode = 'yue'

    const ok = await store.submitTurn('问题')

    expect(ok).toBe(true)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/local-resources/dialect-assistant/turns',
      {
        method: 'POST',
        body: JSON.stringify({
          dialect_code: 'yue',
          question: '问题'
        })
      }
    )
    expect(store.audioUrl).toBe('blob:audio-1')
    expect(store.lastTurn?.mandarin_answer).toBe('普通话回答')
    const audio = vi.mocked(URL.createObjectURL).mock.calls[0][0]
    if (!(audio instanceof Blob)) {
      throw new Error('Expected createObjectURL to receive a Blob')
    }
    expect(audio.type).toBe('audio/mpeg')
    expect(await readBlobAsText(audio)).toBe('ID3')
    expect(Object.keys(store.$state).sort()).toEqual(
      [
        'audioUrl',
        'dialectCode',
        'error',
        'lastTurn',
        'loading',
        'recognizedText',
        'recording'
      ].sort()
    )
  })

  it('revokes the previous object URL before replacing it', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      turn: completedTurn,
      audio_base64: 'SUQz',
      audio_content_type: 'audio/mpeg'
    } as never)
    const createObjectURL = vi.mocked(URL.createObjectURL)
    createObjectURL
      .mockReturnValueOnce('blob:audio-1')
      .mockReturnValueOnce('blob:audio-2')
    const revokeObjectURL = vi.mocked(URL.revokeObjectURL)
    const store = useDialectAssistantStore()
    store.dialectCode = 'yue'
    let urlAtRevoke: string | null = null
    revokeObjectURL.mockImplementation(() => {
      urlAtRevoke = store.audioUrl
    })

    await store.submitTurn('第一个问题')
    await store.submitTurn('第二个问题')

    expect(revokeObjectURL).toHaveBeenCalledWith('blob:audio-1')
    expect(store.audioUrl).toBe('blob:audio-2')
    expect(urlAtRevoke).toBe('blob:audio-1')
  })

  it('disposes playback without creating another turn', async () => {
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      turn: completedTurn,
      audio_base64: 'SUQz',
      audio_content_type: 'audio/mpeg'
    } as never)
    const store = useDialectAssistantStore()
    store.dialectCode = 'yue'

    await store.submitTurn('问题')
    store.disposeAudio()

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:audio-1')
    expect(store.audioUrl).toBeNull()
    expect(mockedApiFetch).toHaveBeenCalledTimes(1)
  })

  it('uses the exact unavailable copy for answer or TTS failure', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('AI 服务暂时不可用', 503)
    )
    const store = useDialectAssistantStore()
    store.dialectCode = 'nan'
    store.recognizedText = '问题'

    const ok = await store.submitTurn('问题')

    expect(ok).toBe(false)
    expect(store.error).toBe('AI 服务暂时不可用')
    expect(store.lastTurn).toBeNull()
    expect(store.recognizedText).toBe('问题')
  })

  it('maps malformed or empty returned audio to the unavailable copy', async () => {
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      turn: completedTurn,
      audio_base64: '',
      audio_content_type: 'audio/mpeg'
    } as never)
    const store = useDialectAssistantStore()
    store.dialectCode = 'yue'

    const ok = await store.submitTurn('问题')

    expect(ok).toBe(false)
    expect(store.error).toBe('AI 服务暂时不可用')
    expect(store.lastTurn).toBeNull()
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })

  it('clears only the visible error', () => {
    const store = useDialectAssistantStore()
    store.error = '未能识别，请重说或改用文字'
    store.recognizedText = '保留文本'

    store.clearError()

    expect(store.error).toBe('')
    expect(store.recognizedText).toBe('保留文本')
  })
})
