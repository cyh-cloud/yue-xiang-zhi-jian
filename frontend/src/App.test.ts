import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type { UserRole } from '@/api/types'

import { useAuthStore } from '@/stores/auth'

import App from './App.vue'

// 角色矩阵：四个 AI 学伴角色加两个管理角色。全局入口显隐只应由角色决定。
const ROLE_MATRIX: readonly UserRole[] = [
  'student',
  'teacher',
  'enterprise',
  'government',
  'super_admin',
  'admin'
]

// 路由 meta 矩阵：无 meta、空 roles 数组、以及故意只标 student 的误导性 meta。
const ROUTE_META_MATRIX: readonly { roles?: UserRole[] }[] = [
  {},
  { roles: [] },
  { roles: ['student'] }
]

// 门户路由：第一项只是标签，显隐判断只认第二项的路径。
const PORTAL_ROUTE_MATRIX: readonly (readonly [string, string])[] = [
  ['student', '/student'],
  ['teacher', '/teacher'],
  ['enterprise', '/enterprise'],
  ['government', '/government']
]

// 只有这四个非管理角色能使用 AI 学伴；入口显隐的唯一依据。
const COMPANION_ROLES: ReadonlySet<UserRole> = new Set<UserRole>([
  'student',
  'teacher',
  'enterprise',
  'government'
])

// 每次迭代都新建 pinia 与 router，避免状态或当前路由在组合之间串味。
async function mountAppAt(
  role: UserRole,
  path: string,
  meta: { roles?: UserRole[] }
) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path, component: { template: '<div />' }, meta }]
  })
  await router.push(path)
  await router.isReady()

  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.sessionState = 'active'
  auth.user = { id: 1, username: role, name: role, role }

  return mount(App, { global: { plugins: [pinia, router] } })
}

describe('App 的 AI 学伴全局入口集成', () => {
  // 角色 x 路由 meta x 门户/未来路径 的完整笛卡尔积，是“显隐只由角色决定、
  // 绝不读路由 meta”的证据。任一组合都不折叠成代表用例。
  it('在 角色xmeta x路径 的每种组合下，入口显隐只由角色决定', async () => {
    const paths = [...PORTAL_ROUTE_MATRIX, ['temporary', '/future-area'] as const]
    for (const role of ROLE_MATRIX) {
      for (const meta of ROUTE_META_MATRIX) {
        for (const [, path] of paths) {
          const wrapper = await mountAppAt(role, path, meta)
          const exists = wrapper
            .find('[data-test="ai-companion-launcher"]')
            .exists()
          // 失败信息带上 role/meta/path，红了也能一眼定位是哪一种组合。
          expect(
            exists,
            `role=${role} meta=${JSON.stringify(meta)} path=${path}`
          ).toBe(COMPANION_ROLES.has(role))
          wrapper.unmount()
        }
      }
    }
  })

  // 独立于路由 meta 的具体证据：管理角色在未来区域始终隐藏，学生始终显示。
  describe('入口显隐独立于路由 meta', () => {
    it.each(['super_admin', 'admin'] as const)(
      '让 %s 在 /future-area 上无论 meta 如何都保持隐藏',
      async role => {
        for (const meta of [{}, { roles: ['student'] as UserRole[] }]) {
          const wrapper = await mountAppAt(role, '/future-area', meta)
          expect(
            wrapper.find('[data-test="ai-companion-launcher"]').exists()
          ).toBe(false)
          wrapper.unmount()
        }
      }
    )

    it('让 student 在 /future-area 上无论 meta 如何都显示', async () => {
      for (const meta of [{}, { roles: ['student'] as UserRole[] }]) {
        const wrapper = await mountAppAt('student', '/future-area', meta)
        expect(
          wrapper.find('[data-test="ai-companion-launcher"]').exists()
        ).toBe(true)
        wrapper.unmount()
      }
    })
  })
})
