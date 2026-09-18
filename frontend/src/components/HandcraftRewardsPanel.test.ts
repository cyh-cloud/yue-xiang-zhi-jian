import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type {
  HandcraftFulfillmentStatus,
  HandcraftRedemption,
  HandcraftRedemptionHistory,
  HandcraftReward,
  HandcraftVerification
} from '@/api/types'

import HandcraftRewardsPanel from './HandcraftRewardsPanel.vue'
import handcraftRewardsPanelSource from './HandcraftRewardsPanel.vue?raw'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function reward(overrides: Partial<HandcraftReward> = {}): HandcraftReward {
  return {
    reward_id: 'reward-1',
    name: '广绣书签',
    points_cost: 30,
    stock: 5,
    is_online: true,
    is_demo: true,
    source_available: true,
    affordable: true,
    can_redeem: true,
    unavailable_reason: null,
    ...overrides
  }
}

function redemption(
  id: number,
  status: HandcraftFulfillmentStatus = 'pending',
  rewardId = 'reward-1'
): HandcraftRedemption {
  return {
    id,
    user_id: 1,
    reward_id: rewardId,
    reward_name: '广绣书签',
    reward: {
      reward_id: rewardId,
      name: '广绣书签',
      points_cost: 30,
      stock: 5,
      is_online: true,
      is_demo: true,
      source_available: true
    },
    points_cost: 30,
    request_id: `request-${id}`,
    status,
    reservation_status: status === 'canceled' ? 'released' : 'reserved',
    created_at: '2026-09-18T09:00:00+08:00',
    updated_at: '2026-09-18T09:00:00+08:00',
    canceled_at:
      status === 'canceled' ? '2026-09-18T10:00:00+08:00' : null
  }
}

function fulfillment(
  id: number,
  status: HandcraftFulfillmentStatus
): HandcraftRedemptionHistory {
  const record = redemption(id, status)
  return {
    fulfillment: {
      id: id + 100,
      redemption_id: id,
      status,
      issued_at:
        status === 'issued' || status === 'verified'
          ? '2026-09-18T11:00:00+08:00'
          : null,
      verified_at:
        status === 'verified' ? '2026-09-18T12:00:00+08:00' : null,
      canceled_at:
        status === 'canceled' ? '2026-09-18T10:00:00+08:00' : null,
      created_at: record.created_at,
      updated_at: record.updated_at
    },
    redemption: {
      id: record.id,
      reward_id: record.reward_id,
      reward_name: record.reward_name,
      points_cost: record.points_cost,
      request_id: record.request_id,
      status,
      created_at: record.created_at,
      updated_at: record.updated_at
    },
    stock_reservation: {
      reservation_id: String(id),
      status: status === 'canceled' ? 'released' : 'reserved'
    },
    status,
    restored_points: status === 'canceled' ? 30 : 0
  }
}

function cssRule(css: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(
    new RegExp(
      `(?:^|[{}])\\s*[^{}]*?${escaped}[^{}]*?\\s*\\{([\\s\\S]*?)\\}`
    )
  )
  expect(match).not.toBeNull()
  return (match?.[1] ?? '').replace(/\s+/g, ' ').trim()
}

function mountPanel() {
  return mount(HandcraftRewardsPanel, {
    global: {
      plugins: [createPinia()]
    }
  })
}

function mockCatalog(
  rewards: HandcraftReward[],
  fulfillments: HandcraftRedemptionHistory[] = []
) {
  mockedApiFetch.mockImplementation(async (path, options) => {
    if (
      path === '/api/handcraft-inheritance/rewards' &&
      !options?.method
    ) {
      return { success: true, rewards } as never
    }
    if (
      path === '/api/handcraft-inheritance/redemptions' &&
      !options?.method
    ) {
      return {
        success: true,
        redemptions: fulfillments.map(item => item.redemption),
        fulfillments
      } as never
    }
    throw new Error(`Unexpected request: ${path}`)
  })
}

describe('HandcraftRewardsPanel', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('shows insufficient points and does not allow redemption', async () => {
    mockCatalog([
      reward({
        affordable: false,
        can_redeem: false,
        unavailable_reason: '积分不足，还差 20 分'
      })
    ])

    const wrapper = mountPanel()
    await flushPromises()

    const card = wrapper.get('[data-test="reward-reward-1"]')
    expect(card.text()).toContain('积分不足，还差 20 分')
    expect(
      card.get('[data-test="redeem-reward-1"]').attributes('disabled')
    ).toBeDefined()
    expect(wrapper.find('[data-test="redeem-confirmation"]').exists()).toBe(
      false
    )
  })

  it('marks an offline reward non-selectable', async () => {
    mockCatalog([
      reward({
        is_online: false,
        affordable: true,
        can_redeem: false,
        unavailable_reason: '奖品已下架'
      })
    ])

    const wrapper = mountPanel()
    await flushPromises()

    const card = wrapper.get('[data-test="reward-reward-1"]')
    expect(card.text()).toContain('已下架')
    expect(
      card.get('[data-test="redeem-reward-1"]').attributes('disabled')
    ).toBeDefined()
  })

  it('marks zero-stock rewards non-selectable as sold out', async () => {
    mockCatalog([
      reward({
        stock: 0,
        can_redeem: false,
        unavailable_reason: '已抢完'
      })
    ])

    const wrapper = mountPanel()
    await flushPromises()

    const card = wrapper.get('[data-test="reward-reward-1"]')
    expect(card.text()).toContain('已抢完')
    expect(
      card.get('[data-test="redeem-reward-1"]').attributes('disabled')
    ).toBeDefined()
  })

  it('requires confirmation and shows successful redemption', async () => {
    const pending = redemption(12)
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (
        path === '/api/handcraft-inheritance/rewards' &&
        !options?.method
      ) {
        return { success: true, rewards: [reward()] } as never
      }
      if (
        path === '/api/handcraft-inheritance/redemptions' &&
        !options?.method
      ) {
        return {
          success: true,
          redemptions: [],
          fulfillments: []
        } as never
      }
      if (
        path === '/api/handcraft-inheritance/redemptions' &&
        options?.method === 'POST'
      ) {
        return { success: true, redemption: pending } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.get('[data-test="redeem-reward-1"]').trigger('click')

    expect(wrapper.get('[data-test="redeem-confirmation"]').text()).toContain(
      '广绣书签'
    )
    expect(
      mockedApiFetch.mock.calls.filter(
        ([path, options]) =>
          path === '/api/handcraft-inheritance/redemptions' &&
          options?.method === 'POST'
      )
    ).toHaveLength(0)

    await wrapper
      .get('[data-test="confirm-redeem-reward-1"]')
      .trigger('click')
    await flushPromises()

    const postCalls = mockedApiFetch.mock.calls.filter(
      ([path, options]) =>
        path === '/api/handcraft-inheritance/redemptions' &&
        options?.method === 'POST'
    )
    expect(postCalls).toHaveLength(1)
    const body = JSON.parse(String(postCalls[0][1]?.body))
    expect(body).toMatchObject({ reward_id: 'reward-1' })
    expect(body.request_id).toEqual(expect.any(String))
    expect(wrapper.get('[data-test="redemption-success"]').text()).toContain(
      '兑换成功'
    )
  })

  it('displays the exact conflict message without retrying', async () => {
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (
        path === '/api/handcraft-inheritance/rewards' &&
        !options?.method
      ) {
        return { success: true, rewards: [reward()] } as never
      }
      if (
        path === '/api/handcraft-inheritance/redemptions' &&
        !options?.method
      ) {
        return {
          success: true,
          redemptions: [],
          fulfillments: []
        } as never
      }
      if (
        path === '/api/handcraft-inheritance/redemptions' &&
        options?.method === 'POST'
      ) {
        throw new ApiError('库存或积分已变化，请刷新后重试', 409)
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.get('[data-test="redeem-reward-1"]').trigger('click')
    await wrapper
      .get('[data-test="confirm-redeem-reward-1"]')
      .trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="rewards-action-error"]').text()).toBe(
      '库存或积分已变化，请刷新后重试'
    )
    expect(
      mockedApiFetch.mock.calls.filter(
        ([path, options]) =>
          path === '/api/handcraft-inheritance/redemptions' &&
          options?.method === 'POST'
      )
    ).toHaveLength(1)
  })

  it('renders pending, issued, verified and canceled fulfillment states', async () => {
    mockCatalog(
      [],
      [
        fulfillment(11, 'pending'),
        fulfillment(12, 'issued'),
        fulfillment(13, 'verified'),
        fulfillment(14, 'canceled')
      ]
    )

    const wrapper = mountPanel()
    await flushPromises()

    expect(
      wrapper
        .findAll('[data-test="redemption-status"]')
        .map(item => item.text())
    ).toEqual(['待发放', '已发放', '已核销', '已取消'])
    expect(
      wrapper.find('[data-test="cancel-redemption-11"]').exists()
    ).toBe(true)
    expect(
      wrapper.find('[data-test="cancel-redemption-12"]').exists()
    ).toBe(false)
    expect(
      wrapper.find('[data-test="verify-redemption-12"]').exists()
    ).toBe(true)
    expect(
      wrapper.find('[data-test="auto-verify-redemption"]').exists()
    ).toBe(false)
  })

  it('cancels a pending redemption through the store action once', async () => {
    const pending = redemption(11)
    let rewardsLoads = 0
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (
        path === '/api/handcraft-inheritance/rewards' &&
        !options?.method
      ) {
        rewardsLoads += 1
        return {
          success: true,
          rewards: rewardsLoads === 1 ? [] : [reward()]
        } as never
      }
      if (
        path === '/api/handcraft-inheritance/redemptions' &&
        !options?.method
      ) {
        return {
          success: true,
          redemptions: [pending],
          fulfillments: [fulfillment(11, 'pending')]
        } as never
      }
      if (
        path === '/api/handcraft-inheritance/redemptions/11/cancel' &&
        options?.method === 'POST'
      ) {
        return {
          success: true,
          cancellation: {
            fulfillment_id: 111,
            redemption_id: 11,
            user_id: 1,
            status: 'canceled',
            changed: true,
            issued_at: null,
            verified_at: null,
            canceled_at: '2026-09-18T10:00:00+08:00',
            points_cost: 30,
            restored_points: 30,
            outbox_id: null,
            notification_type: 'cancelled',
            notification: null
          }
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = mountPanel()
    await flushPromises()
    await wrapper
      .get('[data-test="cancel-redemption-11"]')
      .trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="redemption-status"]').text()).toBe(
      '已取消'
    )
    expect(
      wrapper.get('[data-test="redeem-reward-1"]').attributes('disabled')
    ).toBeUndefined()
    expect(rewardsLoads).toBe(2)
    expect(
      mockedApiFetch.mock.calls.filter(
        ([path, options]) =>
          path === '/api/handcraft-inheritance/redemptions/11/cancel' &&
          options?.method === 'POST'
      )
    ).toHaveLength(1)
  })

  it('retries only redemption history when the catalog already loaded', async () => {
    let historyAttempts = 0
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (
        path === '/api/handcraft-inheritance/rewards' &&
        !options?.method
      ) {
        return { success: true, rewards: [reward()] } as never
      }
      if (
        path === '/api/handcraft-inheritance/redemptions' &&
        !options?.method
      ) {
        historyAttempts += 1
        if (historyAttempts === 1) {
          throw new ApiError('兑换记录加载失败', 503)
        }
        return {
          success: true,
          redemptions: [],
          fulfillments: []
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.get('[data-test="fulfillment-error"]').text()).toContain(
      '兑换记录加载失败'
    )
    expect(wrapper.find('[data-test="fulfillment-empty"]').exists()).toBe(false)
    const rewardsCallsBeforeRetry = mockedApiFetch.mock.calls.filter(
      ([path, options]) =>
        path === '/api/handcraft-inheritance/rewards' &&
        !options?.method
    ).length

    await wrapper.get('[data-test="fulfillment-retry"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="fulfillment-error"]').exists()).toBe(false)
    expect(wrapper.get('[data-test="fulfillment-empty"]').text()).toBe(
      '暂无兑换记录'
    )
    expect(
      mockedApiFetch.mock.calls.filter(
        ([path, options]) =>
          path === '/api/handcraft-inheritance/rewards' &&
          !options?.method
      )
    ).toHaveLength(rewardsCallsBeforeRetry)
    expect(historyAttempts).toBe(2)
  })

  it('keeps a cancellation error visible with an empty catalog', async () => {
    const pending = redemption(11)
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (
        path === '/api/handcraft-inheritance/rewards' &&
        !options?.method
      ) {
        return { success: true, rewards: [] } as never
      }
      if (
        path === '/api/handcraft-inheritance/redemptions' &&
        !options?.method
      ) {
        return {
          success: true,
          redemptions: [pending],
          fulfillments: [fulfillment(11, 'pending')]
        } as never
      }
      if (
        path === '/api/handcraft-inheritance/redemptions/11/cancel' &&
        options?.method === 'POST'
      ) {
        throw new ApiError('取消兑换失败', 409)
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = mountPanel()
    await flushPromises()
    await wrapper
      .get('[data-test="cancel-redemption-11"]')
      .trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="rewards-action-error"]').text()).toContain(
      '取消兑换失败'
    )
  })

  it('verifies an issued fulfillment with one click and no confirmation', async () => {
    const verification = {
      fulfillment_id: 112,
      redemption_id: 12,
      user_id: 1,
      status: 'verified',
      changed: true,
      issued_at: '2026-09-18T11:00:00+08:00',
      verified_at: '2026-09-18T12:00:00+08:00',
      canceled_at: null,
      points_cost: 30,
      restored_points: 0,
      outbox_id: null,
      notification_type: null,
      notification: null
    } satisfies HandcraftVerification
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (
        path === '/api/handcraft-inheritance/rewards' &&
        !options?.method
      ) {
        return { success: true, rewards: [] } as never
      }
      if (
        path === '/api/handcraft-inheritance/redemptions' &&
        !options?.method
      ) {
        return {
          success: true,
          redemptions: [redemption(12, 'issued')],
          fulfillments: [fulfillment(12, 'issued')]
        } as never
      }
      if (
        path === '/api/handcraft-inheritance/redemptions/12/verify' &&
        options?.method === 'POST'
      ) {
        return { success: true, verification } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = mountPanel()
    await flushPromises()
    expect(
      wrapper.find('[data-test="confirm-verify-redemption-12"]').exists()
    ).toBe(false)

    await wrapper
      .get('[data-test="verify-redemption-12"]')
      .trigger('click')
    await flushPromises()

    expect(
      mockedApiFetch.mock.calls.filter(
        ([path, options]) =>
          path === '/api/handcraft-inheritance/redemptions/12/verify' &&
          options?.method === 'POST'
      )
    ).toHaveLength(1)
    expect(wrapper.get('[data-test="redemption-status"]').text()).toBe(
      '已核销'
    )
    expect(wrapper.get('[data-test="redemption-success"]').text()).toContain(
      '确认收货成功'
    )
  })

  it('shows catalog errors without fabricating rewards', async () => {
    mockedApiFetch.mockRejectedValue(
      new ApiError('积分规则暂不可用，请稍后重试', 503)
    )

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.get('[data-test="rewards-error"]').text()).toContain(
      '积分规则暂不可用，请稍后重试'
    )
    expect(wrapper.find('[data-test="reward-reward-1"]').exists()).toBe(false)
  })

  it('keeps CSS tokenized, focus-visible, portrait-ready and CJK-safe', () => {
    expect(handcraftRewardsPanelSource).not.toMatch(
      /#[0-9a-f]{3,8}|rgba?\(|hsla?\(|rgb\(24\s+209\s+255/i
    )
    expect(handcraftRewardsPanelSource).toContain(
      '@media (max-width: 760px), (orientation: portrait)'
    )
    expect(
      cssRule(
        handcraftRewardsPanelSource,
        '.rewards-panel :is(button, a):focus-visible'
      )
    ).toContain('outline: 2px solid var(--ark-focus)')
    expect(
      cssRule(handcraftRewardsPanelSource, '.reward-card__state')
    ).toContain('white-space: nowrap')
    expect(
      cssRule(handcraftRewardsPanelSource, '.reward-card__state')
    ).not.toContain('overflow-wrap: anywhere')
  })
})
