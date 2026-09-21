import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { AiCompanionConversation, AiCompanionMessage } from '@/api/types'

import { useAiCompanionStore } from '@/stores/aiCompanion'

import AiCompanionHistory from './AiCompanionHistory.vue'

function conversation(
  conversationId: string,
  title: string,
  updatedAt: string
): AiCompanionConversation {
  return {
    conversation_id: conversationId,
    title,
    last_intent: 'platform_usage',
    jump_target: '/student/employment/jobs',
    created_at: updatedAt,
    updated_at: updatedAt
  }
}

function companionMessage(content: string): AiCompanionMessage {
  return {
    message_id: 'message-1',
    role: 'user',
    content,
    intent: 'platform_usage',
    jump_target: '/student/employment/jobs',
    created_at: '2026-09-20T10:00:00+08:00'
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('AiCompanionHistory', () => {
  it('loads and renders only the current store conversations', async () => {
    const store = useAiCompanionStore()
    store.conversations = [
      conversation('conversation-2', '怎么订阅政策', '2026-09-20T11:00:00+08:00'),
      conversation('conversation-1', '怎么投简历', '2026-09-20T10:00:00+08:00')
    ]
    const wrapper = mount(AiCompanionHistory)
    expect(wrapper.findAll('[data-test="ai-companion-history-item"]')).toHaveLength(2)
    expect(wrapper.text().indexOf('怎么订阅政策')).toBeLessThan(
      wrapper.text().indexOf('怎么投简历')
    )
  })

  it('opens a selected conversation into the chat tab', async () => {
    const store = useAiCompanionStore()
    const openConversation = vi
      .spyOn(store, 'openConversation')
      .mockResolvedValue([])
    // 冻结测试未种子化会话，这里补上最小数据，使第一项即为 conversation-1。
    store.conversations = [
      conversation('conversation-1', '怎么投简历', '2026-09-20T10:00:00+08:00')
    ]
    const wrapper = mount(AiCompanionHistory)
    await wrapper.get('[data-test="ai-companion-history-item"]').trigger('click')
    expect(openConversation).toHaveBeenCalledWith('conversation-1')
  })

  it('shows empty history without an error', () => {
    const wrapper = mount(AiCompanionHistory)
    expect(wrapper.text()).toContain('暂无历史会话')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('renders the loading, error and list states separately', async () => {
    const store = useAiCompanionStore()
    store.loadingHistory = true
    const loading = mount(AiCompanionHistory)
    expect(loading.text()).toContain('正在加载历史会话')
    expect(
      loading.findAll('[data-test="ai-companion-history-item"]')
    ).toHaveLength(0)

    store.loadingHistory = false
    store.historyError = '历史会话加载失败'
    const failed = mount(AiCompanionHistory)
    expect(failed.get('[role="alert"]').text()).toBe('历史会话加载失败')
    expect(failed.text()).not.toContain('暂无历史会话')
  })

  // 历史列表域与对话域的错误互不覆盖：对话失败提示不能顶掉历史列表。
  it('keeps the list when the conversation domain already has an error', () => {
    const store = useAiCompanionStore()
    store.error = 'AI 服务暂时不可用'
    store.conversations = [
      conversation('conversation-1', '怎么投简历', '2026-09-20T10:00:00+08:00')
    ]
    const wrapper = mount(AiCompanionHistory)
    expect(
      wrapper.findAll('[data-test="ai-companion-history-item"]')
    ).toHaveLength(1)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('AI 服务暂时不可用')
  })

  it('returns the panel to the chat tab after reopening a conversation', async () => {
    const store = useAiCompanionStore()
    vi.spyOn(store, 'openConversation').mockResolvedValue([
      companionMessage('怎么投简历')
    ])
    store.activeView = 'history'
    store.conversations = [
      conversation('conversation-1', '怎么投简历', '2026-09-20T10:00:00+08:00')
    ]
    const wrapper = mount(AiCompanionHistory)
    await wrapper.get('[data-test="ai-companion-history-item"]').trigger('click')
    await flushPromises()
    expect(store.activeView).toBe('chat')
  })

  it('stays on the history list when the detail request fails', async () => {
    const store = useAiCompanionStore()
    // 复刻 openConversation 的失败契约：写 error 并原样返回既有消息。
    vi.spyOn(store, 'openConversation').mockImplementation(async () => {
      store.error = '会话读取失败'
      return store.messages
    })
    store.messages = [companionMessage('上一轮问题')]
    store.activeView = 'history'
    store.conversations = [
      conversation('conversation-1', '怎么投简历', '2026-09-20T10:00:00+08:00')
    ]
    const wrapper = mount(AiCompanionHistory)
    await wrapper.get('[data-test="ai-companion-history-item"]').trigger('click')
    await flushPromises()
    expect(store.activeView).toBe('history')
    expect(store.error).toBe('会话读取失败')
    expect(
      wrapper.findAll('[data-test="ai-companion-history-item"]')
    ).toHaveLength(1)
  })

  it('offers no cross-user read, delete or export action', () => {
    const store = useAiCompanionStore()
    store.conversations = [
      conversation('conversation-1', '怎么投简历', '2026-09-20T10:00:00+08:00')
    ]
    const wrapper = mount(AiCompanionHistory)
    expect(wrapper.findAll('button')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('删除')
    expect(wrapper.text()).not.toContain('导出')
    expect(wrapper.text()).not.toContain('其他用户')
  })
})
