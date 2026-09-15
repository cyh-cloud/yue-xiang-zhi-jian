import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type {
  ConversationSummary,
  MessageContact,
  PrivateMessage,
  SystemNotification
} from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { useMessageStore } from '@/stores/messages'

import MessageCenterView from './MessageCenterView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const teacherContact: MessageContact = {
  id: 9,
  name: '陈老师',
  role: 'teacher',
  relationship: 'teacher_student'
}

const notificationFixture: SystemNotification = {
  id: 7,
  event_type: 'application_status',
  title: '申请状态更新',
  body: '你的岗位申请已进入面试阶段。',
  source_type: 'application',
  source_id: '12',
  source_available: true,
  created_at: '2026-09-15T08:00:00+00:00',
  read: false
}

function message(overrides: Partial<PrivateMessage> = {}): PrivateMessage {
  return {
    id: 7,
    conversation_id: 3,
    sender_id: 9,
    body: '请准备课程材料',
    created_at: '2026-09-15T08:00:00+00:00',
    read: false,
    ...overrides
  }
}

function conversation(lastMessage: PrivateMessage | null): ConversationSummary {
  return {
    id: 3,
    participant: teacherContact,
    last_message: lastMessage,
    unread_count: lastMessage?.read ? 0 : 1,
    updated_at: '2026-09-15T08:00:00+00:00'
  }
}

async function mountView(
  role: 'student' | 'teacher' | 'admin' | 'government' = 'student',
  setup?: (store: ReturnType<typeof useMessageStore>) => void
) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const auth = useAuthStore()
  auth.sessionState = 'active'
  auth.user = {
    id: 1,
    username: `${role}01`,
    name: '测试用户',
    role
  }

  const store = useMessageStore()
  setup?.(store)
  vi.spyOn(store, 'loadSummary').mockResolvedValue(store.summary)
  vi.spyOn(store, 'loadContacts').mockResolvedValue(store.contacts)
  vi.spyOn(store, 'loadConversations').mockResolvedValue(store.conversations)
  vi.spyOn(store, 'loadNotifications').mockResolvedValue(store.notifications)
  vi.spyOn(store, 'loadThread').mockResolvedValue(store.messages)

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/login', component: { template: '<div />' } },
      { path: '/messages', component: { template: '<div />' } }
    ]
  })
  await router.push('/messages')
  await router.isReady()

  const wrapper = mount(MessageCenterView, {
    global: { plugins: [pinia, router] }
  })
  await flushPromises()

  return { wrapper, store }
}

describe('MessageCenterView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders one empty state when there is no visible content', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.findAll('[data-test="empty-state"]')).toHaveLength(1)
    expect(wrapper.get('[data-test="empty-state"]').text()).toContain(
      '暂无消息'
    )
  })

  it('marks a system notification read when opened', async () => {
    const { wrapper, store } = await mountView('student', currentStore => {
      currentStore.notifications = [notificationFixture]
    })
    const markRead = vi
      .spyOn(store, 'markNotificationRead')
      .mockResolvedValue()

    await wrapper.get('[data-test="notification-7"]').trigger('click')

    expect(markRead).toHaveBeenCalledWith(7)
  })

  it('shows every unread summary total', async () => {
    const { wrapper } = await mountView('student', currentStore => {
      currentStore.summary = {
        unread_private: 2,
        unread_notifications: 3,
        unread_total: 5
      }
    })

    expect(wrapper.get('[data-test="summary-private"]').text()).toContain('2')
    expect(wrapper.get('[data-test="summary-notifications"]').text()).toContain(
      '3'
    )
    expect(wrapper.get('[data-test="summary-total"]').text()).toContain('5')
  })

  it('creates a first conversation with a valid contact', async () => {
    const { wrapper, store } = await mountView('student', currentStore => {
      currentStore.contacts = [teacherContact]
    })
    const sendMessage = vi.spyOn(store, 'sendMessage').mockResolvedValue()

    await wrapper.get('[data-test="contact-select"]').setValue('9')
    await wrapper.get('[data-test="message-input"]').setValue('您好，陈老师')
    await wrapper.get('[data-test="send-message"]').trigger('click')

    expect(sendMessage).toHaveBeenCalledWith(9, '您好，陈老师')
  })

  it('does not invent prohibited contacts', async () => {
    const { wrapper } = await mountView('student', currentStore => {
      currentStore.contacts = [teacherContact]
    })

    expect(wrapper.get('[data-test="contact-select"]').text()).toContain(
      '陈老师'
    )
    expect(wrapper.get('[data-test="contact-select"]').text()).not.toContain(
      '无关企业'
    )
  })

  it('marks an opened private message read and sends a reply', async () => {
    const privateMessage = message()
    const { wrapper, store } = await mountView('student', currentStore => {
      currentStore.conversations = [conversation(privateMessage)]
      currentStore.activeThreadId = 3
      currentStore.messages = [privateMessage]
    })
    const markRead = vi.spyOn(store, 'markPrivateRead').mockResolvedValue()
    const reply = vi.spyOn(store, 'reply').mockResolvedValue()

    await wrapper.get('[data-test="message-7"]').trigger('click')
    await wrapper.get('[data-test="reply-input"]').setValue('收到')
    await wrapper.get('[data-test="reply-submit"]').trigger('click')

    expect(markRead).toHaveBeenCalledWith(7)
    expect(reply).toHaveBeenCalledWith(3, '收到')
  })

  it.each(['admin', 'government'] as const)(
    'shows the private-message restriction for %s without a composer',
    async role => {
      const { wrapper } = await mountView(role)

      expect(wrapper.text()).toContain('当前角色不支持私信')
      expect(wrapper.find('[data-test="message-input"]').exists()).toBe(false)
      expect(wrapper.find('[data-test="reply-input"]').exists()).toBe(false)
    }
  )

  it('invokes mark-all-read and clear-read actions', async () => {
    const { wrapper, store } = await mountView()
    const markAllRead = vi.spyOn(store, 'markAllRead').mockResolvedValue()
    const clearRead = vi.spyOn(store, 'clearRead').mockResolvedValue()

    await wrapper.get('[data-test="mark-all-read"]').trigger('click')
    await wrapper.get('[data-test="clear-read"]').trigger('click')

    expect(markAllRead).toHaveBeenCalledOnce()
    expect(clearRead).toHaveBeenCalledOnce()
  })

  it('keeps unread private messages after clearing read items', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      cleared_private: 1,
      cleared_notifications: 0,
      unread_total: 1
    } as never)
    const unread = message({ id: 7, body: '未读消息', read: false })
    const read = message({ id: 8, body: '已读消息', read: true })
    const { wrapper } = await mountView('student', currentStore => {
      currentStore.conversations = [conversation(unread)]
      currentStore.activeThreadId = 3
      currentStore.messages = [unread, read]
      currentStore.summary = {
        unread_private: 1,
        unread_notifications: 0,
        unread_total: 1
      }
    })

    await wrapper.get('[data-test="clear-read"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('未读消息')
    expect(wrapper.text()).not.toContain('已读消息')
  })
})
