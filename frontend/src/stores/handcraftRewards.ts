import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type {
  HandcraftCancellation,
  HandcraftRedemption,
  HandcraftRedemptionHistory,
  HandcraftReward,
  HandcraftVerification
} from '@/api/types'

const API_PREFIX = '/api/handcraft-inheritance'

interface HandcraftRewardsState {
  rewards: HandcraftReward[]
  redemptions: HandcraftRedemption[]
  fulfillments: HandcraftRedemptionHistory[]
  loading: boolean
  redeeming: boolean
  canceling: boolean
  verifying: boolean
  catalogError: string
  historyError: string
  error: string
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : fallback
}

export const useHandcraftRewardsStore = defineStore(
  'handcraftRewards',
  {
    state: (): HandcraftRewardsState => ({
      rewards: [],
      redemptions: [],
      fulfillments: [],
      loading: false,
      redeeming: false,
      canceling: false,
      verifying: false,
      catalogError: '',
      historyError: '',
      error: ''
    }),
    actions: {
      async loadRewards(): Promise<boolean> {
        this.loading = true
        this.catalogError = ''
        try {
          const response = await apiFetch<{
            success: true
            rewards: HandcraftReward[]
          }>(`${API_PREFIX}/rewards`)
          this.rewards = response.rewards
          return true
        } catch (error) {
          this.catalogError = errorMessage(error, '奖品列表加载失败')
          return false
        } finally {
          this.loading = false
        }
      },
      async loadRedemptions(): Promise<boolean> {
        this.loading = true
        this.historyError = ''
        try {
          const response = await apiFetch<{
            success: true
            redemptions: HandcraftRedemption[]
            fulfillments: HandcraftRedemptionHistory[]
          }>(`${API_PREFIX}/redemptions`)
          this.redemptions = response.redemptions
          this.fulfillments = response.fulfillments
          return true
        } catch (error) {
          this.historyError = errorMessage(error, '兑换记录加载失败')
          return false
        } finally {
          this.loading = false
        }
      },
      async redeem(
        rewardId: string,
        requestId: string
      ): Promise<boolean> {
        this.redeeming = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            redemption: HandcraftRedemption
          }>(`${API_PREFIX}/redemptions`, {
            method: 'POST',
            body: JSON.stringify({
              reward_id: rewardId,
              request_id: requestId
            })
          })
          this.redemptions = [
            response.redemption,
            ...this.redemptions.filter(
              item => item.id !== response.redemption.id
            )
          ]
          return true
        } catch (error) {
          this.error = errorMessage(error, '兑换失败，请刷新后重试')
          return false
        } finally {
          this.redeeming = false
        }
      },
      async cancelRedemption(redemptionId: number): Promise<boolean> {
        this.canceling = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            cancellation: HandcraftCancellation
          }>(
            `${API_PREFIX}/redemptions/${redemptionId}/cancel`,
            { method: 'POST' }
          )
          const cancellation = response.cancellation
          this.redemptions = this.redemptions.map(item =>
            item.id === redemptionId
              ? {
                  ...item,
                  status: cancellation.status,
                  canceled_at: cancellation.canceled_at,
                  updated_at:
                    cancellation.canceled_at ?? item.updated_at
                }
              : item
          )
          this.fulfillments = this.fulfillments.map(item =>
            item.redemption.id === redemptionId
              ? {
                  ...item,
                  status: cancellation.status,
                  restored_points: cancellation.restored_points,
                  fulfillment: {
                    ...item.fulfillment,
                    status: cancellation.status,
                    canceled_at: cancellation.canceled_at,
                    updated_at:
                      cancellation.canceled_at ??
                      item.fulfillment.updated_at
                  }
                }
              : item
          )
          return true
        } catch (error) {
          this.error = errorMessage(error, '取消兑换失败')
          return false
        } finally {
          this.canceling = false
        }
      },
      async verifyRedemption(redemptionId: number): Promise<boolean> {
        this.verifying = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            verification: HandcraftVerification
          }>(
            `${API_PREFIX}/redemptions/${redemptionId}/verify`,
            { method: 'POST' }
          )
          const verification = response.verification
          const verifiedAt =
            verification.verified_at ?? verification.issued_at
          this.redemptions = this.redemptions.map(item =>
            item.id === redemptionId
              ? {
                  ...item,
                  status: verification.status,
                  updated_at: verifiedAt ?? item.updated_at
                }
              : item
          )
          this.fulfillments = this.fulfillments.map(item =>
            item.redemption.id === redemptionId
              ? {
                  ...item,
                  status: verification.status,
                  fulfillment: {
                    ...item.fulfillment,
                    status: verification.status,
                    verified_at: verification.verified_at,
                    updated_at: verifiedAt ?? item.fulfillment.updated_at
                  }
                }
              : item
          )
          return true
        } catch (error) {
          this.error = errorMessage(error, '确认收货失败')
          return false
        } finally {
          this.verifying = false
        }
      },
      clearError() {
        this.error = ''
      }
    }
  }
)
