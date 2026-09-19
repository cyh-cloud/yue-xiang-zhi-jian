import { describe, expect, it } from 'vitest'

import router from './index'

const teacherConsolePaths = [
  '/teacher/courses',
  '/teacher/announcements',
  '/teacher/interactions',
  '/teacher/dashboard'
]

describe('teacher console routes', () => {
  it.each(teacherConsolePaths)(
    'registers %s under the teacher role guard',
    path => {
      expect(router.resolve(path).matched[0]?.meta).toMatchObject({
        requiresAuth: true,
        roles: ['teacher']
      })
    }
  )

  it('redirects the teacher root to the dashboard', () => {
    const matched = router.resolve('/teacher').matched
    expect(matched[matched.length - 1]?.redirect).toBe('/teacher/dashboard')
  })
})
