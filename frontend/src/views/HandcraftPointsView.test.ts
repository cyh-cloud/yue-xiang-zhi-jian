import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import HandcraftInheritanceNav from '@/components/HandcraftInheritanceNav.vue'
import HandcraftPointsPanel from '@/components/HandcraftPointsPanel.vue'

import HandcraftPointsView from './HandcraftPointsView.vue'

vi.mock('@/api/client', () => ({
  apiFetch: vi.fn().mockResolvedValue({
    success: true,
    account: { user_id: 1, balance: 0, updated_at: null },
    ledger: []
  })
}))

describe('HandcraftPointsView', () => {
  it('composes the points panel inside the handcraft shell', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/:pathMatch(.*)*', component: { template: '<div />' } }
      ]
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(HandcraftPointsView, {
      global: {
        plugins: [createPinia(), router]
      }
    })

    expect(wrapper.findComponent(HandcraftPointsPanel).exists()).toBe(true)
    expect(wrapper.findComponent(HandcraftInheritanceNav).exists()).toBe(true)
  })
})
