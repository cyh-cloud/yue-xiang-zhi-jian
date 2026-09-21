import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type {
  AiCompanionConversation,
  AiCompanionIntent,
  AiCompanionMessage,
  UserRole
} from '@/api/types'

import { useAuthStore } from '@/stores/auth'
import { useAiCompanionStore } from '@/stores/aiCompanion'

import AiCompanionPanel from './AiCompanionPanel.vue'
// 样式源码单独引入，用于校验 jsdom 无法计算的 CSS 兜底声明。
import panelSource from './AiCompanionPanel.vue?raw'
import VoiceInputButton from './VoiceInputButton.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const CONVERSATIONS_PATH = '/api/ai-companion/conversations'

const ROUTES = [
  { path: '/', component: { template: '<div />' } },
  {
    path: '/student/employment/jobs',
    component: { template: '<div />' },
    meta: { roles: ['student'] }
  },
  {
    path: '/student/agri-skills/qa',
    component: { template: '<div />' },
    meta: { roles: ['student'] }
  }
]

let pinia: Pinia

let messageSeq = 0

function message(
  role: 'user' | 'assistant',
  content: string,
  intent: AiCompanionIntent,
  jumpTarget: string | null
): AiCompanionMessage {
  messageSeq += 1
  return {
    message_id: `message-${messageSeq}`,
    role,
    content,
    intent,
    jump_target: jumpTarget,
    created_at: '2026-09-20T10:00:00+08:00'
  }
}

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

interface MountPanelOptions {
  role?: UserRole
  messages?: AiCompanionMessage[]
  attach?: boolean
  slots?: Record<string, string>
}

// 所有面板测试共用的挂载脚手架：pinia、登录态、路由与 store 种子只在这里写一次。
function mountPanel(options: MountPanelOptions = {}) {
  const role = options.role ?? 'student'
  const auth = useAuthStore()
  auth.sessionState = 'active'
  auth.user = { id: 1, username: role, name: role, role }
  const store = useAiCompanionStore()
  // 面板只在打开时挂载，这里复现该条件以触发一次历史加载。
  store.panelOpen = true
  if (options.messages) {
    store.messages = options.messages
  }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ROUTES
  })
  const wrapper = mount(AiCompanionPanel, {
    attachTo: options.attach ? document.body : undefined,
    global: { plugins: [pinia, router] },
    slots: options.slots
  })
  return { wrapper, store }
}

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
  sessionStorage.clear()
  vi.clearAllMocks()
  mockedApiFetch.mockResolvedValue({
    success: true,
    conversations: [],
    text: '荔枝什么时候套袋'
  } as never)
})

// 断言焦点归还的用例会把面板挂到 document.body，这里统一清理，避免残留节点
// 影响后续用例的 activeElement 判断。
afterEach(() => {
  document.body.innerHTML = ''
})

describe('AiCompanionPanel', () => {
  it('renders the three intent branches distinctly', () => {
    const { wrapper } = mountPanel({
      messages: [
        message(
          'assistant',
          '进入就业对接后选择岗位投递。',
          'platform_usage',
          '/student/employment/jobs'
        ),
        message(
          'assistant',
          '- 先确认品种\n- 进入农业技能继续追问',
          'learning_question',
          '/student/agri-skills/qa'
        ),
        message('assistant', 'AI 学伴不代办业务操作。', 'out_of_scope', null)
      ]
    })
    expect(wrapper.findAll('[data-intent="platform_usage"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-intent="learning_question"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-intent="out_of_scope"]')).toHaveLength(1)
  })

  it('shows a jump button only for an allowed resolved target', () => {
    const { wrapper } = mountPanel({
      role: 'student',
      messages: [
        message(
        'assistant',
        '进入就业对接。',
        'platform_usage',
        '/student/employment/jobs'
        )
      ]
    })
    expect(wrapper.get('[data-test="ai-companion-jump"]').text()).toContain(
      '去查看'
    )
  })

  it('does not submit until recognized text is confirmed', async () => {
    const { wrapper, store } = mountPanel()
    const send = vi.spyOn(store, 'sendQuestion')
    wrapper.findComponent(VoiceInputButton).vm.$emit(
      'recorded',
      new Blob(['audio'], { type: 'audio/webm' }),
      'question.webm'
    )
    await flushPromises()
    expect(send).not.toHaveBeenCalled()
    expect(wrapper.get('textarea').element.value).toBe('荔枝什么时候套袋')
  })

  it('requires an explicit dialect selection before recording', async () => {
    const { wrapper } = mountPanel()
    expect(wrapper.get('[data-test="ai-companion-voice"]').attributes('disabled'))
      .toBeDefined()
    expect(wrapper.findComponent(VoiceInputButton).props('disabled')).toBe(true)
    await wrapper.get('[data-test="ai-companion-dialect-yue"]').trigger('click')
    expect(wrapper.get('[data-test="ai-companion-voice"]').attributes('disabled'))
      .toBeUndefined()
    expect(wrapper.findComponent(VoiceInputButton).props('disabled')).toBe(
      false
    )
  })

  it('maps microphone denial to retry-or-type copy', async () => {
    const { wrapper } = mountPanel()
    wrapper.findComponent(VoiceInputButton).vm.$emit('permission-denied')
    await flushPromises()
    expect(wrapper.text()).toContain('未能识别，请重说或改用文字')
    expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
  })

  it('maps cancelled or zero-byte recording to retry-or-type copy', async () => {
    const { wrapper } = mountPanel()
    await wrapper.get('[data-test="ai-companion-dialect-yue"]').trigger('click')
    wrapper.findComponent(VoiceInputButton).vm.$emit(
      'recorded',
      new Blob([], { type: 'audio/webm' }),
      'question.webm'
    )
    await flushPromises()
    expect(apiFetch).not.toHaveBeenCalledWith(
      '/api/ai-companion/speech/transcriptions',
      expect.anything()
    )
    expect(wrapper.text()).toContain('未能识别，请重说或改用文字')
  })

  it('shows the two AI failure messages as distinct copy', async () => {
    const { wrapper, store } = mountPanel()
    store.error = 'AI 服务暂时不可用'
    await flushPromises()
    expect(wrapper.get('[data-test="ai-companion-error"]').text()).toBe(
      'AI 服务暂时不可用'
    )
    store.error = '暂无法回答，请稍后再试'
    await flushPromises()
    expect(wrapper.get('[data-test="ai-companion-error"]').text()).toBe(
      '暂无法回答，请稍后再试'
    )
  })

  it('keeps the microphone usable after a permission denial emit', async () => {
    const { wrapper } = mountPanel()
    expect(wrapper.findComponent(VoiceInputButton).props('disabled')).toBe(true)
    wrapper.findComponent(VoiceInputButton).vm.$emit('permission-denied')
    await flushPromises()
    expect(wrapper.text()).toContain('未能识别，请重说或改用文字')
    expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
    expect(
      wrapper.get('[data-test="ai-companion-voice"]').attributes('disabled')
    ).toBeDefined()
    expect(wrapper.findComponent(VoiceInputButton).props('disabled')).toBe(true)
  })

  it('submits the confirmed draft and blocks a blank one', async () => {
    const { wrapper, store } = mountPanel()
    const send = vi.spyOn(store, 'sendQuestion').mockResolvedValue(true)
    expect(
      wrapper.get('[data-test="ai-companion-submit"]').attributes('disabled')
    ).toBeDefined()

    await wrapper.get('[data-test="ai-companion-dialect-yue"]').trigger('click')
    wrapper.findComponent(VoiceInputButton).vm.$emit(
      'recorded',
      new Blob(['audio'], { type: 'audio/webm' }),
      'question.webm'
    )
    await flushPromises()
    await wrapper.get('form').trigger('submit')
    expect(send).toHaveBeenCalledWith('荔枝什么时候套袋')
  })

  it('caps the question length at 2000 characters', () => {
    const { wrapper } = mountPanel()
    expect(wrapper.get('textarea').attributes('maxlength')).toBe('2000')
  })

  it('reads and writes the active tab through the store', async () => {
    const { wrapper, store } = mountPanel()
    expect(wrapper.find('[data-test="ai-companion-chat-region"]').exists()).toBe(
      true
    )

    store.activeView = 'history'
    await flushPromises()
    expect(wrapper.find('[data-test="ai-companion-history-region"]').exists()).toBe(
      true
    )
    expect(wrapper.find('[data-test="ai-companion-chat-region"]').exists()).toBe(
      false
    )

    await wrapper.findAll('button[role="tab"]')[0].trigger('click')
    expect(store.activeView).toBe('chat')
    expect(wrapper.find('[data-test="ai-companion-chat-region"]').exists()).toBe(
      true
    )
  })

  it('loads history once per open and keeps the current conversation', async () => {
    const conversations = [
      conversation('conversation-1', '怎么投简历', '2026-09-20T10:00:00+08:00')
    ]
    mockedApiFetch.mockResolvedValue({
      success: true,
      conversations
    } as never)
    const { wrapper, store } = mountPanel()
    store.conversationId = 'conversation-1'
    store.messages = [message('user', '怎么投简历', 'platform_usage', null)]
    await flushPromises()

    expect(store.conversations).toEqual(conversations)
    expect(mockedApiFetch).toHaveBeenCalledTimes(1)
    expect(mockedApiFetch).toHaveBeenCalledWith(CONVERSATIONS_PATH)

    // 再次切到历史会话不重复请求，重开面板也保留当前会话。
    await wrapper.get('#ai-companion-tab-history').trigger('click')
    await flushPromises()
    expect(mockedApiFetch).toHaveBeenCalledTimes(1)
    expect(
      wrapper.findAll('[data-test="ai-companion-history-item"]')
    ).toHaveLength(1)
    expect(store.conversationId).toBe('conversation-1')
    expect(store.messages).toHaveLength(1)
    expect(wrapper.find('[data-test="ai-companion-chat-region"]').exists()).toBe(
      false
    )
  })

  it('reloads history from the server when the panel is remounted', async () => {
    const first = mountPanel()
    await flushPromises()
    expect(mockedApiFetch).toHaveBeenCalledTimes(1)
    first.wrapper.unmount()

    const second = mountPanel()
    await flushPromises()
    expect(mockedApiFetch).toHaveBeenCalledTimes(2)
    second.wrapper.unmount()
  })

  it('reloads history when a kept-mounted panel is reopened', async () => {
    const { store } = mountPanel()
    await flushPromises()
    expect(mockedApiFetch).toHaveBeenCalledTimes(1)

    store.panelOpen = false
    await flushPromises()
    expect(mockedApiFetch).toHaveBeenCalledTimes(1)

    store.panelOpen = true
    await flushPromises()
    expect(mockedApiFetch).toHaveBeenCalledTimes(2)
  })

  it('lets a provided history slot replace the built-in view', async () => {
    const { wrapper } = mountPanel({
      slots: { history: '<p data-test="custom-history">自定义历史</p>' }
    })
    await wrapper.get('#ai-companion-tab-history').trigger('click')
    expect(wrapper.find('[data-test="custom-history"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="ai-companion-history"]').exists()).toBe(
      false
    )
  })

  it('wires each tab to its panel and moves selection with arrow keys', async () => {
    const { wrapper, store } = mountPanel({ attach: true })
    const chatTab = wrapper.get('#ai-companion-tab-chat')
    const historyTab = wrapper.get('#ai-companion-tab-history')
    const chatPanel = wrapper.get('#ai-companion-chat-panel')

    expect(chatTab.attributes('aria-controls')).toBe('ai-companion-chat-panel')
    expect(chatPanel.attributes('role')).toBe('tabpanel')
    expect(chatPanel.attributes('aria-labelledby')).toBe('ai-companion-tab-chat')
    expect(historyTab.attributes('aria-controls')).toBe(
      'ai-companion-history-panel'
    )

    // roving tabindex：只有选中的 tab 停在 tab 序列里。
    expect(chatTab.attributes('tabindex')).toBe('0')
    expect(historyTab.attributes('tabindex')).toBe('-1')

    await wrapper.get('.ai-companion-panel-tabs').trigger('keydown', {
      key: 'ArrowRight'
    })
    expect(store.activeView).toBe('history')
    expect(historyTab.attributes('tabindex')).toBe('0')
    expect(chatTab.attributes('tabindex')).toBe('-1')
    expect(document.activeElement).toBe(historyTab.element)

    await wrapper.get('.ai-companion-panel-tabs').trigger('keydown', {
      key: 'ArrowLeft'
    })
    expect(store.activeView).toBe('chat')
    expect(chatTab.attributes('tabindex')).toBe('0')
  })

  // jsdom 既不注入 scoped 样式也不解析 min()/calc()，这里直接校验样式源码里
  // 兜底声明在 svh 之前，保证旧 Safari 仍拿到一条可用的高度。
  it('keeps a viewport-unit height fallback ahead of the svh value', () => {
    const fallbackIndex = panelSource.indexOf(
      'height: min(680px, calc(100vh - 96px))'
    )
    const svhIndex = panelSource.indexOf(
      'height: min(680px, calc(100svh - 96px))'
    )
    expect(fallbackIndex).toBeGreaterThan(-1)
    expect(svhIndex).toBeGreaterThan(fallbackIndex)
  })
})
