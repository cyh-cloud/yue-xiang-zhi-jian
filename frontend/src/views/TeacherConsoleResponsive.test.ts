// @ts-expect-error Vitest executes this source-guard test in Node.
import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

function source(path: string): string {
  return readFileSync(path, 'utf8')
}

const navSource = source('src/components/TeacherConsoleNav.vue')
const portalSource = source('src/views/TeacherPortalView.vue')
const coursesSource = source('src/views/TeacherCoursesView.vue')
const managerSource = source('src/components/TeacherCourseManager.vue')
const quizSource = source('src/components/TeacherQuizEditor.vue')
const announcementsSource = source(
  'src/views/TeacherAnnouncementsView.vue'
)
const interactionsSource = source('src/views/TeacherInteractionsView.vue')
const dashboardSource = source('src/views/TeacherDashboardView.vue')

describe('teacher console responsive and accessibility guards', () => {
  it('keeps teacher navigation and cards within 320/375/1280 layouts', () => {
    expect(navSource).toContain('@media (max-width: 760px)')
    expect(navSource).toContain('overflow-x: clip')
    expect(navSource).toContain('grid-template-columns: repeat(4, minmax(0, 1fr))')
    expect(navSource).toContain('min-height: 58px')
    expect(managerSource).toContain(
      'grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr))'
    )
    expect(managerSource).toContain('@media (max-width: 360px)')

    for (const viewport of [320, 375, 1280]) {
      expect(
        [navSource, managerSource, coursesSource].every(
          item =>
            !item.includes(`min-width: ${viewport}px`) &&
            !item.includes(`width: ${viewport}px`)
        )
      ).toBe(true)
    }
  })

  it('declares mobile containment and collapse contracts for every shell view', () => {
    const containedSources = [
      portalSource,
      coursesSource,
      managerSource,
      quizSource,
      announcementsSource,
      interactionsSource,
      dashboardSource
    ]

    for (const item of containedSources) {
      expect(item).toContain('min-width: 0')
    }
    for (const item of [
      coursesSource,
      announcementsSource,
      interactionsSource,
      dashboardSource
    ]) {
      expect(item).toContain('overflow-x: clip')
    }

    expect(portalSource).toContain('@media (max-width: 760px)')
    expect(coursesSource).toContain(
      '@media (max-width: 760px), (orientation: portrait)'
    )
    expect(managerSource).toContain(
      '@media (max-width: 760px), (orientation: portrait)'
    )
    expect(managerSource).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(quizSource).toContain(
      '@media (max-width: 640px), (orientation: portrait)'
    )
    expect(quizSource).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(announcementsSource).toContain('@media (max-width: 820px)')
    expect(announcementsSource).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(interactionsSource).toContain('@media (max-width: 820px)')
    expect(interactionsSource).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(dashboardSource).toContain('@media (max-width: 860px)')
    expect(dashboardSource).toContain('@media (max-width: 640px)')
  })

  it('keeps teacher workflows labelled, announced and keyboard focusable', () => {
    expect(navSource).toContain('aria-label="教师工作台导航"')
    expect(navSource).toContain(':focus-visible')

    expect(managerSource).toContain('aria-labelledby="filters-title"')
    expect(managerSource).toContain('role="radiogroup"')
    expect(managerSource).toContain('aria-label="视频媒体来源"')
    expect(managerSource).toContain('role="alert"')
    expect(managerSource).toContain(':focus-visible')

    expect(quizSource).toContain('aria-labelledby="quiz-editor-title"')
    expect(quizSource).toContain('role="alert"')
    expect(quizSource).toContain('role="status"')
    expect(quizSource).toContain('prefers-reduced-motion: reduce')

    expect(announcementsSource).toContain(
      'aria-labelledby="announcement-form-title"'
    )
    expect(announcementsSource).toContain(
      'aria-labelledby="announcement-history-title"'
    )
    expect(announcementsSource).toContain('role="alert"')

    expect(interactionsSource).toContain('role="tablist"')
    expect(interactionsSource).toContain(':aria-selected=')
    expect(interactionsSource).toContain(
      'aria-labelledby="comment-list-title"'
    )
    expect(interactionsSource).toContain('role="alert"')

    expect(dashboardSource).toContain('aria-label="学习数据总览"')
    expect(dashboardSource).toContain('aria-labelledby="direction-title"')
    expect(dashboardSource).toContain('aria-labelledby="report-title"')
    expect(dashboardSource).toContain(':aria-pressed=')
    expect(dashboardSource).toContain('role="alert"')
  })
})
