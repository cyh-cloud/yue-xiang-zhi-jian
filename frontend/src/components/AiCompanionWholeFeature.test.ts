import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError, apiFetch } from '@/api/client'
import type {
  AiCompanionConversation,
  AiCompanionIntent,
  AiCompanionMessage,
  UserRole
} from '@/api/types'

import { useAuthStore } from '@/stores/auth'
import { useAiCompanionStore } from '@/stores/aiCompanion'

import App from '../App.vue'
import AiCompanionPanel from './AiCompanionPanel.vue'
import VoiceInputButton from './VoiceInputButton.vue'

// mock：展开真实模块，只把 apiFetch 换成 vi.fn()。
vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const CONVERSATIONS_PATH = '/api/ai-companion/conversations'
const TRANSCRIPTIONS_PATH = '/api/ai-companion/speech/transcriptions'
const RECOGNITION_FAILURE_MESSAGE = '未能识别，请重说或改用文字'
const REFUSAL_TEXT = 'AI 学伴不代办业务操作，请使用对应功能入口或联系管理员。'

// 六个角色：四个 AI 学伴角色 + 两个管理角色。
const ALL_ROLES: readonly UserRole[] = [
  'student',
  'teacher',
  'enterprise',
  'government',
  'super_admin',
  'admin'
]

// 只有这四个非管理角色能使用 AI 学伴。
const COMPANION_ROLES: ReadonlySet<UserRole> = new Set<UserRole>([
  'student',
  'teacher',
  'enterprise',
  'government'
])

// 路由 meta 三种形态：空 roles、以及故意只标管理角色的误导性 meta。
const ROUTE_META_MATRIX: readonly { roles?: UserRole[] }[] = [
  {},
  { roles: [] },
  { roles: ['super_admin', 'admin'] }
]

// 面板与跳转校验共用的路由表：包含角色受限的学生路由和一条兜底路由。
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
  },
  { path: '/:pathMatch(.*)*', component: { template: '<div />' } }
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

function signIn(role: UserRole): void {
  const auth = useAuthStore()
  auth.sessionState = 'active'
  auth.user = { id: 1, username: role, name: role, role }
}

// 面板只在打开时挂载，这里复现该条件。
function mountPanel(
  options: { role?: UserRole; messages?: AiCompanionMessage[] } = {}
) {
  const role = options.role ?? 'student'
  signIn(role)
  const store = useAiCompanionStore()
  store.panelOpen = true
  if (options.messages) {
    store.messages = options.messages
  }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ROUTES
  })
  const wrapper = mount(AiCompanionPanel, {
    global: { plugins: [pinia, router] }
  })
  return { wrapper, store, router }
}

// 每次迭代都新建 pinia 与 router，避免角色状态或当前路由在组合之间串味。
async function mountAppAt(
  role: UserRole,
  path: string,
  meta: { roles?: UserRole[] }
) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path, component: { template: '<div />' }, meta }]
  })
  await router.push(path)
  await router.isReady()
  const freshPinia = createPinia()
  setActivePinia(freshPinia)
  signIn(role)
  return mount(App, { global: { plugins: [freshPinia, router] } })
}

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
  sessionStorage.clear()
  vi.resetAllMocks()
  mockedApiFetch.mockResolvedValue({
    success: true,
    conversations: [],
    text: '荔枝什么时候套袋'
  } as never)
})

afterEach(() => {
  document.body.innerHTML = ''
})
describe('012 AI 学伴整功能验收', () => {
  // 条目 1：入口显隐只由角色决定，与路由 meta 完全无关。
  describe('条目 1 启动器显隐独立于路由 meta', () => {
    it('在 角色 x meta 的每种组合下都只按角色决定显隐', async () => {
      for (const role of ALL_ROLES) {
        for (const meta of ROUTE_META_MATRIX) {
          const wrapper = await mountAppAt(role, '/portal-area', meta)
          const exists = wrapper
            .find('[data-test="ai-companion-launcher"]')
            .exists()
          // 失败信息带上 role/meta，红了也能一眼定位是哪一种组合。
          expect(
            exists,
            `role=${role} meta=${JSON.stringify(meta)}`
          ).toBe(COMPANION_ROLES.has(role))
          wrapper.unmount()
        }
      }
    })

    it('路由完全缺失 meta 时同样只按角色决定', async () => {
      for (const role of ALL_ROLES) {
        const wrapper = await mountAppAt(role, '/no-meta-route', {})
        expect(
          wrapper.find('[data-test="ai-companion-launcher"]').exists(),
          `role=${role} 缺少 meta`
        ).toBe(COMPANION_ROLES.has(role))
        wrapper.unmount()
      }
    })
  })

  // 条目 2：三类意图渲染出彼此不同且有界的输出。
  describe('条目 2 三类意图分支渲染不同且有界的输出', () => {
    it('platform_usage 渲染散文段落，learning_question 渲染要点列表，out_of_scope 只给拒绝话术', () => {
      const { wrapper } = mountPanel({
        messages: [
          message(
            'assistant',
            '进入就业对接后选择岗位投递。\n- 这行不是要点',
            'platform_usage',
            '/student/employment/jobs'
          ),
          message(
            'assistant',
            '- 先确认品种\n- 进入农业技能继续追问\n- 避开中午高温',
            'learning_question',
            '/student/agri-skills/qa'
          ),
          message('assistant', REFUSAL_TEXT, 'out_of_scope', null)
        ]
      })

      const platform = wrapper.get('[data-intent="platform_usage"]')
      const learning = wrapper.get('[data-intent="learning_question"]')
      const refusal = wrapper.get('[data-intent="out_of_scope"]')

      // data-intent 三者互不相同。
      expect(platform.attributes('data-intent')).toBe('platform_usage')
      expect(learning.attributes('data-intent')).toBe('learning_question')
      expect(refusal.attributes('data-intent')).toBe('out_of_scope')

      // platform_usage：散文段落；"- " 行不被解释成列表（无 Markdown 解析）。
      expect(platform.find('p.ai-companion-message-text').exists()).toBe(true)
      expect(platform.find('ul').exists()).toBe(false)
      expect(platform.text()).toContain('进入就业对接后选择岗位投递。')

      // learning_question：一个 <ul>，条目数与种子要点数一致，不增不减。
      const bullets = learning.get('ul').findAll('li')
      expect(bullets).toHaveLength(3)
      expect(bullets.map(item => item.text())).toEqual([
        '先确认品种',
        '进入农业技能继续追问',
        '避开中午高温'
      ])

      // out_of_scope：只有拒绝话术，没有列表，也没有跳转。
      expect(refusal.text()).toContain(REFUSAL_TEXT)
      expect(refusal.find('ul').exists()).toBe(false)
      expect(
        refusal.find('[data-test="ai-companion-jump"]').exists()
      ).toBe(false)

      // 结构互不相同：三个分支的 DOM 形状不是同一个模板。
      expect(platform.html()).not.toBe(learning.html())
      expect(learning.html()).not.toBe(refusal.html())
      wrapper.unmount()
    })

    it('platform_usage 在缺少有效 jump_target 时只输出文字', () => {
      const { wrapper } = mountPanel({
        messages: [
          message('assistant', '平台使用说明正文。', 'platform_usage', null)
        ]
      })
      expect(wrapper.find('[data-intent="platform_usage"]').exists()).toBe(true)
      expect(wrapper.find('[data-test="ai-companion-jump"]').exists()).toBe(
        false
      )
      expect(wrapper.text()).toContain('平台使用说明正文。')
      wrapper.unmount()
    })
  })
  // 条目 3：“去查看”只对有效且角色允许的目标出现。
  describe('条目 3 去查看只对有效且角色允许的目标出现', () => {
    it('student 访问 /student/employment/jobs 时显示“去查看”', () => {
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
      wrapper.unmount()
    })

    it('外部 URL 的 jump_target 不渲染“去查看”', () => {
      const { wrapper } = mountPanel({
        messages: [
          message(
            'assistant',
            '查看外部资源。',
            'platform_usage',
            'https://evil.example/path'
          )
        ]
      })
      expect(wrapper.find('[data-test="ai-companion-jump"]').exists()).toBe(
        false
      )
      wrapper.unmount()
    })

    it('角色不允许的内部路径不渲染“去查看”', () => {
      // teacher 不在 /student/employment/jobs 的 meta.roles 内。
      const { wrapper } = mountPanel({
        role: 'teacher',
        messages: [
          message(
            'assistant',
            '进入就业对接。',
            'platform_usage',
            '/student/employment/jobs'
          )
        ]
      })
      expect(wrapper.find('[data-test="ai-companion-jump"]').exists()).toBe(
        false
      )
      wrapper.unmount()
    })

    it('out_of_scope 即使带上 jump_target 也不渲染“去查看”', () => {
      const { wrapper } = mountPanel({
        messages: [
          message(
            'assistant',
            REFUSAL_TEXT,
            'out_of_scope',
            '/student/employment/jobs'
          )
        ]
      })
      expect(wrapper.find('[data-test="ai-companion-jump"]').exists()).toBe(
        false
      )
      wrapper.unmount()
    })
  })

  // 条目 4：语音失败后文字输入始终可用。
  describe('条目 4 语音失败保留文字输入', () => {
    it('转写失败（ApiError 422）后输入框仍可编辑并提示改用文字', async () => {
      const { wrapper, store } = mountPanel()
      await wrapper
        .get('[data-test="ai-companion-dialect-yue"]')
        .trigger('click')
      store.setDraft('荔枝什么时候套袋')
      mockedApiFetch.mockRejectedValueOnce(new ApiError('识别失败', 422))
      wrapper.findComponent(VoiceInputButton).vm.$emit(
        'recorded',
        new Blob(['audio'], { type: 'audio/webm' }),
        'question.webm'
      )
      await flushPromises()

      expect(mockedApiFetch).toHaveBeenCalledWith(
        TRANSCRIPTIONS_PATH,
        expect.objectContaining({ method: 'POST' })
      )
      expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
      expect(wrapper.text()).toContain(RECOGNITION_FAILURE_MESSAGE)
      // 草稿没有被失败清掉，且仍可继续编辑。
      expect(store.draft).toBe('荔枝什么时候套袋')
      await wrapper.get('textarea').setValue('改用文字继续提问')
      expect(store.draft).toBe('改用文字继续提问')
      wrapper.unmount()
    })

    it('麦克风权限被拒后输入框仍可编辑并提示改用文字', async () => {
      const { wrapper, store } = mountPanel()
      store.setDraft('已输入的草稿')
      wrapper.findComponent(VoiceInputButton).vm.$emit('permission-denied')
      await flushPromises()

      expect(apiFetch).not.toHaveBeenCalledWith(
        TRANSCRIPTIONS_PATH,
        expect.anything()
      )
      expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
      expect(wrapper.text()).toContain(RECOGNITION_FAILURE_MESSAGE)
      await wrapper.get('textarea').setValue('权限被拒后继续输入')
      expect(store.draft).toBe('权限被拒后继续输入')
      wrapper.unmount()
    })
  })
  // 条目 5：历史有序、属主隔离、可重开。
  describe('条目 5 历史有序、属主隔离、可重开', () => {
    // updated_at 倒序即服务端返回顺序；前端必须原样渲染，不得重排。
    const ORDERED: readonly AiCompanionConversation[] = [
      conversation(
        'conversation-3',
        '第三次提问',
        '2026-09-20T12:00:00+08:00'
      ),
      conversation(
        'conversation-2',
        '第二次提问',
        '2026-09-20T11:00:00+08:00'
      ),
      conversation(
        'conversation-1',
        '第一次提问',
        '2026-09-20T10:00:00+08:00'
      )
    ]

    const OWNER_MESSAGES: readonly AiCompanionMessage[] = [
      message('user', '我的第一次提问', 'platform_usage', null),
      message(
        'assistant',
        '进入就业对接后选择岗位投递。',
        'platform_usage',
        '/student/employment/jobs'
      )
    ]

    async function openHistoryTab(
      wrapper: ReturnType<typeof mountPanel>['wrapper']
    ) {
      await wrapper.get('#ai-companion-tab-history').trigger('click')
      await flushPromises()
    }

    it('按 updated_at 倒序渲染历史，点击后重开会话并渲染其消息', async () => {
      mockedApiFetch.mockResolvedValueOnce({
        success: true,
        conversations: ORDERED
      } as never)
      const { wrapper, store } = mountPanel()
      await openHistoryTab(wrapper)

      const items = wrapper.findAll('[data-test="ai-companion-history-item"]')
      expect(items).toHaveLength(3)
      expect(items.map(item => item.text())).toEqual([
        expect.stringContaining('第三次提问'),
        expect.stringContaining('第二次提问'),
        expect.stringContaining('第一次提问')
      ])

      // 点击第一条：openConversation 请求该会话详情，并渲染它的消息。
      mockedApiFetch.mockResolvedValueOnce({
        success: true,
        conversation: {
          ...ORDERED[0],
          messages: OWNER_MESSAGES
        }
      } as never)
      await items[0].trigger('click')
      await flushPromises()

      expect(mockedApiFetch).toHaveBeenCalledWith(
        `${CONVERSATIONS_PATH}/conversation-3`
      )
      expect(store.conversationId).toBe('conversation-3')
      expect(store.messages).toEqual(OWNER_MESSAGES)
      expect(
        wrapper.find('[data-test="ai-companion-chat-region"]').exists()
      ).toBe(true)
      expect(wrapper.text()).toContain('进入就业对接后选择岗位投递。')
      wrapper.unmount()
    })

    it('跨用户读取返回 404 时显示失败，且不泄露他人会话内容', async () => {
      mockedApiFetch.mockResolvedValueOnce({
        success: true,
        conversations: ORDERED
      } as never)
      const { wrapper, store } = mountPanel()
      // 先打开自己的会话，让面板里已经有一篇属主可见的对话。
      mockedApiFetch.mockResolvedValueOnce({
        success: true,
        conversation: {
          ...ORDERED[2],
          messages: OWNER_MESSAGES
        }
      } as never)
      await openHistoryTab(wrapper)
      const items = wrapper.findAll('[data-test="ai-companion-history-item"]')
      await items[2].trigger('click')
      await flushPromises()
      expect(store.messages).toEqual(OWNER_MESSAGES)

      // 再点一条别人的会话：后端 404，前端必须显示失败而不是渲染别人的内容。
      mockedApiFetch.mockRejectedValueOnce(new ApiError('会话不存在', 404))
      await wrapper.get('#ai-companion-tab-history').trigger('click')
      await flushPromises()
      const refreshed = wrapper.findAll(
        '[data-test="ai-companion-history-item"]'
      )
      await refreshed[0].trigger('click')
      await flushPromises()

      expect(store.error).toBe('会话不存在')
      expect(wrapper.get('[data-test="ai-companion-error"]').text()).toBe(
        '会话不存在'
      )
      // 属主隔离由后端强制：前端只能显示失败，且已有消息不被他人内容替换。
      expect(store.messages).toEqual(OWNER_MESSAGES)
      expect(wrapper.text()).not.toContain('他人私有答案')
      wrapper.unmount()
    })
  })
})