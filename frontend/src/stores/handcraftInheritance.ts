import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type {
  HandcraftArGuidance,
  HandcraftCraft,
  HandcraftProgress,
  HandcraftStepCompletion,
  HandcraftVideo
} from '@/api/types'

const API_PREFIX = '/api/handcraft-inheritance'

interface HandcraftInheritanceState {
  crafts: HandcraftCraft[]
  activeCraft: HandcraftCraft | null
  materialGuideByCraft: Record<string, HandcraftCraft>
  progressByCraft: Record<string, HandcraftProgress>
  videosByCraft: Record<string, HandcraftVideo[]>
  arGuidance: HandcraftArGuidance | null
  lastStepCompletion: HandcraftStepCompletion | null
  loading: boolean
  completingStep: boolean
  generatingGuidance: boolean
  error: string
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : fallback
}

export const useHandcraftInheritanceStore = defineStore(
  'handcraftInheritance',
  {
    state: (): HandcraftInheritanceState => ({
      crafts: [],
      activeCraft: null,
      materialGuideByCraft: {},
      progressByCraft: {},
      videosByCraft: {},
      arGuidance: null,
      lastStepCompletion: null,
      loading: false,
      completingStep: false,
      generatingGuidance: false,
      error: ''
    }),
    actions: {
      async loadCrafts(): Promise<boolean> {
        this.loading = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            crafts: HandcraftCraft[]
          }>(`${API_PREFIX}/crafts`)
          this.crafts = response.crafts
          return true
        } catch (error) {
          this.error = errorMessage(error, '技艺列表加载失败')
          return false
        } finally {
          this.loading = false
        }
      },
      async loadCraft(craftKey: string): Promise<boolean> {
        this.loading = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            craft: HandcraftCraft
          }>(
            `${API_PREFIX}/crafts/${encodeURIComponent(craftKey)}`
          )
          this.activeCraft = response.craft
          return true
        } catch (error) {
          this.error = errorMessage(error, '技艺详情加载失败')
          return false
        } finally {
          this.loading = false
        }
      },
      async loadProgress(craftKey: string): Promise<boolean> {
        this.loading = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            progress: HandcraftProgress
          }>(
            `${API_PREFIX}/crafts/${encodeURIComponent(craftKey)}/progress`
          )
          this.progressByCraft[craftKey] = response.progress
          return true
        } catch (error) {
          this.error = errorMessage(error, '技艺进度加载失败')
          return false
        } finally {
          this.loading = false
        }
      },
      async completeStep(
        craftKey: string,
        stepNo: number,
        activeSeconds: number,
        eventId: string
      ): Promise<boolean> {
        this.completingStep = true
        this.error = ''
        this.lastStepCompletion = null
        try {
          const response = await apiFetch<{
            success: true
            progress: HandcraftStepCompletion
          }>(
            `${API_PREFIX}/crafts/${encodeURIComponent(craftKey)}/steps/${stepNo}/complete`,
            {
              method: 'POST',
              body: JSON.stringify({
                active_seconds: activeSeconds,
                event_id: eventId
              })
            }
          )
          this.lastStepCompletion = response.progress
          if (response.progress.accepted) {
            this.progressByCraft[craftKey] = response.progress
          }
          return true
        } catch (error) {
          this.error = errorMessage(error, '步骤完成状态保存失败')
          return false
        } finally {
          this.completingStep = false
        }
      },
      async loadMaterialGuide(craftKey: string): Promise<boolean> {
        this.loading = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            craft: HandcraftCraft
          }>(
            `${API_PREFIX}/crafts/${encodeURIComponent(craftKey)}`
          )
          this.materialGuideByCraft[craftKey] = response.craft
          return true
        } catch (error) {
          this.error = errorMessage(error, '材料指南加载失败')
          return false
        } finally {
          this.loading = false
        }
      },
      async loadVideos(craftKey: string): Promise<boolean> {
        this.loading = true
        this.error = ''
        try {
          const response = await apiFetch<{
            success: true
            videos: HandcraftVideo[]
          }>(
            `${API_PREFIX}/videos?craft_key=${encodeURIComponent(craftKey)}`
          )
          this.videosByCraft[craftKey] = response.videos
          return true
        } catch (error) {
          this.error = errorMessage(error, '教学视频加载失败')
          return false
        } finally {
          this.loading = false
        }
      },
      async generateArGuidance(
        craftKey: string,
        projectLabel: string,
        activeSeconds?: number,
        eventId?: string
      ): Promise<boolean> {
        this.generatingGuidance = true
        this.error = ''
        const body: {
          craft_key: string
          project_label: string
          active_seconds?: number
          event_id?: string
        } = {
          craft_key: craftKey,
          project_label: projectLabel
        }
        if (activeSeconds !== undefined) {
          body.active_seconds = activeSeconds
        }
        if (eventId !== undefined) {
          body.event_id = eventId
        }
        try {
          const response = await apiFetch<{
            success: true
            guidance: HandcraftArGuidance
          }>(`${API_PREFIX}/ar-guidance`, {
            method: 'POST',
            body: JSON.stringify(body)
          })
          this.arGuidance = response.guidance
          return true
        } catch (error) {
          this.error = errorMessage(error, 'AI 服务暂时不可用')
          return false
        } finally {
          this.generatingGuidance = false
        }
      }
    }
  }
)
