import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type {
  AiCompanionMessage as CompanionMessage,
  UserRole
} from '@/api/types'

import AiCompanionMessage from './AiCompanionMessage.vue'

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

function message(overrides: Partial<CompanionMessage> = {}): CompanionMessage {
  return {
    message_id: 'message-1',
    role: 'assistant',
    content: '进入就业对接投递。',
    intent: 'platform_usage',
    jump_target: null,
    created_at: '2026-09-20T10:00:00+08:00',
    ...overrides
  }
}

function mountMessage(target: CompanionMessage, role: UserRole = 'student') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ROUTES
  })
  return mount(AiCompanionMessage, {
    props: { message: target, role },
    global: { plugins: [router] }
  })
}

describe('AiCompanionMessage', () => {
  it('splits learning guidance into a bullet list', () => {
    const wrapper = mountMessage(
      message({
        content: '- 先确认品种\n- 进入农业技能继续追问',
        intent: 'learning_question'
      })
    )
    const items = wrapper.get('ul').findAll('li')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toBe('先确认品种')
    expect(items[1].text()).toBe('进入农业技能继续追问')
  })

  it('keeps prose answers as plain paragraphs without a list', () => {
    const wrapper = mountMessage(message({ content: '进入就业对接投递。' }))
    expect(wrapper.find('ul').exists()).toBe(false)
    expect(wrapper.get('.ai-companion-message-text').text()).toBe(
      '进入就业对接投递。'
    )
  })

  it('shows the jump button for a resolved target', () => {
    const wrapper = mountMessage(
      message({ jump_target: '/student/employment/jobs' })
    )
    expect(wrapper.get('[data-test="ai-companion-jump"]').text()).toContain(
      '去查看'
    )
  })

  it('hides the jump button for an out-of-scope answer', () => {
    const wrapper = mountMessage(
      message({
        content: 'AI 学伴不代办业务操作。',
        intent: 'out_of_scope',
        jump_target: '/student/employment/jobs'
      })
    )
    expect(wrapper.find('[data-test="ai-companion-jump"]').exists()).toBe(false)
  })

  it('hides the jump button when the target is not available to the role', () => {
    const wrapper = mountMessage(
      message({ jump_target: '/student/employment/jobs' }),
      'teacher'
    )
    expect(wrapper.find('[data-test="ai-companion-jump"]').exists()).toBe(false)
  })

  it('renders user messages as plain text', () => {
    const wrapper = mountMessage(
      message({
        role: 'user',
        content: '- 不是列表\n**不是加粗**',
        intent: null,
        jump_target: '/student/employment/jobs'
      })
    )
    expect(wrapper.find('ul').exists()).toBe(false)
    expect(wrapper.find('strong').exists()).toBe(false)
    expect(wrapper.find('em').exists()).toBe(false)
    expect(wrapper.find('[data-test="ai-companion-jump"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('- 不是列表')
    expect(wrapper.text()).toContain('**不是加粗**')
  })

  it('tags every message with its intent', () => {
    expect(mountMessage(message({ intent: 'platform_usage' })).attributes(
      'data-intent'
    )).toBe('platform_usage')
    expect(mountMessage(message({ intent: 'learning_question' })).attributes(
      'data-intent'
    )).toBe('learning_question')
    expect(mountMessage(message({ intent: 'out_of_scope' })).attributes(
      'data-intent'
    )).toBe('out_of_scope')
    expect(
      mountMessage(message({ role: 'user', intent: null })).attributes(
        'data-intent'
      )
    ).toBeUndefined()
  })

  it('navigates to the resolved target from the jump button', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: ROUTES
    })
    const wrapper = mount(AiCompanionMessage, {
      props: {
        message: message({ jump_target: '/student/employment/jobs' }),
        role: 'student'
      },
      global: { plugins: [router] }
    })
    await wrapper.get('[data-test="ai-companion-jump"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/student/employment/jobs')
  })
})
