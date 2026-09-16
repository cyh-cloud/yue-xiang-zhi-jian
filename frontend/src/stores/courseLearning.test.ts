import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'

import { useAgriCoursesStore } from './agriCourses'
import { useCourseLearningStore } from './courseLearning'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

describe('courseLearning store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('switches course endpoints and direction without creating another store', async () => {
    const store = useCourseLearningStore()
    store.configure('/api/ecommerce-training', 'ecommerce')
    mockedApiFetch.mockResolvedValueOnce({ success: true, courses: [] })
    await store.loadCourses()
    expect(apiFetch).toHaveBeenCalledWith('/api/ecommerce-training/courses')
    expect(store.direction).toBe('ecommerce')
    expect(store.apiPrefix).toBe('/api/ecommerce-training')
  })

  it('keeps agriculture defaults for the legacy store', async () => {
    const store = useAgriCoursesStore()
    mockedApiFetch.mockResolvedValueOnce({ success: true, courses: [] })
    await store.loadCourses()
    expect(apiFetch).toHaveBeenCalledWith('/api/agri-skills/courses')
  })
})
