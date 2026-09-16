import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError, apiFetch } from '@/api/client'
import type { CustomerScenario, CustomerSession } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import EcommerceTrainingNav from '@/components/EcommerceTrainingNav.vue'

import EcommerceCustomerServiceView from './EcommerceCustomerServiceView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const scenarios: CustomerScenario[] = [
  {
    key: 'product_info',
    label: '商品咨询',
    criteria: [
      'product_need_identified',
      'accurate_info_and_next_step',
      'legacy_unknown_key'
    ]
  },
  {
    key: 'price_promo',
    label: '价格优惠',
    criteria: ['promotion_rule_explained', 'eligibility_verified']
  },
  {
    key: 'shipping',
    label: '物流配送',
    criteria: ['order_context_identified', 'delivery_and_next_step']
  },
  {
    key: 'after_sales',
    label: '售后处理',
    criteria: ['issue_identified', 'policy_and_process_explained']
  },
  {
    key: 'complaint',
    label: '投诉处理',
    criteria: ['emotion_acknowledged', 'resolution_or_escalation']
  }
]

function customerTurn(
  turnNo: number,
  patch: Partial<CustomerSession['turns'][number]> = {}
): CustomerSession['turns'][number] {
  return {
    id: turnNo,
    turn_no: turnNo,
    customer_message: turnNo === 1 ? '这个商品拆封后还能退吗？' : '那需要准备什么材料？',
    student_reply: null,
    analysis: null,
    created_at: `2026-09-17T08:0${turnNo}:00+08:00`,
    ...patch
  }
}

function customerSession(
  patch: Partial<CustomerSession> = {}
): CustomerSession {
  return {
    id: 7,
    scenario_key: 'after_sales',
    scenario_label: '售后处理',
    goal_criteria: ['确认订单情况', '说明退换流程'],
    status: 'active',
    end_suggested: false,
    turns: [customerTurn(1)],
    summary: null,
    confirmed_at: null,
    created_at: '2026-09-17T08:00:00+08:00',
    updated_at: '2026-09-17T08:00:00+08:00',
    completed_at: null,
    ...patch
  }
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      '/',
      '/login',
      '/student/ecommerce-training',
      '/student/ecommerce-training/customer-service'
    ].map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}

function mountView() {
  const pinia = createPinia()
  const wrapper = mount(EcommerceCustomerServiceView, {
    global: {
      plugins: [pinia, createTestRouter()]
    }
  })
  return { pinia, wrapper }
}

describe('EcommerceCustomerServiceView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    mockedApiFetch.mockResolvedValue({
      success: true,
      scenarios
    } as never)
  })

  it('renders all five scenario cards with labels and goal criteria', async () => {
    const { wrapper } = mountView()
    await flushPromises()

    expect(wrapper.findComponent(AppHeader).exists()).toBe(true)
    expect(wrapper.findComponent(EcommerceTrainingNav).exists()).toBe(true)
    const cards = wrapper.findAll('[data-test="customer-service-scenario"]')
    expect(cards).toHaveLength(5)
    expect(cards.map(card => card.get('h2').text())).toEqual([
      '商品咨询',
      '价格优惠',
      '物流配送',
      '售后处理',
      '投诉处理'
    ])
    expect(cards.every(card => card.findAll('li').length >= 2)).toBe(true)
    expect(cards[0].findAll('li').map(item => item.text())).toEqual([
      '识别商品需求',
      '提供准确信息与下一步',
      '训练目标'
    ])
    expect(wrapper.get('h1').text()).toBe('客服模拟训练')
    expect(wrapper.get('.page-kicker').text()).toBe('04 / 电商运营实训')
    expect(wrapper.text()).not.toMatch(
      /product_need_identified|accurate_info_and_next_step|promotion_rule_explained|eligibility_verified|order_context_identified|delivery_and_next_step|issue_identified|policy_and_process_explained|emotion_acknowledged|resolution_or_escalation|legacy_unknown_key/
    )
    expect(
      wrapper
        .get('[data-test="customer-service-scenario-region"]')
        .attributes('aria-busy')
    ).toBe('false')
    expect(
      wrapper
        .get('[data-test="customer-service-operation-status"]')
        .attributes('aria-live')
    ).toBe('polite')
  })

  it('loads history and opens a historical session without duplicating it', async () => {
    const historical = customerSession({
      id: 9,
      status: 'completed',
      end_suggested: true,
      updated_at: '2026-09-17T09:00:00+08:00',
      summary: {
        overall_performance: '整体回应清楚',
        main_problems: ['首轮缺少共情'],
        prioritized_improvements: ['先确认顾客顾虑'],
        goal_completion: '两项目标均已达成'
      },
      completed_at: '2026-09-17T09:00:00+08:00'
    })
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, scenarios } as never)
      .mockResolvedValueOnce({
        success: true,
        sessions: [historical]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        session: historical
      } as never)
    const { wrapper } = mountView()
    await flushPromises()

    expect(mockedApiFetch.mock.calls.slice(0, 2).map(([url]) => url)).toEqual([
      '/api/ecommerce-training/customer-service/scenarios',
      '/api/ecommerce-training/customer-service/sessions'
    ])
    const history = wrapper.get('[data-test="customer-service-history"]')
    const item = history.get(
      '[data-test="customer-service-history-item-9"]'
    )
    expect(item.text()).toContain('售后处理')
    expect(item.text()).toContain('已完成')
    expect(item.text()).toContain('两项目标均已达成')
    expect(item.get('time').attributes('datetime')).toBe(
      '2026-09-17T09:00:00+08:00'
    )

    await item.trigger('click')
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      '/api/ecommerce-training/customer-service/sessions/9'
    )
    expect(wrapper.text()).toContain('整体回应清楚')
    expect(
      wrapper.findAll('[data-test="customer-service-history-item-9"]')
    ).toHaveLength(1)
  })

  it('renders ordered turns and only exposes continue or end for the allowed states', async () => {
    const analyzed = customerSession({
      turns: [
        customerTurn(1, {
          student_reply: '请提供订单号',
          analysis: {
            problem: '未先确认订单状态',
            evidence: '学员直接要求提供订单号',
            suggestion: '先共情，再确认订单和商品状态',
            criteria: {
              确认订单情况: true,
              说明退换流程: false
            },
            goal_status: 'not_reached'
          }
        })
      ]
    })
    const reached = customerSession({
      status: 'goal_reached',
      end_suggested: true,
      turns: [
        ...analyzed.turns,
        customerTurn(2, {
          student_reply: '拆封后可按流程申请',
          analysis: {
            problem: '可补充材料清单',
            evidence: '学员说明拆封后可申请',
            suggestion: '继续说明所需材料',
            criteria: {
              确认订单情况: true,
              说明退换流程: true
            },
            goal_status: 'reached'
          }
        })
      ]
    })
    const completed = customerSession({
      ...reached,
      status: 'completed',
      summary: {
        overall_performance: '整场回应清楚',
        main_problems: ['首轮缺少共情'],
        prioritized_improvements: ['先确认订单情况'],
        goal_completion: '两项目标均已达成'
      },
      confirmed_at: '2026-09-17T08:03:00+08:00',
      completed_at: '2026-09-17T08:03:00+08:00'
    })
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, scenarios } as never)
      .mockResolvedValueOnce({ success: true, sessions: [] } as never)
      .mockResolvedValueOnce({ success: true, session: customerSession() } as never)
      .mockResolvedValueOnce({ success: true, session: analyzed } as never)
      .mockResolvedValueOnce({
        success: true,
        session: customerSession({ turns: [analyzed.turns[0], customerTurn(2)] })
      } as never)
      .mockResolvedValueOnce({ success: true, session: reached } as never)
      .mockResolvedValueOnce({ success: true, session: completed } as never)
    const { wrapper } = mountView()
    await flushPromises()

    expect(
      wrapper.find('[data-test="customer-service-continue"]').exists()
    ).toBe(false)
    expect(wrapper.find('[data-test="customer-service-end"]').exists()).toBe(
      false
    )

    await wrapper
      .get('[data-test="customer-service-scenario-after_sales"]')
      .trigger('click')
    await flushPromises()
    expect(
      wrapper
        .get('[data-test="customer-service-conversation"]')
        .attributes('aria-busy')
    ).toBe('false')
    await wrapper
      .get('[data-test="customer-service-reply"]')
      .setValue('请提供订单号')
    await wrapper
      .get('.reply-form')
      .trigger('submit')
    await flushPromises()

    const firstTurn = wrapper
      .findAll('[data-test="customer-service-turn"]')[0]
    const firstText = firstTurn.text()
    expect(firstText.indexOf('这个商品拆封后还能退吗？')).toBeLessThan(
      firstText.indexOf('请提供订单号')
    )
    expect(firstText).toContain('未先确认订单状态')
    expect(firstText).toContain('学员直接要求提供订单号')
    expect(firstText).toContain('先共情，再确认订单和商品状态')
    expect(firstText).toContain('确认订单情况')
    expect(firstText).toContain('说明退换流程')
    expect(wrapper.find('[data-test="customer-service-continue"]').exists()).toBe(
      true
    )
    expect(wrapper.find('[data-test="customer-service-end"]').exists()).toBe(
      false
    )
    expect(wrapper.text()).not.toMatch(/第\s*\d+\s*轮|轮数上限/)

    await wrapper
      .get('[data-test="customer-service-continue"]')
      .trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-test="customer-service-turn"]')).toHaveLength(
      2
    )

    await wrapper
      .get('[data-test="customer-service-reply"]')
      .setValue('拆封后可按流程申请')
    await wrapper
      .get('.reply-form')
      .trigger('submit')
    await flushPromises()

    expect(wrapper.find('[data-test="customer-service-continue"]').exists()).toBe(
      false
    )
    expect(wrapper.find('[data-test="customer-service-end"]').exists()).toBe(
      true
    )
    expect(
      mockedApiFetch.mock.calls.some(
        ([url, options]) =>
          url === '/api/ecommerce-training/customer-service/sessions/7/end' &&
          options?.method === 'POST'
      )
    ).toBe(false)

    await wrapper
      .get('[data-test="customer-service-end"]')
      .trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('整场回应清楚')
    expect(wrapper.text()).toContain('首轮缺少共情')
    expect(wrapper.text()).toContain('先确认订单情况')
    expect(wrapper.text()).toContain('两项目标均已达成')
  })

  it('preserves transcript and pending reply after analysis failure without fabricating feedback', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, scenarios } as never)
      .mockResolvedValueOnce({ success: true, sessions: [] } as never)
      .mockResolvedValueOnce({ success: true, session: customerSession() } as never)
      .mockRejectedValueOnce(new ApiError('provider timeout', 503))
    const { wrapper } = mountView()
    await flushPromises()

    await wrapper
      .get('[data-test="customer-service-scenario-after_sales"]')
      .trigger('click')
    await flushPromises()
    await wrapper
      .get('[data-test="customer-service-reply"]')
      .setValue('请提供订单号')
    await wrapper
      .get('.reply-form')
      .trigger('submit')
    await flushPromises()

    expect(wrapper.get('[aria-live="assertive"]').text()).toBe(
      'AI 服务暂时不可用'
    )
    expect(
      wrapper.get<HTMLTextAreaElement>(
        '[data-test="customer-service-reply"]'
      ).element.value
    ).toBe('请提供订单号')
    expect(
      wrapper.findAll('[data-test="customer-service-turn"]')
    ).toHaveLength(1)
    expect(wrapper.text()).toContain('这个商品拆封后还能退吗？')
    expect(wrapper.find('[data-test="customer-service-continue"]').exists()).toBe(
      false
    )
    expect(wrapper.find('[data-test="customer-service-end"]').exists()).toBe(
      false
    )
    expect(wrapper.text()).not.toMatch(/本地兜底|SSE|003|降级/)
  })

  it('safely renders analysis strings and summary string, list and dictionary values', async () => {
    const mixed = customerSession({
      status: 'completed',
      end_suggested: true,
      turns: [
        customerTurn(1, {
          student_reply: '请提供订单号',
          analysis: {
            problem: '未先确认订单状态',
            evidence: '学员直接要求提供订单号，未确认订单',
            suggestion: '先共情，再确认订单和商品状态',
            criteria: {
              确认订单情况: true,
              说明退换流程: false
            },
            goal_status: 'not_reached'
          }
        })
      ],
      summary: {
        overall_performance: {
          summary: '整场回应清楚',
          highlights: [
            {
              label: '先确认顾客顾虑',
              examples: ['先回应顾客顾虑']
            }
          ]
        },
        main_problems: [
          {
            title: '首轮缺少共情',
            detail: ['可直接回应顾虑']
          }
        ],
        prioritized_improvements: [
          '先确认订单情况',
          {
            action: '补充凭证说明',
            examples: ['说明订单和商品状态凭证']
          }
        ],
        goal_completion: {
          outcome: '两项目标均已达成',
          criteria: [
            '确认订单情况',
            {
              name: '说明退换流程',
              result: '已说明'
            }
          ]
        }
      }
    })
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, scenarios } as never)
      .mockResolvedValueOnce({ success: true, sessions: [] } as never)
      .mockResolvedValueOnce({ success: true, session: mixed } as never)
    const { wrapper } = mountView()
    await flushPromises()

    await wrapper
      .get('[data-test="customer-service-scenario-after_sales"]')
      .trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('未先确认订单状态')
    expect(wrapper.text()).toContain('未确认订单')
    expect(wrapper.text()).toContain('确认订单情况')
    expect(wrapper.text()).toContain('已达成')
    expect(wrapper.text()).toContain('未达成')
    expect(wrapper.text()).toContain('整场回应清楚')
    expect(wrapper.text()).toContain('先确认顾客顾虑')
    expect(wrapper.text()).toContain('可直接回应顾虑')
    expect(wrapper.text()).toContain('补充凭证说明')
    expect(wrapper.text()).toContain('说明订单和商品状态凭证')
    expect(wrapper.text()).toContain('两项目标均已达成')
    expect(wrapper.text()).toContain('说明退换流程')
    expect(wrapper.text()).toContain('已说明')
    expect(wrapper.text()).not.toContain('[object Object]')
  })
})
