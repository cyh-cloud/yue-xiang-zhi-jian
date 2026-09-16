import { defineStore } from 'pinia'

import { apiFetch } from '@/api/client'
import type { CopyTrainingSession } from '@/api/types'

export interface CopyTrainingCatalog {
  product_types: string[]
  scenes: string[]
  defect_categories: string[]
}

interface EcommerceCopyTrainingState {
  catalog: CopyTrainingCatalog
  productType: string
  scene: string
  current: CopyTrainingSession | null
  sessionHistory: CopyTrainingSession[]
  critiqueDraft: string
  optimizedPrompt: string
  loading: boolean
  creating: boolean
  submittingCritique: boolean
  generatingCopy: boolean
  generatingOptimization: boolean
  openingSession: boolean
  error: string
}

const AI_UNAVAILABLE_MESSAGE = 'AI 服务暂时不可用'
const API_PREFIX = '/api/ecommerce-training/copy-training'

function emptyCatalog(): CopyTrainingCatalog {
  return {
    product_types: [],
    scenes: [],
    defect_categories: []
  }
}

function replaceHistoryItem(
  history: CopyTrainingSession[],
  session: CopyTrainingSession
): CopyTrainingSession[] {
  return [
    session,
    ...history.filter(item => item.id !== session.id)
  ].sort((left, right) => right.id - left.id)
}

export const useEcommerceCopyTrainingStore = defineStore(
  'ecommerceCopyTraining',
  {
    state: (): EcommerceCopyTrainingState => ({
      catalog: emptyCatalog(),
      productType: '',
      scene: '',
      current: null,
      sessionHistory: [],
      critiqueDraft: '',
      optimizedPrompt: '',
      loading: false,
      creating: false,
      submittingCritique: false,
      generatingCopy: false,
      generatingOptimization: false,
      openingSession: false,
      error: ''
    }),
    getters: {
      history(state): CopyTrainingSession[] {
        return state.sessionHistory
      },
      isBusy(state): boolean {
        return (
          state.loading ||
          state.creating ||
          state.submittingCritique ||
          state.generatingCopy ||
          state.generatingOptimization ||
          state.openingSession
        )
      },
      canStart(state): boolean {
        return Boolean(
          state.productType.trim() &&
          state.scene.trim() &&
          !this.isBusy
        )
      },
      canSubmitCritique(state): boolean {
        return Boolean(
          state.current?.status === 'case_ready' &&
          state.critiqueDraft.trim() &&
          !this.isBusy
        )
      },
      canGenerateCopy(state): boolean {
        return Boolean(
          state.current?.status === 'critique_ready' &&
          state.current.reference &&
          state.optimizedPrompt.trim() &&
          !this.isBusy
        )
      },
      canGenerateOptimization(state): boolean {
        return Boolean(
          state.current?.status === 'copy_ready' &&
          state.current.optimized_prompt &&
          state.current.revised_copy &&
          !this.isBusy
        )
      }
    },
    actions: {
      applySession(session: CopyTrainingSession) {
        this.current = session
        this.sessionHistory = replaceHistoryItem(
          this.sessionHistory,
          session
        )
        if (session.learner_critique) {
          this.critiqueDraft = session.learner_critique
        }
        if (session.optimized_prompt) {
          this.optimizedPrompt = session.optimized_prompt
        }
      },
      async loadCatalog(): Promise<boolean> {
        this.loading = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            catalog: CopyTrainingCatalog
          }>(`${API_PREFIX}/catalog`)
          this.catalog = response.catalog
          if (!this.productType && response.catalog.product_types.length) {
            this.productType = response.catalog.product_types[0]
          }
          if (!this.scene && response.catalog.scenes.length) {
            this.scene = response.catalog.scenes[0]
          }
          return true
        } catch {
          this.error = '文案训练配置加载失败'
          return false
        } finally {
          this.loading = false
        }
      },
      async create(
        productType: string,
        scene: string
      ): Promise<boolean> {
        const normalizedProductType = productType.trim()
        const normalizedScene = scene.trim()
        this.productType = normalizedProductType
        this.scene = normalizedScene

        if (!normalizedProductType || !normalizedScene) {
          this.error = '请选择商品类型和训练场景'
          return false
        }
        if (this.isBusy) {
          return false
        }

        this.creating = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            session: CopyTrainingSession
          }>(API_PREFIX, {
            method: 'POST',
            body: JSON.stringify({
              product_type: normalizedProductType,
              scene: normalizedScene
            })
          })
          this.critiqueDraft = ''
          this.optimizedPrompt = ''
          this.applySession(response.session)
          return true
        } catch {
          this.error = AI_UNAVAILABLE_MESSAGE
          return false
        } finally {
          this.creating = false
        }
      },
      async submitCritique(text: string): Promise<boolean> {
        this.critiqueDraft = text
        const session = this.current
        if (!session || session.status !== 'case_ready') {
          return false
        }

        const normalized = text.trim()
        if (!normalized) {
          this.error = '请填写学员评判'
          return false
        }
        if (this.isBusy) {
          return false
        }

        this.submittingCritique = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            session: CopyTrainingSession
          }>(`${API_PREFIX}/${session.id}/critique`, {
            method: 'POST',
            body: JSON.stringify({ critique: normalized })
          })
          this.applySession(response.session)
          return true
        } catch {
          this.error = AI_UNAVAILABLE_MESSAGE
          return false
        } finally {
          this.submittingCritique = false
        }
      },
      async generateCopy(prompt: string): Promise<boolean> {
        this.optimizedPrompt = prompt
        const session = this.current
        if (
          !session ||
          session.status !== 'critique_ready' ||
          !session.reference
        ) {
          return false
        }

        const normalized = prompt.trim()
        if (!normalized) {
          this.error = '请填写优化提示词'
          return false
        }
        if (this.isBusy) {
          return false
        }

        this.generatingCopy = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            session: CopyTrainingSession
          }>(`${API_PREFIX}/${session.id}/copy`, {
            method: 'POST',
            body: JSON.stringify({
              optimized_prompt: normalized
            })
          })
          this.applySession(response.session)
          return true
        } catch {
          this.error = AI_UNAVAILABLE_MESSAGE
          return false
        } finally {
          this.generatingCopy = false
        }
      },
      async generateOptimization(): Promise<boolean> {
        const session = this.current
        if (
          !session ||
          session.status !== 'copy_ready' ||
          !session.optimized_prompt ||
          !session.revised_copy
        ) {
          return false
        }
        if (this.isBusy) {
          return false
        }

        this.generatingOptimization = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            session: CopyTrainingSession
          }>(`${API_PREFIX}/${session.id}/optimization`, {
            method: 'POST'
          })
          this.applySession(response.session)
          return true
        } catch {
          this.error = AI_UNAVAILABLE_MESSAGE
          return false
        } finally {
          this.generatingOptimization = false
        }
      },
      async loadHistory(): Promise<boolean> {
        this.loading = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            sessions: CopyTrainingSession[]
          }>(API_PREFIX)
          this.sessionHistory = response.sessions
          return true
        } catch {
          this.error = '文案训练记录加载失败'
          return false
        } finally {
          this.loading = false
        }
      },
      async openSession(id: number): Promise<boolean> {
        if (this.isBusy) {
          return false
        }

        this.openingSession = true
        this.error = ''

        try {
          const response = await apiFetch<{
            success: true
            session: CopyTrainingSession
          }>(`${API_PREFIX}/${id}`)
          this.productType = response.session.product_type
          this.scene = response.session.scene
          this.critiqueDraft = response.session.learner_critique ?? ''
          this.optimizedPrompt = response.session.optimized_prompt ?? ''
          this.applySession(response.session)
          return true
        } catch {
          this.error = '文案训练记录加载失败'
          return false
        } finally {
          this.openingSession = false
        }
      },
      clearError() {
        this.error = ''
      }
    }
  }
)
