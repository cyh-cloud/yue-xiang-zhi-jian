import type { Router } from 'vue-router'

import type { UserRole } from '@/api/types'
import type { AuthRouteMeta } from '@/router/roleRoutes'

export const AI_COMPANION_ROLES: ReadonlySet<UserRole> = new Set<UserRole>([
  'student',
  'teacher',
  'enterprise',
  'government'
])

const ABSOLUTE_URL_PATTERN = /^[a-zA-Z][a-zA-Z0-9+.-]*:/

// Role-only predicate: it must never read the current route or route meta.
export function canUseAiCompanion(role: UserRole | null | undefined): boolean {
  return role != null && AI_COMPANION_ROLES.has(role)
}

// The only frontend place allowed to read route meta.roles, and only to
// validate an explicit jump_target for the current role. It never feeds the
// AI companion entry visibility decision.
export function resolveCompanionJumpTarget(
  router: Router,
  role: UserRole | null | undefined,
  target: string | null | undefined
): string | null {
  if (typeof target !== 'string') return null

  const trimmed = target.trim()
  if (!trimmed) return null
  if (trimmed.startsWith('//')) return null
  if (ABSOLUTE_URL_PATTERN.test(trimmed)) return null
  if (trimmed.includes('\\')) return null

  const resolved = router.resolve(target)
  if (resolved.matched.length === 0) return null

  const meta = resolved.meta as AuthRouteMeta
  if (meta.roles && !(role && meta.roles.includes(role))) return null

  return resolved.fullPath
}
