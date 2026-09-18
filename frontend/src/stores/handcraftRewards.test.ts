import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'
import type {
  HandcraftVerification,
  HandcraftRedemption,
  HandcraftRedemptionHistory
} from '@/api/types'

import { useHandcraftRewardsStore } from './handcraftRewards'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const reward = {
  reward_id: 'reward-guangxiu-bookmark',
  name: '广绣书签',
  points_cost: 30,
  stock: 9,
  is_online: true,
  is_demo: true,
  source_available: true,
  affordable: true,
  can_redeem: true,
  unavailable_reason: null
}

const redemption = {
  id: 12,
  user_id: 1,
  reward_id: reward.reward_id,
  reward_name: reward.name,
  reward,
  points_cost: 30,
  request_id: 'request-1',
  status: 'pending',
  reservation_status: 'reserved',
  created_at: '2026-09-18T09:00:00+08:00',
  updated_at: '2026-09-18T09:00:00+08:00',
  canceled_at: null
} satisfies HandcraftRedemption

const fulfillment = {
  fulfillment: {
    id: 5,
    redemption_id: 12,
    status: 'pending',
    issued_at: null,
    verified_at: null,
    canceled_at: null,
    created_at: '2026-09-18T09:00:00+08:00',
    updated_at: '2026-09-18T09:00:00+08:00'
  },
  redemption: {
    id: 12,
    reward_id: reward.reward_id,
    reward_name: reward.name,
    points_cost: 30,
    request_id: 'request-1',
    status: 'pending',
    created_at: '2026-09-18T09:00:00+08:00',
    updated_at: '2026-09-18T09:00:00+08:00'
  },
  stock_reservation: {
    reservation_id: '12',
    status: 'reserved'
  },
  status: 'pending',
  restored_points: 0
} satisfies HandcraftRedemptionHistory

const issuedFulfillment = {
  ...fulfillment,
  fulfillment: {
    ...fulfillment.fulfillment,
    status: 'issued',
    issued_at: '2026-09-18T10:00:00+08:00',
    updated_at: '2026-09-18T10:00:00+08:00'
  },
  redemption: {
    ...fulfillment.redemption,
    status: 'issued',
    updated_at: '2026-09-18T10:00:00+08:00'
  },
  status: 'issued'
} satisfies HandcraftRedemptionHistory

describe('handcraftRewards store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('loads rewards and redemption history from their route payloads', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        rewards: [reward]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        redemptions: [redemption],
        fulfillments: [fulfillment]
      } as never)
    const store = useHandcraftRewardsStore()

    expect(await store.loadRewards()).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/handcraft-inheritance/rewards'
    )
    expect(store.rewards[0].can_redeem).toBe(true)

    expect(await store.loadRedemptions()).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/handcraft-inheritance/redemptions'
    )
    expect(store.redemptions[0].request_id).toBe('request-1')
    expect(store.fulfillments[0].stock_reservation.status).toBe('reserved')
  })

  it('posts a redemption with the exact reward and request identifiers', async () => {
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      redemption
    } as never)
    const store = useHandcraftRewardsStore()

    expect(
      await store.redeem('reward-guangxiu-bookmark', 'request-1')
    ).toBe(true)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/handcraft-inheritance/redemptions',
      {
        method: 'POST',
        body: JSON.stringify({
          reward_id: 'reward-guangxiu-bookmark',
          request_id: 'request-1'
        })
      }
    )
    expect(store.redemptions[0].id).toBe(12)
  })

  it('cancels a pending redemption and replaces its fulfillment state', async () => {
    const cancellation = {
      fulfillment_id: 5,
      redemption_id: 12,
      user_id: 1,
      status: 'canceled',
      changed: true,
      issued_at: null,
      verified_at: null,
      canceled_at: '2026-09-18T10:00:00+08:00',
      points_cost: 30,
      restored_points: 30,
      outbox_id: 4,
      notification_type: 'cancelled',
      notification: null
    }
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      cancellation
    } as never)
    const store = useHandcraftRewardsStore()
    store.redemptions = [redemption]
    store.fulfillments = [fulfillment]

    expect(await store.cancelRedemption(12)).toBe(true)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/handcraft-inheritance/redemptions/12/cancel',
      { method: 'POST' }
    )
    expect(store.redemptions[0].status).toBe('canceled')
    expect(store.fulfillments[0].status).toBe('canceled')
    expect(store.fulfillments[0].restored_points).toBe(30)
  })

  it('verifies an issued fulfillment and replaces both state projections', async () => {
    const verification = {
      fulfillment_id: 5,
      redemption_id: 12,
      user_id: 1,
      status: 'verified',
      changed: true,
      issued_at: '2026-09-18T10:00:00+08:00',
      verified_at: '2026-09-18T11:00:00+08:00',
      canceled_at: null,
      points_cost: 30,
      restored_points: 0,
      outbox_id: null,
      notification_type: null,
      notification: null
    } satisfies HandcraftVerification
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      verification
    } as never)
    const store = useHandcraftRewardsStore()
    store.redemptions = [
      { ...redemption, status: 'issued' }
    ]
    store.fulfillments = [issuedFulfillment]

    expect(await store.verifyRedemption(12)).toBe(true)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/handcraft-inheritance/redemptions/12/verify',
      { method: 'POST' }
    )
    expect(store.redemptions[0].status).toBe('verified')
    expect(store.fulfillments[0].status).toBe('verified')
    expect(store.fulfillments[0].fulfillment.verified_at).toBe(
      '2026-09-18T11:00:00+08:00'
    )
  })

  it('keeps history errors separate from action errors', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new Error('history unavailable')
    )
    const store = useHandcraftRewardsStore()

    expect(await store.loadRedemptions()).toBe(false)
    expect(store.historyError).toBe('history unavailable')
    expect(store.error).toBe('')
  })
})
