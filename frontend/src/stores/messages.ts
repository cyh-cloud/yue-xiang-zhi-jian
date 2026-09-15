import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type {
  ConversationSummary,
  MessageContact,
  MessagingSummary,
  PrivateMessage,
  SystemNotification
} from '@/api/types'

interface SummaryResponse extends MessagingSummary {
  success: true
}

interface ContactsResponse {
  success: true
  contacts: MessageContact[]
}

interface ConversationsResponse {
  success: true
  conversations: ConversationSummary[]
}

interface ThreadResponse {
  success: true
  conversation: ConversationSummary
  messages: PrivateMessage[]
}

interface SendResponse {
  success: true
  conversation: ConversationSummary
  message: PrivateMessage
}

interface NotificationsResponse {
  success: true
  notifications: SystemNotification[]
}

interface ClearReadResponse {
  success: true
  cleared_private: number
  cleared_notifications: number
  unread_total: number
}

interface MessagingState {
  summary: MessagingSummary
  contacts: MessageContact[]
  conversations: ConversationSummary[]
  activeThreadId: number | null
  messages: PrivateMessage[]
  notifications: SystemNotification[]
  loading: boolean
  error: string
}

function emptySummary(): MessagingSummary {
  return {
    unread_private: 0,
    unread_notifications: 0,
    unread_total: 0
  }
}

function applySummary(
  summary: MessagingSummary,
  response: MessagingSummary
): void {
  summary.unread_private = response.unread_private
  summary.unread_notifications = response.unread_notifications
  summary.unread_total = response.unread_total
}

function upsertConversation(
  conversations: ConversationSummary[],
  conversation: ConversationSummary
): ConversationSummary[] {
  return [
    conversation,
    ...conversations.filter(item => item.id !== conversation.id)
  ]
}

async function fetchOverview() {
  const [summaryResponse, conversationsResponse] = await Promise.all([
    apiFetch<SummaryResponse>('/api/messages/summary'),
    apiFetch<ConversationsResponse>('/api/messages/conversations')
  ])
  return { summaryResponse, conversationsResponse }
}

export const useMessageStore = defineStore('messages', {
  state: (): MessagingState => ({
    summary: emptySummary(),
    contacts: [],
    conversations: [],
    activeThreadId: null,
    messages: [],
    notifications: [],
    loading: false,
    error: ''
  }),
  actions: {
    captureError(error: unknown, fallback: string) {
      if (error instanceof ApiError) {
        this.error = error.message
        return
      }

      this.error = error instanceof Error ? error.message : fallback
    },
    async loadSummary(): Promise<MessagingSummary> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<SummaryResponse>('/api/messages/summary')
        applySummary(this.summary, response)
        return this.summary
      } catch (error) {
        this.captureError(error, '未读消息加载失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async loadContacts(): Promise<MessageContact[]> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<ContactsResponse>('/api/messages/contacts')
        this.contacts = response.contacts
        return this.contacts
      } catch (error) {
        this.captureError(error, '联系人加载失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async loadConversations(): Promise<ConversationSummary[]> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<ConversationsResponse>(
          '/api/messages/conversations'
        )
        this.conversations = response.conversations
        return this.conversations
      } catch (error) {
        this.captureError(error, '会话列表加载失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async loadThread(conversationId: number): Promise<PrivateMessage[]> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<ThreadResponse>(
          `/api/messages/conversations/${conversationId}`
        )
        this.activeThreadId = conversationId
        this.messages = response.messages
        this.conversations = upsertConversation(
          this.conversations,
          response.conversation
        )
        return this.messages
      } catch (error) {
        this.captureError(error, '消息加载失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async sendMessage(recipientId: number, body: string): Promise<void> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<SendResponse>('/api/messages/conversations', {
          method: 'POST',
          body: JSON.stringify({ recipient_id: recipientId, body })
        })
        this.activeThreadId = response.conversation.id
        this.messages = [response.message]
        this.conversations = upsertConversation(
          this.conversations,
          response.conversation
        )

        const { summaryResponse, conversationsResponse } = await fetchOverview()
        applySummary(this.summary, summaryResponse)
        this.conversations = conversationsResponse.conversations
      } catch (error) {
        this.captureError(error, '消息发送失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async reply(conversationId: number, body: string): Promise<void> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<SendResponse>(
          `/api/messages/conversations/${conversationId}/messages`,
          {
            method: 'POST',
            body: JSON.stringify({ body })
          }
        )
        const [{ summaryResponse, conversationsResponse }, threadResponse] =
          await Promise.all([
            fetchOverview(),
            apiFetch<ThreadResponse>(
              `/api/messages/conversations/${conversationId}`
            )
          ])
        applySummary(this.summary, summaryResponse)
        this.conversations = conversationsResponse.conversations
        this.activeThreadId = conversationId
        this.messages = threadResponse.messages
        this.conversations = upsertConversation(
          this.conversations,
          response.conversation
        )
      } catch (error) {
        this.captureError(error, '消息回复失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async loadNotifications(): Promise<SystemNotification[]> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<NotificationsResponse>(
          '/api/messages/notifications'
        )
        this.notifications = response.notifications
        return this.notifications
      } catch (error) {
        this.captureError(error, '通知加载失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async markPrivateRead(messageId: number): Promise<void> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<SummaryResponse>(
          `/api/messages/private/${messageId}/read`,
          { method: 'POST' }
        )
        applySummary(this.summary, response)
        const message = this.messages.find(item => item.id === messageId)
        if (message) {
          message.read = true
          this.conversations = this.conversations.map(conversation => {
            if (
              conversation.id !== message.conversation_id ||
              conversation.unread_count === 0
            ) {
              return conversation
            }
            return {
              ...conversation,
              unread_count: conversation.unread_count - 1
            }
          })
        }
      } catch (error) {
        this.captureError(error, '消息状态更新失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async markNotificationRead(notificationId: number): Promise<void> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<SummaryResponse>(
          `/api/messages/notifications/${notificationId}/read`,
          { method: 'POST' }
        )
        applySummary(this.summary, response)
        const notification = this.notifications.find(
          item => item.id === notificationId
        )
        if (notification) {
          notification.read = true
        }
      } catch (error) {
        this.captureError(error, '通知状态更新失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async markAllRead(): Promise<void> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<SummaryResponse>('/api/messages/read-all', {
          method: 'POST'
        })
        applySummary(this.summary, response)
        this.messages = this.messages.map(message => ({
          ...message,
          read: true
        }))
        this.notifications = this.notifications.map(notification => ({
          ...notification,
          read: true
        }))
        this.conversations = this.conversations.map(conversation => ({
          ...conversation,
          unread_count: 0
        }))
      } catch (error) {
        this.captureError(error, '全部已读操作失败')
        throw error
      } finally {
        this.loading = false
      }
    },
    async clearRead(): Promise<void> {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<ClearReadResponse>(
          '/api/messages/clear-read',
          { method: 'POST' }
        )
        this.messages = this.messages.filter(message => !message.read)
        this.notifications = this.notifications.filter(
          notification => !notification.read
        )
        this.conversations = this.conversations.filter(
          conversation => conversation.unread_count > 0
        )
        this.summary.unread_total = response.unread_total
      } catch (error) {
        this.captureError(error, '清除已读失败')
        throw error
      } finally {
        this.loading = false
      }
    }
  }
})
