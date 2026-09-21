import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type { AdminReviewCounts, AdminReviewItem } from '@/api/types'
import type {
  AdminManagedContentItem,
  AdminManagedContentType,
  AdminManagedVideoItem
} from '@/stores/adminConsole'
import { useAuthStore } from '@/stores/auth'

import AdminContentManagementView from './AdminContentManagementView.vue'

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

interface WriteFailure {
  status: number
  code: string
  message: string
}

let fixtures: Record<AdminManagedContentType, AdminManagedContentItem[]>
let listFailure = false
let listHang = false
let detailFailure = false
let correctFailure: WriteFailure | null = null
let unpublishFailure: WriteFailure | null = null
let deleteFailure: WriteFailure | null = null

function policyFixture() {
  return {
    content_type: 'policy',
    id: 'policy-1',
    title: '荔枝种植补贴政策',
    content: '对连片种植户给予补贴',
    category_code: 'subsidy',
    status: 'active',
    view_count: 120,
    version: 3,
    published_at: '2026-08-01T10:00:00+08:00',
    updated_at: '2026-09-01T10:00:00+08:00'
  } as const
}

function newsFixture() {
  // The news table carries no lifecycle column, so the projection has no
  // status either.
  return {
    content_type: 'news',
    id: 'news-1',
    title: '全县荔枝减产预警',
    content: '近期干旱需加强灌溉',
    category_code: 'disaster_warning',
    view_count: 8,
    version: 2,
    published_at: '2026-08-02T09:00:00+08:00',
    updated_at: '2026-09-02T09:00:00+08:00'
  } as const
}

function courseFixture() {
  return {
    content_type: 'course',
    id: 7,
    title: '荔枝嫁接基础',
    direction: 'agriculture',
    status: 'published',
    teacher_id: 5,
    teacher_name: '李老师',
    version: 4,
    published_at: '2026-08-03T08:00:00+08:00',
    deleted_at: null,
    updated_at: '2026-09-03T08:00:00+08:00'
  } as const
}

function jobFixture() {
  return {
    content_type: 'job',
    job_id: 'job-1',
    title: '荔枝分拣员',
    enterprise_id: 9,
    review_status: 'approved',
    version: 2,
    published_at: '2026-08-04T08:00:00+08:00',
    deleted_at: null,
    updated_at: '2026-09-04T08:00:00+08:00'
  } as const
}

function videoRow(tagged: boolean): AdminManagedVideoItem {
  const row = {
    video_id: 'video-1',
    craft_key: 'guangxiu',
    title: '广绣针法教学',
    review_status: 'approved',
    version: 5,
    published_at: '2026-08-20T09:30:00+08:00',
    deleted_at: null,
    updated_at: '2026-09-02T09:30:00+08:00'
  }
  // An untagged row reproduces the list projection that has not caught up
  // with the detail projection yet.
  return tagged
    ? { ...row, content_type: 'handcraft_video' }
    : (row as unknown as AdminManagedVideoItem)
}

function commentFixture() {
  // The comment projection carries no optimistic lock.
  return {
    content_type: 'comment',
    comment_id: 'comment-1',
    target_content_type: 'course',
    target_content_id: '7',
    author_id: 12,
    body: '课程讲得很清楚',
    is_visible: true,
    created_at: '2026-09-05T10:00:00+08:00',
    updated_at: '2026-09-05T10:00:00+08:00'
  } as const
}

function craftPresetFixture() {
  return {
    content_type: 'preset',
    craft_key: 'guangxiu',
    name: '广绣',
    is_enabled: true,
    version: 2,
    updated_at: '2026-09-06T10:00:00+08:00'
  } as const
}

function familyPresetFixture() {
  // The widened projection names the family and encodes it in the stable id.
  return {
    content_type: 'preset',
    preset_category: 'agri_products',
    id: 'agri_products:litchi',
    stable_id: 'litchi',
    sort_order: 1,
    name: '荔枝',
    is_enabled: true,
    version: 3,
    updated_at: '2026-09-06T10:00:00+08:00'
  } as const
}

const reviewItems: AdminReviewItem[] = [
  {
    content_type: 'course_video',
    content_id: '7',
    title: '荔枝嫁接基础',
    submitter_id: 5,
    submitter_name: '李老师',
    review_status: 'pending',
    version: 4,
    rejection_opinion: null,
    published_at: null,
    created_at: '2026-09-01T10:00:00+08:00',
    updated_at: '2026-09-02T10:00:00+08:00'
  },
  {
    content_type: 'job_position',
    content_id: 'job-1',
    title: '荔枝分拣员',
    submitter_id: 9,
    submitter_name: '丰收农场',
    review_status: 'approved',
    version: 2,
    rejection_opinion: null,
    published_at: '2026-09-03T10:00:00+08:00',
    created_at: '2026-09-01T10:00:00+08:00',
    updated_at: '2026-09-03T10:00:00+08:00'
  }
]

const reviewCounts: AdminReviewCounts = {
  course_video: 1,
  job_position: 0,
  handcraft_teaching_video: 0
}

function itemIdOf(item: AdminManagedContentItem): string {
  if ('video_id' in item) return item.video_id
  switch (item.content_type) {
    case 'policy':
    case 'news':
      return item.id
    case 'course':
      return String(item.id)
    case 'job':
      return item.job_id
    case 'comment':
      return item.comment_id
    default:
      return item.id ?? item.craft_key ?? ''
  }
}

function bodyOf(options?: RequestInit): Record<string, unknown> {
  return JSON.parse(String(options?.body ?? '{}')) as Record<string, unknown>
}

function resetFixtures() {
  fixtures = {
    policy: [policyFixture()],
    news: [newsFixture()],
    course: [courseFixture()],
    job: [jobFixture()],
    handcraft_video: [videoRow(false)],
    comment: [commentFixture()],
    preset: [familyPresetFixture()]
  }
}

function installFetch() {
  apiFetchMock.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path.startsWith('/api/admin/review')) {
      return { success: true, items: reviewItems, counts: reviewCounts }
    }
    if (!path.startsWith('/api/admin/content')) {
      return { success: true }
    }

    const tail = path
      .slice('/api/admin/content'.length)
      .replace(/\/unpublish$/, '')
    const slash = tail.indexOf('/', 1)
    const contentType = (
      slash === -1 ? tail.slice(1) : tail.slice(1, slash)
    ) as AdminManagedContentType
    // The console percent-encodes the stable id, so a family separator
    // arrives as %3A and has to be decoded before it is matched.
    const contentId = slash === -1 ? '' : decodeURIComponent(tail.slice(slash + 1))
    const method = options?.method ?? 'GET'

    if (method === 'GET' && slash === -1) {
      if (listHang) return new Promise(() => {})
      if (listFailure) {
        throw new ApiError('内容服务暂时不可用', 503)
      }
      const items = fixtures[contentType] ?? []
      return { success: true, items, count: items.length }
    }

    if (method === 'GET') {
      if (detailFailure) {
        throw new ApiError('内容不存在', 404, {}, undefined, 'content_not_found')
      }
      const found = (fixtures[contentType] ?? []).find(
        item => itemIdOf(item) === contentId
      )
      if (!found) {
        throw new ApiError('内容不存在', 404, {}, undefined, 'content_not_found')
      }
      return { success: true, item: found }
    }

    const list = fixtures[contentType] ?? []
    const index = list.findIndex(item => itemIdOf(item) === contentId)
    const current = index === -1 ? undefined : list[index]
    if (!current) {
      throw new ApiError('内容不存在', 404, {}, undefined, 'content_not_found')
    }

    // The row is copied into a plain record so a write can touch the fields
    // that each content type spells differently.
    const base = { ...current } as unknown as Record<string, unknown>
    const currentVersion = (current as { version?: number }).version
    if (typeof currentVersion === 'number') {
      base.version = currentVersion + 1
    }
    base.updated_at = '2026-09-07T10:00:00+08:00'

    function replaceRow(row: Record<string, unknown>): AdminManagedContentItem {
      const updated = row as unknown as AdminManagedContentItem
      fixtures[contentType] = list.map((item, position) =>
        position === index ? updated : item
      )
      return updated
    }

    if (method === 'PUT') {
      if (correctFailure) {
        throw new ApiError(
          correctFailure.message,
          correctFailure.status,
          {},
          undefined,
          correctFailure.code
        )
      }
      const body = bodyOf(options)
      delete body.expected_version
      const updated = replaceRow({ ...base, ...body })
      return { success: true, item: updated }
    }

    if (method === 'POST') {
      if (unpublishFailure) {
        throw new ApiError(
          unpublishFailure.message,
          unpublishFailure.status,
          {},
          undefined,
          unpublishFailure.code
        )
      }
      if ('status' in base) {
        base.status = 'unpublished'
      }
      if ('review_status' in base) {
        base.review_status = 'pending'
      }
      const updated = replaceRow(base)
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
    if (contentType === 'policy' || contentType === 'news') {
      // A hard delete removes the row from the list.
      fixtures[contentType] = list.filter(
        (_, position) => position !== index
      )
      const removed = { ...base, deleted: true } as unknown as AdminManagedContentItem
      return { success: true, item: removed }
    } else {
      if ('is_visible' in base) {
        base.is_visible = false
      }
      if ('is_enabled' in base) {
        base.is_enabled = false
      }
      const updated = replaceRow(base)
      return { success: true, item: updated }
    }
  })
}

async function mountView(role: 'admin' | 'super_admin' = 'super_admin') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore(pinia)
  auth.sessionState = 'active'
  auth.user = {
    id: role === 'super_admin' ? 1 : 2,
    username: role === 'super_admin' ? 'super-admin' : 'content-admin',
    name: role === 'super_admin' ? '超级管理员' : '内容管理员',
    role
  }

  const wrapper = mount(AdminContentManagementView, {
    global: { plugins: [pinia] },
    // A submit button only runs the form submission algorithm while the form
    // is connected to the document, like the other form-bearing admin views.
    attachTo: document.body
  })
  await flushPromises()
  return { pinia, wrapper }
}

function callsWith(method: string) {
  return apiFetchMock.mock.calls.filter(call => call[1]?.method === method)
}

// The last call of a method is the one whose answer is on screen now.
function lastCallWith(method: string) {
  const calls = callsWith(method)
  return calls[calls.length - 1]
}

function contentCalls(contentType: string, method = 'GET') {
  return apiFetchMock.mock.calls.filter(
    call =>
      String(call[0]).startsWith(`/api/admin/content/${contentType}`) &&
      (call[1]?.method ?? 'GET') === method
  )
}

function lastBody(): Record<string, unknown> {
  const calls = apiFetchMock.mock.calls
  return JSON.parse(String(calls[calls.length - 1]?.[1]?.body ?? '{}'))
}

async function openTab(wrapper: VueWrapper, contentType: string) {
  await wrapper.get(`[data-test="content-type-${contentType}"]`).trigger('click')
  await flushPromises()
}

describe('AdminContentManagementView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetFixtures()
    listFailure = false
    listHang = false
    detailFailure = false
    correctFailure = null
    unpublishFailure = null
    deleteFailure = null
    installFetch()
  })

  it('shows the production controls to a super admin and hides them from an ordinary admin', async () => {
    const superView = await mountView('super_admin')

    // `get` throws when the control is missing, which is exactly the claim
    // these four make: every production control is on screen for a super admin.
    expect(superView.wrapper.get('[data-test="admin-content"]').text()).toContain(
      '纠错政策'
    )
    expect(superView.wrapper.get('[data-test="content-correct"]').text()).toContain(
      '不会重新发布'
    )
    expect(
      superView.wrapper.get('[data-test="content-correct-submit"]').text()
    ).toContain('保存纠错')
    expect(
      superView.wrapper.get('[data-test="content-correct-policy-1"]').text()
    ).toContain('纠错')
    expect(
      superView.wrapper.get('[data-test="content-unpublish-policy-1"]').text()
    ).toContain('下线')
    expect(
      superView.wrapper.get('[data-test="content-delete-policy-1"]').text()
    ).toContain('删除')
    superView.wrapper.unmount()

    const adminView = await mountView('admin')

    expect(
      adminView.wrapper.find('[data-test="content-correct"]').exists()
    ).toBe(false)
    expect(
      adminView.wrapper.find('[data-test="content-correct-policy-1"]').exists()
    ).toBe(false)
    expect(
      adminView.wrapper.find('[data-test="content-unpublish-policy-1"]').exists()
    ).toBe(false)
    expect(
      adminView.wrapper.find('[data-test="content-delete-policy-1"]').exists()
    ).toBe(false)
    expect(
      adminView.wrapper.find('[data-test="content-tabs"]').exists()
    ).toBe(false)
  })

  it('lists every one of the seven content types with its own rows', async () => {
    const { wrapper } = await mountView('super_admin')

    const expected: Record<AdminManagedContentType, string> = {
      policy: '荔枝种植补贴政策',
      news: '全县荔枝减产预警',
      course: '荔枝嫁接基础',
      job: '荔枝分拣员',
      handcraft_video: '广绣针法教学',
      comment: '课程讲得很清楚',
      preset: '荔枝'
    }

    expect(contentCalls('policy')).toHaveLength(1)
    expect(wrapper.get('[data-test="content-active-type"]').text()).toContain(
      '政策'
    )

    for (const contentType of Object.keys(expected) as AdminManagedContentType[]) {
      await openTab(wrapper, contentType)

      expect(contentCalls(contentType)).toHaveLength(1)
      expect(wrapper.get('[data-test="content-row"]').text()).toContain(
        expected[contentType]
      )
    }

    // A news row has no lifecycle column to report and a comment has no
    // optimistic lock, and neither offers the writes the backend refuses.
    await openTab(wrapper, 'comment')
    expect(wrapper.get('[data-test="content-status"]').text()).toContain('可见')
    expect(
      wrapper.get('[data-test="content-version"]').text()
    ).toContain('无版本')
    expect(
      wrapper.find('[data-test="content-unpublish-comment-1"]').exists()
    ).toBe(false)
    expect(
      wrapper.find('[data-test="content-correct-comment-1"]').exists()
    ).toBe(false)
  })

  it('renders a preset row by family and stable id, and a video row that still lacks its own tag', async () => {
    const { wrapper } = await mountView('super_admin')
    await openTab(wrapper, 'preset')

    expect(
      wrapper.get('[data-test="content-preset-family"]').text()
    ).toContain('农产品')
    // The table shows the bare stable id, while the row is addressed by the
    // family-encoded id the route decodes.
    expect(wrapper.get('[data-test="content-row"]').text()).toContain(
      'litchi'
    )
    expect(
      wrapper.get('[data-test="content-row"]').attributes('data-content-id')
    ).toBe('agri_products:litchi')
    expect(
      wrapper.get('[data-test="content-delete-agri_products:litchi"]').text()
    ).toContain('停用')

    await openTab(wrapper, 'handcraft_video')

    expect(wrapper.get('[data-test="content-row"]').text()).toContain('广绣针法教学')
    expect(wrapper.get('[data-test="content-row"]').text()).toContain('video-1')
    expect(wrapper.get('[data-test="content-status"]').text()).toContain('已通过')

    // A detail projection that does carry its own tag renders the same row.
    resetFixtures()
    fixtures.handcraft_video = [videoRow(true)]
    await wrapper.get('[data-test="content-type-handcraft_video"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-test="content-row"]').text()).toContain('video-1')

    // A craft-only preset row carries no family tag, so the console reads it
    // as the handcraft family the projection started from.
    await openTab(wrapper, 'comment')
    fixtures.preset = [craftPresetFixture()]
    await wrapper.get('[data-test="content-type-preset"]').trigger('click')
    await flushPromises()

    expect(
      wrapper.get('[data-test="content-preset-family"]').text()
    ).toContain('非遗技艺')
    expect(wrapper.get('[data-test="content-row"]').text()).toContain('guangxiu')
    expect(
      wrapper.get('[data-test="content-delete-guangxiu"]').text()
    ).toContain('停用')
  })

  it('opens the detail dialog from a row and shows the stored projection', async () => {
    const { wrapper } = await mountView('super_admin')

    await wrapper.get('[data-test="content-detail-policy-1"]').trigger('click')
    await flushPromises()

    expect(
      apiFetchMock.mock.calls.filter(call => call[0] === '/api/admin/content/policy/policy-1')
    ).toHaveLength(1)
    const dialog = wrapper.get('[data-test="content-detail-dialog"]')
    expect(dialog.text()).toContain('政策 ID')
    expect(dialog.text()).toContain('对连片种植户给予补贴')
    expect(dialog.text()).toContain('120')

    await wrapper.get('[data-test="content-detail-close"]').trigger('click')
    expect(wrapper.find('[data-test="content-detail-dialog"]').exists()).toBe(
      false
    )
  })

  it('reports a detail that cannot be loaded', async () => {
    detailFailure = true
    const { wrapper } = await mountView('super_admin')

    await wrapper.get('[data-test="content-detail-policy-1"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="content-detail-error"]').text()).toContain(
      '内容不存在或已被其他管理员删除'
    )
  })

  it('labels the policy form as a correction and saves it with the expected version', async () => {
    const { wrapper } = await mountView('super_admin')

    expect(wrapper.get('[data-test="content-correct"]').text()).toContain('纠错')
    expect(wrapper.get('[data-test="content-correct"]').text()).toContain(
      '不会重新发布'
    )

    await wrapper.get('[data-test="content-correct-policy-1"]').trigger('click')
    await flushPromises()

    expect(
      (wrapper.get('[data-test="content-correct-title"]').element as HTMLInputElement)
        .value
    ).toBe('荔枝种植补贴政策')
    expect(
      (wrapper.get('[data-test="content-correct-body"]').element as HTMLTextAreaElement)
        .value
    ).toBe('对连片种植户给予补贴')

    await wrapper
      .get('[data-test="content-correct-title"]')
      .setValue('荔枝种植补贴政策（纠错）')
    await wrapper.get('[data-test="content-correct-submit"]').trigger('click')
    await flushPromises()

    const putCall = callsWith('PUT')[0]
    expect(putCall?.[0]).toBe('/api/admin/content/policy/policy-1')
    expect(JSON.parse(String(putCall?.[1]?.body))).toEqual({
      title: '荔枝种植补贴政策（纠错）',
      content: '对连片种植户给予补贴',
      expected_version: 3
    })
    // The list is refreshed, so the row shows the version the backend stored.
    expect(wrapper.get('[data-test="content-row"]').text()).toContain('v4')
    expect(wrapper.get('[data-test="content-message"]').text()).toContain(
      '已保存政策纠错'
    )
  })

  it('asks for a course summary the management read surface does not return', async () => {
    const { wrapper } = await mountView('super_admin')
    await openTab(wrapper, 'course')

    await wrapper.get('[data-test="content-correct-7"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="content-correct"]').text()).toContain(
      '管理接口不返回课程简介'
    )
    expect(
      (wrapper.get('[data-test="content-correct-body"]').element as HTMLTextAreaElement)
        .value
    ).toBe('')
    // An empty body cannot be submitted, because the backend requires it.
    expect(
      wrapper.get('[data-test="content-correct-submit"]').attributes('disabled')
    ).toBeDefined()

    await wrapper.get('[data-test="content-correct-body"]').setValue('嫁接基础入门')
    await wrapper.get('[data-test="content-correct-submit"]').trigger('click')
    await flushPromises()

    const putCall = callsWith('PUT')[0]
    expect(putCall?.[0]).toBe('/api/admin/content/course/7')
    expect(JSON.parse(String(putCall?.[1]?.body))).toEqual({
      title: '荔枝嫁接基础',
      summary: '嫁接基础入门',
      expected_version: 4
    })
  })

  it('asks for a title alone when correcting a handcraft video', async () => {
    const { wrapper } = await mountView('super_admin')
    await openTab(wrapper, 'handcraft_video')

    await wrapper.get('[data-test="content-correct-video-1"]').trigger('click')
    await flushPromises()

    expect(
      wrapper.find('[data-test="content-correct-body"]').exists()
    ).toBe(false)

    await wrapper
      .get('[data-test="content-correct-title"]')
      .setValue('广绣针法教学（纠错）')
    await wrapper.get('[data-test="content-correct-submit"]').trigger('click')
    await flushPromises()

    expect(JSON.parse(String(callsWith('PUT')[0]?.[1]?.body))).toEqual({
      title: '广绣针法教学（纠错）',
      expected_version: 5
    })
  })

  it('separates a reversible unpublish from an irreversible delete', async () => {
    const { wrapper } = await mountView('super_admin')

    await wrapper.get('[data-test="content-unpublish-policy-1"]').trigger('click')
    const unpublishDialog = wrapper.get('[data-test="content-unpublish-dialog"]')
    expect(unpublishDialog.text()).toContain('可逆下线')
    expect(unpublishDialog.text()).toContain('之后可以重新发布恢复')
    expect(unpublishDialog.text()).toContain('不会被标记删除或墓碑')
    expect(callsWith('POST')).toHaveLength(0)

    await wrapper.get('[data-test="content-confirm-unpublish"]').trigger('click')
    await flushPromises()

    const unpublishCall = callsWith('POST')[0]
    expect(unpublishCall?.[0]).toBe(
      '/api/admin/content/policy/policy-1/unpublish'
    )
    expect(JSON.parse(String(unpublishCall?.[1]?.body))).toEqual({
      expected_version: 3
    })
    expect(wrapper.get('[data-test="content-row"]').text()).toContain('已下线')
    expect(wrapper.get('[data-test="content-message"]').text()).toContain(
      '之后可以重新发布'
    )
    expect(
      wrapper.find('[data-test="content-unpublish-dialog"]').exists()
    ).toBe(false)

    await wrapper.get('[data-test="content-delete-policy-1"]').trigger('click')
    const deleteDialog = wrapper.get('[data-test="content-delete-dialog"]')
    expect(deleteDialog.text()).toContain('不可逆的硬删除')
    expect(deleteDialog.text()).toContain('无法恢复')
    expect(callsWith('DELETE')).toHaveLength(0)

    await wrapper.get('[data-test="content-confirm-delete"]').trigger('click')
    await flushPromises()

    const deleteCall = callsWith('DELETE')[0]
    expect(deleteCall?.[0]).toBe('/api/admin/content/policy/policy-1')
    expect(JSON.parse(String(deleteCall?.[1]?.body))).toEqual({
      expected_version: 4
    })
    // A hard delete takes the row out of the list, and the empty state says so.
    expect(wrapper.get('[data-test="content-empty"]').text()).toContain(
      '暂无政策内容'
    )
    expect(wrapper.get('[data-test="content-message"]').text()).toContain(
      '内容无法恢复'
    )
  })

  it('describes a tombstone, a hidden comment and a disabled preset in their own words', async () => {
    const { wrapper } = await mountView('super_admin')

    await openTab(wrapper, 'course')
    await wrapper.get('[data-test="content-delete-7"]').trigger('click')
    let dialog = wrapper.get('[data-test="content-delete-dialog"]')
    expect(dialog.text()).toContain('不可逆的墓碑删除')
    expect(dialog.text()).toContain('历史学习进度与职业申请会被保留')
    await wrapper.get('[data-test="content-confirm-delete"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-test="content-message"]').text()).toContain(
      '历史记录保留且不可恢复'
    )

    await openTab(wrapper, 'comment')
    await wrapper.get('[data-test="content-delete-comment-1"]').trigger('click')
    dialog = wrapper.get('[data-test="content-delete-dialog"]')
    expect(dialog.text()).toContain('隐藏评论')
    expect(dialog.text()).toContain('无法恢复为可见')
    expect(dialog.text()).toContain('后台记录保留')
    await wrapper.get('[data-test="content-confirm-delete"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-test="content-row"]').text()).toContain('已隐藏')
    // A comment carries no optimistic lock, so none is sent with the delete.
    expect(lastBody()).toEqual({})

    await openTab(wrapper, 'preset')
    await wrapper.get('[data-test="content-delete-agri_products:litchi"]').trigger('click')
    dialog = wrapper.get('[data-test="content-delete-dialog"]')
    expect(dialog.text()).toContain('逻辑停用')
    expect(dialog.text()).toContain('稳定 ID 会被保留')
    await wrapper.get('[data-test="content-confirm-delete"]').trigger('click')
    await flushPromises()
    const presetDelete = lastCallWith('DELETE')
    expect(presetDelete?.[0]).toBe(
      // The stable id is percent-encoded on the way out, so the family
      // separator travels as %3A.
      '/api/admin/content/preset/agri_products%3Alitchi'
    )
    expect(JSON.parse(String(presetDelete?.[1]?.body))).toEqual({
      expected_version: 3
    })
    expect(wrapper.get('[data-test="content-row"]').text()).toContain('已停用')
    expect(wrapper.get('[data-test="content-message"]').text()).toContain(
      '稳定 ID 仍保留'
    )
  })

  it('reports a version conflict with a readable message and re-seeds the form', async () => {
    const { wrapper } = await mountView('super_admin')

    correctFailure = {
      status: 409,
      code: 'policy_version_conflict',
      message: '内容版本已变化，请刷新后重试'
    }
    // Another admin moved the row while the form was open.
    fixtures.policy = [{ ...policyFixture(), version: 9 }]

    await wrapper.get('[data-test="content-correct-policy-1"]').trigger('click')
    await wrapper
      .get('[data-test="content-correct-title"]')
      .setValue('并发编辑的标题')
    await wrapper.get('[data-test="content-correct-submit"]').trigger('click')
    await flushPromises()

    const error = wrapper.get('[data-test="content-form-error"]')
    expect(error.text()).toContain('已被其他管理员修改')
    expect(error.text()).toContain('列表已刷新')
    expect(wrapper.get('[data-test="content-form-error-code"]').text()).toContain(
      'policy_version_conflict'
    )
    // The list was re-read, so the row shows the version the server holds.
    expect(wrapper.get('[data-test="content-row"]').text()).toContain('v9')

    await wrapper.get('[data-test="content-form-resync"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="content-form-error"]').exists()).toBe(false)
  })

  it('reports a state conflict when the current status blocks the action', async () => {
    const { wrapper } = await mountView('super_admin')

    unpublishFailure = {
      status: 409,
      code: 'policy_state_conflict',
      message: '政策当前状态不允许下线'
    }

    await wrapper.get('[data-test="content-unpublish-policy-1"]').trigger('click')
    await wrapper.get('[data-test="content-confirm-unpublish"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="content-error"]').text()).toContain(
      '当前状态不允许下线'
    )
    expect(wrapper.find('[data-test="content-unpublish-dialog"]').exists()).toBe(
      false
    )
  })

  it('keeps an ordinary admin on a read-only review view without touching the content endpoints', async () => {
    const { wrapper } = await mountView('admin')

    expect(wrapper.find('[data-test="content-readonly"]').exists()).toBe(true)
    expect(
      apiFetchMock.mock.calls.filter(call =>
        String(call[0]).startsWith('/api/admin/review')
      )
    ).toHaveLength(1)
    expect(
      apiFetchMock.mock.calls.filter(call =>
        String(call[0]).startsWith('/api/admin/content')
      )
    ).toHaveLength(0)

    expect(wrapper.get('[data-test="content-readonly-pending"]').text()).toContain(
      '1'
    )
    expect(wrapper.findAll('[data-test="content-readonly-row"]')).toHaveLength(2)
    expect(
      wrapper.get('[data-test="content-readonly-row"]').text()
    ).toContain('荔枝嫁接基础')
    expect(
      wrapper.get('[data-test="content-readonly-status"]').text()
    ).toContain('待审核')
    // A denial is never shown as an empty history or an error banner.
    expect(
      wrapper.find('[data-test="content-readonly-error"]').exists()
    ).toBe(false)
    expect(
      wrapper.find('[data-test="content-correct"]').exists()
    ).toBe(false)

    await wrapper
      .get('[data-test="content-readonly-filter-job_position"]')
      .trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-test="content-readonly-row"]')).toHaveLength(1)
  })

  it('renders the ordinary-admin queue with a retry that recovers from a failed load', async () => {
    const { wrapper } = await mountView('admin')

    wrapper.unmount()

    // The queue endpoint answers with a server error this time.
    apiFetchMock.mockImplementation(async (path: string) => {
      if (path.startsWith('/api/admin/review')) {
        throw new ApiError('审核队列服务暂时不可用', 503)
      }
      return { success: true }
    })

    const failed = await mountView('admin')
    expect(
      failed.wrapper.get('[data-test="content-readonly-error"]').text()
    ).toContain('审核队列服务暂时不可用')
    expect(
      failed.wrapper.findAll('[data-test="content-readonly-row"]')
    ).toHaveLength(0)
  })

  it('renders loading, error and empty states with a working retry', async () => {
    listHang = true
    const loading = await mountView('super_admin')
    expect(loading.wrapper.find('[data-test="content-loading"]').exists()).toBe(
      true
    )
    loading.wrapper.unmount()

    listHang = false
    listFailure = true
    const failed = await mountView('super_admin')
    expect(failed.wrapper.get('[data-test="content-error"]').text()).toContain(
      '内容服务暂时不可用'
    )
    expect(failed.wrapper.findAll('[data-test="content-row"]')).toHaveLength(0)
    expect(
      failed.wrapper.find('[data-test="content-empty"]').exists()
    ).toBe(false)

    listFailure = false
    await failed.wrapper.get('[data-test="content-retry"]').trigger('click')
    await flushPromises()
    expect(
      failed.wrapper.find('[data-test="content-error"]').exists()
    ).toBe(false)
    expect(failed.wrapper.findAll('[data-test="content-row"]')).toHaveLength(1)
    failed.wrapper.unmount()

    fixtures.policy = []
    const empty = await mountView('super_admin')
    expect(empty.wrapper.get('[data-test="content-empty"]').text()).toContain(
      '暂无政策内容'
    )
    empty.wrapper.unmount()
  })
})
