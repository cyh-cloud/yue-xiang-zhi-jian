import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import StudentPortalView from './StudentPortalView.vue'

describe('StudentPortalView', () => {
  it('provides a keyboard-focusable handcraft inheritance quick link', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/student', component: StudentPortalView },
        {
          path: '/student/handcraft-inheritance',
          component: { template: '<div />' }
        },
        { path: '/:pathMatch(.*)*', component: { template: '<div />' } }
      ]
    })
    await router.push('/student')
    await router.isReady()

    const wrapper = mount(StudentPortalView, {
      attachTo: document.body,
      global: {
        plugins: [router],
        stubs: {
          PortalShell: { template: '<div />' }
        }
      }
    })
    const link = wrapper.get('a[href="/student/handcraft-inheritance"]')

    expect(link.text()).toContain('进入手工传承')
    expect(link.text()).toContain('非遗技艺、积分、奖品与课程')
    expect(link.attributes('tabindex')).toBeUndefined()

    const element = link.element as HTMLElement
    element.focus()
    expect(document.activeElement).toBe(element)

    wrapper.unmount()
  })

  it('links to the local resources module', async () => {
    const router = createRouter({
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
          path: '/student/local-resources',
          component: { template: '<div />' }
        }
      ]
    })
    await router.push('/student')
    await router.isReady()

    const wrapper = mount(StudentPortalView, {
      global: {
        plugins: [router],
        stubs: {
          PortalShell: { template: '<div />' }
        }
      }
    })
    const link = wrapper.get('a[href="/student/local-resources"]')

    expect(link.text()).toContain('进入本土资源')
    expect(link.text()).toContain('方言助手、案例、政策与新闻')

    wrapper.unmount()
  })
})
