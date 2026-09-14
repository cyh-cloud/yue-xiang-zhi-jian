import type {
  NavigationGuardReturn,
  RouteLocationNormalized
} from 'vue-router'

import type { AuthUser, UserRole } from '@/api/types'

export interface AuthRouteMeta {
  requiresAuth?: boolean
  roles?: UserRole[]
}

export interface AuthRouteStore {
  sessionState: 'unknown' | 'anonymous' | 'pending' | 'active'
  user: AuthUser | null
  nextStep: 'interest-tags' | null
  isAuthenticated: boolean
  isPendingRegistration: boolean
  restoreSession: () => Promise<unknown>
}

const authPagePaths = new Set(['/login', '/register'])
const interestTagsPath = '/register/interest-tags'

export function roleDefaultPath(role: UserRole): string {
  if (role === 'super_admin' || role === 'admin') return '/admin'
  return `/${role}`
}

function loginRedirect(fullPath: string): string {
  return `/login?redirect=${encodeURIComponent(fullPath)}`
}

export async function authGuard(
  to: RouteLocationNormalized,
  auth: AuthRouteStore
): Promise<NavigationGuardReturn> {
  if (auth.sessionState === 'unknown') {
    await auth.restoreSession()
  }

  if (auth.isPendingRegistration) {
    return to.path === interestTagsPath ? true : interestTagsPath
  }

  if (to.path === interestTagsPath) {
    return auth.isAuthenticated && auth.user
      ? roleDefaultPath(auth.user.role)
      : loginRedirect(to.fullPath)
  }

  if (authPagePaths.has(to.path)) {
    return auth.isAuthenticated && auth.user
      ? roleDefaultPath(auth.user.role)
      : true
  }

  const meta = to.meta as AuthRouteMeta
  if (!meta.requiresAuth) {
    return true
  }

  if (!auth.isAuthenticated || !auth.user) {
    return loginRedirect(to.fullPath)
  }

  if (meta.roles?.length && !meta.roles.includes(auth.user.role)) {
    return roleDefaultPath(auth.user.role)
  }

  return true
}
