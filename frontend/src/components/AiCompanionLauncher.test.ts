import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it } from 'vitest'
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
    attachTo: document.body,
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
  // Focus-return tests attach the launcher to document.body; reset it between
  // tests so a stale launcher can never satisfy the activeElement assertion.
  afterEach(() => {
    document.body.innerHTML = ''
  })

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
    expect(document.activeElement).toBe(
      wrapper.find('[data-test="ai-companion-launcher"]').element
    )
  })

  it('returns focus to the launcher when closed via the close button', async () => {
    const wrapper = mountLauncher('student')
    await wrapper.get('[data-test="ai-companion-launcher"]').trigger('click')
    await wrapper.get('.ai-companion-panel-close').trigger('click')
    expect(wrapper.find('[data-test="ai-companion-panel"]').exists()).toBe(false)
    expect(document.activeElement).toBe(
      wrapper.find('[data-test="ai-companion-launcher"]').element
    )
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

  // FR-005: anonymous, invalid session, or an unknown role must all hide the
  // launcher. Only an active session carrying a known companion role shows it.
  describe('visibility gate', () => {
    it.each<
      [string, { sessionState: 'anonymous' | 'pending' | 'active'; user: null }]
    >([
      ['anonymous', { sessionState: 'anonymous', user: null }],
      ['pending', { sessionState: 'pending', user: null }],
      ['active-no-user', { sessionState: 'active', user: null }]
    ])('hides the launcher for the %s session', (_label, session) => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const auth = useAuthStore()
      auth.sessionState = session.sessionState
      auth.user = session.user
      const wrapper = mount(AiCompanionLauncher, {
        global: { plugins: [pinia] }
      })
      expect(
        wrapper.find('[data-test="ai-companion-launcher"]').exists()
      ).toBe(false)
    })

    it('hides the launcher when the active session has an unknown role', () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const auth = useAuthStore()
      auth.sessionState = 'active'
      auth.user = {
        id: 1,
        username: 'ghost',
        name: 'ghost',
        role: 'wizard' as UserRole
      }
      const wrapper = mount(AiCompanionLauncher, {
        global: { plugins: [pinia] }
      })
      expect(
        wrapper.find('[data-test="ai-companion-launcher"]').exists()
      ).toBe(false)
    })
  })
})
