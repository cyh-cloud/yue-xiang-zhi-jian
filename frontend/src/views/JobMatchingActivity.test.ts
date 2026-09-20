import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type {
  EffectiveApplicationStatus,
  JobFavorite,
  StudentApplication
} from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import JobMatchingNav from '@/components/JobMatchingNav.vue'
import JobMatchingStatusBadge from '@/components/JobMatchingStatusBadge.vue'
import jobMatchingStatusBadgeSource from '@/components/JobMatchingStatusBadge.vue?raw'
import { useJobMatchingStore } from '@/stores/jobMatching'

import JobFavoritesView from './JobFavoritesView.vue'
import jobFavoritesViewSource from './JobFavoritesView.vue?raw'
import MyApplicationsView from './MyApplicationsView.vue'
import myApplicationsViewSource from './MyApplicationsView.vue?raw'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const availableFavorite: JobFavorite = {
  job_id: 'job-available',
  title: '最新电商运营岗位',
  enterprise_name: '荔乡电商有限公司',
  salary: '7k-9k',
  location: '佛山',
  description: '负责直播运营与商品内容策划。',
  title_snapshot: '旧电商运营岗位',
  enterprise_name_snapshot: '旧荔乡电商有限公司',
  favorited_at: '2026-09-20T11:20:00+08:00',
  closed: false
}

const closedFavorite: JobFavorite = {
  job_id: 'job-closed',
  title: '',
  enterprise_name: '',
  salary: '5k-6k',
  location: '广州',
  description: '负责乡村振兴项目内容整理。',
  title_snapshot: '已关闭品牌策划岗位',
  enterprise_name_snapshot: '粤北乡村发展有限公司',
  favorited_at: '2026-09-19T09:30:00+08:00',
  closed: true
}

const olderApplication: StudentApplication = {
  application_id: 'application-older',
  job_id: 'job-1',
  enterprise_id: 2,
  enterprise_name: '荔乡电商有限公司',
  student_id: 1,
  student_name: '学员一',
  job_title: '电商运营',
  status: 'pending',
  status_version: 1,
  position_closed: false,
  position_closed_at: null,
  effective_status: 'pending',
  effective_status_label: '待处理',
  submitted_at: '2026-09-19T09:30:00+08:00',
  show_closed_marker: false
}

const newerApplication: StudentApplication = {
  ...olderApplication,
  application_id: 'application-newer',
  job_id: 'job-2',
  enterprise_name: '粤北乡村发展有限公司',
  job_title: '品牌策划',
  status: 'unsuitable',
  status_version: 2,
  position_closed: true,
  position_closed_at: '2026-09-20T12:00:00+08:00',
  effective_status: 'unsuitable',
  effective_status_label: '不合适',
  submitted_at: '2026-09-20T10:10:00+08:00',
  show_closed_marker: true
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

async function mountApplications(
  applications: StudentApplication[] = []
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useJobMatchingStore()
  store.applications = applications
  const loadApplications = vi
    .spyOn(store, 'loadApplications')
    .mockResolvedValue(true)

  const router = testRouter()
  await router.push('/student/employment/applications')
  await router.isReady()

  const wrapper = mount(MyApplicationsView, {
    global: {
      plugins: [pinia, router]
    }
  })
  await flushPromises()

  return { loadApplications, router, store, wrapper }
}

async function mountFavorites(favorites: JobFavorite[] = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useJobMatchingStore()
  store.favorites = favorites
  const loadFavorites = vi
    .spyOn(store, 'loadFavorites')
    .mockResolvedValue(true)
  const removeFavorite = vi
    .spyOn(store, 'removeFavorite')
    .mockImplementation(async jobId => {
      store.favorites = store.favorites.filter(
        favorite => favorite.job_id !== jobId
      )
      return true
    })

  const router = testRouter()
  await router.push('/student/employment/favorites')
  await router.isReady()

  const wrapper = mount(JobFavoritesView, {
    global: {
      plugins: [pinia, router]
    }
  })
  await flushPromises()

  return {
    loadFavorites,
    removeFavorite,
    router,
    store,
    wrapper
  }
}

describe('JobMatchingStatusBadge', () => {
  it('renders the five exact application states', () => {
    const states: Array<{
      status: Exclude<EffectiveApplicationStatus, 'closed'>
      effectiveStatus: EffectiveApplicationStatus
      label: string
    }> = [
      {
        status: 'pending',
        effectiveStatus: 'pending',
        label: '待处理'
      },
      {
        status: 'viewed',
        effectiveStatus: 'viewed',
        label: '已查看'
      },
      {
        status: 'intent',
        effectiveStatus: 'intent',
        label: '意向沟通'
      },
      {
        status: 'unsuitable',
        effectiveStatus: 'unsuitable',
        label: '不合适'
      },
      {
        status: 'pending',
        effectiveStatus: 'closed',
        label: '岗位已关闭'
      }
    ]

    for (const state of states) {
      const wrapper = mount(JobMatchingStatusBadge, {
        props: {
          status: state.status,
          effectiveStatus: state.effectiveStatus,
          positionClosed: state.effectiveStatus === 'closed'
        }
      })

      expect(
        wrapper.get('[data-test="application-status-label"]').text()
      ).toBe(state.label)
    }
  })

  it('keeps unsuitable visible after closure', () => {
    const wrapper = mount(JobMatchingStatusBadge, {
      props: {
        status: 'unsuitable',
        effectiveStatus: 'unsuitable',
        positionClosed: true
      }
    })

    expect(
      wrapper.get('[data-test="application-status-label"]').text()
    ).toBe('不合适')
    expect(
      wrapper.get('[data-test="application-closed-marker"]').text()
    ).toBe('岗位已关闭')
  })

  it('renders closed pending as the primary closed state', () => {
    const wrapper = mount(JobMatchingStatusBadge, {
      props: {
        status: 'pending',
        effectiveStatus: 'closed',
        positionClosed: true
      }
    })

    expect(wrapper.text()).toContain('岗位已关闭')
    expect(wrapper.text()).not.toContain('待处理')
    expect(
      wrapper.find('[data-test="application-closed-marker"]').exists()
    ).toBe(false)
  })
})

describe('MyApplicationsView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    mockedApiFetch.mockReset()
  })

  it('preserves API order and renders the required application fields', async () => {
    const { loadApplications, wrapper } = await mountApplications([
      olderApplication,
      newerApplication
    ])

    expect(loadApplications).toHaveBeenCalledTimes(1)
    expect(wrapper.findComponent(AppHeader).exists()).toBe(true)
    expect(wrapper.findComponent(JobMatchingNav).exists()).toBe(true)

    const rows = wrapper.findAll('[data-test="application-item"]')
    expect(rows.map(row => row.attributes('data-application-id'))).toEqual([
      'application-older',
      'application-newer'
    ])

    expect(rows[0].text()).toContain('电商运营')
    expect(rows[0].text()).toContain('荔乡电商有限公司')
    expect(rows[0].get('time').attributes('datetime')).toBe(
      olderApplication.submitted_at
    )
    expect(rows[0].get('time').text()).toBe('2026-09-19 09:30')
    expect(
      rows[0].get('[data-test="application-status-label"]').text()
    ).toBe('待处理')

    expect(
      rows[1].get('[data-test="application-status-label"]').text()
    ).toBe('不合适')
    expect(
      rows[1].get('[data-test="application-closed-marker"]').text()
    ).toBe('岗位已关闭')
  })

  it('shows the exact empty state', async () => {
    const { wrapper } = await mountApplications()

    expect(
      wrapper.get('[data-test="applications-empty"]').text()
    ).toBe('暂无投递记录')
  })

  it('does not expose mutation, withdraw, or replacement actions', async () => {
    const { wrapper } = await mountApplications([
      olderApplication,
      newerApplication
    ])

    for (const row of wrapper.findAll('[data-test="application-item"]')) {
      expect(row.find('button').exists()).toBe(false)
      expect(row.find('a').exists()).toBe(false)
      expect(row.text()).not.toMatch(/撤回|删除|重新投递|重新提交|替换/)
    }
  })
})

describe('JobFavoritesView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    mockedApiFetch.mockReset()
  })

  it('renders current data and the last snapshot for closed favorites', async () => {
    const { loadFavorites, wrapper } = await mountFavorites([
      availableFavorite,
      closedFavorite
    ])

    expect(loadFavorites).toHaveBeenCalledTimes(1)
    expect(wrapper.findComponent(AppHeader).exists()).toBe(true)
    expect(wrapper.findComponent(JobMatchingNav).exists()).toBe(true)

    const available = wrapper.get('[data-test="favorite-available"]')
    expect(available.text()).toContain(availableFavorite.title)
    expect(available.text()).toContain(
      availableFavorite.enterprise_name
    )
    expect(available.text()).not.toContain(
      availableFavorite.title_snapshot
    )
    expect(
      available.get('[data-test="apply-favorite"]').attributes('href')
    ).toBe('/student/employment/jobs/job-available')

    const closed = wrapper.get('[data-test="favorite-closed"]')
    expect(closed.text()).toContain(closedFavorite.title_snapshot)
    expect(closed.text()).toContain(
      closedFavorite.enterprise_name_snapshot
    )
    expect(closed.text()).toContain(closedFavorite.salary)
    expect(closed.text()).toContain(closedFavorite.location)
    expect(closed.text()).toContain(closedFavorite.description)
    expect(closed.text()).toContain('岗位已关闭')
    expect(
      closed.get('[data-test="apply-favorite"]').attributes('disabled')
    ).toBeDefined()
    expect(
      closed.get('[data-test="remove-favorite"]').attributes('disabled')
    ).toBeUndefined()
  })

  it('allows removal for available and closed favorites', async () => {
    const { removeFavorite, wrapper } = await mountFavorites([
      availableFavorite,
      closedFavorite
    ])

    await wrapper
      .get(
        '[data-test="favorite-available"] [data-test="remove-favorite"]'
      )
      .trigger('click')
    await flushPromises()
    expect(removeFavorite).toHaveBeenCalledWith('job-available')
    expect(
      wrapper.find('[data-test="favorite-available"]').exists()
    ).toBe(false)

    const closedRemove = wrapper.get(
      '[data-test="favorite-closed"] [data-test="remove-favorite"]'
    )
    expect(closedRemove.text()).toBe('移除收藏')
    await closedRemove.trigger('click')
    await flushPromises()

    expect(removeFavorite).toHaveBeenCalledWith('job-closed')
    expect(
      wrapper.find('[data-test="favorite-closed"]').exists()
    ).toBe(false)
  })

  it('removes the closed marker when a favorite becomes available again', async () => {
    const { store, wrapper } = await mountFavorites([closedFavorite])

    expect(wrapper.text()).toContain('岗位已关闭')
    expect(
      wrapper.get('[data-test="apply-favorite"]').attributes('disabled')
    ).toBeDefined()

    store.favorites.splice(0, 1, {
      ...closedFavorite,
      title: '重新上架品牌策划岗位',
      enterprise_name: '粤北乡村发展有限公司',
      closed: false
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('岗位已关闭')
    expect(wrapper.text()).toContain('重新上架品牌策划岗位')
    expect(
      wrapper.get('[data-test="apply-favorite"]').attributes('disabled')
    ).toBeUndefined()
    expect(
      wrapper.get('[data-test="apply-favorite"]').attributes('href')
    ).toBe('/student/employment/jobs/job-closed')
  })

  it('shows the exact empty state', async () => {
    const { wrapper } = await mountFavorites()

    expect(wrapper.get('[data-test="favorites-empty"]').text()).toBe(
      '暂无收藏岗位'
    )
  })

  it('uses the exact favorite add and remove routes', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useJobMatchingStore()
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        favorite: availableFavorite
      } as never)
      .mockResolvedValueOnce({
        success: true,
        favorite: {
          job_id: 'job /一',
          favorited: false
        }
      } as never)

    expect(await store.addFavorite('job /一')).toEqual(
      availableFavorite
    )
    expect(await store.removeFavorite('job /一')).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/job-matching/favorites/job%20%2F%E4%B8%80',
      { method: 'POST' }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/job-matching/favorites/job%20%2F%E4%B8%80',
      { method: 'DELETE' }
    )
  })

  it('keeps the activity UI on light tokens and CJK-safe responsive rules', () => {
    const sources = [
      jobMatchingStatusBadgeSource,
      myApplicationsViewSource,
      jobFavoritesViewSource
    ]

    for (const source of sources) {
      expect(source).toContain('line-break: strict')
      expect(source).toContain('overflow-wrap: anywhere')
      expect(source).toContain('word-break: normal')
      expect(source).toContain('@media (max-width: 720px)')
      expect(source).toContain('@media (max-width: 360px)')
      expect(source).not.toContain('white-space: nowrap')
      expect(source).not.toMatch(
        /#[0-9a-f]{3,8}|rgba?\(|hsla?\(|linear-gradient|radial-gradient|\bcyan\b|\borb\b/i
      )
    }
  })
})
