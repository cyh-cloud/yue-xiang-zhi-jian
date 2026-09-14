import type { ApiError } from './client'
import { setSessionExpiredHandler } from './client'
import type { Router } from 'vue-router'

interface SessionExpiryAuthStore {
  sessionState: 'unknown' | 'anonymous' | 'pending' | 'active'
  isAuthenticated: boolean
  isPendingRegistration: boolean
  clearSession: () => void
}

export function installSessionExpiredHandler(
  auth: SessionExpiryAuthStore,
  router: Router
): () => void {
  return setSessionExpiredHandler(async (error: ApiError) => {
    if (error.status !== 401 || !error.redirect) {
      return
    }
    if (!auth.isAuthenticated && !auth.isPendingRegistration) {
      return
    }

    const currentRoute = router.currentRoute.value.fullPath
    if (!currentRoute.startsWith('/')) {
      return
    }

    auth.clearSession()
    await router.push({
      path: '/login',
      query: { redirect: currentRoute }
    })
  })
}
