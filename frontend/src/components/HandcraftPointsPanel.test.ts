import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type {
  HandcraftLedgerEntry,
  HandcraftPointsAccount
} from '@/api/types'

import HandcraftPointsPanel from './HandcraftPointsPanel.vue'
import handcraftPointsPanelSource from './HandcraftPointsPanel.vue?raw'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const account: HandcraftPointsAccount = {
  user_id: 1,
  balance: 45,
  updated_at: '2026-09-18T10:30:00+08:00',
  awarded_today: 45,
  daily_limit: 60,
  daily_limit_reached: false
}

function ledgerEntry(
  id: number,
  overrides: Partial<HandcraftLedgerEntry> = {}
): HandcraftLedgerEntry {
  return {
    id,
    user_id: 1,
    transaction_type: 'award',
    source_module: 'handcraft',
    source_event_id: `event-${id}`,
    delta: 10,
    balance_after: 45,
    metadata: {},
    created_at: '2026-09-18T10:00:00+08:00',
    ...overrides
  }
}

function cssRule(css: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(
    new RegExp(
      `(?:^|[{}])\\s*[^{}]*?${escaped}[^{}]*?\\s*\\{([\\s\\S]*?)\\}`
    )
  )
  expect(match).not.toBeNull()
  return (match?.[1] ?? '').replace(/\s+/g, ' ').trim()
}

function mountPanel() {
  return mount(HandcraftPointsPanel, {
    global: {
      plugins: [createPinia()]
    }
  })
}

describe('HandcraftPointsPanel', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    window.localStorage.clear()
  })

  it('shows the balance, newest-first ledger and entry types', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/handcraft-inheritance/points') {
        return {
          success: true,
          account: {
            ...account,
            awarded_today: 60,
            daily_limit_reached: true
          }
        } as never
      }
      if (path === '/api/handcraft-inheritance/points/ledger') {
        return {
          success: true,
          ledger: [
            ledgerEntry(2, {
              transaction_type: 'spend',
              source_event_id: 'redemption:12',
              delta: -30,
              balance_after: 20,
              created_at: '2026-09-18T09:00:00+08:00'
            }),
            ledgerEntry(3, {
              transaction_type: 'refund',
              source_event_id: 'redemption:12',
              delta: 30,
              balance_after: 50,
              created_at: '2026-09-18T11:00:00+08:00'
            }),
            ledgerEntry(1, {
              transaction_type: 'expire',
              source_event_id: 'expiry:2025',
              delta: -5,
              balance_after: 15,
              created_at: '2026-09-18T08:00:00+08:00'
            })
          ]
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.get('[data-test="points-balance"]').text()).toContain(
      '45'
    )
    expect(wrapper.get('[data-test="points-balance"]').text()).toContain(
      '积分'
    )

    const entries = wrapper.findAll('[data-test="points-ledger-entry"]')
    expect(entries.map(entry => entry.attributes('data-entry-id'))).toEqual([
      '3',
      '2',
      '1'
    ])
    expect(entries[0].text()).toContain('回退')
    expect(entries[0].text()).toContain('+30')
    expect(entries[0].text()).toContain('余额 50')
    expect(entries[0].text()).toContain('2026-09-18 11:00')
    expect(entries[1].text()).toContain('消耗')
    expect(entries[1].text()).toContain('-30')
    expect(entries[2].text()).toContain('过期')
    expect(entries[2].text()).toContain('-5')
    expect(wrapper.find('[data-test="daily-cap-notice"]').exists()).toBe(true)
  })

  it('shows the exact reached-cap notice once per user and platform day', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/handcraft-inheritance/points') {
        return {
          success: true,
          account: {
            ...account,
            awarded_today: 60,
            daily_limit_reached: true
          }
        } as never
      }
      if (path === '/api/handcraft-inheritance/points/ledger') {
        return { success: true, ledger: [] } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const first = mountPanel()
    await flushPromises()
    expect(first.get('[data-test="daily-cap-notice"]').text()).toBe(
      '今日积分获取已达上限，学习进度将继续累计。'
    )
    first.unmount()

    const repeated = mountPanel()
    await flushPromises()
    expect(
      repeated.find('[data-test="daily-cap-notice"]').exists()
    ).toBe(false)
  })

  it('does not show the notice below the cap', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/handcraft-inheritance/points') {
        return { success: true, account } as never
      }
      if (path === '/api/handcraft-inheritance/points/ledger') {
        return { success: true, ledger: [] } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.find('[data-test="daily-cap-notice"]').exists()).toBe(false)
  })

  it('handles unavailable local storage without breaking the notice', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/handcraft-inheritance/points') {
        return {
          success: true,
          account: {
            ...account,
            awarded_today: 60,
            daily_limit_reached: true
          }
        } as never
      }
      if (path === '/api/handcraft-inheritance/points/ledger') {
        return { success: true, ledger: [] } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    const getItem = vi
      .spyOn(Storage.prototype, 'getItem')
      .mockImplementation(() => {
        throw new Error('storage unavailable')
      })
    const setItem = vi
      .spyOn(Storage.prototype, 'setItem')
      .mockImplementation(() => {
        throw new Error('storage unavailable')
      })

    try {
      const wrapper = mountPanel()
      await flushPromises()
      expect(wrapper.get('[data-test="daily-cap-notice"]').text()).toBe(
        '今日积分获取已达上限，学习进度将继续累计。'
      )
    } finally {
      getItem.mockRestore()
      setItem.mockRestore()
    }
  })

  it('shows loading and an explicit empty state without fabricating entries', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/handcraft-inheritance/points') {
        return {
          success: true,
          account: {
            ...account,
            balance: 0,
            awarded_today: 0,
            daily_limit_reached: false
          }
        } as never
      }
      if (path === '/api/handcraft-inheritance/points/ledger') {
        return { success: true, ledger: [] } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = mountPanel()
    expect(wrapper.get('[data-test="points-loading"]').text()).toContain(
      '正在加载积分'
    )

    await flushPromises()
    expect(wrapper.get('[data-test="points-empty"]').text()).toBe(
      '暂无积分流水'
    )
  })

  it('shows the exact policy-unavailable message', async () => {
    mockedApiFetch.mockRejectedValue(
      new ApiError('积分规则暂不可用，请稍后重试', 503)
    )

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.get('[data-test="points-error"]').text()).toContain(
      '积分规则暂不可用，请稍后重试'
    )
    expect(wrapper.find('[data-test="daily-cap-notice"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="points-ledger-entry"]').exists()).toBe(
      false
    )
  })

  it('keeps CSS tokenized, focus-visible, portrait-ready and CJK-safe', () => {
    expect(handcraftPointsPanelSource).not.toMatch(
      /#[0-9a-f]{3,8}|rgba?\(|hsla?\(|rgb\(24\s+209\s+255/i
    )
    expect(handcraftPointsPanelSource).not.toContain('white-space: nowrap')
    expect(handcraftPointsPanelSource).toContain(
      '@media (max-width: 760px), (orientation: portrait)'
    )
    expect(
      cssRule(
        handcraftPointsPanelSource,
        '.points-panel :is(button, a):focus-visible'
      )
    ).toContain('outline: 2px solid var(--ark-focus)')
    expect(
      cssRule(handcraftPointsPanelSource, '.ledger-entry__detail')
    ).toContain('overflow-wrap: anywhere')
  })
})
