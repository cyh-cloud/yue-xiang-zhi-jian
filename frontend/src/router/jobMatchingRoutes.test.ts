import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { RouteLocationNormalized } from 'vue-router'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it } from 'vitest'

import { portalDefinitions } from '@/data/portal-guides'
import { useAuthStore } from '@/stores/auth'
import StudentPortalView from '@/views/StudentPortalView.vue'

import router from './index'
import { authGuard } from './roleRoutes'

const employmentRoutes = [
  {
    path: '/student/employment',
    name: 'student-employment'
  },
  {
    path: '/student/employment/resume',
    name: 'student-employment-resume'
  },
  {
    path: '/student/employment/skills',
    name: 'student-employment-skills'
  },
  {
    path: '/student/employment/jobs',
    name: 'student-employment-jobs'
  },
  {
    path: '/student/employment/applications',
    name: 'student-employment-applications'
  },
  {
    path: '/student/employment/favorites',
    name: 'student-employment-favorites'
  }
] as const

const employmentDetailRoute = {
  path: '/student/employment/jobs/:jobId',
  name: 'student-employment-job-detail'
} as const

function route(
  fullPath: string,
  meta: RouteLocationNormalized['meta']
): RouteLocationNormalized {
  return {
    fullPath,
    path: fullPath,
    meta
  } as RouteLocationNormalized
}

describe('student employment routes', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it.each(employmentRoutes)(
    'registers $path as $name for students',
    ({ path, name }) => {
      expect(router.getRoutes().find(route => route.path === path)).toMatchObject(
        {
          name,
          meta: {
            requiresAuth: true,
            roles: ['student']
          }
        }
      )
    }
  )

  it('protects the dynamic job detail route for students', () => {
    expect(
      router
        .getRoutes()
        .find(route => route.path === employmentDetailRoute.path)
    ).toMatchObject({
      name: employmentDetailRoute.name,
      meta: {
        requiresAuth: true,
        roles: ['student']
      }
    })
  })

  it('exposes the employment portal entry and onboarding step', () => {
    expect(portalDefinitions.student.entries).toContainEqual({
      id: 'student-employment',
      title: '就业对接',
      description: '维护简历与技能档案，浏览岗位并跟踪投递。',
      href: '/student/employment'
    })
    expect(portalDefinitions.student.steps).toContainEqual({
      selector: '#student-employment',
      title: '就业对接',
      description: '维护简历与技能档案，浏览岗位并跟踪投递。'
    })
  })

  it('adds a direct employment entry to the student portal', async () => {
    const memoryRouter = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/student', component: StudentPortalView },
        { path: '/student/courses', component: { template: '<div />' } },
        { path: '/student/profile', component: { template: '<div />' } },
        { path: '/student/agri-skills', component: { template: '<div />' } },
        {
          path: '/student/ecommerce-training',
          component: { template: '<div />' }
        },
        {
          path: '/student/handcraft-inheritance',
          component: { template: '<div />' }
        },
        {
          path: '/student/employment',
          component: { template: '<div />' }
        }
      ]
    })
    await memoryRouter.push('/student')
    await memoryRouter.isReady()

    const wrapper = mount(StudentPortalView, {
      global: {
        plugins: [memoryRouter],
        stubs: {
          PortalShell: { template: '<div />' }
        }
      }
    })
    const employmentLink = wrapper.get(
      'a[href="/student/employment"]'
    )

    expect(employmentLink.text()).toContain('进入就业对接')
    expect(employmentLink.text()).toContain('简历、技能档案、岗位与投递')
  })

  it('keeps the employment home to exactly five primary entries', async () => {
    const { default: JobMatchingHomeView } = await import(
      '@/views/JobMatchingHomeView.vue'
    )
    const memoryRouter = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/student/employment', component: JobMatchingHomeView },
        { path: '/student', component: { template: '<div />' } },
        {
          path: '/student/employment/resume',
          component: { template: '<div />' }
        },
        {
          path: '/student/employment/skills',
          component: { template: '<div />' }
        },
        {
          path: '/student/employment/jobs',
          component: { template: '<div />' }
        },
        {
          path: '/student/employment/applications',
          component: { template: '<div />' }
        },
        {
          path: '/student/employment/favorites',
          component: { template: '<div />' }
        }
      ]
    })
    await memoryRouter.push('/student/employment')
    await memoryRouter.isReady()

    const wrapper = mount(JobMatchingHomeView, {
      global: {
        plugins: [createPinia(), memoryRouter],
        stubs: {
          AppHeader: true,
          JobMatchingNav: true
        }
      }
    })

    expect(
      wrapper
        .findAll('[data-test="job-matching-entry"]')
        .map(link => ({
          href: link.attributes('href'),
          label: link.get('strong').text()
        }))
    ).toEqual([
      {
        href: '/student/employment/resume',
        label: '简历维护'
      },
      {
        href: '/student/employment/skills',
        label: '我的技能档案'
      },
      {
        href: '/student/employment/jobs',
        label: '岗位浏览'
      },
      {
        href: '/student/employment/applications',
        label: '我的投递'
      },
      {
        href: '/student/employment/favorites',
        label: '岗位收藏'
      }
    ])
  })

  it('redirects a non-student away from the dynamic detail route', async () => {
    const auth = useAuthStore()
    auth.sessionState = 'active'
    auth.user = {
      id: 11,
      username: 'enterprise-demo',
      name: '示范企业',
      role: 'enterprise'
    }
    const target = router.resolve('/student/employment/jobs/job-demo')

    await expect(
      authGuard(
        route(
          '/student/employment/jobs/job-demo',
          target.matched[0]?.meta ?? {}
        ),
        auth
      )
    ).resolves.toBe('/enterprise')
  })
})
