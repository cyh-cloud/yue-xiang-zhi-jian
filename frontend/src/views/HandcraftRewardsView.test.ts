import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import HandcraftInheritanceNav from '@/components/HandcraftInheritanceNav.vue'
import HandcraftRewardsPanel from '@/components/HandcraftRewardsPanel.vue'

import HandcraftRewardsView from './HandcraftRewardsView.vue'

vi.mock('@/api/client', () => ({
  apiFetch: vi.fn().mockResolvedValue({
    success: true,
    rewards: [],
    redemptions: [],
    fulfillments: []
  })
}))

describe('HandcraftRewardsView', () => {
  it('composes the rewards panel inside the handcraft shell', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/:pathMatch(.*)*', component: { template: '<div />' } }
      ]
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(HandcraftRewardsView, {
      global: {
        plugins: [createPinia(), router]
      }
    })

    expect(wrapper.findComponent(HandcraftRewardsPanel).exists()).toBe(true)
    expect(wrapper.findComponent(HandcraftInheritanceNav).exists()).toBe(true)
  })
})
