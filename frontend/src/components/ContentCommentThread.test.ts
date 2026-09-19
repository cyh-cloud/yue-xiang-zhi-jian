import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'
import type { TeacherComment } from '@/api/types'

import ContentCommentThread from './ContentCommentThread.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const studentComment = {
  comment_id: 'comment-1',
  content_type: 'course_video',
  content_id: '101',
  author_id: 2,
  parent_comment_id: null,
  body: '如何保果？',
  is_teacher_reply: false,
  created_at: '2026-09-19T10:00:00+08:00',
  updated_at: '2026-09-19T10:00:00+08:00'
} satisfies TeacherComment

const teacherReply = {
  ...studentComment,
  comment_id: 'reply-1',
  parent_comment_id: studentComment.comment_id,
  author_id: 7,
  body: '先控梢再补钾。',
  is_teacher_reply: true,
  created_at: '2026-09-19T10:05:00+08:00',
  updated_at: '2026-09-19T10:05:00+08:00'
} satisfies TeacherComment

describe('ContentCommentThread', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('loads visible comments and labels teacher replies', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      comments: [studentComment, teacherReply]
    })
    const wrapper = mount(ContentCommentThread, {
      props: {
        endpoint: '/api/agri-skills/courses/101/comments',
        title: '课程评论'
      }
    })
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/agri-skills/courses/101/comments'
    )
    expect(wrapper.get('[data-test="comment-body"]').text()).toBe(
      '如何保果？'
    )
    expect(wrapper.get('[data-test="teacher-reply-label"]').text()).toBe(
      '教师回复'
    )
  })

  it('creates a student comment through the module surface', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, comments: [] })
      .mockResolvedValueOnce({
        success: true,
        comment: studentComment
      })
      .mockResolvedValueOnce({
        success: true,
        comments: [studentComment]
      })
    const wrapper = mount(ContentCommentThread, {
      props: {
        endpoint: '/api/handcraft-inheritance/videos/video-visible/comments',
        title: '非遗视频评论'
      }
    })
    await flushPromises()

    await wrapper.get('[data-test="comment-input"]').setValue('如何起针？')
    await wrapper.get('[data-test="submit-comment"]').trigger('click')
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/handcraft-inheritance/videos/video-visible/comments',
      {
        method: 'POST',
        body: JSON.stringify({ body: '如何起针？' })
      }
    )
    expect(wrapper.get('[data-test="comment-body"]').text()).toBe('如何保果？')
  })
})
