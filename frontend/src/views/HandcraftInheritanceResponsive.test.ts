import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError, apiFetch } from '@/api/client'
import type {
  CourseProgress,
  CourseQuiz,
  CourseQuizAttempt,
  HandcraftCourse,
  HandcraftCraft,
  HandcraftProgress,
  HandcraftVideo
} from '@/api/types'
import CourseLearningPanel from '@/components/CourseLearningPanel.vue'
import appHeaderSource from '@/components/AppHeader.vue?raw'
import handcraftCraftLearningSource from '@/components/HandcraftCraftLearning.vue?raw'
import handcraftPointsSource from '@/components/HandcraftPointsPanel.vue?raw'
import handcraftRewardsSource from '@/components/HandcraftRewardsPanel.vue?raw'

import HandcraftCraftView from './HandcraftCraftView.vue'
import handcraftCraftViewSource from './HandcraftCraftView.vue?raw'
import HandcraftCoursesView from './HandcraftCoursesView.vue'
import handcraftCoursesViewSource from './HandcraftCoursesView.vue?raw'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function cssRule(css: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(
    new RegExp(
      `(?:^|[{}])\\s*[^{}]*?${escaped}[^{}]*?\\s*\\{([\\s\\S]*?)\\}`
    )
  )
  expect(match).not.toBeNull()
  return (match?.[1] ?? '').replace(/\s+/g, ' ').trim()
}

function step(stepNo: number) {
  return {
    step_key: `step-${stepNo}`,
    step_no: stepNo,
    title: `第 ${stepNo} 步`,
    description: `第 ${stepNo} 步操作说明`,
    tips: [`第 ${stepNo} 步技巧`]
  }
}

function craft(): HandcraftCraft {
  return {
    craft_key: 'guangxiu',
    name: '广绣',
    sort_order: 1,
    introduction: '广绣以细密针法和鲜明色彩见长。',
    is_demo: true,
    source_available: true,
    status: 'available',
    available: true,
    unavailable_reason: null,
    steps: Array.from({ length: 6 }, (_, index) => step(index + 1)),
    material_guide: [
      {
        name: '桑蚕丝线',
        reference_price: '每束 18 元',
        purchase_channel: '本地绣材店',
        precautions: '按作品色系分批采购',
        taobao_keyword: '广绣桑蚕丝线'
      }
    ]
  }
}

function progress(completedSteps = [1, 2]): HandcraftProgress {
  return {
    user_id: 1,
    craft_key: 'guangxiu',
    status: 'available',
    available: true,
    unavailable_reason: null,
    completed_steps: completedSteps,
    completed_step_count: completedSteps.length,
    resume_step_no: completedSteps.length + 1,
    is_completed: completedSteps.length === 6,
    updated_at: '2026-09-18T10:00:00+08:00'
  }
}

function video(
  videoId: string,
  patch: Partial<HandcraftVideo> = {}
): HandcraftVideo {
  return {
    video_id: videoId,
    craft_key: 'guangxiu',
    title: `视频 ${videoId}`,
    review_status: 'approved',
    source_available: true,
    media_url: 'https://example.test/guangxiu.mp4',
    playback_url: 'https://example.test/guangxiu.mp4',
    version: 1,
    is_demo: true,
    available: true,
    status: 'available',
    unavailable_reason: null,
    ...patch
  }
}

function handcraftCourse(): HandcraftCourse {
  return {
    id: 501,
    title: '广绣基础课程',
    direction: 'handcraft',
    status: 'published',
    interest_match: true,
    summary: '学习广绣基础针法与配色。',
    teacher_name: '非遗教师',
    published_at: '2026-09-17T00:00:00+00:00',
    tag_ids: [3],
    duration_seconds: 600
  }
}

function courseProgress(): CourseProgress {
  return {
    user_id: 1,
    course_id: 501,
    duration_seconds: 600,
    furthest_position_seconds: 480,
    resume_position_seconds: 450,
    progress_percent: 80,
    watched_seconds: 510,
    completed_at: '2026-09-18T10:00:00+08:00',
    last_viewed_at: '2026-09-18T10:00:00+08:00',
    updated_at: '2026-09-18T10:00:00+08:00',
    quiz_available: true
  }
}

function courseQuiz(): CourseQuiz {
  return {
    course_id: 501,
    questions: [
      {
        id: 'q1',
        type: 'single_choice',
        prompt: '广绣起针时应先确认什么？',
        options: ['针脚均匀', '快速收尾']
      }
    ]
  }
}

function quizAttempt(): CourseQuizAttempt {
  return {
    id: 11,
    course_id: 501,
    score: 80,
    is_formal: true,
    is_current: true,
    is_latest: true,
    questions: [
      {
        ...courseQuiz().questions[0],
        correct: true,
        explanation: '先确认针脚均匀，再继续后续步骤。'
      }
    ],
    created_at: '2026-09-18T10:05:00+08:00'
  }
}

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      '/',
      '/login',
      '/student/handcraft-inheritance',
      '/student/handcraft-inheritance/courses',
      '/student/handcraft-inheritance/crafts/:craftKey',
      '/:pathMatch(.*)*'
    ].map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}

async function mountCraft() {
  const router = testRouter()
  await router.push('/student/handcraft-inheritance/crafts/guangxiu')
  await router.isReady()
  const wrapper = mount(HandcraftCraftView, {
    global: {
      plugins: [createPinia(), router]
    }
  })
  await flushPromises()
  return wrapper
}

async function mountCourses() {
  const router = testRouter()
  await router.push('/student/handcraft-inheritance/courses')
  await router.isReady()
  const wrapper = mount(HandcraftCoursesView, {
    global: {
      plugins: [createPinia(), router]
    }
  })
  await flushPromises()
  return wrapper
}

describe('HandcraftInheritanceResponsive', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('shows AR loading and retries AI failure without losing project or manual progress', async () => {
    const failedGuidance = deferred<never>()
    let guidanceRequests = 0
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/handcraft-inheritance/crafts/guangxiu') {
        return { success: true, craft: craft() } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/crafts/guangxiu/progress'
      ) {
        return { success: true, progress: progress() } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/videos?craft_key=guangxiu'
      ) {
        return { success: true, videos: [] } as never
      }
      if (path === '/api/handcraft-inheritance/ar-guidance') {
        guidanceRequests += 1
        if (guidanceRequests === 1) {
          return failedGuidance.promise
        }
        return {
          success: true,
          guidance: {
            craft_key: 'guangxiu',
            tool_preparation: ['准备绣针'],
            operating_points: ['保持针脚均匀'],
            common_errors: ['线头松散'],
            steps: [
              {
                step_no: 1,
                title: '起针',
                instruction: '从底布背面起针。'
              }
            ]
          }
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = await mountCraft()
    const projectLabel = wrapper.get<HTMLInputElement>(
      '[data-test="ar-project-label"]'
    )
    await projectLabel.setValue('绣制花瓣')

    const firstSubmission = wrapper
      .get('[data-test="ar-form"]')
      .trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-test="ar-loading"]').text()).toContain(
      '正在生成分步指引'
    )

    failedGuidance.reject(new ApiError('provider timeout', 503))
    await firstSubmission
    await flushPromises()

    expect(wrapper.get('[data-test="ar-error"]').text()).toBe(
      'AI 服务暂时不可用'
    )
    expect(projectLabel.element.value).toBe('绣制花瓣')
    expect(wrapper.get('[data-test="completed-count"]').text()).toContain(
      '已完成 2 / 6'
    )
    expect(wrapper.findAll('[data-test="craft-step"]')).toHaveLength(6)

    await wrapper.get('[data-test="ar-retry"]').trigger('click')
    await flushPromises()

    const guidanceBodies = mockedApiFetch.mock.calls
      .filter(([path]) => path === '/api/handcraft-inheritance/ar-guidance')
      .map(([, options]) => JSON.parse(String(options?.body)))
    expect(guidanceRequests).toBe(2)
    expect(guidanceBodies[1].segment_id).toBe(
      guidanceBodies[0].segment_id
    )
    expect(guidanceBodies[1].project_label).toBe('绣制花瓣')
    expect(wrapper.get('[data-test="ar-output"]').text()).toContain('起针')
    expect(projectLabel.element.value).toBe('绣制花瓣')
  })

  it('renders only approved playable videos and keeps hidden states closed', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/handcraft-inheritance/crafts/guangxiu') {
        return { success: true, craft: craft() } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/crafts/guangxiu/progress'
      ) {
        return { success: true, progress: progress([]) } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/videos?craft_key=guangxiu'
      ) {
        return {
          success: true,
          videos: [
            video('approved'),
            video('pending', {
              title: '待审核视频',
              review_status: 'pending',
              available: false,
              status: 'pending'
            }),
            video('rejected', {
              title: '已驳回视频',
              review_status: 'rejected',
              available: false,
              status: 'rejected'
            }),
            video('offline-source', {
              title: '来源不可用视频',
              source_available: false,
              available: false,
              status: 'unavailable'
            }),
            video('missing-url', {
              title: '缺少播放地址视频',
              playback_url: null,
              available: false,
              status: 'unavailable'
            })
          ]
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = await mountCraft()
    const videos = wrapper.findAll('[data-test="craft-video"]')
    const player = videos[0].get('[data-test="craft-video-player"]')

    expect(videos).toHaveLength(1)
    expect(videos[0].attributes('data-comment-capability')).toBe(
      'unavailable'
    )
    expect(player.attributes('controls')).toBeDefined()
    expect(player.attributes('playsinline')).toBeDefined()
    expect(player.attributes('preload')).toBe('metadata')
    expect(player.get('source').attributes('src')).toBe(
      'https://example.test/guangxiu.mp4'
    )
    expect(videos[0].find('[data-test="submit-comment"]').exists()).toBe(
      true
    )
    expect(videos[0].text()).not.toContain('举报')
    expect(
      videos[0].find('[data-test="teacher-reply-label"]').exists()
    ).toBe(false)
    expect(wrapper.text()).not.toContain('待审核视频')
    expect(wrapper.text()).not.toContain('已驳回视频')
    expect(wrapper.text()).not.toContain('来源不可用视频')
    expect(wrapper.text()).not.toContain('缺少播放地址视频')
  })

  it('keeps course progress and quiz answers through AI failure, then accepts a retry', async () => {
    let submitCount = 0
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === '/api/handcraft-inheritance/courses') {
        return { success: true, courses: [handcraftCourse()] } as never
      }
      if (path === '/api/handcraft-inheritance/recommendations') {
        return { success: true, courses: [handcraftCourse()] } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/courses/501/progress'
      ) {
        return { success: true, progress: courseProgress() } as never
      }
      if (
        path === '/api/handcraft-inheritance/courses/501/quiz' &&
        options?.method !== 'POST'
      ) {
        return { success: true, quiz: courseQuiz() } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/courses/501/quiz/attempts'
      ) {
        return { success: true, attempts: [] } as never
      }
      if (
        path === '/api/handcraft-inheritance/courses/501/quiz' &&
        options?.method === 'POST'
      ) {
        submitCount += 1
        if (submitCount === 1) {
          throw new ApiError('AI 服务暂时不可用', 503)
        }
        return { success: true, attempt: quizAttempt() } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = await mountCourses()
    const page = wrapper.get('[data-test="handcraft-courses-page"]')
    const panel = wrapper.getComponent(CourseLearningPanel)

    expect(panel.props()).toMatchObject({
      direction: 'handcraft',
      apiPrefix: '/api/handcraft-inheritance'
    })
    expect(
      wrapper.get('[data-test="course-progress-501"]').attributes('value')
    ).toBe('80')
    expect(
      wrapper.get('[data-test="quiz-entry-501"]').attributes('disabled')
    ).toBeUndefined()
    expect(wrapper.find('[data-test="course-comments-501"]').exists()).toBe(
      false
    )
    expect(wrapper.find('[data-test*="report"]').exists()).toBe(false)

    await wrapper.get('[data-test="quiz-entry-501"]').trigger('click')
    await flushPromises()
    const answer = wrapper.get<HTMLInputElement>(
      '[data-test="quiz-option-0-0"]'
    )
    await answer.setValue()
    await wrapper.get('[data-test="quiz-submit-501"]').trigger('submit')
    await flushPromises()

    expect(page.get('.agri-courses-error').text()).toContain(
      'AI 服务暂时不可用'
    )
    expect(answer.element.checked).toBe(true)
    expect(wrapper.find('[data-test="quiz-result-501"]').exists()).toBe(false)

    await wrapper.get('[data-test="quiz-submit-501"]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-test="quiz-result-501"]').text()).toContain(
      '80 分'
    )
    expect(submitCount).toBe(2)
    expect(
      JSON.parse(
        String(
          mockedApiFetch.mock.calls.find(
            ([path, options]) =>
              path === '/api/handcraft-inheritance/courses/501/quiz' &&
              options?.method === 'POST'
          )?.[1]?.body
        )
      )
    ).toEqual({ answers: { q1: '针脚均匀' } })
  })

  it('locks 320/375/1280 overflow, wrapping and mobile recomposition contracts', () => {
    // jsdom does not perform CSS layout or media-query evaluation. These
    // assertions lock the source contract; Task 20 owns real browser geometry.
    const viewports = [320, 375, 1280]
    const sources = [
      handcraftCraftLearningSource,
      handcraftCraftViewSource,
      handcraftCoursesViewSource,
      handcraftPointsSource,
      handcraftRewardsSource
    ]

    expect(
      cssRule(handcraftCraftLearningSource, '.craft-learning')
    ).toContain('overflow-x: clip')
    expect(
      cssRule(handcraftCraftLearningSource, '.ar-workspace')
    ).toContain('minmax(min(100%, 260px)')
    expect(
      cssRule(handcraftCraftLearningSource, '.video-item video')
    ).toContain('aspect-ratio: 16 / 9')
    expect(
      cssRule(handcraftCraftLearningSource, '.craft-learning__heading p')
    ).toContain('word-break: keep-all')
    expect(handcraftCraftLearningSource).toContain(
      '@media (max-width: 760px), (orientation: portrait)'
    )
    expect(handcraftCraftLearningSource).toContain(
      '@media (max-width: 420px)'
    )

    expect(
      cssRule(handcraftCraftViewSource, '.handcraft-craft-page')
    ).toContain('grid-template-columns: minmax(0, 1fr)')
    expect(
      cssRule(handcraftCraftViewSource, '.handcraft-craft-page')
    ).toContain('overflow-x: clip')
    expect(
      cssRule(handcraftCoursesViewSource, '.handcraft-courses-page')
    ).toContain('grid-template-columns: minmax(0, 1fr)')
    expect(
      cssRule(handcraftCoursesViewSource, '.handcraft-courses-page')
    ).toContain('overflow-x: clip')
    expect(
      cssRule(handcraftPointsSource, '.points-panel')
    ).toContain('width: min(100%, 1180px)')
    expect(
      cssRule(handcraftPointsSource, '.points-panel')
    ).toContain('min-width: 0')
    expect(
      cssRule(handcraftPointsSource, '.points-hero')
    ).toContain('grid-template-columns: minmax(0, 1fr) minmax(280px, 0.72fr)')
    expect(
      cssRule(handcraftPointsSource, '.ledger-entry')
    ).toContain('grid-template-columns: auto minmax(0, 1fr)')
    expect(handcraftPointsSource).toContain(
      '@media (max-width: 760px), (orientation: portrait)'
    )
    expect(
      cssRule(handcraftRewardsSource, '.rewards-panel')
    ).toContain('width: min(100%, 1180px)')
    expect(
      cssRule(handcraftRewardsSource, '.rewards-panel')
    ).toContain('min-width: 0')
    expect(
      cssRule(handcraftRewardsSource, '.reward-grid')
    ).toContain('minmax(min(100%, 280px), 1fr)')
    expect(
      cssRule(handcraftRewardsSource, '.fulfillment-record')
    ).toContain('grid-template-columns: minmax(0, 1fr) auto auto')
    expect(
      cssRule(appHeaderSource, '.brand')
    ).toContain('min-width: 0')
    expect(
      cssRule(appHeaderSource, '.brand-copy strong')
    ).toContain('white-space: nowrap')
    expect(
      cssRule(handcraftRewardsSource, '.reward-card__state')
    ).toContain('white-space: nowrap')
    expect(handcraftRewardsSource).toContain(
      '@media (max-width: 760px), (orientation: portrait)'
    )

    viewports.forEach(viewport => {
      expect(
        sources.every(
          source =>
            !source.includes(`min-width: ${viewport}px`) &&
            !source.includes(`width: ${viewport}px`)
        )
      ).toBe(true)
    })
    expect(sources.join('\n')).not.toMatch(/#[0-9a-f]{3,8}|rgba?\(/i)
  })
})
