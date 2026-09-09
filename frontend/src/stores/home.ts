import { defineStore } from 'pinia'

import { fetchHomeSnapshot } from '@/api/adapters/home'
import { createMockSnapshot, moduleOrder } from '@/data/mock-home'
import type { HomeModule, HomeSnapshot, ModuleId } from '@/api/types'

interface HomeState {
  snapshot: HomeSnapshot
  activeModuleId: ModuleId
  loading: boolean
  loaded: boolean
  error: string
}

export const useHomeStore = defineStore('home', {
  state: (): HomeState => ({
    snapshot: createMockSnapshot(),
    activeModuleId: 'agriculture',
    loading: false,
    loaded: false,
    error: ''
  }),
  getters: {
    modules(state): HomeModule[] {
      return moduleOrder
        .map(id => state.snapshot.modules.find(module => module.id === id))
        .filter((module): module is HomeModule => Boolean(module))
    },
    activeModule(state): HomeModule {
      return (
        state.snapshot.modules.find(module => module.id === state.activeModuleId) ??
        state.snapshot.modules[0]
      )
    },
    liveModuleCount(state): number {
      return state.snapshot.modules.filter(module => module.source === 'live').length
    }
  },
  actions: {
    selectModule(id: ModuleId) {
      this.activeModuleId = id
    },
    async load(force = false) {
      if (this.loading || (this.loaded && !force)) {
        return
      }

      this.loading = true
      this.error = ''

      try {
        this.snapshot = await fetchHomeSnapshot()
      } catch (error) {
        this.snapshot = createMockSnapshot()
        this.error = error instanceof Error ? error.message : '数据加载失败，已切换到示例数据'
      } finally {
        this.loaded = true
        this.loading = false
      }
    }
  }
})
