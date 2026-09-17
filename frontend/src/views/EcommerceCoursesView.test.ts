import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import EcommerceTrainingNav from '@/components/EcommerceTrainingNav.vue'
import CourseLearningPanel from '@/components/CourseLearningPanel.vue'

import EcommerceCoursesView from './EcommerceCoursesView.vue'

vi.mock('@/api/client', () => ({
  apiFetch: vi.fn().mockResolvedValue({
    success: true,
    courses: [],
    recommendations: []
  })
}))

describe('EcommerceCoursesView', () => {
  it('passes the ecommerce configuration to the shared course panel', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/:pathMatch(.*)*', component: { template: '<div />' } }
      ]
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(EcommerceCoursesView, {
      global: {
        plugins: [createPinia(), router]
      }
    })
    const panel = wrapper.getComponent(CourseLearningPanel)

    expect(panel.props()).toMatchObject({
      direction: 'ecommerce',
      moduleCode: '04',
      title: '电商课程',
      apiPrefix: '/api/ecommerce-training'
    })
    expect(panel.get('.agri-courses-heading__nowrap').text()).toBe('获取推荐')
    expect(panel.findComponent(EcommerceTrainingNav).exists()).toBe(true)
  })
})
