import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'
import type { TeacherAnnouncement } from '@/api/types'

import TeacherAnnouncementsView from './TeacherAnnouncementsView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function announcement(
  overrides: Partial<TeacherAnnouncement> = {}
): TeacherAnnouncement {
  return {
    announcement_id: 'teaching-1',
    teacher_id: 7,
    title: '课程安排',
    body: '本周调整',
    event_id: 'teaching-1:v1',
    delivery_status: 'sent',
    delivery_result: {},
    created_at: '2026-09-18T10:00:00+08:00',
    ...overrides
  }
}

function mountView() {
  return mount(TeacherAnnouncementsView, {
    global: { plugins: [createPinia()] }
  })
}

describe('TeacherAnnouncementsView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    mockedApiFetch.mockResolvedValue({
      success: true,
      announcements: []
    } as never)
  })

  it('loads pending, sent, and failed history without sent actions', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      announcements: [
        announcement({
          announcement_id: 'teaching-pending',
          title: '待发送公告',
          delivery_status: 'pending',
          created_at: '2026-09-18T09:00:00+08:00'
        }),
        announcement({
          announcement_id: 'teaching-sent',
          title: '已发送公告',
          delivery_status: 'sent',
          created_at: '2026-09-18T10:00:00+08:00'
        }),
        announcement({
          announcement_id: 'teaching-failed',
          title: '失败公告',
          delivery_status: 'failed',
          created_at: '2026-09-18T08:00:00+08:00'
        })
      ]
    } as never)

    const wrapper = mountView()
    await flushPromises()

    const statuses = wrapper
      .findAll('[data-test="announcement-item"]')
      .map(item => item.attributes('data-status'))
    expect(statuses).toEqual(['sent', 'pending', 'failed'])
    expect(wrapper.text()).toContain('已群发')
    expect(wrapper.text()).toContain('待发送')
    expect(wrapper.text()).toContain('群发失败')
    expect(wrapper.find('[data-test="edit-announcement"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="delete-announcement"]').exists()).toBe(false)
    expect(wrapper.get('[data-test="sent-immutable"]').text()).toContain(
      '已群发，不可编辑或撤回'
    )
  })

  it('publishes an announcement and moves it into history', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        announcements: []
      } as never)
      .mockResolvedValueOnce({
        success: true,
        announcement: announcement()
      } as never)
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('[data-test="announcement-title"]').setValue('课程安排')
    await wrapper.get('[data-test="announcement-body"]').setValue('本周调整')
    await wrapper.get('[data-test="publish-announcement"]').trigger('click')
    await flushPromises()

    expect(mockedApiFetch).toHaveBeenLastCalledWith(
      '/api/teacher/announcements',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          title: '课程安排',
          body: '本周调整'
        })
      })
    )
    expect(wrapper.text()).toContain('已群发')
    expect(wrapper.find('[data-test="edit-announcement"]').exists()).toBe(false)
    expect(
      (wrapper.get('[data-test="announcement-title"]').element as HTMLInputElement)
        .value
    ).toBe('')
    expect(
      (wrapper.get('[data-test="announcement-body"]').element as HTMLTextAreaElement)
        .value
    ).toBe('')
  })

  it('rejects a blank announcement before making a publish request', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('[data-test="publish-announcement"]').trigger('click')

    expect(wrapper.text()).toContain('请填写公告标题和正文')
    expect(mockedApiFetch).toHaveBeenCalledTimes(1)
    expect(mockedApiFetch).toHaveBeenCalledWith('/api/teacher/announcements')
  })
})
