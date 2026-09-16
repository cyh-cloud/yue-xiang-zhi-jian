import { describe, expect, it } from 'vitest'

import { portalDefinitions } from '@/data/portal-guides'

import router from './index'

const paths = [
  '/student/ecommerce-training',
  '/student/ecommerce-training/live-script',
  '/student/ecommerce-training/simulation',
  '/student/ecommerce-training/copy-training',
  '/student/ecommerce-training/store-guidance',
  '/student/ecommerce-training/customer-service',
  '/student/ecommerce-training/courses'
]

describe('ecommerce training routes', () => {
  it.each(paths)('protects %s for students', path => {
    expect(router.resolve(path).matched[0]?.meta).toMatchObject({
      requiresAuth: true,
      roles: ['student']
    })
  })

  it('links the ecommerce training entry from the student portal guide', () => {
    const entry = portalDefinitions.student.entries.find(
      item => item.id === 'student-ecommerce-training'
    )

    expect(entry).toMatchObject({
      title: '电商运营实训',
      href: '/student/ecommerce-training'
    })
    expect(
      portalDefinitions.student.steps.find(
        step => step.selector === '#student-ecommerce-training'
      )
    ).toMatchObject({
      title: '电商运营实训'
    })
  })
})
