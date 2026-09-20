import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { ApiError } from '@/api/client'
import type {
  AdminConsoleRole,
  AdminDashboard
} from '@/api/types'
import { useAuthStore } from '@/stores/auth'

export const useAdminConsoleStore = defineStore('adminConsole', () => {
  const auth = useAuthStore()
  const dashboard = ref<AdminDashboard | null>(null)
  const loading = ref(false)
  const error = ref('')

  const role = computed<AdminConsoleRole>(() =>
    auth.user?.role === 'super_admin' ? 'super_admin' : 'admin'
  )
  const canManagePlatform = computed(() => role.value === 'super_admin')

  function captureError(caught: unknown, fallback: string) {
    error.value =
      caught instanceof ApiError
        ? caught.message
        : caught instanceof Error
          ? caught.message
          : fallback
  }

  function clearError() {
    error.value = ''
  }

  return {
    dashboard,
    loading,
    error,
    role,
    canManagePlatform,
    captureError,
    clearError
  }
})
