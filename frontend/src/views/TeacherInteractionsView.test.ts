import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'
import type { TeacherComment } from '@/api/types'

import TeacherInteractionsView from './TeacherInteractionsView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function comment(
  overrides: Partial<TeacherComment> = {}
): TeacherComment {
  return {
    comment_id: 'comment-1',
    content_type: 'course_video',
    content_id: '7',
    author_id: 21,
    parent_comment_id: null,
    body: '课程第一节什么时候更新？',
    is_teacher_reply: false,
    created_at: '2026-09-18T09:00:00+08:00',
    updated_at: '2026-09-18T09:00:00+08:00',
    ...overrides
  }
}

function mountView() {
  return mount(TeacherInteractionsView, {
    global: { plugins: [createPinia()] }
  })
}

describe('TeacherInteractionsView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    mockedApiFetch.mockResolvedValue({
      success: true,
      comments: [comment()]
    } as never)
  })

  it('labels teacher replies and supports heritage comments', async () => {
    const heritageComment = comment({
      comment_id: 'heritage-comment',
      content_type: 'handcraft_teaching_video',
      content_id: 'video-9',
      body: '起针时线总是松，应该怎么处理？'
    })
    const teacherReply = comment({
      comment_id: 'teacher-reply',
      content_type: 'handcraft_teaching_video',
      content_id: 'video-9',
      parent_comment_id: 'heritage-comment',
      body: '先固定绣线再起针',
      is_teacher_reply: true,
      created_at: '2026-09-18T10:00:00+08:00',
      updated_at: '2026-09-18T10:00:00+08:00'
    })
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        comments: [comment()]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        comments: [heritageComment]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        comment: teacherReply
      } as never)
    const wrapper = mountView()
    await flushPromises()

    await wrapper
      .get('[data-test="tab-handcraft_teaching_video"]')
      .trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('非遗视频评论')

    await wrapper.get('[data-test="reply-body"]').setValue('先固定绣线再起针')
    await wrapper.get('[data-test="submit-reply"]').trigger('click')
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      '/api/teacher/comments/heritage-comment/replies',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ body: '先固定绣线再起针' })
      })
    )
    expect(wrapper.find('[data-test="teacher-reply-label"]').exists()).toBe(true)
    expect(wrapper.get('[data-test="teacher-reply-label"]').text()).toBe(
      '教师回复'
    )
  })

  it('filters visible comments by target content id', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      comments: [
        comment({
          comment_id: 'comment-7',
          content_id: '7',
          body: '课程七的留言'
        }),
        comment({
          comment_id: 'comment-8',
          content_id: '8',
          body: '课程八的留言'
        })
      ]
    } as never)
    const wrapper = mountView()
    await flushPromises()

    const targetOptions = wrapper
      .findAll('[data-test="target-filter"] option')
      .map(option => option.attributes('value'))
    expect(targetOptions).toEqual(['', '7', '8'])

    await wrapper.get('[data-test="target-filter"]').setValue('8')

    expect(wrapper.text()).toContain('课程八的留言')
    expect(wrapper.text()).not.toContain('课程七的留言')
  })

  it('renders comments in chronological order', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      comments: [
        comment({
          comment_id: 'newer',
          body: '较新的留言',
          created_at: '2026-09-18T11:00:00+08:00'
        }),
        comment({
          comment_id: 'older',
          body: '较早的留言',
          created_at: '2026-09-18T09:00:00+08:00'
        })
      ]
    } as never)
    const wrapper = mountView()
    await flushPromises()

    expect(
      wrapper
        .findAll('[data-test="comment-body"]')
        .map(item => item.text())
    ).toEqual(['较早的留言', '较新的留言'])
  })
})
