import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type { HandcraftCraft } from '@/api/types'

import HandcraftInheritanceHomeView from './HandcraftInheritanceHomeView.vue'
import handcraftHomeSource from './HandcraftInheritanceHomeView.vue?raw'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

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

function craft(
  craftKey: string,
  name: string,
  available = true,
  unavailableReason: string | null = null
): HandcraftCraft {
  return {
    craft_key: craftKey,
    name,
    sort_order: 1,
    introduction: `${name}介绍`,
    is_demo: true,
    source_available: available,
    status: available ? 'available' : 'unavailable',
    available,
    unavailable_reason: unavailableReason,
    steps: [],
    material_guide: []
  }
}

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      '/',
      '/login',
      '/register',
      '/student/handcraft-inheritance',
      '/student/handcraft-inheritance/courses',
      '/student/handcraft-inheritance/crafts/:craftKey'
    ].map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}

describe('HandcraftInheritanceHomeView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('shows all four provider crafts and explicit unavailable states', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      crafts: [
        craft('guangxiu', '广绣'),
        craft('chaoshan-woodcarving', '潮汕木雕'),
        craft('shiwan-ceramics', '石湾陶艺'),
        craft(
          'yangjiang-lacquerware',
          '阳江漆器',
          false,
          '来源内容暂不可用'
        )
      ]
    } as never)

    const wrapper = mount(HandcraftInheritanceHomeView, {
      global: {
        plugins: [createPinia(), testRouter()]
      }
    })
    await flushPromises()

    const cards = wrapper.findAll('[data-test="craft-card"]')
    expect(cards).toHaveLength(4)
    expect(cards.map(card => card.get('h2').text())).toEqual([
      '广绣',
      '潮汕木雕',
      '石湾陶艺',
      '阳江漆器'
    ])

    expect(cards[0].get('a').attributes('href')).toBe(
      '/student/handcraft-inheritance/crafts/guangxiu'
    )
    expect(cards[3].find('a').exists()).toBe(false)
    expect(cards[3].text()).toContain('来源内容暂不可用')
    expect(cards[3].text()).toContain('暂不可学习')
  })

  it('keeps a visible learning action on all four available craft cards', async () => {
    mockedApiFetch.mockResolvedValue({
      success: true,
      crafts: [
        craft('guangxiu', '广绣'),
        craft('chaoshan-woodcarving', '潮汕木雕'),
        craft('shiwan-ceramics', '石湾陶艺'),
        craft('yangjiang-lacquerware', '阳江漆器')
      ]
    } as never)

    const wrapper = mount(HandcraftInheritanceHomeView, {
      global: {
        plugins: [createPinia(), testRouter()]
      }
    })
    await flushPromises()

    const actions = wrapper.findAll('[data-test="craft-card-action"]')
    expect(actions).toHaveLength(4)
    expect(actions.map(action => action.text())).toEqual([
      '进入学习',
      '进入学习',
      '进入学习',
      '进入学习'
    ])
    expect(cssRule(handcraftHomeSource, '.craft-card')).toContain(
      'grid-template-rows: minmax(0, 1fr) auto'
    )
    expect(
      cssRule(handcraftHomeSource, '.craft-card__action')
    ).toContain('align-self: end')
  })

  it('declares CJK-safe wrapping for the home introduction and craft copy', () => {
    const intro = cssRule(
      handcraftHomeSource,
      '.handcraft-home__intro p'
    )
    const cardCopy = cssRule(
      handcraftHomeSource,
      '.craft-card__body p'
    )

    expect(intro).toContain('line-break: strict')
    expect(intro).toContain('overflow-wrap: break-word')
    expect(intro).toContain('text-wrap: pretty')
    expect(intro).toContain('word-break: normal')
    expect(intro).not.toContain('overflow-wrap: anywhere')
    expect(cardCopy).toContain('overflow-wrap: break-word')
    expect(cardCopy).toContain('word-break: normal')
    expect(cardCopy).not.toContain('overflow-wrap: anywhere')
    expect(handcraftHomeSource).not.toContain('white-space: nowrap')
    expect(handcraftHomeSource).not.toMatch(/#[0-9a-f]{3,8}|rgba?\(/i)
  })
})
