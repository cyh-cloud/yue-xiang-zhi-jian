import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'
import type {
  TeacherCourse,
  TeacherCourseStatus
} from '@/api/types'
import TeacherCourseManager from '@/components/TeacherCourseManager.vue'

import TeacherCoursesView from './TeacherCoursesView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function course(
  id: number,
  status: TeacherCourseStatus
): TeacherCourse {
  return {
    id,
    title: `课程 ${id}`,
    direction: 'agriculture',
    status,
    duration_seconds: 300,
    media_url: `https://media.example.test/${id}.mp4`,
    published_at:
      status === 'published' || status === 'offline'
        ? '2026-09-19T10:00:00+08:00'
        : null,
    summary: '课程简介',
    teacher_name: '教师甲',
    teacher_id: 7,
    media_source_type: 'external_url',
    content_tags_json: '["农业"]',
    version: 1,
    rejection_opinion:
      status === 'rejected' ? '请补充知识点要点' : null,
    submitted_at:
      status === 'pending' ? '2026-09-19T10:00:00+08:00' : null,
    created_at: '2026-09-19T09:00:00+08:00',
    updated_at: '2026-09-19T10:00:00+08:00',
    content_tags: ['农业'],
    tag_ids: []
  }
}

function mountManager(courses?: TeacherCourse[]) {
  const pinia = createPinia()
  const wrapper = mount(TeacherCourseManager, {
    props: courses ? { courses } : undefined,
    global: { plugins: [pinia] }
  })
  return { pinia, wrapper }
}

describe('TeacherCoursesView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    mockedApiFetch.mockResolvedValue({
      success: true,
      courses: []
    } as never)
  })

  it('blocks submit when summary is blank', async () => {
    const { wrapper } = mountManager()
    await wrapper.get('[data-test="course-title"]').setValue('课程')
    await wrapper.get('[data-test="course-summary"]').setValue('   ')
    await wrapper.get('[data-test="save-course"]').trigger('click')

    expect(wrapper.text()).toContain('课程简介/知识点要点不能为空')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('shows all five teacher states and only valid actions', () => {
    const { wrapper } = mountManager([
      course(1, 'draft'),
      course(2, 'pending'),
      course(3, 'published'),
      course(4, 'rejected'),
      course(5, 'offline')
    ])

    expect(wrapper.text()).toContain('草稿')
    expect(wrapper.text()).toContain('待审核')
    expect(wrapper.text()).toContain('已上架')
    expect(wrapper.text()).toContain('已驳回')
    expect(wrapper.text()).toContain('已下架')
    expect(wrapper.find('[data-test="submit-draft"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="submit-rejected"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="edit-pending"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="edit-published"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="offline-published"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="relist-offline"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="publish-pending"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="publish-rejected"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="publish-offline"]').exists()).toBe(false)
  })

  it('provides complete direction and supported status filters', async () => {
    const { wrapper } = mountManager()
    const directionOptions = wrapper
      .findAll('[data-test="course-direction-filter"] option')
      .map(option => option.attributes('value'))
    const statusOptions = wrapper
      .findAll('[data-test="course-status-filter"] option')
      .map(option => option.attributes('value'))

    expect(directionOptions).toEqual([
      '',
      'agriculture',
      'ecommerce',
      'handcraft'
    ])
    expect(statusOptions).toEqual([
      '',
      'draft',
      'pending',
      'published',
      'offline'
    ])

    await wrapper
      .get('[data-test="course-direction-filter"]')
      .setValue('handcraft')
    await wrapper
      .get('[data-test="course-status-filter"]')
      .setValue('draft')
    await flushPromises()

    expect(apiFetch).toHaveBeenLastCalledWith(
      '/api/teacher/courses?direction=handcraft&status=draft'
    )
  })

  it('creates a course with normalized free tags and a selected direction', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      course: {
        ...course(2, 'draft'),
        title: '电商直播基础',
        direction: 'ecommerce'
      }
    } as never)
    const { wrapper } = mountManager()

    await wrapper.get('[data-test="course-title"]').setValue('电商直播基础')
    await wrapper
      .get('[data-test="course-direction"]')
      .setValue('ecommerce')
    await wrapper
      .get('[data-test="course-summary"]')
      .setValue('掌握直播准备与讲解要点')
    await wrapper
      .get('[data-test="course-tags"]')
      .setValue('直播, 选品，直播')
    await wrapper.get('[data-test="course-duration"]').setValue('420')
    await wrapper
      .get('[data-test="course-media-url"]')
      .setValue('https://media.example.test/live.mp4')
    await wrapper.get('[data-test="save-course"]').trigger('click')
    await flushPromises()

    const request = mockedApiFetch.mock.calls[0]
    const payload = JSON.parse(request[1]?.body as string)
    expect(request[0]).toBe('/api/teacher/courses')
    expect(request[1]?.method).toBe('POST')
    expect(payload).toEqual({
      title: '电商直播基础',
      direction: 'ecommerce',
      summary: '掌握直播准备与讲解要点',
      content_tags: ['直播', '选品'],
      duration_seconds: 420,
      media_source_type: 'external_url',
      media_url: 'https://media.example.test/live.mp4'
    })
  })

  it('switches to local upload and rejects files over 500 MiB', async () => {
    const { wrapper } = mountManager()
    await wrapper.get('[data-test="media-local"]').setValue('local_upload')
    const input = wrapper.get('[data-test="course-video"]')

    expect(input.attributes('accept')).toContain('video/mp4')
    expect(input.attributes('accept')).toContain('video/webm')

    const oversized = new File(['video'], 'oversized.mp4', {
      type: 'video/mp4'
    })
    Object.defineProperty(oversized, 'size', {
      configurable: true,
      value: 500 * 1024 * 1024 + 1
    })
    Object.defineProperty(input.element, 'files', {
      configurable: true,
      value: [oversized]
    })
    await input.trigger('change')

    expect(wrapper.text()).toContain('视频文件不能超过 500 MiB')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('requires a selected file when an external course switches to local upload', async () => {
    const existing = course(1, 'draft')
    const { wrapper } = mountManager([existing])

    await wrapper.get('[data-test="edit-draft"]').trigger('click')
    await wrapper.get('[data-test="media-local"]').setValue('local_upload')
    await wrapper.get('[data-test="save-course"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('请选择视频文件')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('clears the native file input after an invalid file selection', async () => {
    const { wrapper } = mountManager()
    await wrapper.get('[data-test="media-local"]').setValue('local_upload')
    const input = wrapper.get('[data-test="course-video"]')
    const inputElement = input.element as HTMLInputElement
    const invalid = new File(['text'], 'notes.txt', {
      type: 'text/plain'
    })

    Object.defineProperty(inputElement, 'files', {
      configurable: true,
      value: [invalid]
    })
    Object.defineProperty(inputElement, 'value', {
      configurable: true,
      writable: true,
      value: 'C:\\fakepath\\notes.txt'
    })
    await input.trigger('change')

    expect(wrapper.text()).toContain('仅支持 MP4 或 WebM 视频')
    expect(inputElement.value).toBe('')
    expect(wrapper.text()).not.toContain('notes.txt')
  })

  it('uploads a local video before saving the course', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        media: {
          media_source_type: 'local_upload',
          media_url: '/media/teacher-courses/uploaded.mp4',
          size_bytes: 12
        }
      } as never)
      .mockResolvedValueOnce({
        success: true,
        course: {
          ...course(2, 'draft'),
          media_source_type: 'local_upload',
          media_url: '/media/teacher-courses/uploaded.mp4'
        }
      } as never)
    const { wrapper } = mountManager()

    await wrapper.get('[data-test="media-local"]').setValue('local_upload')
    const file = new File(['video'], 'lesson.mp4', { type: 'video/mp4' })
    const videoInput = wrapper.get('[data-test="course-video"]')
    Object.defineProperty(videoInput.element, 'files', {
      configurable: true,
      value: [file]
    })
    await videoInput.trigger('change')
    await wrapper.get('[data-test="course-title"]').setValue('本地视频课程')
    await wrapper
      .get('[data-test="course-summary"]')
      .setValue('本地视频知识点')
    await wrapper.get('[data-test="course-duration"]').setValue('300')
    await wrapper.get('[data-test="save-course"]').trigger('click')
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/teacher/uploads/video',
      expect.objectContaining({ method: 'POST', body: expect.any(FormData) })
    )
    const createRequest = mockedApiFetch.mock.calls[1]
    const payload = JSON.parse(createRequest[1]?.body as string)
    expect(createRequest[0]).toBe('/api/teacher/courses')
    expect(payload.media_source_type).toBe('local_upload')
    expect(payload.media_url).toBe('/media/teacher-courses/uploaded.mp4')
  })

  it('edits an existing course with its expected version', async () => {
    const existing = course(1, 'draft')
    mockedApiFetch.mockResolvedValue({
      success: true,
      course: { ...existing, title: '修订课程', version: 2 }
    } as never)
    const { wrapper } = mountManager([existing])

    await wrapper.get('[data-test="edit-draft"]').trigger('click')
    await wrapper.get('[data-test="course-title"]').setValue('修订课程')
    await wrapper.get('[data-test="save-course"]').trigger('click')
    await flushPromises()

    const request = mockedApiFetch.mock.calls[0]
    const payload = JSON.parse(request[1]?.body as string)
    expect(request[0]).toBe('/api/teacher/courses/1')
    expect(request[1]?.method).toBe('PUT')
    expect(payload.expected_version).toBe(1)
    expect(payload.title).toBe('修订课程')
  })

  it('submits, offlines, and relists only through valid state actions', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        course: course(1, 'pending')
      } as never)
      .mockResolvedValueOnce({
        success: true,
        course: course(4, 'pending')
      } as never)
      .mockResolvedValueOnce({
        success: true,
        course: course(3, 'offline')
      } as never)
      .mockResolvedValueOnce({
        success: true,
        course: course(5, 'pending')
      } as never)
    const { wrapper } = mountManager([
      course(1, 'draft'),
      course(4, 'rejected'),
      course(3, 'published'),
      course(5, 'offline')
    ])

    await wrapper.get('[data-test="submit-draft"]').trigger('click')
    await wrapper.get('[data-test="submit-rejected"]').trigger('click')
    await wrapper.get('[data-test="offline-published"]').trigger('click')
    await wrapper.get('[data-test="relist-offline"]').trigger('click')
    await flushPromises()

    expect(mockedApiFetch.mock.calls.map(call => call[0])).toEqual([
      '/api/teacher/courses/1/submit',
      '/api/teacher/courses/4/submit',
      '/api/teacher/courses/3/offline',
      '/api/teacher/courses/5/relist'
    ])
    expect(
      mockedApiFetch.mock.calls.map(call =>
        JSON.parse(call[1]?.body as string).expected_version
      )
    ).toEqual([1, 1, 1, 1])
  })

  it('composes the manager in the course view and loads the store', async () => {
    const pinia = createPinia()
    const wrapper = mount(TeacherCoursesView, {
      global: { plugins: [pinia] }
    })
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('课程管理')
    expect(wrapper.findComponent(TeacherCourseManager).exists()).toBe(true)
    expect(apiFetch).toHaveBeenCalledWith('/api/teacher/courses')
  })
})
