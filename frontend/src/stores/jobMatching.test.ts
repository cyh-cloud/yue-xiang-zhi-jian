import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type {
  JobFavorite,
  JobMatchingJob,
  ResumeOptimizationOffer,
  SkillProfile,
  StudentApplication,
  StudentResume
} from '@/api/types'

import { useJobMatchingStore } from './jobMatching'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const resumeFixture: StudentResume = {
  education_experiences: [
    {
      school: '广东职业学院',
      major: '电子商务',
      degree: '专科',
      start_date: '2022-09',
      end_date: '2025-06'
    }
  ],
  work_experiences: [],
  skills: ['直播运营'],
  version: 1,
  saved_at: '2026-09-20T10:00:00+08:00',
  has_saved_resume: true
}

const offerFixture: ResumeOptimizationOffer = {
  offer_id: 'offer-1',
  base_version: 1,
  suggestions: ['补充量化成果'],
  rewritten_resume: {
    education_experiences: resumeFixture.education_experiences,
    work_experiences: [],
    skills: ['直播运营', '数据分析']
  },
  status: 'offered',
  created_at: '2026-09-20T10:05:00+08:00'
}

const skillProfileFixture: SkillProfile = {
  items: [
    {
      item_id: 'ecommerce:live_script:1',
      category: 'live_script',
      source_module: 'ecommerce',
      source_type: 'live_script',
      title: '农产品直播话术',
      summary: '完成直播话术训练',
      score: 88,
      is_formal: true,
      occurred_at: '2026-09-20T09:00:00+08:00',
      source_available: true,
      visible: false
    }
  ],
  visible_item_ids: [],
  summary: {
    live_script: 1,
    simulation_training: 0,
    quiz_score: 0,
    learning_record: 0
  }
}

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
  title: jobFixture.title,
  enterprise_name: jobFixture.enterprise_name,
  salary: jobFixture.salary,
  location: jobFixture.location,
  description: jobFixture.description,
  title_snapshot: jobFixture.title,
  enterprise_name_snapshot: jobFixture.enterprise_name,
  favorited_at: '2026-09-20T10:15:00+08:00',
  closed: false
}

describe('jobMatching store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('loads resume and sends the current version on save', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        resume: resumeFixture
      } as never)
      .mockResolvedValueOnce({
        success: true,
        resume: { ...resumeFixture, version: 2 }
      } as never)

    const store = useJobMatchingStore()
    await store.loadResume()
    await store.saveResume({
      expected_version: 1,
      education_experiences: [],
      work_experiences: [],
      skills: ['直播运营']
    })

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/job-matching/resume'
    )
    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      '/api/job-matching/resume',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          expected_version: 1,
          education_experiences: [],
          work_experiences: [],
          skills: ['直播运营']
        })
      })
    )
    expect(store.resume).toEqual({ ...resumeFixture, version: 2 })
  })

  it('optimizes, adopts and discards resume offers through exact routes', async () => {
    const adoptedResume = { ...resumeFixture, version: 2 }
    const discardedOffer = {
      ...offerFixture,
      status: 'discarded' as const
    }
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        offer: offerFixture
      } as never)
      .mockResolvedValueOnce({
        success: true,
        resume: adoptedResume
      } as never)
      .mockResolvedValueOnce({
        success: true,
        offer: discardedOffer
      } as never)

    const store = useJobMatchingStore()
    store.resume = resumeFixture

    expect(await store.optimizeResume(1)).toEqual(offerFixture)
    expect(await store.adoptOptimization('offer /一', 1)).toEqual(
      adoptedResume
    )
    expect(await store.discardOptimization('offer /一')).toEqual(
      discardedOffer
    )

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/job-matching/resume/optimize',
      {
        method: 'POST',
        body: JSON.stringify({ expected_version: 1 })
      }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/job-matching/resume/optimizations/offer%20%2F%E4%B8%80/adopt',
      {
        method: 'POST',
        body: JSON.stringify({ expected_version: 1 })
      }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/job-matching/resume/optimizations/offer%20%2F%E4%B8%80/discard',
      { method: 'POST' }
    )
    expect(store.resume).toEqual(adoptedResume)
    expect(store.optimizationOffer).toEqual(discardedOffer)
  })

  it('loads the skill profile and saves the complete visible set', async () => {
    const visibleProfile: SkillProfile = {
      ...skillProfileFixture,
      items: skillProfileFixture.items.map(item => ({
        ...item,
        visible: true
      })),
      visible_item_ids: ['ecommerce:live_script:1']
    }
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        profile: skillProfileFixture
      } as never)
      .mockResolvedValueOnce({
        success: true,
        profile: visibleProfile
      } as never)

    const store = useJobMatchingStore()

    expect(await store.loadSkillProfile()).toEqual(skillProfileFixture)
    expect(
      await store.saveSkillVisibility(['ecommerce:live_script:1'])
    ).toEqual(visibleProfile)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/job-matching/skill-profile'
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/job-matching/skill-profile/visibility',
      {
        method: 'PUT',
        body: JSON.stringify({
          visible_item_ids: ['ecommerce:live_script:1']
        })
      }
    )
    expect(store.skillProfile).toEqual(visibleProfile)
  })

  it('loads jobs, recommendations and an encoded job detail', async () => {
    const recommendedJob = {
      ...jobFixture,
      category_match_count: 1,
      recent_learning: true
    }
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        jobs: [jobFixture],
        recommended_jobs: [recommendedJob]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        job: recommendedJob
      } as never)

    const store = useJobMatchingStore()

    expect(await store.loadJobs()).toBe(true)
    expect(await store.loadJob('job /一')).toEqual(recommendedJob)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/job-matching/jobs'
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/job-matching/jobs/job%20%2F%E4%B8%80'
    )
    expect(store.jobs).toEqual([jobFixture])
    expect(store.recommendedJobs).toEqual([recommendedJob])
    expect(store.activeJob).toEqual(recommendedJob)
  })

  it('loads applications', async () => {
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      applications: [applicationFixture]
    } as never)

    const store = useJobMatchingStore()

    expect(await store.loadApplications()).toBe(true)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/job-matching/applications'
    )
    expect(store.applications).toEqual([applicationFixture])
  })

  it('submits an application with the exact attachment flag', async () => {
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      application: applicationFixture
    } as never)

    const store = useJobMatchingStore()

    expect(await store.submitApplication('job /一', true)).toEqual(
      applicationFixture
    )
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/job-matching/jobs/job%20%2F%E4%B8%80/applications',
      {
        method: 'POST',
        body: JSON.stringify({ attach_skill_profile: true })
      }
    )
  })

  it('loads, adds and removes favorites', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        favorites: [favoriteFixture]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        favorite: favoriteFixture
      } as never)
      .mockResolvedValueOnce({
        success: true,
        favorite: {
          job_id: favoriteFixture.job_id,
          favorited: false
        }
      } as never)

    const store = useJobMatchingStore()

    expect(await store.loadFavorites()).toBe(true)
    expect(await store.addFavorite('job /一')).toEqual(favoriteFixture)
    expect(await store.removeFavorite('job /一')).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/job-matching/favorites'
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/job-matching/favorites/job%20%2F%E4%B8%80',
      { method: 'POST' }
    )
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/job-matching/favorites/job%20%2F%E4%B8%80',
      { method: 'DELETE' }
    )
    expect(store.favorites).toEqual([])
  })

  it('preserves provider branch codes in errors', async () => {
    mockedApiFetch.mockRejectedValue(
      new ApiError(
        '已投递该岗位',
        409,
        { application_id: 'application-1' },
        '/student/employment/jobs',
        'already_applied'
      )
    )
    const store = useJobMatchingStore()

    await store.submitApplication('job-1', false)

    expect(store.error).toBe('已投递该岗位')
    expect(store.errorCode).toBe('already_applied')
    expect(store.fieldErrors).toEqual({
      application_id: 'application-1'
    })
  })
})
