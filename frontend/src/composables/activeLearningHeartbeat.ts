import { onBeforeUnmount, onMounted } from 'vue'

export interface ActiveLearningHeartbeatPayload {
  segment_id: string | null
  heartbeat_seq: number
}

export interface ActiveLearningHeartbeatResponse {
  segment_id: string
  heartbeat_seq: number
  active_seconds: number
  restarted: boolean
}

interface ActiveLearningHeartbeatOptions {
  heartbeat: (
    payload: ActiveLearningHeartbeatPayload
  ) => Promise<ActiveLearningHeartbeatResponse>
  intervalMs?: number
  idleMs?: number
  onError?: (error: unknown) => void
}

const HEARTBEAT_INTERVAL_MS = 30_000
const IDLE_CUTOFF_MS = 180_000

export class ActiveLearningHeartbeatController {
  private readonly heartbeatRequest: ActiveLearningHeartbeatOptions['heartbeat']
  private readonly intervalMs: number
  private readonly idleMs: number
  private readonly onError?: (error: unknown) => void
  private segmentId: string | null = null
  private heartbeatSeq = 0
  private intervalId: ReturnType<typeof setInterval> | null = null
  private idleId: ReturnType<typeof setTimeout> | null = null
  private inFlight: Promise<string | null> | null = null
  private active = false
  private generation = 0

  constructor(options: ActiveLearningHeartbeatOptions) {
    this.heartbeatRequest = options.heartbeat
    this.intervalMs = options.intervalMs ?? HEARTBEAT_INTERVAL_MS
    this.idleMs = options.idleMs ?? IDLE_CUTOFF_MS
    this.onError = options.onError
  }

  touch(): void {
    this.active = true
    this.clearIdleTimer()
    this.idleId = setTimeout(() => this.stop(), this.idleMs)
    if (this.intervalId === null) {
      this.intervalId = setInterval(() => {
        void this.flush()
      }, this.intervalMs)
      void this.flush()
    }
  }

  flush(): Promise<string | null> {
    if (!this.active) {
      return Promise.resolve(null)
    }
    if (this.inFlight) {
      return this.inFlight
    }
    const request = this.sendHeartbeat()
    this.inFlight = request
    void request.finally(() => {
      if (this.inFlight === request) {
        this.inFlight = null
      }
    })
    return request
  }

  currentSegmentId(): string | null {
    return this.segmentId
  }

  reset(): void {
    this.generation += 1
    this.active = false
    this.clearTimers()
    this.segmentId = null
    this.heartbeatSeq = 0
    this.inFlight = null
  }

  stop(): void {
    this.reset()
  }

  private async sendHeartbeat(): Promise<string | null> {
    const generation = this.generation
    const payload: ActiveLearningHeartbeatPayload = {
      segment_id: this.segmentId,
      heartbeat_seq: this.segmentId ? this.heartbeatSeq + 1 : 0
    }
    try {
      const response = await this.heartbeatRequest(payload)
      if (generation !== this.generation) {
        return null
      }
      this.segmentId = response.segment_id
      this.heartbeatSeq = response.heartbeat_seq
      return response.segment_id
    } catch (error) {
      this.onError?.(error)
      return this.segmentId
    }
  }

  private clearTimers(): void {
    if (this.intervalId !== null) {
      clearInterval(this.intervalId)
      this.intervalId = null
    }
    this.clearIdleTimer()
  }

  private clearIdleTimer(): void {
    if (this.idleId !== null) {
      clearTimeout(this.idleId)
      this.idleId = null
    }
  }
}

export function useActiveLearningHeartbeat(
  heartbeat: ActiveLearningHeartbeatOptions['heartbeat'],
  options: Omit<ActiveLearningHeartbeatOptions, 'heartbeat'> = {}
) {
  const controller = new ActiveLearningHeartbeatController({
    heartbeat,
    ...options
  })

  function handleVisibilityChange() {
    if (document.visibilityState === 'hidden') {
      void controller.flush()
      controller.stop()
    }
  }

  onMounted(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    controller.stop()
  })

  return {
    touch: () => controller.touch(),
    flush: () => controller.flush(),
    currentSegmentId: () => controller.currentSegmentId(),
    reset: () => controller.reset(),
    stop: () => controller.stop()
  }
}
