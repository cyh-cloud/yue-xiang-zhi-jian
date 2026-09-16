import { defineStore } from 'pinia'

import { apiFetch } from '@/api/client'
import type { SimulationScene, SimulationTraining } from '@/api/types'

interface EcommerceSimulationState {
  scenes: SimulationScene[]
  current: SimulationTraining | null
  history: SimulationTraining[]
  drafts: Record<string, string>
  savedSegments: Record<string, boolean>
  savingSegments: Record<string, boolean>
  loading: boolean
  starting: boolean
  scoring: boolean
  error: string
}

const AI_UNAVAILABLE_MESSAGE = 'AI 服务暂时不可用'

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
      starting: false,
      scoring: false,
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
      isBusy(state): boolean {
        return (
          state.loading ||
          state.starting ||
          state.scoring ||
          Object.values(state.savingSegments).some(Boolean)
        )
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
          this.loading = false
        }
      },
      async start(sceneKey: string): Promise<boolean> {
        if (this.starting) {
          return false
        }

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
          this.applyTraining(response.training)
          this.history = replaceHistoryItem(this.history, response.training)
          return true
        } catch {
          this.error = '模拟训练创建失败'
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
          this.savingSegments[segmentKey]
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
        } catch {
          this.error = '环节话术保存失败'
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
        if (!training || !this.canScore || this.scoring) {
          return false
        }

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
          this.current = response.training
          this.history = replaceHistoryItem(this.history, response.training)
          return true
        } catch {
          this.error = AI_UNAVAILABLE_MESSAGE
          return false
        } finally {
          this.scoring = false
        }
      },
      async loadHistory(): Promise<boolean> {
        this.loading = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            trainings: SimulationTraining[]
          }>('/api/ecommerce-training/simulations')
          this.history = response.trainings
          return true
        } catch {
          this.error = '模拟训练记录加载失败'
          return false
        } finally {
          this.loading = false
        }
      },
      async openTraining(id: number): Promise<boolean> {
        this.loading = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            training: SimulationTraining
          }>(`/api/ecommerce-training/simulations/${id}`)
          this.applyTraining(response.training)
          this.history = replaceHistoryItem(this.history, response.training)
          return true
        } catch {
          this.error = '模拟训练记录加载失败'
          return false
        } finally {
          this.loading = false
        }
      },
      clearError() {
        this.error = ''
      }
    }
  }
)
