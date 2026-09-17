import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type {
  HandcraftLedgerEntry,
  HandcraftPointsAccount
} from '@/api/types'

const API_PREFIX = '/api/handcraft-inheritance'

interface HandcraftPointsState {
  account: HandcraftPointsAccount | null
  ledger: HandcraftLedgerEntry[]
  loading: boolean
  error: string
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : fallback
}

export const useHandcraftPointsStore = defineStore('handcraftPoints', {
  state: (): HandcraftPointsState => ({
    account: null,
    ledger: [],
    loading: false,
    error: ''
  }),
  actions: {
    async loadAccount(): Promise<boolean> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<{
          success: true
          account: HandcraftPointsAccount
        }>(`${API_PREFIX}/points`)
        this.account = response.account
        return true
      } catch (error) {
        this.error = errorMessage(error, '积分账户加载失败')
        return false
      } finally {
        this.loading = false
      }
    },
    async loadLedger(): Promise<boolean> {
      this.loading = true
      this.error = ''
      try {
        const response = await apiFetch<{
          success: true
          ledger: HandcraftLedgerEntry[]
        }>(`${API_PREFIX}/points/ledger`)
        this.ledger = response.ledger
        return true
      } catch (error) {
        this.error = errorMessage(error, '积分流水加载失败')
        return false
      } finally {
        this.loading = false
      }
    },
    clearError() {
      this.error = ''
    }
  }
})
