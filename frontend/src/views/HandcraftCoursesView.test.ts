import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import CourseLearningPanel from '@/components/CourseLearningPanel.vue'
import HandcraftCoursePlayer from '@/components/HandcraftCoursePlayer.vue'
import HandcraftInheritanceNav from '@/components/HandcraftInheritanceNav.vue'

import HandcraftCoursesView from './HandcraftCoursesView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

describe('HandcraftCoursesView', () => {
  afterEach(() => {
    vi.useRealTimers()
    mockedApiFetch.mockReset()
  })

  it('configures the shared course panel for handcraft courses', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      courses: [],
      recommendations: []
    } as never)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/:pathMatch(.*)*', component: { template: '<div />' } }
      ]
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(HandcraftCoursesView, {
      global: {
        plugins: [createPinia(), router]
      }
    })
    const panel = wrapper.getComponent(CourseLearningPanel)

    expect(panel.props()).toMatchObject({
      direction: 'handcraft',
      moduleCode: '05',
      title: '手工课程',
      apiPrefix: '/api/handcraft-inheritance'
    })
    expect(panel.findComponent(HandcraftInheritanceNav).exists()).toBe(true)
  })

  it('plays course media and saves server-validated progress at 80%', async () => {
    vi.useFakeTimers()
    const course = {
      id: 501,
      title: '广绣基础',
      direction: 'handcraft',
      status: 'published',
      interest_match: true,
      summary: '广绣针法与配色基础',
      teacher_name: '梁老师',
      published_at: '2026-09-01T00:00:00+00:00',
      duration_seconds: 100,
      media_url: 'https://media.example.test/guangxiu.mp4',
      tag_ids: []
    }
    const progress = {
      user_id: 1,
      course_id: 501,
      duration_seconds: 100,
      furthest_position_seconds: 0,
      resume_position_seconds: 0,
      progress_percent: 0,
      watched_seconds: 0,
      completed_at: null,
      last_viewed_at: null,
      updated_at: null,
      quiz_available: false
    }
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === '/api/handcraft-inheritance/courses') {
        return { success: true, courses: [course] } as never
      }
      if (
        path === '/api/handcraft-inheritance/courses/501/progress' &&
        options?.method === 'PUT'
      ) {
        return {
          success: true,
          progress: {
            ...progress,
            furthest_position_seconds: 80,
            resume_position_seconds: 80,
            progress_percent: 80,
            watched_seconds: 30,
            completed_at: '2026-09-18T09:00:00+08:00',
            updated_at: '2026-09-18T09:00:00+08:00',
            quiz_available: true
          }
        } as never
      }
      if (path === '/api/handcraft-inheritance/courses/501/progress') {
        return { success: true, progress } as never
      }
      if (path === '/api/handcraft-inheritance/recommendations') {
        return { success: true, courses: [] } as never
      }
      if (
        path === '/api/handcraft-inheritance/courses/501/heartbeat'
      ) {
        return {
          success: true,
          session: {
            segment_id: 'segment-1',
            heartbeat_seq: 0,
            active_seconds: 0,
            settled_seconds: 0,
            closed: false,
            restarted: false,
            duplicate: false
          }
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/:pathMatch(.*)*', component: { template: '<div />' } }
      ]
    })
    await router.push('/')
    await router.isReady()
    const wrapper = mount(HandcraftCoursesView, {
      global: {
        plugins: [createPinia(), router]
      }
    })
    await flushPromises()

    const player = wrapper.getComponent(HandcraftCoursePlayer)
    const video = player.get('video')
    Object.defineProperty(video.element, 'currentTime', {
      configurable: true,
      value: 80,
      writable: true
    })
    await video.trigger('timeupdate')
    await video.trigger('play')
    await vi.advanceTimersByTimeAsync(30_000)
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/handcraft-inheritance/courses/501/heartbeat',
      {
        method: 'POST',
        body: JSON.stringify({
          segment_id: null,
          heartbeat_seq: 0
        })
      }
    )
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/handcraft-inheritance/courses/501/progress',
      {
        method: 'PUT',
        body: JSON.stringify({
          position_seconds: 80,
          segment_id: 'segment-1'
        })
      }
    )
    expect(
      wrapper.get('[data-test="quiz-entry-501"]').attributes('disabled')
    ).toBeUndefined()
  })
})
