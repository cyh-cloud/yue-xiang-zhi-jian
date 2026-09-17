import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type { SimulationScene, SimulationTraining } from '@/api/types'

interface EcommerceSimulationState {
  scenes: SimulationScene[]
  current: SimulationTraining | null
  history: SimulationTraining[]
  drafts: Record<string, string>
  savedSegments: Record<string, boolean>
  savingSegments: Record<string, boolean>
  loading: boolean
  activeReadRequests: number
  starting: boolean
  openingTraining: boolean
  scoring: boolean
  contextRequestId: number
  error: string
}

const AI_UNAVAILABLE_MESSAGE = 'AI 服务暂时不可用'

function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

function isAiUnavailable(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.status === 503 || error.message === AI_UNAVAILABLE_MESSAGE)
  )
}

function actionErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.message) {
    return error.message
  }
  return fallback
}

function hasPendingMutation(state: {
  starting: boolean
  openingTraining: boolean
  scoring: boolean
  savingSegments: Record<string, boolean>
}): boolean {
  return (
    state.starting ||
    state.openingTraining ||
    state.scoring ||
    Object.values(state.savingSegments).some(Boolean)
  )
}

function segmentState(training: SimulationTraining) {
  return {
    drafts: Object.fromEntries(
      training.segments.map(segment => [segment.key, segment.text])
    ),
    savedSegments: Object.fromEntries(
      training.segments.map(segment => [
        segment.key,
        segment.text.trim().length > 0
      ])
    ),
    savingSegments: Object.fromEntries(
      training.segments.map(segment => [segment.key, false])
    )
  }
}

function replaceHistoryItem(
  history: SimulationTraining[],
  training: SimulationTraining
): SimulationTraining[] {
  const existingIndex = history.findIndex(item => item.id === training.id)
  if (existingIndex === -1) {
    return [training, ...history]
  }

  return history.map(item => (item.id === training.id ? training : item))
}

export const useEcommerceSimulationStore = defineStore(
  'ecommerceSimulation',
  {
    state: (): EcommerceSimulationState => ({
      scenes: [],
      current: null,
      history: [],
      drafts: {},
      savedSegments: {},
      savingSegments: {},
      loading: false,
      activeReadRequests: 0,
      starting: false,
      openingTraining: false,
      scoring: false,
      contextRequestId: 0,
      error: ''
    }),
    getters: {
      canScore(state): boolean {
        if (!state.current || state.current.status !== 'draft') {
          return false
        }

        return (
          state.current.segments.length > 0 &&
          state.current.segments.every(
            segment =>
              Boolean(state.drafts[segment.key]?.trim()) &&
              state.savedSegments[segment.key] === true
          )
        )
      },
      mutationBusy(state): boolean {
        return hasPendingMutation(state)
      },
      isBusy(state): boolean {
        return state.loading || hasPendingMutation(state)
      }
    },
    actions: {
      applyTraining(training: SimulationTraining) {
        const nextState = segmentState(training)
        this.current = training
        this.drafts = nextState.drafts
        this.savedSegments = nextState.savedSegments
        this.savingSegments = nextState.savingSegments
      },
      async loadScenes(): Promise<boolean> {
        this.activeReadRequests += 1
        this.loading = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            scenes: SimulationScene[]
          }>('/api/ecommerce-training/simulations/scenes')
          this.scenes = response.scenes
          return true
        } catch {
          this.error = '模拟训练场景加载失败'
          return false
        } finally {
          this.activeReadRequests = Math.max(
            0,
            this.activeReadRequests - 1
          )
          this.loading = this.activeReadRequests > 0
        }
      },
      async start(sceneKey: string): Promise<boolean> {
        if (this.mutationBusy) {
          return false
        }

        const requestId = ++this.contextRequestId
        this.starting = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            training: SimulationTraining
          }>('/api/ecommerce-training/simulations', {
            method: 'POST',
            body: JSON.stringify({ scene_key: sceneKey })
          })
          if (requestId !== this.contextRequestId) {
            return false
          }
          this.applyTraining(response.training)
          this.history = replaceHistoryItem(this.history, response.training)
          return true
        } catch (error) {
          if (requestId === this.contextRequestId && !isUnauthorized(error)) {
            this.error = actionErrorMessage(error, '模拟训练创建失败')
          }
          return false
        } finally {
          this.starting = false
        }
      },
      async saveSegment(
        segmentKey: string,
        text: string
      ): Promise<boolean> {
        const training = this.current
        if (
          !training ||
          training.status !== 'draft' ||
          this.savedSegments[segmentKey] ||
          this.savingSegments[segmentKey] ||
          this.mutationBusy
        ) {
          return false
        }

        const normalized = text.trim()
        if (!normalized) {
          this.error = '请填写环节话术'
          return false
        }
        if (
          !training.segments.some(segment => segment.key === segmentKey)
        ) {
          return false
        }

        const requestId = this.contextRequestId
        this.savingSegments = {
          ...this.savingSegments,
          [segmentKey]: true
        }
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            training: SimulationTraining
          }>(
            `/api/ecommerce-training/simulations/${training.id}/segments/${segmentKey}`,
            {
              method: 'PUT',
              body: JSON.stringify({ text: normalized })
            }
          )
          if (
            requestId !== this.contextRequestId ||
            this.current?.id !== training.id
          ) {
            return false
          }
          const savedSegment = response.training.segments.find(
            segment => segment.key === segmentKey
          )
          this.current = response.training
          this.drafts = {
            ...this.drafts,
            [segmentKey]: savedSegment?.text ?? normalized
          }
          this.savedSegments = {
            ...this.savedSegments,
            [segmentKey]: Boolean(savedSegment?.text.trim())
          }
          return true
        } catch (error) {
          if (
            requestId === this.contextRequestId &&
            this.current?.id === training.id &&
            !isUnauthorized(error)
          ) {
            this.error = actionErrorMessage(error, '环节话术保存失败')
          }
          return false
        } finally {
          this.savingSegments = {
            ...this.savingSegments,
            [segmentKey]: false
          }
        }
      },
      async score(): Promise<boolean> {
        const training = this.current
        if (!training || !this.canScore || this.mutationBusy) {
          return false
        }

        const requestId = this.contextRequestId
        this.scoring = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            training: SimulationTraining
          }>(
            `/api/ecommerce-training/simulations/${training.id}/score`,
          { method: 'POST' }
          )
          if (
            requestId !== this.contextRequestId ||
            this.current?.id !== training.id
          ) {
            return false
          }
          this.current = response.training
          this.history = replaceHistoryItem(this.history, response.training)
          return true
        } catch (error) {
          if (
            requestId === this.contextRequestId &&
            this.current?.id === training.id &&
            !isUnauthorized(error)
          ) {
            this.error = isAiUnavailable(error)
              ? AI_UNAVAILABLE_MESSAGE
              : actionErrorMessage(error, '评分请求失败')
          }
          return false
        } finally {
          this.scoring = false
        }
      },
      async loadHistory(): Promise<boolean> {
        this.activeReadRequests += 1
        this.loading = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            trainings: SimulationTraining[]
          }>('/api/ecommerce-training/simulations')
          this.history = response.trainings
          return true
        } catch (error) {
          if (!isUnauthorized(error)) {
            this.error = actionErrorMessage(
              error,
              '模拟训练记录加载失败'
            )
          }
          return false
        } finally {
          this.activeReadRequests = Math.max(
            0,
            this.activeReadRequests - 1
          )
          this.loading = this.activeReadRequests > 0
        }
      },
      async openTraining(id: number): Promise<boolean> {
        if (this.mutationBusy) {
          return false
        }

        const requestId = ++this.contextRequestId
        this.openingTraining = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            training: SimulationTraining
          }>(`/api/ecommerce-training/simulations/${id}`)
          if (requestId !== this.contextRequestId) {
            return false
          }
          this.applyTraining(response.training)
          this.history = replaceHistoryItem(this.history, response.training)
          return true
        } catch (error) {
          if (requestId === this.contextRequestId && !isUnauthorized(error)) {
            this.error = actionErrorMessage(
              error,
              '模拟训练记录加载失败'
            )
          }
          return false
        } finally {
          this.openingTraining = false
        }
      },
      clearError() {
        this.error = ''
      }
    }
  }
)
