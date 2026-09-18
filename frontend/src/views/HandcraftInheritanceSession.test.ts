import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { installSessionExpiredHandler } from '@/api/session-expiry'
import { useAuthStore } from '@/stores/auth'
import { useHandcraftPointsStore } from '@/stores/handcraftPoints'
import { useHandcraftRewardsStore } from '@/stores/handcraftRewards'

function activeAuth() {
  const auth = useAuthStore()
  auth.sessionState = 'active'
  auth.user = {
    id: 1,
    username: 'student01',
    name: '林晓',
    role: 'student'
  }
  auth.defaultPath = '/student'
  return auth
}

function expiredResponse() {
  return {
    ok: false,
    status: 401,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    json: async () => ({
      success: false,
      message: '未登录或会话已过期',
      redirect: '/login?redirect=%2Fapi%2Fhandcraft-inheritance'
    })
  }
}

describe('HandcraftInheritance session expiry', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('redirects an expired points request to the current points route', async () => {
    const auth = activeAuth()
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/login', component: { template: '<div />' } },
        {
          path: '/student/handcraft-inheritance/points',
          component: { template: '<div />' }
        }
      ]
    })
    await router.push('/student/handcraft-inheritance/points')
    await router.isReady()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(expiredResponse()))

    const stopHandler = installSessionExpiredHandler(auth, router)
    try {
      expect(await useHandcraftPointsStore().loadAccount()).toBe(false)
    } finally {
      stopHandler()
    }

    expect(auth.sessionState).toBe('anonymous')
    expect(auth.user).toBeNull()
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe(
      '/student/handcraft-inheritance/points'
    )
  })

  it('redirects an expired reward action without mutating local history', async () => {
    const auth = activeAuth()
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/login', component: { template: '<div />' } },
        {
          path: '/student/handcraft-inheritance/rewards',
          component: { template: '<div />' }
        }
      ]
    })
    await router.push('/student/handcraft-inheritance/rewards')
    await router.isReady()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(expiredResponse()))
    const rewards = useHandcraftRewardsStore()

    const stopHandler = installSessionExpiredHandler(auth, router)
    try {
      expect(
        await rewards.redeem('reward-guangxiu-bookmark', 'request-1')
      ).toBe(false)
    } finally {
      stopHandler()
    }

    expect(rewards.redemptions).toEqual([])
    expect(rewards.fulfillments).toEqual([])
    expect(auth.sessionState).toBe('anonymous')
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe(
      '/student/handcraft-inheritance/rewards'
    )
  })
})
