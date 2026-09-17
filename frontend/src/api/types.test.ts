import { describe, expect, it } from 'vitest'

import type {
  AgriculturalCourse,
  CourseProgress,
  CourseQuiz,
  CourseQuizAttempt,
  EcommerceCourse,
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
