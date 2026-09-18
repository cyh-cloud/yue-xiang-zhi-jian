import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'

import { useHandcraftPointsStore } from './handcraftPoints'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

describe('handcraftPoints store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('loads the account and newest-first ledger without fabricating values', async () => {
    const ledger = [
      {
        id: 3,
        user_id: 1,
        transaction_type: 'award',
        source_module: 'handcraft',
        source_event_id: 'guangxiu|1:step-1',
        delta: 10,
        balance_after: 40,
        metadata: { learning_source_key: 'guangxiu' },
        created_at: '2026-09-18T10:00:00+08:00'
      },
      {
        id: 2,
        user_id: 1,
        transaction_type: 'spend',
        source_module: 'handcraft',
        source_event_id: 'redemption:request-1',
        delta: -30,
        balance_after: 30,
        metadata: {},
        created_at: '2026-09-18T09:00:00+08:00'
      }
    ]
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        account: {
          user_id: 1,
          balance: 40,
          updated_at: null,
          awarded_today: 40,
          daily_limit: 60,
          daily_limit_reached: false
        }
      } as never)
      .mockResolvedValueOnce({ success: true, ledger } as never)
    const store = useHandcraftPointsStore()

    expect(await store.loadAccount()).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/handcraft-inheritance/points'
    )
    expect(store.account?.balance).toBe(40)
    expect(store.account?.updated_at).toBeNull()
    expect(store.account?.awarded_today).toBe(40)
    expect(store.account?.daily_limit).toBe(60)
    expect(store.account?.daily_limit_reached).toBe(false)

    expect(await store.loadLedger()).toBe(true)
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/handcraft-inheritance/points/ledger'
    )
    expect(store.ledger.map(entry => entry.id)).toEqual([3, 2])
  })
})
