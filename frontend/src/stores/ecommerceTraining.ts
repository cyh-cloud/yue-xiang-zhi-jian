import { defineStore } from 'pinia'

import { ApiError } from '@/api/client'

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : fallback
}

export const useEcommerceTrainingStore = defineStore('ecommerceTraining', {
  state: () => ({
    loading: false,
    error: ''
  }),
  actions: {
    startLoading() {
      this.loading = true
      this.error = ''
    },
    stopLoading() {
      this.loading = false
    },
    setError(error: unknown, fallback = '操作失败') {
      this.error = errorMessage(error, fallback)
    },
    clearError() {
      this.error = ''
    }
  }
})
