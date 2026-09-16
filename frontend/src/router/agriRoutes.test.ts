import { describe, expect, it } from 'vitest'

import { portalDefinitions } from '@/data/portal-guides'

import router from './index'

const agriculturalRoutes = [
  ['/student/agri-skills', 'student-agri-skills'],
  ['/student/agri-skills/calendar', 'student-agri-calendar'],
  ['/student/agri-skills/qa', 'student-agri-qa'],
  ['/student/agri-skills/diagnosis', 'student-agri-diagnosis'],
  ['/student/agri-skills/courses', 'student-agri-courses']
] as const

describe('agricultural skill routes', () => {
  it('registers all agricultural skill routes for students', () => {
    const routes = router.getRoutes()

    for (const [path, name] of agriculturalRoutes) {
      const route = routes.find(candidate => candidate.path === path)

      expect(route).toMatchObject({
        name,
        meta: {
          requiresAuth: true,
          roles: ['student']
        }
      })
    }
  })

  it('adds the agricultural skill entry to the student portal', () => {
    expect(portalDefinitions.student.entries).toContainEqual({
      id: 'student-agri-skills',
      title: '农业技能',
      description: '农时日历、农技问答、病虫害诊断与农业课程。',
      href: '/student/agri-skills'
    })
  })
})
