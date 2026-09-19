import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type {
  TeacherAnnouncement,
  TeacherComment,
  TeacherCourse,
  TeacherDashboard,
  TeacherQuiz,
  TeacherReport
} from '@/api/types'

import { useTeacherConsoleStore } from './teacherConsole'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const courseFixture = {
  id: 1,
  title: '课程',
  direction: 'agriculture',
  status: 'draft',
  duration_seconds: 300,
  media_url: 'https://media.example.test/a.mp4',
  published_at: null,
  summary: '简介',
  teacher_name: '教师甲',
  teacher_id: 7,
  media_source_type: 'external_url',
  content_tags_json: '[]',
  version: 1,
  rejection_opinion: null,
  submitted_at: null,
  created_at: '2026-09-19T09:00:00+08:00',
  updated_at: '2026-09-19T09:00:00+08:00',
  content_tags: [],
  tag_ids: []
} satisfies TeacherCourse

const quizFixture = {
  enabled: true,
  scoring_rule: 'all_correct',
  questions: [
    {
      id: 'q1',
      type: 'true_false',
      prompt: '?',
      options: ['正确', '错误'],
      answer: '正确'
    },
    {
      id: 'q2',
      type: 'single_choice',
      prompt: '?',
      options: ['A', 'B'],
      answer: 'A'
    },
    {
      id: 'q3',
      type: 'true_false',
      prompt: '?',
      options: ['正确', '错误'],
      answer: '错误'
    }
  ]
} satisfies TeacherQuiz

const announcementFixture = {
  announcement_id: 'teaching-1',
  teacher_id: 7,
  title: '课程安排',
  body: '本周调整',
  event_id: 'teaching-1:v1',
  delivery_status: 'sent',
  delivery_result: { recipient_count: 12 },
  created_at: '2026-09-19T10:00:00+08:00'
} satisfies TeacherAnnouncement

const commentFixture = {
  comment_id: 'comment-1',
  content_type: 'course_video',
  content_id: '1',
  author_id: 2,
  parent_comment_id: null,
  body: '如何起针？',
  is_teacher_reply: false,
  created_at: '2026-09-19T10:00:00+08:00',
  updated_at: '2026-09-19T10:00:00+08:00'
} satisfies TeacherComment

const dashboardFixture = {
  student_total: 12,
  average_progress: 62.5,
  completion_rate: 25,
  quiz_attempt_count: 30,
  quiz_average_score: 84.2,
  directions: {
    agriculture: { student_count: 4, average_progress: 75 },
    ecommerce: { student_count: 4, average_progress: 50 },
    handcraft: { student_count: 2, average_progress: 60 },
    comprehensive: { student_count: 2, average_progress: 55 }
  }
} satisfies TeacherDashboard

const reportFixture = {
  report_id: 'report-1',
  teacher_id: 7,
  created_at: '2026-09-19T11:00:00+08:00',
  stats_snapshot: {
    aggregate_stats: {
      student_total: 12,
      average_progress: 62.5,
      completion_rate: 25,
      quiz_attempt_count: 30,
      quiz_average_score: 84.2
    },
    direction_comparison: dashboardFixture.directions,
    risk_summary: {
      student_count: 12,
      at_risk_count: 2,
      at_risk_ratio: 16.67,
      directions: {
        agriculture: {
          student_count: 4,
          at_risk_count: 1,
          at_risk_ratio: 25
        },
        ecommerce: {
          student_count: 4,
          at_risk_count: 1,
          at_risk_ratio: 25
        },
        handcraft: {
          student_count: 2,
          at_risk_count: 0,
          at_risk_ratio: 0
        },
        comprehensive: {
          student_count: 2,
          at_risk_count: 0,
          at_risk_ratio: 0
        }
      }
    }
  },
  sections: {
    progress_analysis: '整体进度稳定',
    direction_comparison: '农业方向领先',
    risk_warning: '2 名学员长期零进度'
  }
} satisfies TeacherReport

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('apiFetch multipart bodies', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('leaves the multipart Content-Type boundary to the browser', async () => {
    const { apiFetch } = await vi.importActual<typeof import('@/api/client')>(
      '@/api/client'
    )
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/api/teacher/uploads/video', {
      method: 'POST',
      body: new FormData()
    })

    const options = fetchMock.mock.calls[0][1] as RequestInit
    expect(options.body).toBeInstanceOf(FormData)
    expect(new Headers(options.headers).has('Content-Type')).toBe(false)
  })
})

describe('useTeacherConsoleStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('keeps FormData multipart and does not force JSON', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      media: {
        media_source_type: 'local_upload',
        media_url: '/media/teacher-courses/a.mp4',
        size_bytes: 12
      }
    } as never)
    const store = useTeacherConsoleStore()
    const file = new File(['video'], 'a.mp4', { type: 'video/mp4' })
    await store.uploadVideo(file)
    const options = mockedApiFetch.mock.calls[0][1]
    expect(options?.body).toBeInstanceOf(FormData)
    expect((options?.body as FormData).get('file')).toBe(file)
    expect(new Headers(options?.headers).has('Content-Type')).toBe(false)
  })

  it('generates quiz then stores editable draft', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      quiz: {
        questions: [
          {
            id: 'q1',
            type: 'true_false',
            prompt: '?',
            options: ['正确', '错误'],
            answer: '正确'
          },
          {
            id: 'q2',
            type: 'single_choice',
            prompt: '?',
            options: ['A', 'B'],
            answer: 'A'
          },
          {
            id: 'q3',
            type: 'true_false',
            prompt: '?',
            options: ['正确', '错误'],
            answer: '错误'
          }
        ]
      }
    } as never)
    const store = useTeacherConsoleStore()
    await store.generateQuiz(1, {
      summary: '简介',
      direction: 'agriculture'
    })
    expect(store.quizDraft?.questions[0].id).toBe('q1')
  })

  it('creates a course through the collection endpoint', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      course: courseFixture
    } as never)
    const store = useTeacherConsoleStore()
    await store.createCourse({
      title: '课程',
      direction: 'agriculture',
      summary: '简介',
      content_tags: [],
      duration_seconds: 300,
      media_source_type: 'external_url',
      media_url: 'https://media.example.test/a.mp4'
    })
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/teacher/courses',
      expect.objectContaining({ method: 'POST' })
    )
    expect(store.courses).toEqual([courseFixture])
  })

  it('loads courses with filters and replaces the server collection', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      courses: [courseFixture]
    })
    const store = useTeacherConsoleStore()

    await store.loadCourses({
      direction: 'agriculture',
      status: 'draft'
    })

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/teacher/courses?direction=agriculture&status=draft'
    )
    expect(store.courses).toEqual([courseFixture])
  })

  it('saves a course and replaces it with the returned server state', async () => {
    const updated = {
      ...courseFixture,
      title: '修订课程',
      version: 2
    } satisfies TeacherCourse
    const payload = {
      ...courseFixture,
      title: '修订课程',
      expected_version: 1
    }
    mockedApiFetch.mockResolvedValue({
      success: true,
      course: updated
    })
    const store = useTeacherConsoleStore()
    store.courses = [courseFixture]

    await store.saveCourse(1, payload)

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/teacher/courses/1',
      {
        method: 'PUT',
        body: JSON.stringify(payload)
      }
    )
    expect(store.courses).toEqual([updated])
  })

  it('does not optimistically change status while a course action is pending', async () => {
    const published = {
      ...courseFixture,
      status: 'published'
    } satisfies TeacherCourse
    const offline = {
      ...published,
      status: 'offline',
      published_at: null
    } satisfies TeacherCourse
    const request = deferred<{
      success: true
      course: TeacherCourse
    }>()
    mockedApiFetch.mockReturnValue(request.promise)
    const store = useTeacherConsoleStore()
    store.courses = [published]

    const action = store.offlineCourse(1, 2)

    expect(store.courses[0].status).toBe('published')
    request.resolve({ success: true, course: offline })
    await action
    expect(store.courses[0].status).toBe('offline')
  })

  it('submits and relists using expected versions and server responses', async () => {
    const pending = {
      ...courseFixture,
      status: 'pending',
      version: 2
    } satisfies TeacherCourse
    const relisted = {
      ...pending,
      version: 3
    } satisfies TeacherCourse
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, course: pending })
      .mockResolvedValueOnce({ success: true, course: relisted })
    const store = useTeacherConsoleStore()
    store.courses = [courseFixture]

    await store.submitCourse(1, 1)
    await store.relistCourse(1, 2)

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/teacher/courses/1/submit',
      {
        method: 'POST',
        body: JSON.stringify({ expected_version: 1 })
      }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/teacher/courses/1/relist',
      {
        method: 'POST',
        body: JSON.stringify({ expected_version: 2 })
      }
    )
    expect(store.courses).toEqual([relisted])
  })

  it('saves the editable quiz response as the current draft', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      quiz: quizFixture
    })
    const store = useTeacherConsoleStore()
    const payload = {
      expected_version: 1,
      enabled: true,
      scoring_rule: 'all_correct',
      questions: quizFixture.questions
    }

    await store.saveQuiz(1, payload)

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/teacher/courses/1/quiz',
      {
        method: 'POST',
        body: JSON.stringify(payload)
      }
    )
    expect(store.quizDraft).toEqual(quizFixture)
  })

  it('loads announcements and prepends newly published server state', async () => {
    const second = {
      ...announcementFixture,
      announcement_id: 'teaching-2',
      title: '第二次公告'
    } satisfies TeacherAnnouncement
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        announcements: [announcementFixture]
      })
      .mockResolvedValueOnce({ success: true, announcement: second })
    const store = useTeacherConsoleStore()

    await store.loadAnnouncements()
    await store.publishAnnouncement({
      title: second.title,
      body: second.body
    })

    expect(store.announcements).toEqual([second, announcementFixture])
  })

  it('loads filtered comments and appends the returned teacher reply', async () => {
    const reply = {
      ...commentFixture,
      comment_id: 'reply-1',
      parent_comment_id: commentFixture.comment_id,
      author_id: 7,
      body: '先固定绣线再起针',
      is_teacher_reply: true
    } satisfies TeacherComment
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        comments: [commentFixture]
      })
      .mockResolvedValueOnce({ success: true, comment: reply })
    const store = useTeacherConsoleStore()

    await store.loadComments({
      content_type: 'course_video',
      content_id: '1'
    })
    await store.replyComment('comment-1', reply.body)

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/teacher/comments?content_type=course_video&content_id=1'
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/teacher/comments/comment-1/replies',
      {
        method: 'POST',
        body: JSON.stringify({ body: reply.body })
      }
    )
    expect(store.comments).toEqual([commentFixture, reply])
  })

  it('loads the aggregate dashboard', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      dashboard: dashboardFixture
    })
    const store = useTeacherConsoleStore()

    await store.loadDashboard()

    expect(mockedApiFetch).toHaveBeenCalledWith('/api/teacher/dashboard')
    expect(store.dashboard).toEqual(dashboardFixture)
  })

  it('loads reports and prepends a newly generated report', async () => {
    const generated = {
      ...reportFixture,
      report_id: 'report-2',
      created_at: '2026-09-19T12:00:00+08:00'
    } satisfies TeacherReport
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        reports: [reportFixture]
      })
      .mockResolvedValueOnce({ success: true, report: generated })
    const store = useTeacherConsoleStore()

    await store.loadReports()
    await store.generateReport()

    expect(store.reports).toEqual([generated, reportFixture])
  })

  it('captures request errors and rethrows them to callers', async () => {
    const error = new ApiError('课程版本已变化', 409)
    mockedApiFetch.mockRejectedValue(error)
    const store = useTeacherConsoleStore()

    await expect(
      store.saveCourse(1, {
        ...courseFixture,
        expected_version: 1
      })
    ).rejects.toBe(error)

    expect(store.error).toBe('课程版本已变化')
    expect(store.loading).toBe(false)
  })
})
