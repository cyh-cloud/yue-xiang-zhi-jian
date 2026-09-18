import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ActiveLearningHeartbeatController } from './activeLearningHeartbeat'

describe('ActiveLearningHeartbeatController', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('sends a server heartbeat every 30 seconds while active', async () => {
    const heartbeat = vi
      .fn()
      .mockResolvedValueOnce({
        segment_id: 'segment-1',
        heartbeat_seq: 0,
        active_seconds: 0,
        restarted: false
      })
      .mockResolvedValueOnce({
        segment_id: 'segment-1',
        heartbeat_seq: 1,
        active_seconds: 30,
        restarted: false
      })
    const controller = new ActiveLearningHeartbeatController({ heartbeat })

    controller.touch()
    await vi.advanceTimersByTimeAsync(30_000)

    expect(heartbeat).toHaveBeenNthCalledWith(1, {
      segment_id: null,
      heartbeat_seq: 0
    })
    expect(heartbeat).toHaveBeenNthCalledWith(2, {
      segment_id: 'segment-1',
      heartbeat_seq: 1
    })
    expect(controller.currentSegmentId()).toBe('segment-1')
  })

  it('stops after three idle minutes and resumes in a new segment', async () => {
    let segmentNumber = 0
    const heartbeat = vi.fn().mockImplementation(
      async (payload: {
        segment_id: string | null
        heartbeat_seq: number
      }) => {
        if (payload.segment_id === null) {
          segmentNumber += 1
          return {
            segment_id: `segment-${segmentNumber}`,
            heartbeat_seq: 0,
            active_seconds: 0,
            restarted: false
          }
        }
        return {
          segment_id: payload.segment_id,
          heartbeat_seq: payload.heartbeat_seq,
          active_seconds: payload.heartbeat_seq * 30,
          restarted: false
        }
      }
    )
    const controller = new ActiveLearningHeartbeatController({ heartbeat })

    controller.touch()
    await vi.advanceTimersByTimeAsync(180_000)
    expect(controller.currentSegmentId()).toBeNull()

    controller.touch()
    await vi.advanceTimersByTimeAsync(0)

    expect(heartbeat).toHaveBeenLastCalledWith({
      segment_id: null,
      heartbeat_seq: 0
    })
    expect(controller.currentSegmentId()).toBe('segment-2')
  })

  it('serializes concurrent flushes to preserve heartbeat ordering', async () => {
    let resolveHeartbeat!: (value: {
      segment_id: string
      heartbeat_seq: number
      active_seconds: number
      restarted: boolean
    }) => void
    const heartbeat = vi
      .fn()
      .mockResolvedValueOnce({
        segment_id: 'segment-1',
        heartbeat_seq: 0,
        active_seconds: 0,
        restarted: false
      })
      .mockImplementationOnce(
        () =>
          new Promise(resolve => {
            resolveHeartbeat = resolve
          })
      )
    const controller = new ActiveLearningHeartbeatController({ heartbeat })

    controller.touch()
    await vi.advanceTimersByTimeAsync(0)
    const first = controller.flush()
    const second = controller.flush()
    resolveHeartbeat({
      segment_id: 'segment-1',
      heartbeat_seq: 1,
      active_seconds: 30,
      restarted: false
    })
    await Promise.all([first, second])

    expect(heartbeat).toHaveBeenCalledTimes(2)
    expect(heartbeat).toHaveBeenLastCalledWith({
      segment_id: 'segment-1',
      heartbeat_seq: 1
    })
  })
})
