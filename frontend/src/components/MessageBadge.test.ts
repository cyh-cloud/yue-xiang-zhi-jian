import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'

import MessageBadge from './MessageBadge.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

async function mountBadge(unreadTotal: number) {
  mockedApiFetch.mockResolvedValue({
    success: true,
    unread_private: unreadTotal,
    unread_notifications: 0,
    unread_total: unreadTotal
  } as never)

  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/messages', component: { template: '<div />' } }
    ]
  })
  await router.push('/')
  await router.isReady()

  const wrapper = mount(MessageBadge, {
    global: { plugins: [pinia, router] }
  })
  await flushPromises()
  return wrapper
}

describe('MessageBadge', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders the unread total', async () => {
    const wrapper = await mountBadge(12)

    expect(wrapper.text()).toContain('12')
  })

  it('caps totals above 99 at 99+', async () => {
    const wrapper = await mountBadge(100)

    expect(wrapper.text()).toContain('99+')
  })

  it('hides the numeric bubble when there are no unread items', async () => {
    const wrapper = await mountBadge(0)

    expect(wrapper.find('.message-badge-count').exists()).toBe(false)
  })

  it('links to the message center with an accessible unread label', async () => {
    const wrapper = await mountBadge(12)
    const link = wrapper.get('a')

    expect(link.attributes('href')).toBe('/messages')
    expect(link.attributes('aria-label')).toBe('消息中心，未读 12 条')
  })
})
