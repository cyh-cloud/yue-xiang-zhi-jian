import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'

import { useHandcraftInheritanceStore } from './handcraftInheritance'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

describe('handcraftInheritance store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('loads craft progress and sends explicit step completion fields', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        progress: {
          user_id: 1,
          craft_key: 'guangxiu',
          status: 'available',
          available: true,
          unavailable_reason: null,
          completed_steps: [],
          completed_step_count: 0,
          resume_step_no: 1,
          is_completed: false,
          updated_at: null
        }
      } as never)
      .mockResolvedValueOnce({
        success: true,
        progress: {
          user_id: 1,
          craft_key: 'guangxiu',
          status: 'completed',
          available: true,
          unavailable_reason: null,
          completed_steps: [1],
          completed_step_count: 1,
          resume_step_no: 2,
          is_completed: false,
          updated_at: '2026-09-18T09:00:00+08:00',
          accepted: true,
          reason: null,
          step_no: 1,
          points_source_event_id: 'guangxiu|1:step-1',
          points_event: null,
          points_status: 'not_enqueued'
        }
      } as never)
    const store = useHandcraftInheritanceStore()

    expect(await store.loadProgress('guangxiu')).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/handcraft-inheritance/crafts/guangxiu/progress'
    )
    expect(store.progressByCraft.guangxiu.completed_steps).toEqual([])

    expect(await store.completeStep('guangxiu', 1, 'segment-1')).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/handcraft-inheritance/crafts/guangxiu/steps/1/complete',
      {
        method: 'POST',
        body: JSON.stringify({
          segment_id: 'segment-1'
        })
      }
    )
    expect(store.progressByCraft.guangxiu.completed_steps).toEqual([1])
  })

  it('keeps material, video and AR payloads separate', async () => {
    const craft = {
      craft_key: 'guangxiu',
      name: '广绣',
      sort_order: 1,
      introduction: '广绣针法细密。',
      is_demo: true,
      source_available: true,
      status: 'available',
      available: true,
      unavailable_reason: null,
      steps: [],
      material_guide: []
    }
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, craft } as never)
      .mockResolvedValueOnce({
        success: true,
        videos: [
          {
            video_id: 'demo-guangxiu-approved',
            craft_key: 'guangxiu',
            title: '广绣安全演示教学',
            review_status: 'approved',
            source_available: true,
            media_url: 'https://example.test/guangxiu.mp4',
            playback_url: 'https://example.test/guangxiu.mp4',
            version: 1,
            is_demo: true,
            available: true,
            status: 'available',
            unavailable_reason: null,
            published_at: '2026-09-17T00:00:00+08:00',
            created_at: '2026-09-17T00:00:00+08:00',
            updated_at: '2026-09-17T00:00:00+08:00'
          }
        ]
      } as never)
      .mockResolvedValueOnce({
        success: true,
        guidance: {
          craft_key: 'guangxiu',
          tool_preparation: ['绣线'],
          operating_points: ['先定位图案'],
          common_errors: ['针脚不匀'],
          steps: [
            {
              step_no: 1,
              title: '起针',
              instruction: '从背面起针并固定绣线。'
            }
          ]
        }
      } as never)
    const store = useHandcraftInheritanceStore()

    expect(await store.loadMaterialGuide('guangxiu')).toBe(true)
    expect(store.materialGuideByCraft.guangxiu?.material_guide).toEqual([])

    expect(await store.loadVideos('guangxiu')).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/handcraft-inheritance/videos?craft_key=guangxiu'
    )
    expect(store.videosByCraft.guangxiu[0].source_available).toBe(true)

    expect(
      await store.generateArGuidance(
        'guangxiu',
        '绣制花瓣',
        'segment-2'
      )
    ).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      '/api/handcraft-inheritance/ar-guidance',
      {
        method: 'POST',
        body: JSON.stringify({
          craft_key: 'guangxiu',
          project_label: '绣制花瓣',
          segment_id: 'segment-2'
        })
      }
    )
    expect(store.arGuidance?.steps[0].step_no).toBe(1)
  })
})
