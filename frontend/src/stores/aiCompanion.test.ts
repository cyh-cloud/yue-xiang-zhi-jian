import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAiCompanionStore } from './aiCompanion'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

beforeEach(() => {
  setActivePinia(createPinia())
  sessionStorage.clear()
  vi.clearAllMocks()
})

describe('aiCompanion store', () => {
  it('reuses a pending request id when retrying the same question', async () => {
    const apiFetch = vi.mocked(await import('@/api/client')).apiFetch
    apiFetch.mockRejectedValueOnce(new Error('offline'))
    const store = useAiCompanionStore()
    await store.sendQuestion('怎么投简历')
    const firstBody = JSON.parse(apiFetch.mock.calls[0][1]!.body as string)
    await store.sendQuestion('怎么投简历')
    const secondBody = JSON.parse(apiFetch.mock.calls[1][1]!.body as string)
    expect(secondBody.client_request_id).toBe(firstBody.client_request_id)
  })

  it('clears the pending request id after success', async () => {
    const apiFetch = vi.mocked(await import('@/api/client')).apiFetch
    apiFetch.mockResolvedValue({
      success: true,
      conversation_id: 'conversation-1',
      user_message: {
        message_id: 'message-user',
        role: 'user',
        content: '怎么投简历',
        intent: 'platform_usage',
        jump_target: null,
        created_at: '2026-09-20T10:00:00+08:00'
      },
      assistant_message: {
        message_id: 'message-ai',
        role: 'assistant',
        content: '进入就业对接投递。',
        intent: 'platform_usage',
        jump_target: '/student/employment/jobs',
        created_at: '2026-09-20T10:00:01+08:00'
      },
      bullets: [],
      module_key: null,
      jump_target: '/student/employment/jobs'
    })
    const store = useAiCompanionStore()
    await store.sendQuestion('怎么投简历')
    expect(store.pendingRequest).toBeNull()
    expect(store.messages).toHaveLength(2)
    expect(store.draft).toBe('')
    expect(sessionStorage.getItem('ai-companion:draft')).toBeNull()
  })

  it('maps recognition failure and preserves editable text', async () => {
    const { apiFetch, ApiError } = await import('@/api/client')
    vi.mocked(apiFetch).mockRejectedValue(new ApiError('noise', 422))
    const store = useAiCompanionStore()
    store.draft = '保留文字'
    await store.transcribe(new Blob(['x'], { type: 'audio/webm' }), 'question.webm')
    expect(store.error).toBe('未能识别，请重说或改用文字')
    expect(store.draft).toBe('保留文字')
  })

  it('restores and clears draft through sessionStorage', async () => {
    sessionStorage.setItem('ai-companion:draft', '刷新前草稿')
    setActivePinia(createPinia())
    const store = useAiCompanionStore()
    expect(store.draft).toBe('刷新前草稿')
    store.setDraft('更新草稿')
    expect(sessionStorage.getItem('ai-companion:draft')).toBe('更新草稿')
    store.clearDraft()
    expect(sessionStorage.getItem('ai-companion:draft')).toBeNull()
  })
})
