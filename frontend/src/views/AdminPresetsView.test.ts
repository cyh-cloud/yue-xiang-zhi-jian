import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type {
  AdminAgriCalendarPreset,
  AdminAgriProductPreset,
  AdminAssistantKnowledgePreset,
  AdminHandcraftCraftPreset,
  AdminPresetCategory,
  AdminPresetItem,
  AdminPestKnowledgePreset,
  AdminSuccessCasePreset
} from '@/stores/adminConsole'
import { useAuthStore } from '@/stores/auth'

import AdminPresetsView from './AdminPresetsView.vue'

vi.mock('@/api/client', () => {
  class MockApiError extends Error {
    readonly status: number
    readonly code: string
    readonly errors: Record<string, string>

    constructor(
      message: string,
      status = 400,
      errors: Record<string, string> = {},
      _redirect?: string,
      code = ''
    ) {
      super(message)
      this.name = 'ApiError'
      this.status = status
      this.code = code
      this.errors = errors
    }
  }

  return { ApiError: MockApiError, apiFetch: vi.fn() }
})

const apiFetchMock = vi.mocked(apiFetch)

function craftSteps() {
  return Array.from({ length: 6 }, (_, index) => ({
    step_no: index + 1,
    step_key: `step-${index + 1}`,
    title: `步骤 ${index + 1}`,
    description: `第 ${index + 1} 步的操作说明`,
    tips: ['保持手稳']
  }))
}

function agriProductFixture(
  patch: Partial<AdminAgriProductPreset> = {}
): AdminAgriProductPreset {
  return {
    product_key: 'litchi',
    name: '荔枝',
    sort_order: 1,
    is_enabled: true,
    version: 3,
    created_at: '2026-09-01T09:00:00+08:00',
    updated_at: '2026-09-02T09:00:00+08:00',
    ...patch
  }
}

function calendarFixture(
  patch: Partial<AdminAgriCalendarPreset> = {}
): AdminAgriCalendarPreset {
  return {
    item_id: 'calendar-litchi-4',
    product_key: 'litchi',
    month: 4,
    tasks: ['疏除病弱花穗', '施保果肥'],
    management: ['控制土壤湿度'],
    solar_terms: ['清明', '谷雨'],
    reminder: '注意防范连续阴雨',
    sort_order: 4,
    is_enabled: true,
    version: 2,
    created_at: '2026-09-01T09:00:00+08:00',
    updated_at: '2026-09-02T09:00:00+08:00',
    ...patch
  }
}

function pestFixture(
  patch: Partial<AdminPestKnowledgePreset> = {}
): AdminPestKnowledgePreset {
  return {
    item_id: 'pest-1',
    sort_order: 1,
    pest_name: '荔枝蒂蛀虫',
    product_names: ['荔枝'],
    symptoms: ['果蒂有蛀孔', '果内蛀道'],
    aliases: ['蛀果虫'],
    answer: '以及时喷药与清园为主',
    is_enabled: true,
    version: 4,
    created_at: '2026-09-01T09:00:00+08:00',
    updated_at: '2026-09-02T09:00:00+08:00',
    ...patch
  }
}

function craftFixture(
  patch: Partial<AdminHandcraftCraftPreset> = {}
): AdminHandcraftCraftPreset {
  return {
    craft_key: 'guangxiu',
    name: '广绣',
    introduction: '广绣以构图饱满、针法多样著称。',
    steps: craftSteps(),
    material_guide: [
      {
        name: '绣线',
        reference_price: '20 元/束',
        purchase_channel: '本地工艺店',
        precautions: '避光保存',
        taobao_keyword: '广绣绣线'
      }
    ],
    is_demo: false,
    source_available: true,
    available: true,
    sort_order: 1,
    is_enabled: true,
    version: 2,
    created_at: '2026-09-01T09:00:00+08:00',
    updated_at: '2026-09-02T09:00:00+08:00',
    ...patch
  }
}

function caseFixture(
  patch: Partial<AdminSuccessCasePreset> = {}
): AdminSuccessCasePreset {
  return {
    id: 'case-litchi',
    title: '荔枝合作社案例',
    summary: '从单户到合作社的经营路径',
    background: '村里荔枝长期零散销售',
    journey: '先统一分级，再统一品牌',
    lessons: '品牌与分级是溢价的关键',
    published_at: '2026-08-01T10:00:00+08:00',
    updated_at: '2026-09-01T10:00:00+08:00',
    is_demo: false,
    sort_order: 1,
    is_enabled: true,
    source_available: true,
    version: 5,
    ...patch
  }
}

function knowledgeFixture(
  patch: Partial<AdminAssistantKnowledgePreset> = {}
): AdminAssistantKnowledgePreset {
  return {
    knowledge_id: 'knowledge-agri-entry',
    title: '如何进入农技学堂',
    body: '在首页选择农技学堂入口即可进入。',
    feature_key: 'agri_skills',
    jump_target: '/agri',
    is_enabled: true,
    sort_order: 1,
    version: 2,
    created_at: '2026-09-01T09:00:00+08:00',
    updated_at: '2026-09-02T09:00:00+08:00',
    ...patch
  }
}

const categories: AdminPresetCategory[] = [
  'agri_products',
  'agri_calendar',
  'pest_knowledge',
  'handcraft_crafts',
  'success_cases',
  'assistant_knowledge'
]

let fixtures: Record<AdminPresetCategory, AdminPresetItem[]>
let createFailure: { status: number; code: string; message: string } | null =
  null
let updateFailure: { status: number; code: string; message: string } | null =
  null
let deleteFailure: { status: number; code: string; message: string } | null =
  null
let listFailure = false
let listHang = false

function itemIdOf(item: AdminPresetItem): string {
  if ('product_key' in item) return item.product_key
  if ('item_id' in item) return item.item_id
  if ('craft_key' in item) return item.craft_key
  if ('knowledge_id' in item) return item.knowledge_id
  return item.id
}

function applyPayload(
  category: AdminPresetCategory,
  current: AdminPresetItem,
  payload: Record<string, unknown>
): AdminPresetItem {
  const next: Record<string, unknown> = { ...current }
  for (const [key, value] of Object.entries(payload)) {
    if (key === 'expected_version') continue
    next[key] = value
  }
  next.version = current.version + 1
  if (category === 'success_cases') {
    const existing = current as AdminSuccessCasePreset
    next.id = next.case_id ?? existing.id
    delete next.case_id
  }
  return next as unknown as AdminPresetItem
}

function bodyOf(options?: RequestInit): Record<string, unknown> {
  return JSON.parse(String(options?.body ?? '{}')) as Record<string, unknown>
}

// Reading a control's current value is how the edit form's backfill is
// checked, so the DOM element is narrowed once instead of at every site.
function fieldValue(wrapper: VueWrapper, selector: string): string {
  return (wrapper.get(selector).element as HTMLInputElement).value
}

function installFetch() {
  apiFetchMock.mockImplementation(async (path: string, options?: RequestInit) => {
    if (!path.startsWith('/api/admin/presets/')) return { success: true }
    const rest = path.slice('/api/admin/presets/'.length)
    const queryStart = rest.indexOf('?')
    const withoutQuery = queryStart === -1 ? rest : rest.slice(0, queryStart)
    const slash = withoutQuery.indexOf('/')
    const category = (
      slash === -1 ? withoutQuery : withoutQuery.slice(0, slash)
    ) as AdminPresetCategory
    const itemId = slash === -1 ? '' : withoutQuery.slice(slash + 1)
    const method = options?.method ?? 'GET'

    if (method === 'GET') {
      if (listHang) return new Promise(() => {})
      if (listFailure) {
        throw new ApiError('预置内容服务暂时不可用', 503)
      }
      const items = fixtures[category]
      return { success: true, items, count: items.length }
    }

    const list = fixtures[category]
    const index = list.findIndex(item => itemIdOf(item) === itemId)

    if (method === 'POST') {
      if (createFailure) {
        throw new ApiError(
          createFailure.message,
          createFailure.status,
          {},
          undefined,
          createFailure.code
        )
      }
      const created = applyPayload(
        category,
        list[0] ?? agriProductFixture(),
        bodyOf(options)
      )
      // Every write answers with a fresh array and fresh rows so the store's
      // ref sees a new value and the table re-renders.
      fixtures[category] = [...list, created]
      return { success: true, item: created }
    }

    if (index === -1) {
      throw new ApiError('条目不存在', 404, {}, undefined, 'preset_not_found')
    }

    if (method === 'PUT') {
      if (updateFailure) {
        throw new ApiError(
          updateFailure.message,
          updateFailure.status,
          {},
          undefined,
          updateFailure.code
        )
      }
      const updated = applyPayload(category, list[index], bodyOf(options))
      fixtures[category] = list.map((item, position) =>
        position === index ? updated : item
      )
      return { success: true, item: updated }
    }

    if (deleteFailure) {
      throw new ApiError(
        deleteFailure.message,
        deleteFailure.status,
        {},
        undefined,
        deleteFailure.code
      )
    }
    const disabled = {
      ...list[index],
      is_enabled: false,
      version: list[index].version + 1
    } as AdminPresetItem
    fixtures[category] = list.map((item, position) =>
      position === index ? disabled : item
    )
    return { success: true, item: disabled }
  })
}

async function mountView(role: 'admin' | 'super_admin' = 'admin') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore(pinia)
  auth.sessionState = 'active'
  auth.user = {
    id: 1,
    username: 'content-admin',
    name: '内容管理员',
    role
  }

  const wrapper = mount(AdminPresetsView, {
    global: { plugins: [pinia] },
    // A submit button only runs the form submission algorithm while the form
    // is connected to the document, so the console is attached like the other
    // form-bearing admin views.
    attachTo: document.body
  })
  await flushPromises()
  return { pinia, wrapper }
}

function callsWith(method: string) {
  return apiFetchMock.mock.calls.filter(call => call[1]?.method === method)
}

function presetCalls(category: string) {
  return apiFetchMock.mock.calls.filter(call =>
    String(call[0]).startsWith(`/api/admin/presets/${category}`)
  )
}

function resetFixtures() {
  fixtures = {
    agri_products: [agriProductFixture()],
    agri_calendar: [calendarFixture()],
    pest_knowledge: [pestFixture()],
    handcraft_crafts: [craftFixture()],
    success_cases: [caseFixture()],
    assistant_knowledge: [knowledgeFixture()]
  }
}

describe('AdminPresetsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetFixtures()
    createFailure = null
    updateFailure = null
    deleteFailure = null
    listFailure = false
    listHang = false
    installFetch()
  })

  it('opens the preset console for both admin roles', async () => {
    for (const role of ['admin', 'super_admin'] as const) {
      const { wrapper } = await mountView(role)

      expect(wrapper.find('[data-test="admin-presets"]').exists()).toBe(true)
      expect(wrapper.findAll('[data-test="preset-row"]')).toHaveLength(1)
      for (const category of categories) {
        expect(
          wrapper.find(`[data-test="preset-tab-${category}"]`).exists()
        ).toBe(true)
      }
      expect(
        wrapper.get('[data-test="preset-tab-agri_products"]').text()
      ).toContain('农产品')
      wrapper.unmount()
    }
  })

  it('loads the first category on mount and renders every category list', async () => {
    const { wrapper } = await mountView()

    expect(presetCalls('agri_products')).toHaveLength(1)
    expect(wrapper.get('[data-test="preset-count"]').text()).toContain('1')
    expect(wrapper.get('[data-test="preset-row"]').text()).toContain('荔枝')

    const expectedText: Record<AdminPresetCategory, string> = {
      agri_products: '荔枝',
      agri_calendar: 'calendar-litchi-4',
      pest_knowledge: '荔枝蒂蛀虫',
      handcraft_crafts: '广绣',
      success_cases: '荔枝合作社案例',
      assistant_knowledge: '如何进入农技学堂'
    }

    for (const category of categories) {
      await wrapper.get(`[data-test="preset-tab-${category}"]`).trigger('click')
      await flushPromises()

      expect(wrapper.get('[data-test="preset-row"]').text()).toContain(
        expectedText[category]
      )
    }

    expect(presetCalls('pest_knowledge')).toHaveLength(1)
    expect(presetCalls('handcraft_crafts')).toHaveLength(1)
    expect(presetCalls('assistant_knowledge')).toHaveLength(1)
  })

  it('fills the edit form from the row and saves with the expected version', async () => {
    const { wrapper } = await mountView()
    await wrapper
      .get('[data-test="preset-tab-pest_knowledge"]')
      .trigger('click')
    await flushPromises()

    await wrapper.get('[data-test="preset-edit-pest-1"]').trigger('click')
    await flushPromises()

    expect(fieldValue(wrapper, '[data-test="preset-answer"]')).toBe(
      '以及时喷药与清园为主'
    )
    expect(fieldValue(wrapper, '[data-test="preset-pest-name"]')).toBe(
      '荔枝蒂蛀虫'
    )
    expect(
      wrapper.get('[data-test="preset-stable-id"]').attributes('disabled')
    ).toBeDefined()
    expect(wrapper.get('[data-test="preset-form"]').text()).toContain(
      '创建后不可修改'
    )

    await wrapper.get('[data-test="preset-answer"]').setValue('更新答案')
    await wrapper.get('[data-test="preset-save"]').trigger('click')
    await flushPromises()

    const putCall = callsWith('PUT')[0]
    expect(putCall?.[0]).toBe('/api/admin/presets/pest_knowledge/pest-1')
    expect(JSON.parse(String(putCall?.[1]?.body))).toEqual({
      item_id: 'pest-1',
      sort_order: 1,
      pest_name: '荔枝蒂蛀虫',
      product_names: ['荔枝'],
      symptoms: ['果蒂有蛀孔', '果内蛀道'],
      aliases: ['蛀果虫'],
      answer: '更新答案',
      is_enabled: true,
      expected_version: 4
    })

    // The row shows the version the backend stored, not the one that was sent.
    expect(wrapper.get('[data-test="preset-row"]').text()).toContain('v5')
    expect(wrapper.get('[data-test="preset-message"]').text()).toContain(
      '已保存病虫害条目「pest-1」'
    )
    // A successful save returns the form to its create state with the typed
    // values cleared, so the next entry starts from a blank answer.
    expect(fieldValue(wrapper, '[data-test="preset-answer"]')).toBe('')
    expect(wrapper.get('[data-test="preset-save"]').text()).toContain('创建条目')
    expect(
      wrapper.get('[data-test="preset-stable-id"]').attributes('disabled')
    ).toBeUndefined()
  })

  it('states in the delete confirmation that the entry is only disabled', async () => {
    const { wrapper } = await mountView()
    await wrapper
      .get('[data-test="preset-tab-pest_knowledge"]')
      .trigger('click')
    await flushPromises()

    await wrapper.get('[data-test="preset-delete-pest-1"]').trigger('click')
    const dialog = wrapper.get('[data-test="preset-delete-dialog"]')

    expect(dialog.text()).toContain('逻辑停用')
    expect(dialog.text()).toContain('不是物理删除')
    expect(dialog.text()).toContain('停止对学员端、教师端等用户端可见')
    expect(dialog.text()).toContain('稳定 ID 会被保留')
    expect(dialog.text()).toContain('管理员在后台仍然可以看到')
    expect(callsWith('DELETE')).toHaveLength(0)

    await wrapper.get('[data-test="preset-confirm-delete"]').trigger('click')
    await flushPromises()

    const deleteCall = callsWith('DELETE')[0]
    expect(deleteCall?.[0]).toBe(
      '/api/admin/presets/pest_knowledge/pest-1?expected_version=4'
    )
    expect(wrapper.get('[data-test="preset-row"]').text()).toContain('已停用')
    expect(wrapper.get('[data-test="preset-message"]').text()).toContain(
      '稳定 ID 仍保留'
    )
    expect(wrapper.find('[data-test="preset-delete-dialog"]').exists()).toBe(
      false
    )
  })

  it('presents a rejected create with the backend code and message', async () => {
    createFailure = {
      status: 409,
      code: 'agri_product_preset_conflict',
      message: '农产品键已存在'
    }
    const { wrapper } = await mountView()

    await wrapper.get('[data-test="preset-stable-id"]').setValue('litchi')
    await wrapper.get('[data-test="preset-name"]').setValue('荔枝')
    await wrapper.get('[data-test="preset-save"]').trigger('click')
    await flushPromises()

    expect(callsWith('POST')).toHaveLength(1)
    expect(wrapper.get('[data-test="preset-form-error"]').text()).toContain(
      '农产品稳定 ID 已存在，请更换后重试'
    )
    expect(wrapper.get('[data-test="preset-form-error-code"]').text()).toContain(
      'agri_product_preset_conflict'
    )
    expect(wrapper.find('[data-test="preset-message"]').exists()).toBe(false)
  })

  it('reports a version conflict and re-seeds the edit from the refreshed list', async () => {
    const { wrapper } = await mountView()
    await wrapper
      .get('[data-test="preset-tab-pest_knowledge"]')
      .trigger('click')
    await flushPromises()

    updateFailure = {
      status: 409,
      code: 'pest_knowledge_preset_version_conflict',
      message: '病虫害条目已被其他管理员修改'
    }
    // Another admin moved the row while the form was open.
    fixtures.pest_knowledge = [pestFixture({ version: 9 })]

    await wrapper.get('[data-test="preset-edit-pest-1"]').trigger('click')
    await wrapper.get('[data-test="preset-answer"]').setValue('第二次编辑')
    await wrapper.get('[data-test="preset-save"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="preset-form-error"]').text()).toContain(
      '已被其他管理员修改'
    )
    expect(wrapper.get('[data-test="preset-form-error"]').text()).toContain(
      '列表已刷新'
    )
    expect(wrapper.get('[data-test="preset-row"]').text()).toContain('v9')

    await wrapper.get('[data-test="preset-form-resync"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="preset-form-error"]').exists()).toBe(false)
  })

  it('adds and removes rows in the calendar text-list editors', async () => {
    const { wrapper } = await mountView()
    await wrapper
      .get('[data-test="preset-tab-agri_calendar"]')
      .trigger('click')
    await flushPromises()

    await wrapper
      .get('[data-test="preset-edit-calendar-litchi-4"]')
      .trigger('click')
    await flushPromises()

    expect(fieldValue(wrapper, '[data-test="preset-tasks-0"]')).toBe(
      '疏除病弱花穗'
    )
    expect(
      wrapper.get('[data-test="preset-month"]').attributes('disabled')
    ).toBeDefined()
    expect(
      wrapper.get('[data-test="preset-product-key"]').attributes('disabled')
    ).toBeDefined()
    expect(wrapper.get('[data-test="preset-stable-id"]').text()).toContain(
      'calendar-litchi-4'
    )
    expect(fieldValue(wrapper, '[data-test="preset-tasks-1"]')).toBe(
      '施保果肥'
    )
    expect(wrapper.findAll('[data-test="preset-tasks-2"]')).toHaveLength(0)

    await wrapper.get('[data-test="preset-tasks-add"]').trigger('click')
    await wrapper.get('[data-test="preset-tasks-2"]').setValue('套袋护果')
    await wrapper.get('[data-test="preset-solar-terms-add"]').trigger('click')
    await wrapper.get('[data-test="preset-solar-terms-2"]').setValue('立夏')

    expect(wrapper.findAll('[data-test="preset-tasks-0"]')).toHaveLength(1)
    expect(fieldValue(wrapper, '[data-test="preset-tasks-2"]')).toBe(
      '套袋护果'
    )
    expect(fieldValue(wrapper, '[data-test="preset-solar-terms-2"]')).toBe(
      '立夏'
    )

    await wrapper.get('[data-test="preset-tasks-remove-1"]').trigger('click')
    expect(fieldValue(wrapper, '[data-test="preset-tasks-1"]')).toBe(
      '套袋护果'
    )
    expect(wrapper.findAll('[data-test="preset-tasks-2"]')).toHaveLength(0)

    await wrapper.get('[data-test="preset-save"]').trigger('click')
    await flushPromises()

    const putCall = callsWith('PUT')[0]
    expect(putCall?.[0]).toBe(
      '/api/admin/presets/agri_calendar/calendar-litchi-4'
    )
    expect(JSON.parse(String(putCall?.[1]?.body))).toEqual({
      product_key: 'litchi',
      month: 4,
      tasks: ['疏除病弱花穗', '套袋护果'],
      management: ['控制土壤湿度'],
      solar_terms: ['清明', '谷雨', '立夏'],
      reminder: '注意防范连续阴雨',
      sort_order: 4,
      is_enabled: true,
      expected_version: 2
    })
  })

  it('adds and removes craft steps and material guide rows', async () => {
    const { wrapper } = await mountView()
    await wrapper
      .get('[data-test="preset-tab-handcraft_crafts"]')
      .trigger('click')
    await flushPromises()

    await wrapper.get('[data-test="preset-edit-guangxiu"]').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('[data-test="preset-step-0"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-test="preset-step-5"]')).toHaveLength(1)
    expect(fieldValue(wrapper, '[data-test="preset-step-no-0"]')).toBe('1')
    expect(fieldValue(wrapper, '[data-test="preset-step-tip-0-0"]')).toBe(
      '保持手稳'
    )
    expect(wrapper.findAll('[data-test="preset-material-0"]')).toHaveLength(1)

    await wrapper.get('[data-test="preset-step-add"]').trigger('click')
    expect(wrapper.findAll('[data-test="preset-step-6"]')).toHaveLength(1)
    await wrapper.get('[data-test="preset-step-remove-6"]').trigger('click')
    expect(wrapper.findAll('[data-test="preset-step-6"]')).toHaveLength(0)

    await wrapper.get('[data-test="preset-material-add"]').trigger('click')
    expect(wrapper.findAll('[data-test="preset-material-1"]')).toHaveLength(1)
    await wrapper.get('[data-test="preset-material-remove-1"]').trigger('click')
    expect(wrapper.findAll('[data-test="preset-material-1"]')).toHaveLength(0)

    await wrapper.get('[data-test="preset-step-tip-add-0"]').trigger('click')
    await wrapper.get('[data-test="preset-step-tip-0-1"]').setValue('针脚均匀')

    await wrapper.get('[data-test="preset-save"]').trigger('click')
    await flushPromises()

    const body = JSON.parse(String(callsWith('PUT')[0]?.[1]?.body))
    expect(body.steps).toHaveLength(6)
    expect(body.steps[0].tips).toEqual(['保持手稳', '针脚均匀'])
    expect(body.material_guide).toHaveLength(1)
    expect(body.expected_version).toBe(2)
  })

  it('keeps a seeded demo case out of reach of edit and stop', async () => {
    fixtures.success_cases = [caseFixture({ is_demo: true })]
    const { wrapper } = await mountView()
    await wrapper
      .get('[data-test="preset-tab-success_cases"]')
      .trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="preset-demo-tag"]').text()).toContain('演示')
    expect(
      wrapper.get('[data-test="preset-edit-case-litchi"]').attributes('disabled')
    ).toBeDefined()
    expect(
      wrapper.get('[data-test="preset-delete-case-litchi"]').attributes('disabled')
    ).toBeDefined()
  })

  it('renders loading, error and empty states with a working retry', async () => {
    listHang = true
    const loading = await mountView()
    expect(loading.wrapper.find('[data-test="preset-loading"]').exists()).toBe(
      true
    )
    loading.wrapper.unmount()

    listHang = false
    listFailure = true
    const failed = await mountView()
    expect(failed.wrapper.get('[data-test="preset-error"]').text()).toContain(
      '预置内容服务暂时不可用'
    )
    expect(failed.wrapper.findAll('[data-test="preset-row"]')).toHaveLength(0)

    listFailure = false
    await failed.wrapper.get('[data-test="preset-retry"]').trigger('click')
    await flushPromises()
    expect(failed.wrapper.find('[data-test="preset-error"]').exists()).toBe(
      false
    )
    expect(failed.wrapper.findAll('[data-test="preset-row"]')).toHaveLength(1)
    failed.wrapper.unmount()

    fixtures.agri_products = []
    const empty = await mountView()
    expect(empty.wrapper.get('[data-test="preset-empty"]').text()).toContain(
      '没有农产品列表'
    )
    empty.wrapper.unmount()
  })
})
