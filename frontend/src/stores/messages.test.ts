import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'

import { useMessageStore } from './messages'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

describe('useMessageStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('updates the global badge after reading one item', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        unread_private: 2,
        unread_notifications: 1,
        unread_total: 3
      })
      .mockResolvedValueOnce({
        success: true,
        unread_private: 1,
        unread_notifications: 1,
        unread_total: 2
      })

    const store = useMessageStore()
    await store.loadSummary()
    await store.markPrivateRead(7)

    expect(store.summary.unread_total).toBe(2)
  })
})
