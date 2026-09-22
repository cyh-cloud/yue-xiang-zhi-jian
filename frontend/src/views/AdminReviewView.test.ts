import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { AdminReviewItem } from '@/api/types'
import { useAdminConsoleStore } from '@/stores/adminConsole'

import AdminReviewView from './AdminReviewView.vue'

function reviewFixture(
  patch: Partial<AdminReviewItem> = {}
): AdminReviewItem {
  return {
    content_type: 'course_video',
    content_id: '41',
    title: '荔枝保果',
    submitter_id: 7,
    submitter_name: '陈老师',
    review_status: 'pending',
    version: 3,
    rejection_opinion: null,
    published_at: null,
    created_at: '2026-09-20T08:00:00+08:00',
    updated_at: '2026-09-20T10:00:00+08:00',
    ...patch
  }
}

async function mountView({
  items = [],
  loading = false,
  error = ''
}: {
  items?: AdminReviewItem[]
  loading?: boolean
  error?: string
} = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useAdminConsoleStore()
  store.reviewItems = items
  store.reviewCounts = {
    course_video: items.filter(
      item =>
        item.content_type === 'course_video' &&
        item.review_status === 'pending'
    ).length,
    job_position: items.filter(
      item =>
        item.content_type === 'job_position' &&
        item.review_status === 'pending'
    ).length,
    handcraft_teaching_video: items.filter(
      item =>
        item.content_type === 'handcraft_teaching_video' &&
        item.review_status === 'pending'
    ).length
  }
  store.reviewLoading = loading
  store.reviewError = error

  vi.spyOn(store, 'loadReviewQueue').mockResolvedValue(true)
  vi.spyOn(store, 'approveReview').mockResolvedValue(true)
  vi.spyOn(store, 'rejectReview').mockResolvedValue(true)

  const wrapper = mount(AdminReviewView, {
    global: {
      plugins: [pinia]
    }
  })
  await flushPromises()

  return { store, wrapper }
}

describe('AdminReviewView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows three pending counts and filters the queue by content type', async () => {
    const items = [
      reviewFixture(),
      reviewFixture({
        content_type: 'job_position',
        content_id: 'job-1',
        title: '农业技术员',
        submitter_name: '农企甲',
        version: 2
      }),
      reviewFixture({
        content_type: 'handcraft_teaching_video',
        content_id: 'video-1',
        title: '广绣针法',
        submitter_name: '非遗老师',
        version: 1
      }),
      reviewFixture({
        content_id: '42',
        title: '已通过课程',
        review_status: 'approved'
      })
    ]
    const { wrapper } = await mountView({ items })

    expect(
      wrapper.get('[data-test="admin-review-count-course_video"]').text()
    ).toContain('1')
    expect(
      wrapper.get('[data-test="admin-review-count-job_position"]').text()
    ).toContain('1')
    expect(
      wrapper.get(
        '[data-test="admin-review-count-handcraft_teaching_video"]'
      ).text()
    ).toContain('1')
    expect(wrapper.findAll('[data-test="admin-review-row"]')).toHaveLength(4)

    await wrapper
      .get('[data-test="admin-review-filter-course_video"]')
      .trigger('click')

    expect(wrapper.findAll('[data-test="admin-review-row"]')).toHaveLength(2)
    expect(
      wrapper.findAll('[data-test="admin-review-row"]').every(row =>
        row.text().includes('课程视频')
      )
    ).toBe(true)

    await wrapper
      .get('[data-test="admin-review-filter-all"]')
      .trigger('click')
    expect(wrapper.findAll('[data-test="admin-review-row"]')).toHaveLength(4)
  })

  it('renders status, version, submitter, updated time, and pending actions', async () => {
    const pending = reviewFixture()
    const approved = reviewFixture({
      content_id: '42',
      title: '已通过课程',
      review_status: 'approved',
      version: 4
    })
    const { wrapper } = await mountView({ items: [pending, approved] })
    const rows = wrapper.findAll('[data-test="admin-review-row"]')

    expect(rows[0].text()).toContain('待审核')
    expect(rows[0].text()).toContain('版本 3')
    expect(rows[0].text()).toContain('陈老师')
    expect(rows[0].text()).toContain('2026-09-20 10:00')
    expect(
      rows[0].find('[data-test="admin-review-approve"]').exists()
    ).toBe(true)
    expect(
      rows[0].find('[data-test="admin-review-reject"]').exists()
    ).toBe(true)

    expect(rows[1].text()).toContain('已通过')
    expect(rows[1].text()).toContain('版本 4')
    expect(
      rows[1].find('[data-test="admin-review-approve"]').exists()
    ).toBe(false)
    expect(
      rows[1].find('[data-test="admin-review-reject"]').exists()
    ).toBe(false)
  })

  it('confirms approval with the current review version', async () => {
    const item = reviewFixture()
    const { store, wrapper } = await mountView({ items: [item] })

    await wrapper.get('[data-test="admin-review-approve"]').trigger('click')
    expect(
      wrapper.find('[data-test="admin-review-approve-dialog"]').exists()
    ).toBe(true)
    expect(store.approveReview).not.toHaveBeenCalled()

    await wrapper
      .get('[data-test="admin-review-confirm-approve"]')
      .trigger('click')

    expect(store.approveReview).toHaveBeenCalledWith(
      'course_video',
      '41',
      3
    )
    expect(
      wrapper.find('[data-test="admin-review-approve-dialog"]').exists()
    ).toBe(false)
  })

  it('requires a trimmed rejection opinion and shows a 500-character counter', async () => {
    const item = reviewFixture()
    const { store, wrapper } = await mountView({ items: [item] })

    await wrapper.get('[data-test="admin-review-reject"]').trigger('click')
    const opinion = wrapper.get('[data-test="admin-review-opinion"]')
    const submit = wrapper.get('[data-test="admin-review-confirm-reject"]')

    expect(opinion.attributes('maxlength')).toBe('500')
    expect(submit.attributes('disabled')).toBeDefined()
    expect(
      wrapper.get('[data-test="admin-review-opinion-count"]').text()
    ).toContain('0 / 500')

    await opinion.setValue('   ')
    expect(submit.attributes('disabled')).toBeDefined()
    expect(
      wrapper.get('[data-test="admin-review-opinion-count"]').text()
    ).toContain('3 / 500')

    await opinion.setValue(' 补充材料 ')
    expect(submit.attributes('disabled')).toBeUndefined()
    expect(
      wrapper.get('[data-test="admin-review-opinion-count"]').text()
    ).toContain('6 / 500')

    await submit.trigger('click')

    expect(store.rejectReview).toHaveBeenCalledWith(
      'course_video',
      '41',
      3,
      '补充材料'
    )
  })

  it('renders loading, error, and empty states', async () => {
    const loading = await mountView({ loading: true })
    expect(
      loading.wrapper.find('[data-test="admin-review-loading"]').exists()
    ).toBe(true)

    const failed = await mountView({ error: '审核队列加载失败' })
    expect(
      failed.wrapper.get('[data-test="admin-review-error"]').text()
    ).toContain('审核队列加载失败')
    await failed.wrapper
      .get('[data-test="admin-review-retry"]')
      .trigger('click')
    expect(failed.store.loadReviewQueue).toHaveBeenCalled()

    const empty = await mountView()
    expect(
      empty.wrapper.get('[data-test="admin-review-empty"]').text()
    ).toContain('暂无待审核内容')
  })
})
