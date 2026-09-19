import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type {
  JobFavorite,
  JobMatchingJob,
  StudentApplication
} from '@/api/types'
import JobMatchingNav from '@/components/JobMatchingNav.vue'
import { useJobMatchingStore } from '@/stores/jobMatching'

import JobDetailView from './JobDetailView.vue'
import JobsView from './JobsView.vue'
import jobDetailViewSource from './JobDetailView.vue?raw'
import jobsViewSource from './JobsView.vue?raw'

const jobFixture: JobMatchingJob = {
  job_id: 'job-1',
  enterprise_id: 2,
  enterprise_name: '荔乡电商',
  title: '电商运营',
  salary: '7k-9k',
  location: '佛山',
  category_id: 10,
  category_name: '电商运营',
  description: '负责直播运营。',
  review_status: 'approved',
  version: 1,
  published_at: '2026-09-20T09:00:00+08:00',
  updated_at: '2026-09-20T09:00:00+08:00'
}

const applicationFixture: StudentApplication = {
  application_id: 'application-1',
  job_id: jobFixture.job_id,
  enterprise_id: jobFixture.enterprise_id,
  enterprise_name: jobFixture.enterprise_name,
  student_id: 1,
  student_name: '学员一',
  job_title: jobFixture.title,
  status: 'pending',
  status_version: 1,
  position_closed: false,
  position_closed_at: null,
  effective_status: 'pending',
  effective_status_label: '待处理',
  submitted_at: '2026-09-20T10:10:00+08:00',
  show_closed_marker: false
}

const favoriteFixture: JobFavorite = {
  job_id: jobFixture.job_id,
  title: '旧收藏岗位标题',
  enterprise_name: '旧收藏公司',
  salary: '5k-6k',
  location: '广州',
  description: '不应作为详情回退。',
  title_snapshot: '旧收藏岗位标题',
  enterprise_name_snapshot: '旧收藏公司',
  favorited_at: '2026-09-20T10:15:00+08:00',
  closed: false
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

async function mountJobs(
  jobs: JobMatchingJob[] = [],
  recommendedJobs: JobMatchingJob[] = []
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useJobMatchingStore()
  store.jobs = jobs
  store.recommendedJobs = recommendedJobs
  vi.spyOn(store, 'loadJobs').mockResolvedValue(true)

  const router = testRouter()
  await router.push('/student/employment/jobs')
  await router.isReady()

  const wrapper = mount(JobsView, {
    global: {
      plugins: [pinia, router]
    }
  })
  await flushPromises()

  return { router, store, wrapper }
}

async function mountDetail(
  job: JobMatchingJob | null = jobFixture,
  jobId = jobFixture.job_id
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useJobMatchingStore()
  store.activeJob = job
  const loadJob = vi
    .spyOn(store, 'loadJob')
    .mockResolvedValue(job?.job_id === jobId ? job : null)

  const router = testRouter()
  await router.push(`/student/employment/jobs/${jobId}`)
  await router.isReady()

  const wrapper = mount(JobDetailView, {
    global: {
      plugins: [pinia, router]
    }
  })
  await flushPromises()

  return { loadJob, router, store, wrapper }
}

describe('JobsView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders recommended jobs separately from the complete list', async () => {
    const { wrapper } = await mountJobs([jobFixture], [jobFixture])

    expect(
      wrapper.get('[data-test="recommended-jobs"]').text()
    ).toContain('推荐岗位')
    expect(wrapper.get('[data-test="all-jobs"]').text()).toContain(
      '电商运营'
    )
    expect(
      wrapper.findAll('[data-test="recommended-job-card"]')
    ).toHaveLength(1)
    expect(wrapper.findAll('[data-test="job-card"]')).toHaveLength(1)
  })

  it('renders both exact empty states independently', async () => {
    const { wrapper } = await mountJobs()

    expect(
      wrapper.get('[data-test="recommended-jobs"]').text()
    ).toContain('暂无推荐')
    expect(wrapper.get('[data-test="all-jobs"]').text()).toContain(
      '暂无岗位'
    )
  })

  it('renders the required job fields without review controls', async () => {
    const { wrapper } = await mountJobs([jobFixture], [jobFixture])
    const card = wrapper.get('[data-test="job-card"]')

    expect(card.text()).toContain(jobFixture.title)
    expect(card.text()).toContain(jobFixture.enterprise_name)
    expect(card.text()).toContain(jobFixture.salary)
    expect(card.text()).toContain(jobFixture.location)
    expect(card.text()).toContain(jobFixture.description)
    expect(wrapper.text()).not.toContain('待审核')
    expect(wrapper.text()).not.toContain('已驳回')
    expect(wrapper.find('[data-test="job-review"]').exists()).toBe(false)
  })

  it('does not render a nonpublished projection if one reaches the store', async () => {
    const nonpublishedJob = {
      ...jobFixture,
      job_id: 'job-pending',
      title: '不应显示的岗位',
      review_status: 'pending'
    } as unknown as JobMatchingJob
    const { wrapper } = await mountJobs(
      [jobFixture, nonpublishedJob],
      [jobFixture, nonpublishedJob]
    )

    expect(wrapper.text()).not.toContain(nonpublishedJob.title)
    expect(wrapper.findAll('[data-test="job-card"]')).toHaveLength(1)
    expect(
      wrapper.findAll('[data-test="recommended-job-card"]')
    ).toHaveLength(1)
  })

  it('exposes the exact employment navigation links and accessible labels', async () => {
    const { wrapper } = await mountJobs()
    const nav = wrapper.getComponent(JobMatchingNav)

    expect(nav.get('nav').attributes('aria-label')).toBe('就业对接导航')
    expect(
      nav.findAll('a').map(link => ({
        href: link.attributes('href'),
        label: link.attributes('aria-label')
      }))
    ).toEqual([
      {
        href: '/student/employment/resume',
        label: '简历维护'
      },
      {
        href: '/student/employment/skills',
        label: '我的技能档案'
      },
      {
        href: '/student/employment/jobs',
        label: '岗位浏览'
      },
      {
        href: '/student/employment/applications',
        label: '我的投递'
      },
      {
        href: '/student/employment/favorites',
        label: '岗位收藏'
      },
      {
        href: '/student',
        label: '返回学员门户'
      }
    ])
  })

  it('uses the requested bounded grid and light-token CJK constraints', () => {
    expect(jobsViewSource).toContain(
      `.recommended-grid,
.job-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
  gap: 1px;
}`
    )

    for (const source of [jobsViewSource, jobDetailViewSource]) {
      expect(source).toContain('min-width: 0')
      expect(source).toContain('line-break: strict')
      expect(source).toContain('overflow-wrap: anywhere')
      expect(source).toContain('word-break: normal')
      expect(source).toContain('@media (max-width: 720px)')
      expect(source).toContain('@media (max-width: 360px)')
      expect(source).not.toMatch(
        /#[0-9a-f]{3,8}|rgba?\(|hsla?\(|linear-gradient|radial-gradient/i
      )
    }
  })
})

describe('JobDetailView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads the route job into activeJob and shows its complete details', async () => {
    const { loadJob, wrapper } = await mountDetail()

    expect(loadJob).toHaveBeenCalledWith(jobFixture.job_id)
    expect(wrapper.get('[data-test="job-detail"]').text()).toContain(
      jobFixture.title
    )
    expect(wrapper.get('[data-test="job-detail"]').text()).toContain(
      jobFixture.enterprise_name
    )
    expect(wrapper.get('[data-test="job-detail"]').text()).toContain(
      jobFixture.salary
    )
    expect(wrapper.get('[data-test="job-detail"]').text()).toContain(
      jobFixture.location
    )
    expect(wrapper.get('[data-test="job-description"]').text()).toBe(
      jobFixture.description
    )
    expect(wrapper.get('[data-test="application-form"]').text()).toContain(
      '附带技能档案'
    )
    expect(wrapper.get('[data-test="submit-application"]').text()).toBe(
      '投递简历'
    )
  })

  it('does not fall back to a stale favorite snapshot', async () => {
    const { store, wrapper } = await mountDetail(null)
    store.favorites = [favoriteFixture]
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain(favoriteFixture.title)
    expect(wrapper.text()).not.toContain(favoriteFixture.description)
    expect(
      wrapper.get('[data-test="job-detail-unavailable"]').text()
    ).toContain('岗位已关闭或暂不可投递')
  })

  it('sends the exact attachment boolean', async () => {
    const { store, wrapper } = await mountDetail()
    const submitApplication = vi
      .spyOn(store, 'submitApplication')
      .mockResolvedValue(applicationFixture)

    await wrapper
      .get('[data-test="attach-skill-profile"]')
      .setValue(true)
    await wrapper
      .get('[data-test="application-form"]')
      .trigger('submit')
    await flushPromises()

    expect(submitApplication).toHaveBeenCalledWith('job-1', true)
  })

  it('links to resume maintenance for the exact resume_required branch', async () => {
    const { store, wrapper } = await mountDetail()
    vi.spyOn(store, 'submitApplication').mockImplementation(async () => {
      store.error = '请先创建并保存简历'
      store.errorCode = 'resume_required'
      return null
    })

    await wrapper
      .get('[data-test="application-form"]')
      .trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-test="application-error"]').text()).toBe(
      '请先创建并保存简历'
    )
    expect(
      wrapper
        .get('[data-test="create-resume-link"]')
        .attributes('href')
    ).toBe('/student/employment/resume')
  })

  it.each([
    ['already_applied', '已投递该岗位'],
    ['job_unavailable', '岗位已关闭或暂不可投递']
  ])(
    'shows the exact %s branch message without debug details',
    async (errorCode, message) => {
      const { store, wrapper } = await mountDetail()
      vi.spyOn(store, 'submitApplication').mockImplementation(async () => {
        store.error = message
        store.errorCode = errorCode
        return null
      })

      await wrapper
        .get('[data-test="application-form"]')
        .trigger('submit')
      await flushPromises()

      expect(wrapper.get('[data-test="application-error"]').text()).toBe(
        message
      )
      expect(wrapper.get('[data-test="application-error"]').text()).not.toContain(
        errorCode
      )
      expect(
        wrapper.find('[data-test="create-resume-link"]').exists()
      ).toBe(false)
    }
  )

  it('navigates to my applications after a successful submission', async () => {
    const { router, store, wrapper } = await mountDetail()
    vi.spyOn(store, 'submitApplication').mockResolvedValue(
      applicationFixture
    )

    await wrapper
      .get('[data-test="application-form"]')
      .trigger('submit')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe(
      '/student/employment/applications'
    )
  })

  it('does not render out-of-scope lifecycle controls', async () => {
    const { wrapper } = await mountDetail()

    expect(wrapper.text()).not.toContain('撤回')
    expect(wrapper.text()).not.toContain('线上面试')
    expect(wrapper.text()).not.toContain('电子签约')
    expect(wrapper.text()).not.toContain('入职流程')
    expect(wrapper.find('[data-test="withdraw-application"]').exists()).toBe(
      false
    )
    expect(wrapper.find('[data-test="interview-action"]').exists()).toBe(
      false
    )
    expect(wrapper.find('[data-test="contract-action"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="onboarding-action"]').exists()).toBe(
      false
    )
  })
})
