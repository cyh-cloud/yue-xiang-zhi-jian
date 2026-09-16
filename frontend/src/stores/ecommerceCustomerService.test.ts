import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type { CustomerScenario, CustomerSession } from '@/api/types'

import { useEcommerceCustomerServiceStore } from './ecommerceCustomerService'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)
const API_PREFIX = '/api/ecommerce-training/customer-service'

const scenarios: CustomerScenario[] = [
  { key: 'product_info', label: '商品咨询', criteria: ['说明商品信息', '确认顾客需求'] },
  { key: 'price_promo', label: '价格优惠', criteria: ['解释优惠规则', '促成下单'] },
  { key: 'shipping', label: '物流配送', criteria: ['说明配送安排', '给出查询方式'] },
  { key: 'after_sales', label: '售后处理', criteria: ['确认订单情况', '说明退换流程'] },
  { key: 'complaint', label: '投诉处理', criteria: ['共情顾客诉求', '给出解决路径'] }
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

describe('ecommerceCustomerService store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('loads exactly five scenarios and starts the selected scenario', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        scenarios
      } as never)
      .mockResolvedValueOnce({
        success: true,
        session: customerSession()
      } as never)
    const store = useEcommerceCustomerServiceStore()

    expect(await store.loadScenarios()).toBe(true)
    expect(mockedApiFetch).toHaveBeenLastCalledWith(`${API_PREFIX}/scenarios`)
    expect(store.scenarios.map(item => item.key)).toEqual([
      'product_info',
      'price_promo',
      'shipping',
      'after_sales',
      'complaint'
    ])
    expect(store.scenarios.every(item => item.criteria.length >= 2)).toBe(true)

    expect(await store.start('after_sales')).toBe(true)
    expect(mockedApiFetch).toHaveBeenLastCalledWith(`${API_PREFIX}/sessions`, {
      method: 'POST',
      body: JSON.stringify({ scenario_key: 'after_sales' })
    })
    expect(store.current?.turns[0].customer_message).toContain('退')
    expect(store.pendingReply).toBe('')
    expect(store.history.map(item => item.id)).toEqual([7])
  })

  it('upserts current sessions without duplicate ids and sorts by latest update', () => {
    const store = useEcommerceCustomerServiceStore()
    store.history = [
      customerSession({
        id: 2,
        updated_at: '2026-09-17T09:00:00+08:00'
      }),
      customerSession({
        id: 1,
        updated_at: '2026-09-17T08:00:00+08:00'
      })
    ]

    store.replaceSession(
      customerSession({
        id: 1,
        updated_at: '2026-09-17T10:00:00+08:00'
      })
    )

    expect(store.history.map(item => item.id)).toEqual([1, 2])

    store.replaceSession(
      customerSession({
        id: 3,
        updated_at: '2026-09-17T07:00:00+08:00'
      })
    )

    expect(store.history.map(item => item.id)).toEqual([1, 2, 3])
    expect(store.current?.id).toBe(3)
  })

  it('runs the complete ordered multi-turn flow without ending automatically', async () => {
    const analyzed = customerSession({
      turns: [
        customerTurn(1, {
          student_reply: '请提供订单号',
          analysis: {
            problem: '尚未了解订单状态',
            evidence: '学员直接询问订单号',
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
    const nextTurn = customerSession({
      turns: [
        ...analyzed.turns,
        customerTurn(2)
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
            problem: '可以更明确说明凭证要求',
            evidence: '学员已说明拆封后可申请',
            suggestion: '补充订单和商品状态凭证',
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
        overall_performance: '整体能回应顾客问题',
        main_problems: ['首轮缺少共情'],
        prioritized_improvements: ['先确认订单情况'],
        goal_completion: '两项目标均已达成'
      },
      confirmed_at: '2026-09-17T08:03:00+08:00',
      completed_at: '2026-09-17T08:03:00+08:00'
    })
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, session: customerSession() } as never)
      .mockResolvedValueOnce({ success: true, session: analyzed } as never)
      .mockResolvedValueOnce({ success: true, session: nextTurn } as never)
      .mockResolvedValueOnce({ success: true, session: reached } as never)
      .mockResolvedValueOnce({ success: true, session: completed } as never)
    const store = useEcommerceCustomerServiceStore()

    await store.start('after_sales')
    expect(await store.submitReply('请提供订单号')).toBe(true)
    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      `${API_PREFIX}/sessions/7/replies`,
      {
        method: 'POST',
        body: JSON.stringify({ reply: '请提供订单号' })
      }
    )
    expect(store.current?.turns[0].analysis?.problem).toBeTruthy()
    expect(store.current?.turns[0].analysis?.goal_status).toBe('not_reached')
    expect(store.canContinue).toBe(true)
    expect(store.canEnd).toBe(false)

    expect(await store.nextMessage()).toBe(true)
    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      `${API_PREFIX}/sessions/7/next-message`,
      { method: 'POST' }
    )
    expect(store.current?.turns.map(turn => turn.customer_message)).toEqual([
      '这个商品拆封后还能退吗？',
      '那需要准备什么材料？'
    ])

    expect(await store.submitReply('拆封后可按流程申请')).toBe(true)
    expect(store.current?.end_suggested).toBe(true)
    expect(store.current?.status).toBe('goal_reached')
    expect(store.current?.status).not.toBe('completed')
    expect(store.canContinue).toBe(false)
    expect(store.canEnd).toBe(true)

    expect(await store.confirmEnd()).toBe(true)
    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      `${API_PREFIX}/sessions/7/end`,
      { method: 'POST' }
    )
    expect(store.current?.status).toBe('completed')
    expect(store.current?.summary?.goal_completion).toBe('两项目标均已达成')
  })

  it('does not fabricate the first customer message when generation fails', async () => {
    mockedApiFetch.mockRejectedValueOnce(new ApiError('provider timeout', 503))
    const store = useEcommerceCustomerServiceStore()

    expect(await store.start('after_sales')).toBe(false)

    expect(store.current).toBeNull()
    expect(store.history).toEqual([])
    expect(store.error).toBe('AI 服务暂时不可用')
  })

  it('maps only 503 or the exact AI message and leaves 401 to session handling', async () => {
    const store = useEcommerceCustomerServiceStore()
    store.current = customerSession()

    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('provider credentials leaked', 500)
    )
    expect(await store.submitReply('第一条回复')).toBe(false)
    expect(store.error).toBe('操作失败，请稍后重试')
    expect(store.error).not.toContain('credentials')

    store.pendingReply = ''
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('AI 服务暂时不可用', 500)
    )
    expect(await store.submitReply('第二条回复')).toBe(false)
    expect(store.error).toBe('AI 服务暂时不可用')

    store.pendingReply = ''
    mockedApiFetch.mockRejectedValueOnce(new ApiError('登录已过期', 401))
    expect(await store.submitReply('第三条回复')).toBe(false)
    expect(store.error).toBe('')
  })

  it('keeps the submitted reply pending when per-turn analysis fails', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, session: customerSession() } as never)
      .mockRejectedValueOnce(new ApiError('provider timeout', 503))
    const store = useEcommerceCustomerServiceStore()
    await store.start('after_sales')
    const transcriptBefore = JSON.parse(
      JSON.stringify(store.current?.turns)
    ) as CustomerSession['turns']

    expect(await store.submitReply('请提供订单号')).toBe(false)

    expect(store.current?.turns).toEqual(transcriptBefore)
    expect(store.current?.turns[0].student_reply).toBeNull()
    expect(store.current?.turns[0].analysis).toBeNull()
    expect(store.pendingReply).toBe('请提供订单号')
    expect(store.current?.status).toBe('active')
    expect(store.error).toBe('AI 服务暂时不可用')
  })

  it('does not send a second reply while the first reply is pending', async () => {
    let resolveReply!: (value: unknown) => void
    const analyzed = customerSession({
      turns: [
        customerTurn(1, {
          student_reply: '第一条回复',
          analysis: {
            problem: '尚未确认订单',
            evidence: '学员回复未包含订单信息',
            suggestion: '先确认订单情况',
            criteria: {
              确认订单情况: false,
              说明退换流程: false
            },
            goal_status: 'not_reached'
          }
        })
      ]
    })
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        session: customerSession()
      } as never)
      .mockImplementationOnce(
        () =>
          new Promise(resolve => {
            resolveReply = resolve
          })
      )
    const store = useEcommerceCustomerServiceStore()
    await store.start('after_sales')

    const pending = store.submitReply('第一条回复')
    expect(store.submitting).toBe(true)
    expect(await store.submitReply('第二条回复')).toBe(false)
    expect(
      mockedApiFetch.mock.calls.filter(
        ([url]) => url === `${API_PREFIX}/sessions/7/replies`
      )
    ).toHaveLength(1)
    expect(store.pendingReply).toBe('第一条回复')

    resolveReply({ success: true, session: analyzed } as never)
    expect(await pending).toBe(true)
    expect(store.pendingReply).toBe('')
  })

  it('keeps the complete transcript and retry action when customer-message generation fails', async () => {
    const analyzed = customerSession({
      turns: [
        customerTurn(1, {
          student_reply: '请提供订单号',
          analysis: {
            problem: '尚未了解订单状态',
            evidence: '学员询问订单号',
            suggestion: '先确认订单情况',
            criteria: {
              确认订单情况: true,
              说明退换流程: false
            },
            goal_status: 'not_reached'
          }
        })
      ]
    })
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, session: customerSession() } as never)
      .mockResolvedValueOnce({ success: true, session: analyzed } as never)
      .mockRejectedValueOnce(new ApiError('provider timeout', 503))
    const store = useEcommerceCustomerServiceStore()
    await store.start('after_sales')
    await store.submitReply('请提供订单号')
    const transcriptBefore = JSON.parse(
      JSON.stringify(store.current?.turns)
    ) as CustomerSession['turns']

    expect(await store.nextMessage()).toBe(false)

    expect(store.current?.turns).toEqual(transcriptBefore)
    expect(store.current?.turns).toHaveLength(1)
    expect(store.canContinue).toBe(true)
    expect(store.canEnd).toBe(false)
    expect(store.current?.status).toBe('active')
    expect(store.error).toBe('AI 服务暂时不可用')
  })

  it('keeps the session unfinished when summary generation fails', async () => {
    const reached = customerSession({
      status: 'goal_reached',
      end_suggested: true,
      turns: [
        customerTurn(1, {
          student_reply: '拆封后可按流程申请',
          analysis: {
            problem: '可以补充材料说明',
            evidence: '学员说明了退换方式',
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
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, session: customerSession() } as never)
      .mockResolvedValueOnce({ success: true, session: reached } as never)
      .mockRejectedValueOnce(new ApiError('provider timeout', 503))
    const store = useEcommerceCustomerServiceStore()
    await store.start('after_sales')
    await store.submitReply('拆封后可按流程申请')
    const transcriptBefore = JSON.parse(
      JSON.stringify(store.current?.turns)
    ) as CustomerSession['turns']

    expect(await store.confirmEnd()).toBe(false)

    expect(store.current?.turns).toEqual(transcriptBefore)
    expect(store.current?.status).toBe('goal_reached')
    expect(store.current?.summary).toBeNull()
    expect(store.current?.completed_at).toBeNull()
    expect(store.canEnd).toBe(true)
    expect(store.error).toBe('AI 服务暂时不可用')
  })

  it('loads session history and opens a historical transcript', async () => {
    const historical = customerSession({
      id: 9,
      status: 'completed',
      end_suggested: true,
      summary: {
        overall_performance: '表现稳定',
        main_problems: ['说明略简'],
        prioritized_improvements: ['补充政策依据'],
        goal_completion: '目标达成'
      },
      updated_at: '2026-09-17T09:00:00+08:00',
      completed_at: '2026-09-17T09:00:00+08:00'
    })
    const older = customerSession({
      id: 4,
      updated_at: '2026-09-17T08:00:00+08:00'
    })
    const newer = customerSession({
      id: 10,
      updated_at: '2026-09-17T10:00:00+08:00'
    })
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        sessions: [older, historical, newer]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        session: historical
      } as never)
    const store = useEcommerceCustomerServiceStore()

    expect(await store.loadHistory()).toBe(true)
    expect(mockedApiFetch).toHaveBeenLastCalledWith(`${API_PREFIX}/sessions`)
    expect(store.history.map(item => item.id)).toEqual([10, 9, 4])

    expect(await store.openSession(9)).toBe(true)
    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      `${API_PREFIX}/sessions/9`
    )
    expect(store.current?.id).toBe(9)
    expect(store.current?.status).toBe('completed')
    expect(store.history.map(item => item.id)).toEqual([10, 9, 4])
  })
})
