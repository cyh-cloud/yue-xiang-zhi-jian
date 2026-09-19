import { describe, expect, it } from 'vitest'

import localResourcesHomeSource from '@/views/LocalResourcesHomeView.vue?raw'

import router from './index'

const expectedRoutes = [
  ['/student/local-resources', 'local-resources-home'],
  ['/student/local-resources/dialect', 'local-resources-dialect'],
  ['/student/local-resources/cases', 'local-resources-cases'],
  ['/student/local-resources/cases/:caseId', 'local-resources-case-detail'],
  ['/student/local-resources/policies', 'local-resources-policies'],
  ['/student/local-resources/policies/:policyId', 'local-resources-policy-detail'],
  ['/student/local-resources/news', 'local-resources-news'],
  ['/student/local-resources/news/:newsId', 'local-resources-news-detail']
] as const

describe('local resources routes', () => {
  it('registers every route for students only', () => {
    for (const [path, name] of expectedRoutes) {
      const concretePath = path
        .replace(':caseId', 'case-1')
        .replace(':policyId', 'policy-1')
        .replace(':newsId', 'news-1')
      expect(router.resolve(concretePath)).toMatchObject({
        name,
        meta: { requiresAuth: true, roles: ['student'] }
      })
    }
  })

  it('uses the explicit light surface and ink foreground tokens on home', () => {
    const rootRule =
      localResourcesHomeSource.match(/\.local-resources-home \{[^}]*\}/)?.[0] ??
      ''
    const entryRule =
      localResourcesHomeSource.match(
        /\.local-resources-home__entry \{[^}]*\}/
      )?.[0] ?? ''

    expect(rootRule).toContain('background: var(--ark-surface-0)')
    expect(entryRule).toContain('color: var(--ark-paper)')
  })
})
