import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError, apiFetch } from '@/api/client'
import type {
  AiCompanionAnswerResponse,
  AiCompanionIntent,
  AiCompanionMessage,
  UserRole
} from '@/api/types'

import { useAuthStore } from '@/stores/auth'
import { useAiCompanionStore } from '@/stores/aiCompanion'

import AiCompanionPanel from './AiCompanionPanel.vue'
import VoiceInputButton from './VoiceInputButton.vue'

// 与 AiCompanionPanel.test.ts 一致的 mock：展开真实模块，仅把 apiFetch 换成 vi.fn()。
vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const MESSAGES_PATH = '/api/ai-companion/messages'
const CONVERSATIONS_PATH = '/api/ai-companion/conversations'
const TRANSCRIPTIONS_PATH = '/api/ai-companion/speech/transcriptions'

// AI 学伴只允许访问这四类接口；任何越界 URL 都视为违反契约。
const WHITELIST_EXACT = new Set<string>([
  MESSAGES_PATH,
  CONVERSATIONS_PATH,
  TRANSCRIPTIONS_PATH
])
const WHITELIST_PREFIX = `${CONVERSATIONS_PATH}/`

function isWhitelisted(url: unknown): boolean {
  if (typeof url !== 'string') {
    return false
  }
  return WHITELIST_EXACT.has(url) || url.startsWith(WHITELIST_PREFIX)
}

// 读取 Blob 请求体的真实文本；JSON.stringify 会把 Blob 折叠成 {}，看不见体内容。
async function readBlobText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () =>
      resolve(typeof reader.result === 'string' ? reader.result : '')
    reader.onerror = () => reject(reader.error)
    reader.readAsText(blob)
  })
}

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
  // 兜底路由：让绝对 URL 只能被 resolveCompanionJumpTarget 的协议守卫拒绝，
  // 而不是“碰巧没匹配到路由”。这样外部 URL 的负例才真正有区分度。
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

function answer(
  intent: AiCompanionIntent,
  jumpTarget: string | null
): AiCompanionAnswerResponse {
  return {
    success: true,
    conversation_id: 'conversation-1',
    user_message: message('user', '怎么投简历', intent, null),
    assistant_message: message('assistant', '进入就业对接。', intent, jumpTarget),
    bullets: [],
    module_key: null,
    jump_target: jumpTarget
  }
}

interface MountPanelOptions {
  role?: UserRole
  messages?: AiCompanionMessage[]
}

// 与面板测试共用的挂载脚手架：全新 pinia、登录态、路由与 store 种子。
function mountPanel(options: MountPanelOptions = {}) {
  const role = options.role ?? 'student'
  const auth = useAuthStore()
  auth.sessionState = 'active'
  auth.user = { id: 1, username: role, name: role, role }
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
  return { wrapper, store }
}

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
  sessionStorage.clear()
  // reset 而不是 clear：清掉上一个用例可能残留的一次性返回值，避免泄漏。
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

interface IntentCase {
  intent: AiCompanionIntent
  question: string
  content: string
  jumpTarget: string | null
}

// 平台使用类：散文段落 + 角色允许时出现“去查看”跳转。
const PLATFORM_USAGE_CASES: readonly IntentCase[] = [
  {
    intent: 'platform_usage',
    question: '怎么投简历',
    content: '进入就业对接后选择岗位投递。',
    jumpTarget: '/student/employment/jobs'
  },
  {
    intent: 'platform_usage',
    question: '积分怎么算',
    content: '积分按完成的课程与测验累计。',
    jumpTarget: '/student/employment/jobs'
  },
  {
    intent: 'platform_usage',
    question: '怎么订阅政策',
    content: '在政策页点击订阅即可收到推送。',
    jumpTarget: '/student/employment/jobs'
  }
]

// 学习请教类：前端把每个 “- ” 要点原样渲染为一个 <li>。
// 1-5 条的数量上限由后端 answers.py _validate_guidance 拥有，并由后端测试覆盖。
const LEARNING_QUESTION_CASES: readonly IntentCase[] = [
  {
    intent: 'learning_question',
    question: '荔枝什么时候套袋',
    content: '- 花后约 40 天开始\n- 避开中午高温',
    jumpTarget: null
  },
  {
    intent: 'learning_question',
    question: '荔枝蒂蛀虫怎么防',
    content: '- 清园减少虫源\n- 套袋护果\n- 适时用药',
    jumpTarget: null
  },
  {
    intent: 'learning_question',
    question: '广绣怎么起针',
    content: '- 选好底布\n- 定好针距',
    jumpTarget: null
  }
]

// 越界代办类：拒绝话术 + 绝不出现跳转按钮。
const OUT_OF_SCOPE_CASES: readonly IntentCase[] = [
  {
    intent: 'out_of_scope',
    question: '帮我投简历',
    content: 'AI 学伴不代办业务操作，请前往就业对接自行投递。',
    jumpTarget: null
  },
  {
    intent: 'out_of_scope',
    question: '帮我兑换奖品',
    content: 'AI 学伴不代办业务操作，请前往积分商城自行兑换。',
    jumpTarget: null
  },
  {
    intent: 'out_of_scope',
    question: '帮我审核内容',
    content: 'AI 学伴不代办业务操作，请前往管理后台处理。',
    jumpTarget: null
  }
]

describe('AI 学伴三类意图分支验收', () => {
  it.each(PLATFORM_USAGE_CASES)(
    'platform_usage：$question 渲染散文段落与角色允许的跳转',
    testCase => {
      const { wrapper } = mountPanel({
        messages: [
          message('assistant', testCase.content, testCase.intent, testCase.jumpTarget)
        ]
      })
      const article = wrapper.find(`[data-intent="${testCase.intent}"]`)
      expect(article.exists()).toBe(true)
      // 平台使用类是纯散文：渲染一个段落。
      expect(article.find('p.ai-companion-message-text').exists()).toBe(true)
      // 角色允许的有效 jump_target 才出现“去查看”跳转按钮。
      expect(wrapper.get('[data-test="ai-companion-jump"]').text()).toContain(
        '去查看'
      )
      wrapper.unmount()
    }
  )

  it('platform_usage：外部 URL 的 jump_target 不渲染跳转', () => {
    const { wrapper } = mountPanel({
      messages: [
        message('assistant', '查看外部资源。', 'platform_usage', 'https://evil.example')
      ]
    })
    expect(wrapper.find('[data-intent="platform_usage"]').exists()).toBe(true)
    // resolveCompanionJumpTarget 拒绝绝对 URL：不生成跳转按钮。
    expect(wrapper.find('[data-test="ai-companion-jump"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('platform_usage：角色不允许的内部路径不渲染跳转', () => {
    // teacher 不在 /student/employment/jobs 的 meta.roles 内。
    const { wrapper } = mountPanel({
      role: 'teacher',
      messages: [
        message('assistant', '进入就业对接。', 'platform_usage', '/student/employment/jobs')
      ]
    })
    expect(wrapper.find('[data-intent="platform_usage"]').exists()).toBe(true)
    // resolveCompanionJumpTarget 拒绝角色不允许的内部路径：不生成跳转按钮。
    expect(wrapper.find('[data-test="ai-companion-jump"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it.each(LEARNING_QUESTION_CASES)(
    'learning_question：$question 按要点原样渲染为列表',
    testCase => {
      const { wrapper } = mountPanel({
        messages: [
          message('assistant', testCase.content, testCase.intent, testCase.jumpTarget)
        ]
      })
      const article = wrapper.find(`[data-intent="${testCase.intent}"]`)
      expect(article.exists()).toBe(true)
      // 前端不设上限：parseBlocks 原样把每个 “- ” 行渲染成一个 <li>；
      // 精确比对渲染条数与种子要点数，证明前端按条目如实渲染为列表。
      // 1-5 条的数量上限由后端 answers.py _validate_guidance 拥有，不由前端强制。
      const seededBullets = testCase.content
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.startsWith('- ')).length
      const items = article.get('ul').findAll('li')
      expect(items.length).toBe(seededBullets)
      wrapper.unmount()
    }
  )

  it.each(OUT_OF_SCOPE_CASES)(
    'out_of_scope：$question 拒绝代办且不出现跳转',
    testCase => {
      const { wrapper } = mountPanel({
        messages: [
          message('assistant', testCase.content, testCase.intent, testCase.jumpTarget)
        ]
      })
      const article = wrapper.find(`[data-intent="${testCase.intent}"]`)
      expect(article.exists()).toBe(true)
      // 越界请求没有跳转按钮。
      expect(wrapper.find('[data-test="ai-companion-jump"]').exists()).toBe(false)
      // 拒绝话术必须包含“AI 学伴不代办业务操作”。
      expect(article.text()).toContain('AI 学伴不代办业务操作')
      wrapper.unmount()
    }
  )
})

describe('三类分支与语音失败经 store 的接口验收', () => {
  // 关键约束：所有 apiFetch 的 URL 都必须落在这四类白名单内，零越界。
  it('sendQuestion/transcribe 的成切与 503 映射，且所有请求都落在白名单内', async () => {
    const { wrapper, store } = mountPanel()

    // 三类意图各发一次成功问答，均 POST 到 /messages。
    mockedApiFetch.mockResolvedValueOnce(
      answer('platform_usage', '/student/employment/jobs') as never
    )
    await store.sendQuestion('怎么投简历')
    mockedApiFetch.mockResolvedValueOnce(answer('learning_question', null) as never)
    await store.sendQuestion('荔枝什么时候套袋')
    mockedApiFetch.mockResolvedValueOnce(answer('out_of_scope', null) as never)
    await store.sendQuestion('帮我投简历')
    expect(mockedApiFetch).toHaveBeenCalledWith(
      MESSAGES_PATH,
      expect.objectContaining({ method: 'POST' })
    )

    // AI 服务 503：错误文案固定为“AI 服务暂时不可用”，与知识库空/ASR 失败话术不同。
    mockedApiFetch.mockRejectedValueOnce(new ApiError('服务不可用', 503))
    const ok = await store.sendQuestion('积分怎么算')
    expect(ok).toBe(false)
    expect(store.error).toBe('AI 服务暂时不可用')

    // 语音转写成功 POST 到 /speech/transcriptions。
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      text: '荔枝蒂蛀虫怎么防'
    } as never)
    const recognized = await store.transcribe(
      new Blob(['audio'], { type: 'audio/webm' }),
      'question.webm'
    )
    expect(recognized).toBe('荔枝蒂蛀虫怎么防')
    expect(mockedApiFetch).toHaveBeenCalledWith(
      TRANSCRIPTIONS_PATH,
      expect.objectContaining({ method: 'POST' })
    )

    // 语音转写 422：映射为“未能识别，请重说或改用文字”。
    mockedApiFetch.mockRejectedValueOnce(new ApiError('识别失败', 422))
    const failed = await store.transcribe(
      new Blob(['audio'], { type: 'audio/webm' }),
      'question.webm'
    )
    expect(failed).toBe('')
    expect(store.error).toBe('未能识别，请重说或改用文字')

    // 打开历史会话会请求 /conversations/*，让白名单前缀分支在此被覆盖。
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      conversation: {
        conversation_id: 'conversation-1',
        title: '怎么投简历',
        last_intent: 'platform_usage',
        jump_target: '/student/employment/jobs',
        created_at: '2026-09-20T10:00:00+08:00',
        updated_at: '2026-09-20T10:00:00+08:00',
        messages: [message('user', '怎么投简历', 'platform_usage', null)]
      }
    } as never)
    const opened = await store.openConversation('conversation-1')
    expect(store.conversationId).toBe('conversation-1')
    expect(opened.length).toBeGreaterThan(0)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/ai-companion/conversations/conversation-1'
    )

    // 白名单扫描：逐个检查每次 apiFetch 的第一个参数（URL），零越界。
    expect(mockedApiFetch.mock.calls.length).toBeGreaterThan(0)
    for (const [url] of mockedApiFetch.mock.calls) {
      expect(isWhitelisted(url)).toBe(true)
    }

    wrapper.unmount()
  })

  it('区分 AI 服务不可用与知识库空的文案', async () => {
    const { wrapper, store } = mountPanel()
    // 503：无论后端消息如何，都固定映射为“AI 服务暂时不可用”。
    mockedApiFetch.mockRejectedValueOnce(new ApiError('AI 服务暂时不可用', 503))
    await store.sendQuestion('积分怎么算')
    const unavailable = store.error
    // 422：透出后端“暂无法回答，请稍后再试”，与 AI 不可用是两套话术。
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('暂无法回答，请稍后再试', 422)
    )
    await store.sendQuestion('荔枝什么时候套袋')
    const knowledgeEmpty = store.error
    expect(unavailable).toBe('AI 服务暂时不可用')
    expect(knowledgeEmpty).toBe('暂无法回答，请稍后再试')
    // 比较的是 store 实际产出的两个值，二者必须彼此不同。
    expect(unavailable).not.toBe(knowledgeEmpty)
    wrapper.unmount()
  })
})

describe('方言只作为交互上下文，不进入 ASR 请求', () => {
  it.each(['yue', 'hak', 'nan'] as const)(
    '方言 %s 不出现在转写请求参数中',
    async dialect => {
      const { wrapper, store } = mountPanel()
      store.dialectCode = dialect
      wrapper.findComponent(VoiceInputButton).vm.$emit(
        'recorded',
        new Blob(['audio'], { type: 'audio/webm' }),
        'question.webm'
      )
      await flushPromises()
      expect(apiFetch).toHaveBeenCalledWith(
        TRANSCRIPTIONS_PATH,
        expect.objectContaining({ method: 'POST' })
      )
      // 既覆盖 URL/headers/boundary，也覆盖真实请求体：JSON.stringify 会把 Blob
      // 折叠成 {}，必须再把 body 读成文本一起检查，否则体里泄露方言也看不见。
      const calls = mockedApiFetch.mock.calls
      const lastCall = calls[calls.length - 1]
      const serialized = JSON.stringify(lastCall)
      const body = lastCall[1]?.body
      const bodyText =
        body instanceof Blob ? await readBlobText(body) : String(body ?? '')
      const combined = serialized + bodyText
      // Teeth：读取必须拿到真实请求体，否则这道断言对 body 是瞎的。
      expect(bodyText.length).toBeGreaterThan(0)
      // 方言码与任何 “dialect” 字样都不能出现在 URL/headers/boundary 或请求体里。
      expect(combined).not.toContain(dialect)
      expect(combined.toLowerCase()).not.toContain('dialect')
      // 证明 bodyText 真的是读到的 multipart 体：包含 store 写入的固定标记，
      // 而不是把 Blob 折叠成 {} 后的空壳。
      expect(bodyText).toContain('name="audio"')
      expect(bodyText).toContain('question.webm')
      wrapper.unmount()
    }
  )
})

describe('语音失败与输入保留验收', () => {
  it('麦克风拒绝只提示改用文字，不触发转写请求', async () => {
    const { wrapper } = mountPanel()
    wrapper.findComponent(VoiceInputButton).vm.$emit('permission-denied')
    await flushPromises()
    expect(apiFetch).not.toHaveBeenCalledWith(
      TRANSCRIPTIONS_PATH,
      expect.anything()
    )
    expect(wrapper.text()).toContain('未能识别，请重说或改用文字')
    wrapper.unmount()
  })

  it('转写失败后文字输入仍可用、草稿仍可编辑', async () => {
    const { wrapper, store } = mountPanel()
    await wrapper.get('[data-test="ai-companion-dialect-yue"]').trigger('click')
    store.setDraft('荔枝什么时候套袋')
    mockedApiFetch.mockRejectedValueOnce(new ApiError('识别失败', 422))
    wrapper.findComponent(VoiceInputButton).vm.$emit(
      'recorded',
      new Blob(['audio'], { type: 'audio/webm' }),
      'question.webm'
    )
    await flushPromises()
    // 失败不清空草稿，输入框保持可编辑（无 disabled）。
    expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
    expect(store.draft).toBe('荔枝什么时候套袋')
    // 失败后仍可继续编辑草稿。
    await wrapper.get('textarea').setValue('补充：套袋护果')
    expect(store.draft).toBe('补充：套袋护果')
    wrapper.unmount()
  })
})
