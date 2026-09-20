import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, expectTypeOf, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type { AdminDashboardResponse } from '@/api/types'
import AdminConsoleNav from '@/components/AdminConsoleNav.vue'
import AdminMetricGroup from '@/components/AdminMetricGroup.vue'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

import AdminPortalView from './AdminPortalView.vue'

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      '/admin',
      '/admin/dashboard',
      '/admin/review',
      '/admin/moderation',
      '/admin/presets',
      '/admin/rewards',
      '/admin/redemptions',
      '/admin/accounts',
      '/admin/points-policy',
      '/admin/content',
      '/admin/announcements',
      '/login'
    ].map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}

async function mountNav(role: 'admin' | 'super_admin') {
  const test = testRouter()
  await test.push('/admin')
  await test.isReady()
  const wrapper = mount(AdminConsoleNav, {
    props: { role },
    global: {
      plugins: [test],
      stubs: { RouterLink: RouterLinkStub }
    }
  })
  return { test, wrapper }
}

describe('AdminConsoleNav', () => {
  it('hides super-admin-only links from ordinary admins', async () => {
    const { wrapper } = await mountNav('admin')

    expect(wrapper.find('[data-test="admin-nav-accounts"]').exists()).toBe(false)
    expect(
      wrapper.find('[data-test="admin-nav-points-policy"]').exists()
    ).toBe(false)
    expect(wrapper.find('[data-test="admin-nav-content"]').exists()).toBe(false)
    expect(
      wrapper.find('[data-test="admin-nav-announcements"]').exists()
    ).toBe(false)
    expect(wrapper.find('[data-test="admin-nav-review"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="admin-nav-rewards"]').exists()).toBe(true)
  })

  it('shows every admin console entry to super admins', async () => {
    const { wrapper } = await mountNav('super_admin')
    const expected = [
      'dashboard',
      'review',
      'moderation',
      'presets',
      'rewards',
      'redemptions',
      'accounts',
      'points-policy',
      'content',
      'announcements'
    ]

    for (const testId of expected) {
      expect(wrapper.find(`[data-test="admin-nav-${testId}"]`).exists()).toBe(
        true
      )
    }
  })
})

describe('admin console routes', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('registers the admin children with the required role metadata', () => {
    const routes = router.getRoutes()
    const adminPaths = [
      '/admin/dashboard',
      '/admin/review',
      '/admin/moderation',
      '/admin/presets',
      '/admin/rewards',
      '/admin/redemptions',
      '/admin/accounts',
      '/admin/points-policy',
      '/admin/content',
      '/admin/announcements'
    ]

    for (const path of adminPaths) {
      const route = routes.find(record => record.path === path)
      expect(route?.meta.requiresAuth).toBe(true)
      expect(route?.meta.roles).toEqual(['super_admin', 'admin'])
    }
  })

  it('uses render-function placeholders for admin child routes', () => {
    const route = router
      .getRoutes()
      .find(record => record.path === '/admin/dashboard')
    const component = route?.components?.default

    expect(component).toBeTruthy()
    expect(typeof component).toBe('object')
    expect(component).not.toHaveProperty('template')
  })

  it('renders the navigation and child route inside the parent shell', async () => {
    const test = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/admin',
          component: AdminPortalView,
          children: [
            {
              path: '',
              redirect: '/admin/dashboard'
            },
            {
              path: 'dashboard',
              component: {
                template: '<div data-test="admin-child-route">看板</div>'
              }
            },
            ...['review', 'moderation', 'presets', 'rewards', 'redemptions',
              'accounts', 'points-policy', 'content', 'announcements'].map(
              path => ({
                path,
                component: { template: '<div />' }
              })
            )
          ]
        },
        {
          path: '/login',
          component: { template: '<div />' }
        }
      ]
    })
    await test.push('/admin/dashboard')
    await test.isReady()

    const pinia = createPinia()
    const auth = useAuthStore(pinia)
    auth.sessionState = 'active'
    auth.user = {
      id: 1,
      username: 'super-admin',
      name: '超级管理员',
      role: 'super_admin'
    }
    const wrapper = mount(
      { template: '<RouterView />' },
      {
        global: {
          plugins: [pinia, test],
          stubs: {
            AppHeader: {
              template: '<header data-test="admin-header" />'
            }
          }
        }
      }
    )
    await flushPromises()

    expect(wrapper.find('[data-test="admin-console"]').exists()).toBe(true)
    expect(wrapper.get('[data-test="admin-nav-dashboard"]').text()).toContain(
      '数据看板'
    )
    expect(wrapper.get('[data-test="admin-child-route"]').text()).toBe('看板')
  })
})

describe('AdminMetricGroup', () => {
  it('keeps the dashboard DTO metrics flat and numeric', () => {
    expectTypeOf<AdminDashboardResponse['metrics']>().toEqualTypeOf<
      Record<string, number>
    >()
  })

  it('renders stable metric selectors for numeric values', () => {
    const wrapper = mount(AdminMetricGroup, {
      props: {
        metrics: {
          total_users: 12,
          pending_review: 3
        },
        labels: {
          total_users: '总用户数',
          pending_review: '待审核'
        }
      }
    })

    expect(
      wrapper.get('[data-test="admin-metric-total-users"]').text()
    ).toContain('总用户数')
    expect(
      wrapper.get('[data-test="admin-metric-total-users"]').text()
    ).toContain('12')
    expect(
      wrapper.get('[data-test="admin-metric-pending-review"]').text()
    ).toContain('3')
  })
})
