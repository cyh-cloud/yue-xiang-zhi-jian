import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Component } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import type {
  JobMatchingJob,
  SkillProfile,
  StudentResume
} from '@/api/types'
import jobMatchingNavSource from '@/components/JobMatchingNav.vue?raw'
import { useJobMatchingStore } from '@/stores/jobMatching'

import JobDetailView from './JobDetailView.vue'
import jobDetailViewSource from './JobDetailView.vue?raw'
import JobFavoritesView from './JobFavoritesView.vue'
import jobFavoritesViewSource from './JobFavoritesView.vue?raw'
import JobsView from './JobsView.vue'
import jobsViewSource from './JobsView.vue?raw'
import MyApplicationsView from './MyApplicationsView.vue'
import myApplicationsViewSource from './MyApplicationsView.vue?raw'
import ResumeEditorView from './ResumeEditorView.vue'
import resumeEditorViewSource from './ResumeEditorView.vue?raw'
import SkillProfileView from './SkillProfileView.vue'
import skillProfileViewSource from './SkillProfileView.vue?raw'


const widths = [320, 375, 1280]
const longCjk =
  '农产品品牌数字化运营与乡村振兴内容策划及直播电商协同岗位'
const longDescription =
  '负责粤东西北农产品品牌故事整理、短视频内容策划、直播运营、线上店铺管理、数据分析与跨部门协作。'.repeat(
    3
  )

const emptyResume: StudentResume = {
  education_experiences: [],
  work_experiences: [],
  skills: [],
  version: 0,
  saved_at: null,
  has_saved_resume: false
}

const emptyProfile: SkillProfile = {
  items: [],
  visible_item_ids: [],
  summary: {
    live_script: 0,
    simulation_training: 0,
    quiz_score: 0,
    learning_record: 0
  }
}

const jobFixture: JobMatchingJob = {
  job_id: 'job-responsive',
  enterprise_id: 7,
  enterprise_name: '粤北乡村发展有限公司',
  title: longCjk,
  salary: '8000-12000 元/月',
  location: '广州市从化区乡村振兴产业园',
  category_id: 9,
  category_name: '农业数字化运营',
  description: longDescription,
  review_status: 'approved',
  version: 2,
  published_at: '2026-09-20T10:00:00+08:00',
  updated_at: '2026-09-20T10:00:00+08:00'
}

const paths = [
  '/',
  '/login',
  '/register',
  '/student',
  '/student/employment/resume',
  '/student/employment/skills',
  '/student/employment/jobs',
  '/student/employment/jobs/:jobId',
  '/student/employment/applications',
  '/student/employment/favorites'
]


function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: paths.map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}


function mountedOffenders(
  wrapper: ReturnType<typeof mount>
): string[] {
  return wrapper
    .findAll('*')
    .filter(element => {
      const computed = window.getComputedStyle(element.element)
      const hasText = Boolean(element.text().trim())
      return computed.position === 'fixed' && hasText
    })
    .map(element => element.element.tagName)
}


function configureStore(
  name: string,
  store: ReturnType<typeof useJobMatchingStore>
) {
  switch (name) {
    case 'resume':
      store.resume = emptyResume
      break
    case 'skills':
      store.skillProfile = emptyProfile
      break
    case 'jobs':
      store.jobs = []
      store.recommendedJobs = []
      vi.spyOn(store, 'loadJobs').mockResolvedValue(true)
      break
    case 'detail':
      store.activeJob = jobFixture
      vi.spyOn(store, 'loadJob').mockResolvedValue(jobFixture)
      break
    case 'applications':
      store.applications = []
      vi.spyOn(store, 'loadApplications').mockResolvedValue(true)
      break
    case 'favorites':
      store.favorites = []
      vi.spyOn(store, 'loadFavorites').mockResolvedValue(true)
      break
  }
}


async function mountEmploymentView(
  name: string,
  component: Component,
  path: string
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useJobMatchingStore()
  configureStore(name, store)
  const router = testRouter()
  await router.push(path)
  await router.isReady()

  const wrapper = mount(component, {
    global: {
      plugins: [pinia, router]
    }
  })
  await flushPromises()
  return { store, wrapper }
}


describe('job matching responsive acceptance', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('locks containment, wrapping, navigation and breakpoint contracts', () => {
    const viewSources = [
      resumeEditorViewSource,
      skillProfileViewSource,
      jobsViewSource,
      jobDetailViewSource,
      myApplicationsViewSource,
      jobFavoritesViewSource
    ]

    expect(jobMatchingNavSource).toContain('overflow-x: auto')
    expect(jobMatchingNavSource).not.toContain('white-space: nowrap')

    for (const source of viewSources) {
      expect(source).toContain('overflow-x: clip')
      expect(source).toContain('min-width: 0')
      expect(source).toContain('@media (max-width: 720px)')
      expect(source).toContain('@media (max-width: 360px)')
      expect(source).not.toContain('white-space: nowrap')
    }
    expect(viewSources.join('\n')).not.toMatch(
      /#[0-9a-f]{3,8}|rgba?\(|hsla?\(|linear-gradient|radial-gradient/i
    )
  })

  describe.each(widths)('at %dpx', width => {
    it('mounts all six employment views without clipped empty states', async () => {
      vi.stubGlobal('innerWidth', width)
      const cases = [
        {
          name: 'resume',
          component: ResumeEditorView,
          path: '/student/employment/resume',
          expectedText: '暂未添加技能特长。',
          dataTest: 'resume-form'
        },
        {
          name: 'skills',
          component: SkillProfileView,
          path: '/student/employment/skills',
          expectedText: '暂无可展示的技能成果',
          dataTest: 'skill-empty'
        },
        {
          name: 'jobs',
          component: JobsView,
          path: '/student/employment/jobs',
          expectedText: '暂无推荐',
          dataTest: 'recommended-jobs'
        },
        {
          name: 'detail',
          component: JobDetailView,
          path: '/student/employment/jobs/job-responsive',
          expectedText: longCjk,
          dataTest: 'job-detail'
        },
        {
          name: 'applications',
          component: MyApplicationsView,
          path: '/student/employment/applications',
          expectedText: '暂无投递记录',
          dataTest: 'applications-empty'
        },
        {
          name: 'favorites',
          component: JobFavoritesView,
          path: '/student/employment/favorites',
          expectedText: '暂无收藏岗位',
          dataTest: 'favorites-empty'
        }
      ] as const

      for (const view of cases) {
        const { wrapper } = await mountEmploymentView(
          view.name,
          view.component,
          view.path
        )

        expect(wrapper.text()).toContain(view.expectedText)
        expect(wrapper.find(`[data-test="${view.dataTest}"]`).exists())
          .toBe(true)
        expect(
          wrapper.element.querySelectorAll(
            'button, a, input, select, textarea'
          ).length
        ).toBeGreaterThan(0)
        expect(mountedOffenders(wrapper)).toEqual([])

        wrapper.unmount()
      }
    })
  })
})
