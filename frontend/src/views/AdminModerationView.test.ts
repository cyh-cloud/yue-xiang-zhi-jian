import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type {
  AdminCommentReport,
  AdminFeedbackRecord,
  AdminModerationComment
} from '@/stores/adminConsole'
import { useAuthStore } from '@/stores/auth'

import AdminModerationView from './AdminModerationView.vue'

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

function commentFixture(
  patch: Partial<AdminModerationComment> = {}
): AdminModerationComment {
  return {
    comment_id: 'comment-1',
    content_type: 'course_video',
    content_id: 'course-9',
    author_id: 7,
    author: { username: 'student-qi', name: '小齐' },
    parent_comment_id: null,
    body: '保果药剂用多了会不会烧花',
    is_teacher_reply: false,
    is_visible: true,
    created_at: '2026-09-20T08:00:00+08:00',
    updated_at: '2026-09-20T08:00:00+08:00',
    ...patch
  }
}

function reportFixture(
  patch: Partial<AdminCommentReport> = {}
): AdminCommentReport {
  return {
    report_id: 'report-1',
    comment_id: 'comment-1',
    reporter_id: 12,
    reporter: { username: 'student-ye', name: '小叶' },
    reason: '评论包含广告信息',
    status: 'pending',
    resolver_id: null,
    resolver: { username: '', name: '' },
    result: null,
    comment_is_visible: true,
    created_at: '2026-09-20T09:00:00+08:00',
    updated_at: '2026-09-20T09:00:00+08:00',
    resolved_at: null,
    ...patch
  }
}

function feedbackFixture(
  patch: Partial<AdminFeedbackRecord> = {}
): AdminFeedbackRecord {
  return {
    feedback_id: 'feedback-1',
    submitter_id: 21,
    submitter: { username: 'student-lin', name: '小林' },
    body: '课程视频在弱网下无法播放',
    status: 'pending',
    idempotency_key: 'key-1',
    handler_id: null,
    handler: { username: '', name: '' },
    result: null,
    created_at: '2026-09-20T10:00:00+08:00',
    updated_at: '2026-09-20T10:00:00+08:00',
    ...patch
  }
}

let comments: AdminModerationComment[] = []
let reports: AdminCommentReport[] = []
let feedback: AdminFeedbackRecord[] = []
let deleteOutcome: 'hidden' | 'already-hidden' | 'missing' = 'hidden'
let resolveOutcome: 'fresh' | 'repeat' = 'fresh'
let feedbackOutcome: 'fresh' | 'repeat' = 'fresh'
let listFailure: 'none' | 'comments' = 'none'

function page<T extends object>(items: T[], path: string) {
  const query = path.includes('?') ? path.slice(path.indexOf('?') + 1) : ''
  const params = new URLSearchParams(query)
  const limit = Number(params.get('limit') ?? '20')
  const offset = Number(params.get('offset') ?? '0')
  const slice = items.slice(offset, offset + limit)
  return { success: true as const, items: slice, count: slice.length }
}

function installFetch() {
  apiFetchMock.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path.startsWith('/api/admin/comments') && options?.method === 'DELETE') {
      if (deleteOutcome === 'missing') {
        throw new ApiError('评论不存在', 404, {}, undefined, 'comment_not_found')
      }
      return {
        success: true,
        comment_id: 'comment-1',
        is_visible: false,
        changed: deleteOutcome === 'hidden',
        updated_at: '2026-09-21T11:00:00+08:00'
      }
    }
    if (path.startsWith('/api/admin/comments')) {
      if (listFailure === 'comments') {
        throw new ApiError('评论队列暂时不可用', 503)
      }
      const params = new URLSearchParams(
        path.includes('?') ? path.slice(path.indexOf('?') + 1) : ''
      )
      const visible = params.get('is_visible')
      const keyword = params.get('keyword')
      const filtered = comments.filter(
        item =>
          (visible === null ||
            (visible === '1' ? item.is_visible : !item.is_visible)) &&
          (keyword === null || item.body.includes(keyword))
      )
      return page(filtered, path)
    }
    if (path.startsWith('/api/admin/reports') && path.endsWith('/resolve')) {
      const body = JSON.parse(String(options?.body)) as {
        confirmed: boolean
        result: string
      }
      const changed = resolveOutcome === 'fresh'
      // A repeat answers with the decision already on file, which is not the
      // text the operator just typed.
      const stored = changed
        ? reportFixture({
            status: body.confirmed ? 'confirmed' : 'rejected',
            resolver_id: 1,
            resolver: { username: 'admin', name: '管理员' },
            result: body.result,
            resolved_at: '2026-09-21T11:00:00+08:00',
            updated_at: '2026-09-21T11:00:00+08:00',
            comment_is_visible: body.confirmed ? false : true
          })
        : reportFixture({
            status: 'confirmed',
            resolver_id: 1,
            resolver: { username: 'admin', name: '管理员' },
            result: '已存储的决定：广告信息已核实',
            resolved_at: '2026-09-20T09:30:00+08:00',
            updated_at: '2026-09-20T09:30:00+08:00',
            comment_is_visible: false
          })
      return { success: true, report: { ...stored, changed } }
    }
    if (path.startsWith('/api/admin/reports')) {
      const params = new URLSearchParams(
        path.includes('?') ? path.slice(path.indexOf('?') + 1) : ''
      )
      const status = params.get('status')
      const filtered = reports.filter(
        item => status === null || item.status === status
      )
      return page(filtered, path)
    }
    if (path.startsWith('/api/admin/feedback') && options?.method === 'PATCH') {
      const body = JSON.parse(String(options?.body)) as {
        status: AdminFeedbackRecord['status']
        result: string
      }
      const changed = feedbackOutcome === 'fresh'
      const stored = changed
        ? feedbackFixture({
            status: body.status,
            handler_id: 1,
            handler: { username: 'admin', name: '管理员' },
            result: body.result,
            updated_at: '2026-09-21T11:00:00+08:00'
          })
        : feedbackFixture({
            status: 'closed',
            handler_id: 1,
            handler: { username: 'admin', name: '管理员' },
            result: '已存储的决定：重复反馈，直接关闭',
            updated_at: '2026-09-20T10:30:00+08:00'
          })
      return { success: true, feedback: { ...stored, changed } }
    }
    if (path.startsWith('/api/admin/feedback')) {
      const params = new URLSearchParams(
        path.includes('?') ? path.slice(path.indexOf('?') + 1) : ''
      )
      const status = params.get('status')
      const filtered = feedback.filter(
        item => status === null || item.status === status
      )
      return page(filtered, path)
    }
    return { success: true }
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

  const wrapper = mount(AdminModerationView, {
    global: { plugins: [pinia] }
  })
  await flushPromises()
  return { pinia, wrapper }
}

function lastPath(): string {
  const calls = apiFetchMock.mock.calls
  const call = calls[calls.length - 1]
  return String(call?.[0] ?? '')
}

describe('AdminModerationView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    comments = [commentFixture()]
    reports = [reportFixture()]
    feedback = [feedbackFixture()]
    deleteOutcome = 'hidden'
    resolveOutcome = 'fresh'
    feedbackOutcome = 'fresh'
    listFailure = 'none'
    installFetch()
  })

  it('opens the patrol queue for both admin roles', async () => {
    for (const role of ['admin', 'super_admin'] as const) {
      const { wrapper } = await mountView(role)

      expect(wrapper.find('[data-test="admin-moderation"]').exists()).toBe(true)
      expect(wrapper.findAll('[data-test="comment-row"]')).toHaveLength(1)
      expect(
        wrapper.find('[data-test="moderation-tab-comments"]').exists()
      ).toBe(true)
      expect(wrapper.find('[data-test="moderation-tab-reports"]').exists()).toBe(
        true
      )
      expect(
        wrapper.find('[data-test="moderation-tab-feedback"]').exists()
      ).toBe(true)
      wrapper.unmount()
    }
  })

  it('loads the comment queue on mount with the page size in the query', async () => {
    await mountView()

    expect(lastPath()).toContain('/api/admin/comments')
    expect(lastPath()).toContain('limit=20')
    expect(lastPath()).toContain('offset=0')
  })

  it('states in the delete confirmation that no notification is sent', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('[data-test="comment-delete-comment-1"]').trigger('click')
    const dialog = wrapper.get('[data-test="comment-delete-dialog"]')

    expect(dialog.text()).toContain('不会发送通知')
    expect(dialog.text()).toContain('作者与相关用户都不会被告知')
    expect(dialog.text()).toContain('父子评论的可见性不级联')
    expect(wrapper.find('[data-test="comment-delete-dialog"]').exists()).toBe(
      true
    )
    expect(
      apiFetchMock.mock.calls.filter(call => call[1]?.method === 'DELETE')
    ).toHaveLength(0)

    await wrapper.get('[data-test="confirm-comment-delete"]').trigger('click')
    await flushPromises()

    const deleteCall = apiFetchMock.mock.calls.find(
      call => call[1]?.method === 'DELETE'
    )
    expect(deleteCall?.[0]).toBe('/api/admin/comments/comment-1')
    expect(wrapper.get('[data-test="comment-visibility"]').text()).toContain(
      '已隐藏'
    )
    expect(wrapper.find('[data-test="comment-delete-comment-1"]').exists()).toBe(
      false
    )
    expect(wrapper.get('[data-test="moderation-message"]').text()).toContain(
      '不会通知作者与相关用户'
    )
  })

  it('reports a repeat delete as unchanged and never re-renders the action', async () => {
    deleteOutcome = 'already-hidden'
    comments = [commentFixture({ is_visible: false })]
    const { wrapper } = await mountView()

    expect(wrapper.get('[data-test="comment-hidden"]').text()).toContain('已隐藏')
    expect(wrapper.find('[data-test="comment-delete-comment-1"]').exists()).toBe(
      false
    )
  })

  it('maps a missing comment to a readable message and keeps the dialog open', async () => {
    deleteOutcome = 'missing'
    const { wrapper } = await mountView()

    await wrapper.get('[data-test="comment-delete-comment-1"]').trigger('click')
    await wrapper.get('[data-test="confirm-comment-delete"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="moderation-error"]').text()).toContain(
      '评论不存在或已被删除'
    )
    expect(wrapper.find('[data-test="comment-delete-dialog"]').exists()).toBe(true)
  })

  it('renders a reply whose parent left the page without a dangling placeholder', async () => {
    comments = [
      commentFixture(),
      commentFixture({
        comment_id: 'comment-reply-1',
        parent_comment_id: 'comment-1',
        body: '我按老师说的做了，效果好'
      }),
      commentFixture({
        comment_id: 'comment-orphan-1',
        parent_comment_id: 'comment-vanished-9',
        body: '追问肥水比例'
      })
    ]
    const { wrapper } = await mountView()

    const rows = wrapper.findAll('[data-test="comment-row"]')
    expect(rows).toHaveLength(3)
    expect(wrapper.text()).not.toContain('undefined')
    expect(rows[1].text()).toContain('回复：保果药剂用多了会不会烧花')
    expect(rows[2].text()).toContain('原评论已隐藏')
    expect(rows[2].find('[data-test="comment-delete-comment-orphan-1"]').exists()).toBe(
      true
    )
  })

  it('pages the queue by the count the page actually carries', async () => {
    comments = Array.from({ length: 25 }, (_, index) =>
      commentFixture({
        comment_id: `comment-${index + 1}`,
        body: `评论正文 ${index + 1}`
      })
    )
    const { wrapper } = await mountView()

    expect(wrapper.findAll('[data-test="comment-row"]')).toHaveLength(20)
    expect(wrapper.get('[data-test="moderation-count"]').text()).toContain('本页 20 条')
    expect(wrapper.get('[data-test="moderation-page"]').text()).toContain('第 1 页')
    expect(
      wrapper.get('[data-test="moderation-next"]').attributes('disabled')
    ).toBeUndefined()
    expect(
      wrapper.get('[data-test="moderation-prev"]').attributes('disabled')
    ).toBeDefined()

    await wrapper.get('[data-test="moderation-next"]').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('[data-test="comment-row"]')).toHaveLength(5)
    expect(wrapper.get('[data-test="moderation-count"]').text()).toContain('本页 5 条')
    expect(wrapper.get('[data-test="moderation-page"]').text()).toContain('第 2 页')
    expect(
      wrapper.get('[data-test="moderation-next"]').attributes('disabled')
    ).toBeDefined()
    expect(
      wrapper.get('[data-test="moderation-prev"]').attributes('disabled')
    ).toBeUndefined()
    expect(lastPath()).toContain('offset=20')

    await wrapper.get('[data-test="moderation-page-size"]').setValue('50')
    await flushPromises()

    expect(wrapper.findAll('[data-test="comment-row"]')).toHaveLength(25)
    expect(wrapper.get('[data-test="moderation-page"]').text()).toContain('第 1 页')
    expect(lastPath()).toContain('limit=50')
    expect(lastPath()).toContain('offset=0')
  })

  it('applies the comment filters as timezone-aware stamps', async () => {
    const { wrapper } = await mountView()
    apiFetchMock.mockClear()

    await wrapper
      .get('[data-test="moderation-content-type"]')
      .setValue('handcraft_teaching_video')
    await wrapper.get('[data-test="moderation-visibility"]').setValue('hidden')
    await wrapper.get('[data-test="moderation-keyword"]').setValue('广告')
    await wrapper.get('[data-test="moderation-from"]').setValue('2026-09-01')
    await wrapper.get('[data-test="moderation-to"]').setValue('2026-09-30')
    await wrapper.get('[data-test="moderation-apply"]').trigger('click')
    await flushPromises()

    const requested = lastPath()
    expect(requested).toContain('content_type=handcraft_teaching_video')
    expect(requested).toContain('is_visible=0')
    expect(requested).toContain('keyword=' + encodeURIComponent('广告'))
    expect(requested).toContain(
      'created_from=' + encodeURIComponent('2026-09-01T00:00:00+08:00')
    )
    expect(requested).toContain(
      'created_to=' + encodeURIComponent('2026-09-30T23:59:59+08:00')
    )
  })

  it('renders loading, error and empty states with a working retry', async () => {
    apiFetchMock.mockImplementation(() => new Promise(() => {}))
    const loading = await mountView()
    expect(
      loading.wrapper.find('[data-test="moderation-loading"]').exists()
    ).toBe(true)
    loading.wrapper.unmount()

    installFetch()
    listFailure = 'comments'
    const failed = await mountView()

    expect(failed.wrapper.get('[data-test="moderation-error"]').text()).toContain(
      '评论队列暂时不可用'
    )
    expect(failed.wrapper.findAll('[data-test="comment-row"]')).toHaveLength(0)

    listFailure = 'none'
    await failed.wrapper.get('[data-test="moderation-retry"]').trigger('click')
    await flushPromises()

    expect(failed.wrapper.find('[data-test="moderation-error"]').exists()).toBe(
      false
    )
    expect(failed.wrapper.findAll('[data-test="comment-row"]')).toHaveLength(1)
    failed.wrapper.unmount()

    comments = []
    const empty = await mountView()
    expect(empty.wrapper.get('[data-test="moderation-empty"]').text()).toContain(
      '没有评论列表'
    )
    empty.wrapper.unmount()
  })

  it('requires a result note before a report can be resolved', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('[data-test="moderation-tab-reports"]').trigger('click')
    await flushPromises()

    await wrapper.get('[data-test="report-confirm-report-1"]').trigger('click')
    const submit = wrapper.get('[data-test="confirm-report-action"]')

    expect(submit.attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-test="report-result-count"]').text()).toContain('0 / 500')

    await wrapper.get('[data-test="report-result"]').setValue('   ')
    expect(
      wrapper.get('[data-test="confirm-report-action"]').attributes('disabled')
    ).toBeDefined()

    await wrapper.get('[data-test="report-result"]').setValue('已核实为广告')
    expect(
      wrapper.get('[data-test="confirm-report-action"]').attributes('disabled')
    ).toBeUndefined()

    await wrapper.get('[data-test="confirm-report-action"]').trigger('click')
    await flushPromises()

    const resolveCall = apiFetchMock.mock.calls.find(
      call => call[1]?.method === 'POST'
    )
    expect(resolveCall?.[0]).toBe('/api/admin/reports/report-1/resolve')
    expect(JSON.parse(String(resolveCall?.[1]?.body))).toEqual({
      confirmed: true,
      result: '已核实为广告'
    })
  })

  it('renders the stored decision as the terminal state after a resolve', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('[data-test="moderation-tab-reports"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="report-confirm-report-1"]').trigger('click')
    await wrapper.get('[data-test="report-result"]').setValue('已核实为广告')
    await wrapper.get('[data-test="confirm-report-action"]').trigger('click')
    await flushPromises()

    const row = wrapper.get('[data-test="report-row"]')
    expect(row.find('[data-test="report-status"]').text()).toContain('已确认')
    expect(row.find('[data-test="report-decision"]').text()).toBe('已核实为广告')
    expect(row.text()).toContain('评论已隐藏')
    expect(row.find('[data-test="report-confirm-report-1"]').exists()).toBe(false)
    expect(row.find('[data-test="report-reject-report-1"]').exists()).toBe(false)
    expect(row.find('[data-test="report-processed"]').text()).toContain(
      '已处理，不可改判'
    )
    expect(wrapper.get('[data-test="moderation-message"]').text()).toContain(
      '不会通知举报人与作者'
    )
  })

  it('keeps a repeat resolve on the decision already on file', async () => {
    resolveOutcome = 'repeat'
    const { wrapper } = await mountView()

    await wrapper.get('[data-test="moderation-tab-reports"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="report-confirm-report-1"]').trigger('click')
    await wrapper.get('[data-test="report-result"]').setValue('重复提交的备注')
    await wrapper.get('[data-test="confirm-report-action"]').trigger('click')
    await flushPromises()

    const row = wrapper.get('[data-test="report-row"]')
    expect(row.find('[data-test="report-decision"]').text()).toBe(
      '已存储的决定：广告信息已核实'
    )
    expect(row.find('[data-test="report-status"]').text()).toContain('已确认')
    expect(row.text()).not.toContain('重复提交的备注')
    expect(wrapper.get('[data-test="moderation-message"]').text()).toContain(
      '此前已处理'
    )
    expect(row.find('[data-test="report-confirm-report-1"]').exists()).toBe(false)
    expect(row.find('[data-test="report-reject-report-1"]').exists()).toBe(false)
  })

  it('offers no reversal entry for a report that was already processed', async () => {
    reports = [
      reportFixture({
        report_id: 'report-2',
        status: 'rejected',
        resolver_id: 1,
        resolver: { username: 'admin', name: '管理员' },
        result: '已核实为正常讨论',
        resolved_at: '2026-09-20T09:30:00+08:00'
      })
    ]
    const { wrapper } = await mountView()

    await wrapper.get('[data-test="moderation-tab-reports"]').trigger('click')
    await flushPromises()

    const row = wrapper.get('[data-test="report-row"]')
    expect(row.find('[data-test="report-status"]').text()).toContain('已驳回')
    expect(row.find('[data-test="report-decision"]').text()).toBe(
      '已核实为正常讨论'
    )
    expect(row.find('[data-test="report-confirm-report-2"]').exists()).toBe(false)
    expect(row.find('[data-test="report-reject-report-2"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('改判为')
  })

  it('rejects a report without hiding the comment', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('[data-test="moderation-tab-reports"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="report-reject-report-1"]').trigger('click')
    await wrapper.get('[data-test="report-result"]').setValue('属于正常提问')
    await wrapper.get('[data-test="confirm-report-reject"]').trigger('click')
    await flushPromises()

    const resolveCall = apiFetchMock.mock.calls.find(
      call => call[1]?.method === 'POST'
    )
    expect(JSON.parse(String(resolveCall?.[1]?.body))).toEqual({
      confirmed: false,
      result: '属于正常提问'
    })
    expect(
      wrapper.get('[data-test="report-row"]').find('[data-test="report-status"]').text()
    ).toContain('已驳回')
  })

  it('moves feedback between its three statuses with a required result', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('[data-test="moderation-tab-feedback"]').trigger('click')
    await flushPromises()

    const submit = wrapper.get('[data-test="feedback-submit-feedback-1"]')
    expect(submit.attributes('disabled')).toBeDefined()

    await wrapper.get('[data-test="feedback-status-feedback-1"]').setValue('closed')
    await wrapper.get('[data-test="feedback-result-feedback-1"]').setValue('重复反馈')
    expect(
      wrapper.get('[data-test="feedback-submit-feedback-1"]').attributes('disabled')
    ).toBeUndefined()

    await wrapper.get('[data-test="feedback-submit-feedback-1"]').trigger('click')
    await flushPromises()

    const patchCall = apiFetchMock.mock.calls.find(
      call => call[1]?.method === 'PATCH'
    )
    expect(patchCall?.[0]).toBe('/api/admin/feedback/feedback-1')
    expect(JSON.parse(String(patchCall?.[1]?.body))).toEqual({
      status: 'closed',
      result: '重复反馈'
    })
    const row = wrapper.get('[data-test="feedback-row"]')
    expect(row.find('[data-test="feedback-status"]').text()).toContain('已关闭')
    expect(row.find('[data-test="feedback-result"]').text()).toBe('重复反馈')
    expect(wrapper.get('[data-test="moderation-message"]').text()).toContain(
      '不会通知提交人'
    )
  })

  it('submits the stored status when only the note was typed', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('[data-test="moderation-tab-feedback"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="feedback-result-feedback-1"]').setValue('已记录')
    await wrapper.get('[data-test="feedback-submit-feedback-1"]').trigger('click')
    await flushPromises()

    // Typing only the note must not invent a status: the row's stored one is
    // what the menu still shows and what gets submitted.
    const patchCall = apiFetchMock.mock.calls.find(
      call => call[1]?.method === 'PATCH'
    )
    expect(JSON.parse(String(patchCall?.[1]?.body))).toEqual({
      status: 'pending',
      result: '已记录'
    })
  })

  it('keeps the feedback menu open to all three statuses after a change', async () => {
    feedbackOutcome = 'repeat'
    const { wrapper } = await mountView()

    await wrapper.get('[data-test="moderation-tab-feedback"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="feedback-status-feedback-1"]').setValue('processed')
    await wrapper.get('[data-test="feedback-result-feedback-1"]').setValue('重复提交')
    await wrapper.get('[data-test="feedback-submit-feedback-1"]').trigger('click')
    await flushPromises()

    const row = wrapper.get('[data-test="feedback-row"]')
    expect(row.find('[data-test="feedback-result"]').text()).toBe(
      '已存储的决定：重复反馈，直接关闭'
    )
    expect(row.find('[data-test="feedback-status"]').text()).toContain('已关闭')
    expect(wrapper.get('[data-test="moderation-message"]').text()).toContain(
      '未产生新的处理'
    )

    const options = wrapper
      .get('[data-test="feedback-status-feedback-1"]')
      .findAll('option')
      .map(option => option.attributes('value'))
    expect(options).toEqual(['pending', 'processed', 'closed'])
  })
})
