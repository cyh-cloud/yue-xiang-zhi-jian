import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type {
  AiCompanionIntent,
  AiCompanionMessage,
  UserRole
} from '@/api/types'

import { useAuthStore } from '@/stores/auth'
import { useAiCompanionStore } from '@/stores/aiCompanion'

import AiCompanionPanel from './AiCompanionPanel.vue'
import VoiceInputButton from './VoiceInputButton.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

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

interface MountPanelOptions {
  role?: UserRole
  message?: AiCompanionMessage
}

function mountPanel(options: MountPanelOptions = {}) {
  const role = options.role ?? 'student'
  const auth = useAuthStore()
  auth.sessionState = 'active'
  auth.user = { id: 1, username: role, name: role, role }
  const store = useAiCompanionStore()
  if (options.message) {
    store.messages = [options.message]
  }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ROUTES
  })
  return mount(AiCompanionPanel, {
    global: { plugins: [pinia, router] }
  })
}

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
  sessionStorage.clear()
  vi.clearAllMocks()
  mockedApiFetch.mockResolvedValue({
    success: true,
    text: '荔枝什么时候套袋'
  } as never)
})

describe('AiCompanionPanel', () => {
  it('renders the three intent branches distinctly', () => {
    const store = useAiCompanionStore()
    store.messages = [
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
    const wrapper = mountPanel()
    expect(wrapper.findAll('[data-intent="platform_usage"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-intent="learning_question"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-intent="out_of_scope"]')).toHaveLength(1)
  })

  it('shows a jump button only for an allowed resolved target', () => {
    const wrapper = mountPanel({
      role: 'student',
      message: message(
        'assistant',
        '进入就业对接。',
        'platform_usage',
        '/student/employment/jobs'
      )
    })
    expect(wrapper.get('[data-test="ai-companion-jump"]').text()).toContain(
      '去查看'
    )
  })

  it('does not submit until recognized text is confirmed', async () => {
    const store = useAiCompanionStore()
    const send = vi.spyOn(store, 'sendQuestion')
    const wrapper = mountPanel()
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
    const wrapper = mountPanel()
    expect(wrapper.get('[data-test="ai-companion-voice"]').attributes('disabled'))
      .toBeDefined()
    await wrapper.get('[data-test="ai-companion-dialect-yue"]').trigger('click')
    expect(wrapper.get('[data-test="ai-companion-voice"]').attributes('disabled'))
      .toBeUndefined()
  })

  it('maps microphone denial to retry-or-type copy', async () => {
    const wrapper = mountPanel()
    await wrapper.get('[data-test="ai-companion-voice"]').trigger('permission-denied')
    expect(wrapper.text()).toContain('未能识别，请重说或改用文字')
    expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
  })

  it('maps cancelled or zero-byte recording to retry-or-type copy', async () => {
    const wrapper = mountPanel()
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
    const store = useAiCompanionStore()
    const wrapper = mountPanel()
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
    const wrapper = mountPanel()
    wrapper.findComponent(VoiceInputButton).vm.$emit('permission-denied')
    await flushPromises()
    expect(wrapper.text()).toContain('未能识别，请重说或改用文字')
    expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
    expect(
      wrapper.get('[data-test="ai-companion-voice"]').attributes('disabled')
    ).toBeDefined()
  })

  it('submits the confirmed draft and blocks a blank one', async () => {
    const store = useAiCompanionStore()
    const send = vi.spyOn(store, 'sendQuestion').mockResolvedValue(true)
    const wrapper = mountPanel()
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
    const wrapper = mountPanel()
    expect(wrapper.get('textarea').attributes('maxlength')).toBe('2000')
  })

  it('reads and writes the active tab through the store', async () => {
    const store = useAiCompanionStore()
    const wrapper = mountPanel()
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
})
