import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type { UserRole } from '@/api/types'

import { useAuthStore } from '@/stores/auth'

import AiCompanionLauncher from './AiCompanionLauncher.vue'

// SC-002 guard: routes whose meta.roles is empty, missing, or deliberately
// wrong. The launcher must ignore all of it and derive visibility from the
// authenticated user's role alone.
const ROUTES = [
  { path: '/', component: { template: '<div />' } },
  {
    path: '/student',
    component: { template: '<div />' },
    meta: { roles: ['student'] }
  },
  {
    path: '/future-admin-area',
    component: { template: '<div />' },
    meta: {}
  },
  {
    path: '/labeled-admin-only',
    component: { template: '<div />' },
    meta: { roles: ['super_admin', 'admin'] }
  },
  {
    path: '/labeled-student-only',
    component: { template: '<div />' },
    meta: { roles: ['student'] }
  },
  { path: '/:pathMatch(.*)*', component: { template: '<div />' } }
]

function mountLauncher(role: UserRole) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.sessionState = 'active'
  auth.user = { id: 1, username: role, name: role, role }
  return mount(AiCompanionLauncher, {
    global: { plugins: [pinia] }
  })
}

async function mountLauncherAt(role: UserRole, path: string) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.sessionState = 'active'
  auth.user = { id: 1, username: role, name: role, role }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ROUTES
  })
  await router.push(path)
  await router.isReady()
  return mount(AiCompanionLauncher, {
    global: { plugins: [pinia, router] }
  })
}

describe('AiCompanionLauncher', () => {
  it.each(['student', 'teacher', 'enterprise', 'government'] as const)(
    'shows the launcher for %s',
    role => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const auth = useAuthStore()
      auth.sessionState = 'active'
      auth.user = { id: 1, username: role, name: role, role }
      const wrapper = mount(AiCompanionLauncher, {
        global: { plugins: [pinia] }
      })
      expect(
        wrapper.find('[data-test="ai-companion-launcher"]').exists()
      ).toBe(true)
    }
  )

  it.each(['super_admin', 'admin'] as const)(
    'hides the launcher for %s',
    role => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const auth = useAuthStore()
      auth.sessionState = 'active'
      auth.user = { id: 1, username: role, name: role, role }
      const wrapper = mount(AiCompanionLauncher, {
        global: { plugins: [pinia] }
      })
      expect(
        wrapper.find('[data-test="ai-companion-launcher"]').exists()
      ).toBe(false)
    }
  )

  it('opens with keyboard and closes with Escape', async () => {
    const wrapper = mountLauncher('student')
    await wrapper.get('[data-test="ai-companion-launcher"]').trigger('click')
    expect(wrapper.find('[data-test="ai-companion-panel"]').exists()).toBe(true)
    await wrapper.get('[data-test="ai-companion-panel"]').trigger('keydown', {
      key: 'Escape'
    })
    expect(wrapper.find('[data-test="ai-companion-panel"]').exists()).toBe(false)
  })

  // SC-002: visibility must never depend on the current route or its meta.
  describe('SC-002 visibility ignores route meta', () => {
    it.each<[UserRole, string, boolean]>([
      ['super_admin', '/future-admin-area', false],
      ['admin', '/future-admin-area', false],
      ['student', '/future-admin-area', true]
    ])(
      'resolves %s on %s (empty meta) to launcher visible=%s',
      async (role, path, expected) => {
        const wrapper = await mountLauncherAt(role, path)
        expect(
          wrapper.find('[data-test="ai-companion-launcher"]').exists()
        ).toBe(expected)
      }
    )

    it.each<[UserRole, string, boolean]>([
      ['super_admin', '/labeled-student-only', false],
      ['admin', '/labeled-student-only', false],
      ['student', '/labeled-admin-only', true]
    ])(
      'ignores misleading meta.roles for %s on %s (visible=%s)',
      async (role, path, expected) => {
        const wrapper = await mountLauncherAt(role, path)
        expect(
          wrapper.find('[data-test="ai-companion-launcher"]').exists()
        ).toBe(expected)
      }
    )

    it('keeps management roles hidden on the non-admin /student path', async () => {
      for (const role of ['super_admin', 'admin'] as const) {
        const wrapper = await mountLauncherAt(role, '/student')
        expect(
          wrapper.find('[data-test="ai-companion-launcher"]').exists()
        ).toBe(false)
        wrapper.unmount()
      }
    })

    it('keeps the launcher for a student on an unknown future path', async () => {
      const wrapper = await mountLauncherAt('student', '/some-future-unknown')
      expect(
        wrapper.find('[data-test="ai-companion-launcher"]').exists()
      ).toBe(true)
    })

    it('keeps management roles hidden on an unknown future path', async () => {
      for (const role of ['super_admin', 'admin'] as const) {
        const wrapper = await mountLauncherAt(role, '/some-future-unknown')
        expect(
          wrapper.find('[data-test="ai-companion-launcher"]').exists()
        ).toBe(false)
        wrapper.unmount()
      }
    })
  })
})
