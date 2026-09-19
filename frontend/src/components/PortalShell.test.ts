import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import TeacherPortalView from '@/views/TeacherPortalView.vue'

import AppHeader from './AppHeader.vue'
import PortalShell from './PortalShell.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

describe('PortalShell', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('links implemented student entries and keeps future entries inert', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      required: false,
      portal: 'student'
    } as never)

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/login', component: { template: '<div />' } },
        { path: '/register', component: { template: '<div />' } },
        { path: '/messages', component: { template: '<div />' } },
        { path: '/student', component: { template: '<div />' } },
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
        }
      ]
    })

    const wrapper = mount(PortalShell, {
      props: { portal: 'student' },
      global: { plugins: [router] }
    })
    await flushPromises()

    expect(wrapper.get('#student-courses a').attributes('href')).toBe(
      '/student/courses'
    )
    expect(wrapper.get('#student-profile a').attributes('href')).toBe(
      '/student/profile'
    )
    expect(wrapper.get('#student-ecommerce-training a').attributes('href')).toBe(
      '/student/ecommerce-training'
    )
    expect(
      wrapper.get('#student-handcraft-inheritance a').attributes('href')
    ).toBe('/student/handcraft-inheritance')
    expect(wrapper.find('#student-learning-direction a').exists()).toBe(false)
    expect(wrapper.get('#student-learning-direction').text()).toContain(
      '后续开放'
    )
  })
})

describe('TeacherPortalView shell', () => {
  it('renders the shared header, teacher navigation, child route, and onboarding request', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      required: false,
      portal: 'teacher'
    } as never)

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/login', component: { template: '<div />' } },
        { path: '/register', component: { template: '<div />' } },
        { path: '/messages', component: { template: '<div />' } },
        {
          path: '/teacher',
          component: TeacherPortalView,
          children: [
            {
              path: 'courses',
              component: { template: '<div />' }
            },
            {
              path: 'announcements',
              component: { template: '<div />' }
            },
            {
              path: 'interactions',
              component: { template: '<div />' }
            },
            {
              path: 'dashboard',
              component: {
                template: '<div data-test="teacher-route">教师路由</div>'
              }
            }
          ]
        }
      ]
    })
    await router.push('/teacher/dashboard')
    await router.isReady()

    const wrapper = mount(
      { template: '<RouterView />' },
      {
        global: {
          plugins: [router]
        }
      }
    )
    await flushPromises()

    expect(wrapper.findComponent(AppHeader).exists()).toBe(true)

    const navigation = wrapper.get('nav[aria-label="教师工作台导航"]')
    expect(navigation.get('a[href="/teacher/courses"]').text()).toContain(
      '课程管理'
    )
    expect(navigation.get('a[href="/teacher/announcements"]').text()).toContain(
      '教学公告'
    )
    expect(navigation.get('a[href="/teacher/interactions"]').text()).toContain(
      '互动答疑'
    )
    expect(navigation.get('a[href="/teacher/dashboard"]').text()).toContain(
      '数据看板'
    )
    expect(wrapper.get('[data-test="teacher-route"]').text()).toBe('教师路由')
    expect(mockedApiFetch).toHaveBeenCalledWith('/api/onboarding/teacher')
  })
})
