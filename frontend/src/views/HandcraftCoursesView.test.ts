import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import CourseLearningPanel from '@/components/CourseLearningPanel.vue'
import HandcraftInheritanceNav from '@/components/HandcraftInheritanceNav.vue'

import HandcraftCoursesView from './HandcraftCoursesView.vue'

vi.mock('@/api/client', () => ({
  apiFetch: vi.fn().mockResolvedValue({
    success: true,
    courses: [],
    recommendations: []
  })
}))

describe('HandcraftCoursesView', () => {
  it('configures the shared course panel for handcraft courses', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/:pathMatch(.*)*', component: { template: '<div />' } }
      ]
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(HandcraftCoursesView, {
      global: {
        plugins: [createPinia(), router]
      }
    })
    const panel = wrapper.getComponent(CourseLearningPanel)

    expect(panel.props()).toMatchObject({
      direction: 'handcraft',
      moduleCode: '05',
      title: '手工课程',
      apiPrefix: '/api/handcraft-inheritance'
    })
    expect(panel.findComponent(HandcraftInheritanceNav).exists()).toBe(true)
  })
})
