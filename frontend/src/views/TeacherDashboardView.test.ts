import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type { TeacherDashboard, TeacherReport } from '@/api/types'

import TeacherDashboardView from './TeacherDashboardView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

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

function mountView() {
  return mount(TeacherDashboardView, {
    global: { plugins: [createPinia()] }
  })
}

describe('TeacherDashboardView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders exact aggregate cards without student details', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      dashboard: dashboardFixture
    } as never)
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.get('[data-test="student-total"]').text()).toContain('12')
    expect(wrapper.get('[data-test="average-progress"]').text()).toContain(
      '62.5%'
    )
    expect(wrapper.get('[data-test="completion-rate"]').text()).toContain('25%')
    expect(wrapper.get('[data-test="quiz-attempts"]').text()).toContain('30')
    expect(wrapper.get('[data-test="quiz-average-score"]').text()).toContain(
      '84.2'
    )
    expect(wrapper.text()).not.toContain('姓名')
  })

  it('renders all four direction groups with aggregate values', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      dashboard: dashboardFixture
    } as never)
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.get('[data-test="direction-agriculture"]').text()).toContain(
      '农业方向'
    )
    expect(wrapper.get('[data-test="direction-agriculture"]').text()).toContain(
      '4 人'
    )
    expect(wrapper.get('[data-test="direction-agriculture"]').text()).toContain(
      '75%'
    )
    expect(wrapper.get('[data-test="direction-ecommerce"]').text()).toContain(
      '50%'
    )
    expect(wrapper.get('[data-test="direction-handcraft"]').text()).toContain(
      '60%'
    )
    expect(wrapper.get('[data-test="direction-comprehensive"]').text()).toContain(
      '55%'
    )
  })

  it('generates a report and renders history detail with all three sections', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        dashboard: dashboardFixture
      } as never)
      .mockResolvedValueOnce({
        success: true,
        report: reportFixture
      } as never)
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('[data-test="generate-report"]').trigger('click')
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenLastCalledWith('/api/teacher/reports', {
      method: 'POST'
    })
    expect(wrapper.get('[data-test="report-history-item"]').text()).toContain(
      '2026'
    )
    expect(wrapper.get('[data-test="report-detail"]').text()).toContain(
      '进度分析'
    )
    expect(wrapper.get('[data-test="report-detail"]').text()).toContain(
      '整体进度稳定'
    )
    expect(wrapper.get('[data-test="report-detail"]').text()).toContain(
      '方向对比'
    )
    expect(wrapper.get('[data-test="report-detail"]').text()).toContain(
      '农业方向领先'
    )
    expect(wrapper.get('[data-test="report-detail"]').text()).toContain(
      '风险预警'
    )
    expect(wrapper.get('[data-test="report-detail"]').text()).toContain(
      '2 名学员长期零进度'
    )
  })

  it('loads saved report history and opens the newest report', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        dashboard: dashboardFixture
      } as never)
      .mockResolvedValueOnce({
        success: true,
        reports: [reportFixture]
      } as never)
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('[data-test="refresh-reports"]').trigger('click')
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenLastCalledWith('/api/teacher/reports')
    expect(wrapper.get('[data-test="report-history-item"]').text()).toContain(
      '2026'
    )
    expect(wrapper.get('[data-test="report-detail"]').text()).toContain(
      '整体进度稳定'
    )
  })

  it('keeps cards visible when report AI is unavailable', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        dashboard: dashboardFixture
      } as never)
      .mockRejectedValueOnce(new ApiError('AI 服务暂时不可用', 503))
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('[data-test="generate-report"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('AI 服务暂时不可用')
    expect(wrapper.find('[data-test="student-total"]').exists()).toBe(true)
  })
})
