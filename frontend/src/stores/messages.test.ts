import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'
import type {
  ConversationSummary,
  MessageContact,
  PrivateMessage
} from '@/api/types'

import { useMessageStore } from './messages'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const participant: MessageContact = {
  id: 9,
  name: '陈老师',
  role: 'teacher',
  relationship: 'teacher_student'
}

function message(overrides: Partial<PrivateMessage> = {}): PrivateMessage {
  return {
    id: 7,
    conversation_id: 3,
    sender_id: 9,
    body: '测试消息',
    created_at: '2026-09-15T00:00:00+00:00',
    read: false,
    ...overrides
  }
}

function conversation(
  lastMessage: PrivateMessage | null,
  unreadCount: number
): ConversationSummary {
  return {
    id: 3,
    participant,
    last_message: lastMessage,
    unread_count: unreadCount,
    updated_at: '2026-09-15T00:00:00+00:00'
  }
}

describe('useMessageStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('updates the global badge after reading one item', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        unread_private: 2,
        unread_notifications: 1,
        unread_total: 3
      })
      .mockResolvedValueOnce({
        success: true,
        unread_private: 1,
        unread_notifications: 1,
        unread_total: 2
      })
      .mockResolvedValueOnce({
        success: true,
        conversations: []
      })

    const store = useMessageStore()
    await store.loadSummary()
    await store.markPrivateRead(7)

    expect(store.summary.unread_total).toBe(2)
  })

  it('accepts a conversation with no visible last message', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      conversations: [conversation(null, 0)]
    } as never)
    const store = useMessageStore()

    await store.loadConversations()

    expect(store.conversations[0].last_message).toBeNull()
  })

  it('ignores a stale thread response when a newer thread has loaded', async () => {
    let releaseFirst = () => {}
    const firstResponse = new Promise(resolve => {
      releaseFirst = () =>
        resolve({
          success: true,
          conversation: conversation(message(), 1),
          messages: [message()]
        })
    })
    const secondMessage = message({
      id: 8,
      conversation_id: 4,
      body: '最新会话消息'
    })

    mockedApiFetch
      .mockImplementationOnce(() => firstResponse)
      .mockImplementationOnce(() =>
        Promise.resolve({
          success: true,
          conversation: {
            ...conversation(secondMessage, 1),
            id: 4,
            unread_count: 1
          },
          messages: [secondMessage]
        })
      )

    const store = useMessageStore()
    const firstLoad = store.loadThread(3)
    const secondLoad = store.loadThread(4)

    await secondLoad
    releaseFirst()
    await firstLoad

    expect(store.activeThreadId).toBe(4)
    expect(store.messages).toEqual([secondMessage])
    expect(store.conversations.map(item => item.id)).toEqual([4])
  })

  it('refreshes conversation state after reading an unloaded message', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        unread_private: 0,
        unread_notifications: 0,
        unread_total: 0
      })
      .mockResolvedValueOnce({
        success: true,
        conversations: [conversation(message({ read: true }), 0)]
      })
    const store = useMessageStore()
    store.conversations = [conversation(message(), 1)]
    store.messages = []

    await store.markPrivateRead(7)

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/messages/conversations'
    )
    expect(store.conversations[0].last_message?.read).toBe(true)
    expect(store.conversations[0].unread_count).toBe(0)
  })

  it('refreshes conversation state after marking all messages read', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        unread_private: 0,
        unread_notifications: 0,
        unread_total: 0
      })
      .mockResolvedValueOnce({
        success: true,
        conversations: [conversation(message({ read: true }), 0)]
      })
    const store = useMessageStore()
    store.conversations = [conversation(message(), 1)]

    await store.markAllRead()

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/messages/conversations'
    )
    expect(store.conversations[0].last_message?.read).toBe(true)
    expect(store.conversations[0].unread_count).toBe(0)
  })
})
