import { describe, expect, it } from 'vitest'

import type {
  AiCompanionIntent,
  AgriculturalCourse,
  CourseDirection,
  CourseProgress,
  CourseQuiz,
  CourseQuizAttempt,
  EcommerceCourse,
  HandcraftCraft,
  HandcraftFulfillment,
  HandcraftLearningOutcome,
  HandcraftLedgerEntry,
  HandcraftPointsAccount,
  HandcraftRedemption,
  HandcraftReward,
  StorePlan
} from './types'

const agricultureCourseFixture = {
  id: 1,
  title: '农业课程',
  summary: '课程摘要',
  teacher_name: '教师',
  published_at: '2026-09-17T00:00:00+00:00',
  tag_ids: [1],
  duration_seconds: 300
} satisfies AgriculturalCourse

const ecommerceCourseFixture = {
  ...agricultureCourseFixture,
  direction: 'ecommerce',
  status: 'published',
  interest_match: true
} satisfies EcommerceCourse

const handcraftDirection = 'handcraft' satisfies CourseDirection

const handcraftCourseFixture = {
  ...agricultureCourseFixture,
  id: 501,
  title: '广绣基础',
  direction: handcraftDirection,
  status: 'published',
  interest_match: true,
  return_to: '/student/handcraft-inheritance/courses',
  comment_url: '/courses/501/comments'
} satisfies EcommerceCourse

const handcraftCraftFixture = {
  craft_key: 'guangxiu',
  name: '广绣',
  sort_order: 1,
  introduction: '广绣针法细密。',
  is_demo: true,
  source_available: true,
  status: 'available',
  available: true,
  unavailable_reason: null,
  steps: [
    {
      step_key: 'guangxiu-01',
      step_no: 1,
      title: '准备材料',
      description: '准备绣布、绣线与绣针。',
      tips: ['按色系整理绣线。']
    }
  ],
  material_guide: [
    {
      name: '真丝绣线',
      reference_price: '20-40 元/束',
      purchase_channel: '手工材料店',
      precautions: '按色系分批采购。',
      taobao_keyword: '广绣真丝绣线'
    }
  ]
} satisfies HandcraftCraft

const handcraftAccountFixture = {
  user_id: 1,
  balance: 30,
  updated_at: null,
  awarded_today: 0,
  daily_limit: 60,
  daily_limit_reached: false
} satisfies HandcraftPointsAccount

const handcraftLedgerFixture = {
  id: 8,
  user_id: 1,
  transaction_type: 'spend',
  source_module: 'handcraft',
  source_event_id: 'redemption:request-1',
  delta: -30,
  balance_after: 0,
  metadata: {},
  created_at: '2026-09-18T09:00:00+08:00'
} satisfies HandcraftLedgerEntry

const handcraftRewardFixture = {
  reward_id: 'reward-guangxiu-bookmark',
  name: '广绣书签',
  points_cost: 30,
  stock: 9,
  is_online: true,
  is_demo: true,
  source_available: true,
  affordable: false,
  can_redeem: false,
  unavailable_reason: '积分不足，还差 30 分'
} satisfies HandcraftReward

const handcraftRedemptionFixture = {
  id: 12,
  user_id: 1,
  reward_id: handcraftRewardFixture.reward_id,
  reward_name: handcraftRewardFixture.name,
  reward: handcraftRewardFixture,
  points_cost: 30,
  request_id: 'request-1',
  status: 'pending',
  reservation_status: 'reserved',
  created_at: '2026-09-18T09:00:00+08:00',
  updated_at: '2026-09-18T09:00:00+08:00',
  canceled_at: null
} satisfies HandcraftRedemption

const handcraftFulfillmentFixture = {
  id: 5,
  redemption_id: handcraftRedemptionFixture.id,
  status: 'pending',
  issued_at: null,
  verified_at: null,
  canceled_at: null,
  created_at: '2026-09-18T09:00:00+08:00',
  updated_at: '2026-09-18T09:00:00+08:00'
} satisfies HandcraftFulfillment

const handcraftOutcomeFixture = {
  outcome_type: 'course_quiz',
  source_id: 21,
  created_at: '2026-09-18T09:10:00+08:00',
  source_available: true,
  summary: '广绣基础',
  score: 100,
  is_formal: true,
  archive_written: false
} satisfies HandcraftLearningOutcome

const progressFixture = {
  user_id: 1,
  course_id: 2,
  duration_seconds: null,
  furthest_position_seconds: 0,
  resume_position_seconds: 0,
  progress_percent: 0,
  watched_seconds: 0,
  completed_at: null,
  last_viewed_at: null,
  updated_at: null,
  quiz_available: false
} satisfies CourseProgress

const quizFixture = {
  course_id: 2,
  questions: [
    {
      id: 'q1',
      type: 'single_choice',
      prompt: '课程完成后可测验吗？',
      options: ['可以', '不可以']
    }
  ]
} satisfies CourseQuiz

const attemptFixture = {
  id: 3,
  course_id: 2,
  answers: { q1: '可以' },
  score: 100,
  is_formal: true,
  is_current: true,
  is_latest: true,
  questions: [
    {
      ...quizFixture.questions[0],
      correct: true,
      explanation: '完成课程后测验入口才会开放。'
    }
  ],
  created_at: '2026-09-17T00:00:00+00:00'
} satisfies CourseQuizAttempt

const storePlanFixture = {
  id: 4,
  store_type: '农产品旗舰店',
  platform: 'taobao',
  style_preference: '温暖可靠',
  plan: {
    home_layout: [
      {
        zone: '首屏',
        modules: [
          {
            key: 'hero',
            title: '主视觉',
            position: { row: 1, column: 'left' },
            visible: true
          }
        ]
      }
    ],
    color_scheme: {
      primary: '暖红',
      variants: [
        {
          name: '点缀金',
          tokens: { hex: '#F7C948', contrast: 4.5 }
        }
      ]
    },
    detail_structure: ['卖点', '参数', '售后'],
    navigation: {
      primary: {
        label: '首页',
        children: [
          { label: '新品', order: 1, active: true },
          { label: '优惠', order: 2, active: false }
        ]
      }
    }
  },
  created_at: '2026-09-17T00:00:00+00:00'
} satisfies StorePlan

describe('004 wire DTOs', () => {
  it('keeps the legacy agriculture alias compatible without direction', () => {
    expect(Object.keys(agricultureCourseFixture)).toEqual([
      'id',
      'title',
      'summary',
      'teacher_name',
      'published_at',
      'tag_ids',
      'duration_seconds'
    ])
  })

  it('matches the ecommerce provider key set', () => {
    expect(Object.keys(ecommerceCourseFixture)).toEqual([
      'id',
      'title',
      'summary',
      'teacher_name',
      'published_at',
      'tag_ids',
      'duration_seconds',
      'direction',
      'status',
      'interest_match'
    ])
  })

  it('supports handcraft courses and preserves optional link fields', () => {
    expect(handcraftCourseFixture.direction).toBe('handcraft')
    expect(handcraftCourseFixture.return_to).toBe(
      '/student/handcraft-inheritance/courses'
    )
    expect(handcraftCourseFixture.comment_url).toBe(
      '/courses/501/comments'
    )
  })

  it('matches handcraft source, points, redemption and outcome fields', () => {
    expect(handcraftCraftFixture.source_available).toBe(true)
    expect(handcraftAccountFixture.updated_at).toBeNull()
    expect(handcraftAccountFixture.daily_limit).toBe(60)
    expect(handcraftAccountFixture.daily_limit_reached).toBe(false)
    expect(handcraftLedgerFixture.delta).toBe(-30)
    expect(handcraftRewardFixture.source_available).toBe(true)
    expect(handcraftRedemptionFixture.request_id).toBe('request-1')
    expect(handcraftFulfillmentFixture.status).toBe('pending')
    expect(handcraftOutcomeFixture).toMatchObject({
      source_available: true,
      is_formal: true,
      archive_written: false
    })
  })

  it('matches progress and quiz attempt key and marker types', () => {
    expect(Object.keys(progressFixture)).toEqual([
      'user_id',
      'course_id',
      'duration_seconds',
      'furthest_position_seconds',
      'resume_position_seconds',
      'progress_percent',
      'watched_seconds',
      'completed_at',
      'last_viewed_at',
      'updated_at',
      'quiz_available'
    ])
    expect(progressFixture.quiz_available).toBe(false)
    expect(Object.keys(attemptFixture)).toEqual([
      'id',
      'course_id',
      'answers',
      'score',
      'is_formal',
      'is_current',
      'is_latest',
      'questions',
      'created_at'
    ])
    expect([
      attemptFixture.is_formal,
      attemptFixture.is_current,
      attemptFixture.is_latest
    ]).toEqual([true, true, true])
  })

  it('accepts variable platform plan values without unknown casts', () => {
    expect(storePlanFixture.plan.home_layout).toEqual([
      {
        zone: '首屏',
        modules: [
          {
            key: 'hero',
            title: '主视觉',
            position: { row: 1, column: 'left' },
            visible: true
          }
        ]
      }
    ])
    expect(storePlanFixture.plan.color_scheme).toEqual({
      primary: '暖红',
      variants: [
        {
          name: '点缀金',
          tokens: { hex: '#F7C948', contrast: 4.5 }
        }
      ]
    })
    expect(storePlanFixture.plan.navigation).toEqual({
      primary: {
        label: '首页',
        children: [
          { label: '新品', order: 1, active: true },
          { label: '优惠', order: 2, active: false }
        ]
      }
    })
  })
})

describe('012 AI 学伴 wire DTOs', () => {
  it('keeps exactly three AI companion intents', () => {
    const intents: AiCompanionIntent[] = [
      'platform_usage',
      'learning_question',
      'out_of_scope'
    ]
    expect(intents).toHaveLength(3)
  })
})
