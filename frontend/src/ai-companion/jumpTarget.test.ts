import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'

import { canUseAiCompanion, resolveCompanionJumpTarget } from './jumpTarget'

describe('canUseAiCompanion', () => {
  it('allows exactly four non-admin roles', () => {
    expect(canUseAiCompanion('student')).toBe(true)
    expect(canUseAiCompanion('teacher')).toBe(true)
    expect(canUseAiCompanion('enterprise')).toBe(true)
    expect(canUseAiCompanion('government')).toBe(true)
    expect(canUseAiCompanion('super_admin')).toBe(false)
    expect(canUseAiCompanion('admin')).toBe(false)
    expect(canUseAiCompanion(undefined)).toBe(false)
  })
})

describe('resolveCompanionJumpTarget', () => {
  it('accepts only internal routes allowed for the current role', () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/student/employment/jobs',
          component: { template: '<div />' },
          meta: { requiresAuth: true, roles: ['student'] }
        },
        {
          path: '/teacher/courses',
          component: { template: '<div />' },
          meta: { requiresAuth: true, roles: ['teacher'] }
        }
      ]
    })
    expect(
      resolveCompanionJumpTarget(router, 'student', '/student/employment/jobs')
    ).toBe('/student/employment/jobs')
    expect(
      resolveCompanionJumpTarget(router, 'student', '/teacher/courses')
    ).toBeNull()
    expect(
      resolveCompanionJumpTarget(router, 'student', 'https://evil.example')
    ).toBeNull()
    expect(
      resolveCompanionJumpTarget(router, 'student', '/missing')
    ).toBeNull()
  })
})
