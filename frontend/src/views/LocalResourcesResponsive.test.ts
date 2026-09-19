import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick, type Component } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  LocalResourceCase,
  LocalResourceCaseDetail,
  LocalResourceNews,
  LocalResourcePolicy,
  PolicyCategorySubscription
} from '@/api/types'
import { useDialectAssistantStore } from '@/stores/dialectAssistant'
import { useLocalResourcesStore } from '@/stores/localResources'

import DialectAssistantView from './DialectAssistantView.vue'
import LocalResourceCaseDetailView from './LocalResourceCaseDetailView.vue'
import LocalResourceCasesView from './LocalResourceCasesView.vue'
import LocalResourceNewsDetailView from './LocalResourceNewsDetailView.vue'
import LocalResourceNewsView from './LocalResourceNewsView.vue'
import LocalResourcePoliciesView from './LocalResourcePoliciesView.vue'
import LocalResourcePolicyDetailView from './LocalResourcePolicyDetailView.vue'
import LocalResourcesHomeView from './LocalResourcesHomeView.vue'
import dialectAssistantSource from './DialectAssistantView.vue?raw'
import localResourceCaseDetailSource from './LocalResourceCaseDetailView.vue?raw'
import localResourceCasesSource from './LocalResourceCasesView.vue?raw'
import localResourceNewsDetailSource from './LocalResourceNewsDetailView.vue?raw'
import localResourceNewsSource from './LocalResourceNewsView.vue?raw'
import localResourcePoliciesSource from './LocalResourcePoliciesView.vue?raw'
import localResourcePolicyDetailSource from './LocalResourcePolicyDetailView.vue?raw'
import localResourcesHomeSource from './LocalResourcesHomeView.vue?raw'

const widths = [320, 375, 1280] as const
const views = [
  ['home', LocalResourcesHomeView],
  ['dialect', DialectAssistantView],
  ['cases', LocalResourceCasesView],
  ['case-detail', LocalResourceCaseDetailView],
  ['policies', LocalResourcePoliciesView],
  ['policy-detail', LocalResourcePolicyDetailView],
  ['news', LocalResourceNewsView],
  ['news-detail', LocalResourceNewsDetailView]
] as const

type ViewName = (typeof views)[number][0]
type PiniaInstance = ReturnType<typeof createPinia>

const viewPaths: Record<ViewName, string> = {
  home: '/student/local-resources',
  dialect: '/student/local-resources/dialect',
  cases: '/student/local-resources/cases',
  'case-detail': '/student/local-resources/cases/case-1',
  policies: '/student/local-resources/policies',
  'policy-detail': '/student/local-resources/policies/policy-1',
  news: '/student/local-resources/news',
  'news-detail': '/student/local-resources/news/news-1'
}

const rootSelectors: Record<ViewName, string> = {
  home: '.local-resources-home',
  dialect: '.dialect-assistant',
  cases: '.local-resource-cases',
  'case-detail': '.local-resource-case-detail',
  policies: '.local-resource-policies',
  'policy-detail': '.local-resource-policy-detail',
  news: '.local-resource-news',
  'news-detail': '.local-resource-news-detail'
}

const viewSources: Record<ViewName, string> = {
  home: localResourcesHomeSource,
  dialect: dialectAssistantSource,
  cases: localResourceCasesSource,
  'case-detail': localResourceCaseDetailSource,
  policies: localResourcePoliciesSource,
  'policy-detail': localResourcePolicyDetailSource,
  news: localResourceNewsSource,
  'news-detail': localResourceNewsDetailSource
}

const longChinese =
  '本地资源页面需要清晰呈现完整的政策背景、办理条件、材料清单、时间安排和咨询渠道，同时保证较长中文段落能够在窄屏设备上自然换行，避免横向滚动、词语被生硬拆开以及最后一行只剩单个汉字。'.repeat(
    3
  )

const semanticPolicyContent =
  '本地申请补贴时，请先准备材料。' + longChinese

const caseSummary: LocalResourceCase = {
  id: 'case-1',
  title: longChinese,
  summary: longChinese,
  published_at: '2026-09-19T10:00:00+08:00',
  updated_at: '2026-09-19T10:00:00+08:00',
  is_demo: true
}

const caseDetail: LocalResourceCaseDetail = {
  ...caseSummary,
  background: longChinese,
  journey: longChinese,
  lessons: longChinese
}

const policyFixture: LocalResourcePolicy = {
  id: 'policy-1',
  title: longChinese,
  content: semanticPolicyContent,
  category_code: 'entrepreneurship',
  category_label: '创业支持',
  published_at: '2026-09-19T10:00:00+08:00',
  updated_at: '2026-09-19T10:00:00+08:00',
  version: 1
}

const newsFixture: LocalResourceNews = {
  id: 'news-1',
  title: longChinese,
  content: longChinese,
  category_code: 'news',
  category_label: '新闻',
  published_at: '2026-09-19T10:00:00+08:00',
  updated_at: '2026-09-19T10:00:00+08:00',
  version: 1
}

const policyCategories: PolicyCategorySubscription[] = [
  {
    code: 'subsidy',
    label: '补贴',
    subscribed: false,
    recommended: false
  },
  {
    code: 'ecommerce',
    label: '电商',
    subscribed: true,
    recommended: false
  },
  {
    code: 'heritage',
    label: '非遗',
    subscribed: false,
    recommended: false
  },
  {
    code: 'training',
    label: '培训',
    subscribed: false,
    recommended: false
  },
  {
    code: 'certification',
    label: '认证',
    subscribed: false,
    recommended: false
  },
  {
    code: 'general',
    label: '综合',
    subscribed: false,
    recommended: false
  },
  {
    code: 'entrepreneurship',
    label: '创业支持',
    subscribed: false,
    recommended: true
  }
]

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: Object.values(viewPaths).map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}

function prepareView(name: ViewName, pinia: PiniaInstance) {
  const store = useLocalResourcesStore(pinia)

  if (name === 'dialect') {
    const dialectStore = useDialectAssistantStore(pinia)
    dialectStore.recognizedText = longChinese
    dialectStore.audioUrl = 'data:audio/wav;base64,UklGRg=='
    dialectStore.lastTurn = {
      id: 'dialect-1',
      dialect_code: 'yue',
      dialect_label: '粤语',
      recognized_text: longChinese,
      dialect_answer: longChinese,
      mandarin_answer: longChinese,
      status: 'completed',
      created_at: '2026-09-19T10:00:00+08:00'
    }
  }

  if (name === 'cases') {
    store.cases = [caseSummary]
    vi.spyOn(store, 'loadCases').mockResolvedValue(true)
  }

  if (name === 'case-detail') {
    store.caseDetail = caseDetail
    vi.spyOn(store, 'openCase').mockResolvedValue(true)
  }

  if (name === 'policies') {
    store.policies = [policyFixture]
    store.subscriptions = {
      categories: policyCategories,
      recommended_category_codes: ['entrepreneurship']
    }
    vi.spyOn(store, 'loadSubscriptions').mockResolvedValue(true)
    vi.spyOn(store, 'loadPolicies').mockResolvedValue(true)
    vi.spyOn(store, 'subscribePolicyCategory').mockResolvedValue(true)
    vi.spyOn(store, 'unsubscribePolicyCategory').mockResolvedValue(true)
  }

  if (name === 'policy-detail') {
    store.policyDetail = policyFixture
    vi.spyOn(store, 'openPolicy').mockResolvedValue(true)
    vi.spyOn(store, 'recordPolicyView').mockResolvedValue(undefined)
  }

  if (name === 'news') {
    store.news = [newsFixture]
    vi.spyOn(store, 'loadNews').mockResolvedValue(true)
  }

  if (name === 'news-detail') {
    store.newsDetail = newsFixture
    vi.spyOn(store, 'openNews').mockResolvedValue(true)
    vi.spyOn(store, 'recordNewsView').mockResolvedValue(undefined)
  }
}

async function mountView(
  name: ViewName,
  component: Component,
  width: number
) {
  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    value: width
  })

  const pinia = createPinia()
  setActivePinia(pinia)
  prepareView(name, pinia)

  const router = testRouter()
  await router.push(viewPaths[name])
  await router.isReady()

  const wrapper = mount(component, {
    attachTo: document.body,
    global: {
      plugins: [pinia, router],
      stubs: {
        AppHeader: true,
        LocalResourcesNav: true
      }
    }
  })

  await flushPromises()
  await nextTick()
  return wrapper
}

function cssRule(css: string, selector: string): string {
  const styleBlocks = [
    ...css.matchAll(/<style(?:\s[^>]*)?>([\s\S]*?)<\/style>/g)
  ]
    .map(match => match[1] ?? '')
    .join('\n')
  const declarations: string[] = []
  const rulePattern = /([^{}]+)\{([^{}]*)\}/g

  for (const match of styleBlocks.matchAll(rulePattern)) {
    const selectors = (match[1] ?? '')
      .split(',')
      .map(value => value.trim())
    if (selectors.includes(selector)) {
      declarations.push(match[2] ?? '')
    }
  }

  expect(
    declarations,
    `Missing CSS rule for ${selector}`
  ).not.toHaveLength(0)
  return declarations.join('; ').replace(/\s+/g, ' ').trim()
}

function declaredPixels(rule: string, property: string): number | null {
  const match = rule.match(
    new RegExp(`(?:^|;)\\s*${property}:\\s*(\\d+(?:\\.\\d+)?)px(?:;|$)`)
  )
  return match ? Number(match[1]) : null
}

function expectCjkWrapping(
  source: string,
  selector: string,
  label: string
): void {
  const rule = cssRule(source, selector)
  expect(rule, `${label} line-break`).toContain('line-break: strict')
  expect(rule, `${label} overflow-wrap`).toContain(
    'overflow-wrap: anywhere'
  )
  expect(rule, `${label} text-wrap`).toContain('text-wrap: pretty')
  expect(rule, `${label} word-break`).toContain('word-break: keep-all')
  expect(rule, `${label} break-all`).not.toContain('word-break: break-all')
}

function labelText(label: HTMLLabelElement): string {
  const clone = label.cloneNode(true) as HTMLLabelElement
  for (const control of clone.querySelectorAll(
    'button, select, textarea, audio'
  )) {
    control.remove()
  }
  return clone.textContent?.replace(/\s+/g, ' ').trim() ?? ''
}

function explicitAccessibleName(element: Element): string {
  const ariaLabel = element.getAttribute('aria-label')?.trim()
  if (ariaLabel) {
    return ariaLabel
  }

  const labelledBy = element.getAttribute('aria-labelledby')
  if (labelledBy) {
    const label = labelledBy
      .split(/\s+/)
      .map(id => element.ownerDocument.getElementById(id)?.textContent ?? '')
      .join(' ')
      .trim()
    if (label) {
      return label
    }
  }

  const id = element.getAttribute('id')
  if (id) {
    const label = element.ownerDocument.querySelector(`label[for="${id}"]`)
    const text =
      label instanceof HTMLLabelElement ? labelText(label) : ''
    if (text) {
      return text
    }
  }

  const wrappingLabel = element.closest('label')
  return wrappingLabel instanceof HTMLLabelElement
    ? labelText(wrappingLabel)
    : ''
}

function accessibleName(element: Element): string {
  const explicitName = explicitAccessibleName(element)
  if (explicitName) {
    return explicitName
  }

  return element.tagName.toLowerCase() === 'button'
    ? element.textContent?.trim() ?? ''
    : ''
}

const expectedControlCounts: Record<ViewName, number> = {
  home: 0,
  dialect: 5,
  cases: 0,
  'case-detail': 0,
  policies: 14,
  'policy-detail': 0,
  news: 3,
  'news-detail': 0
}

const minimumTargets = [
  {
    label: 'dialect selector',
    source: dialectAssistantSource,
    selector: '.dialect-field select',
    pixels: 44
  },
  {
    label: 'dialect textarea',
    source: dialectAssistantSource,
    selector: '.dialect-field textarea',
    pixels: 44
  },
  {
    label: 'dialect submit',
    source: dialectAssistantSource,
    selector: '.dialect-form__submit',
    pixels: 44
  },
  {
    label: 'dialect audio',
    source: dialectAssistantSource,
    selector: '.dialect-answer audio',
    pixels: 44
  },
  {
    label: 'policy category selector',
    source: localResourcePoliciesSource,
    selector: '.local-resource-policies__category-select',
    pixels: 44
  },
  {
    label: 'policy subscription toggle',
    source: localResourcePoliciesSource,
    selector: '.local-resource-policies__subscription-toggle',
    pixels: 44
  },
  {
    label: 'news category selector',
    source: localResourceNewsSource,
    selector: '.local-resource-news__category',
    pixels: 44
  }
] as const

const longCopyContracts = [
  {
    label: 'home heading',
    source: localResourcesHomeSource,
    selector: '.local-resources-home__heading p'
  },
  {
    label: 'dialect heading',
    source: dialectAssistantSource,
    selector: '.dialect-assistant__heading p'
  },
  {
    label: 'dialect textarea',
    source: dialectAssistantSource,
    selector: '.dialect-field textarea'
  },
  {
    label: 'dialect answer',
    source: dialectAssistantSource,
    selector: '.dialect-answer p'
  },
  {
    label: 'cases heading',
    source: localResourceCasesSource,
    selector: '.local-resource-cases__heading p'
  },
  {
    label: 'cases summary',
    source: localResourceCasesSource,
    selector: '.local-resource-cases__copy > span:last-child'
  },
  {
    label: 'case detail summary',
    source: localResourceCaseDetailSource,
    selector: '.local-resource-case-detail__heading p'
  },
  {
    label: 'case detail body',
    source: localResourceCaseDetailSource,
    selector: '.local-resource-case-detail__section p'
  },
  {
    label: 'policies heading',
    source: localResourcePoliciesSource,
    selector: '.local-resource-policies__heading p'
  },
  {
    label: 'policies body',
    source: localResourcePoliciesSource,
    selector: '.local-resource-policies__copy span'
  },
  {
    label: 'policy detail body',
    source: localResourcePolicyDetailSource,
    selector: '.local-resource-policy-detail__content > p:first-child'
  },
  {
    label: 'news heading',
    source: localResourceNewsSource,
    selector: '.local-resource-news__heading p'
  },
  {
    label: 'news body',
    source: localResourceNewsSource,
    selector: '.local-resource-news__copy span'
  },
  {
    label: 'news detail body',
    source: localResourceNewsDetailSource,
    selector: '.local-resource-news-detail__content > p:first-child'
  }
] as const

describe('local-resources responsive and accessibility acceptance', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  it('resolves accessible names by control type and wrapped labels', () => {
    document.body.innerHTML = `
      <select id="bare-select">
        <option>补贴</option>
      </select>
      <label>
        识别文本
        <textarea id="wrapped-textarea"></textarea>
      </label>
      <label>
        方言
        <select id="wrapped-select">
          <option>粤语</option>
        </select>
      </label>
      <button type="button">提交问题</button>
    `

    expect(
      accessibleName(document.querySelector('#bare-select') as Element)
    ).toBe('')
    expect(
      accessibleName(document.querySelector('#wrapped-textarea') as Element)
    ).toBe('识别文本')
    expect(
      accessibleName(document.querySelector('#wrapped-select') as Element)
    ).toBe('方言')
    expect(
      accessibleName(document.querySelector('button') as Element)
    ).toBe('提交问题')
  })

  for (const width of widths) {
    it(`keeps ${width}px free of horizontal overflow`, async () => {
      for (const [name, component] of views) {
        const wrapper = await mountView(name, component, width)

        expect(
          document.documentElement.scrollWidth,
          `${name} document overflow at ${width}px`
        ).toBeLessThanOrEqual(width)
        expect(
          document.body.scrollWidth,
          `${name} body overflow at ${width}px`
        ).toBeLessThanOrEqual(width)

        const root = wrapper.get(rootSelectors[name]).element
        expect(
          root.scrollWidth,
          `${name} root overflow at ${width}px`
        ).toBeLessThanOrEqual(width)

        const rootRule = cssRule(
          viewSources[name],
          rootSelectors[name]
        )
        expect(rootRule, `${name} containment`).toContain('min-width: 0')
        expect(rootRule, `${name} horizontal clipping`).toContain(
          'overflow-x: clip'
        )

        wrapper.unmount()
      }
    })

    it(`keeps named, target-sized controls at ${width}px`, async () => {
      for (const [name, component] of views) {
        const wrapper = await mountView(name, component, width)
        const controls = wrapper.findAll(
          'button, select, textarea, audio[controls]'
        )

        expect(
          controls,
          `${name} control count at ${width}px`
        ).toHaveLength(expectedControlCounts[name])

        for (const control of controls) {
          expect(
            accessibleName(control.element),
            `${name} control without accessible name: ${control.html()}`
          ).not.toBe('')
        }

        if (name === 'dialect') {
          const voiceEntry = wrapper.get(
            '[data-test="dialect-voice-button"]'
          )
          const voiceTarget = voiceEntry.get(
            'button.voice-input__button'
          )
          expect(voiceEntry.get('strong').text()).toBe('语音提问')
          expect(voiceEntry.get('strong').isVisible()).toBe(true)
          expect(voiceTarget.element.closest(
            '[data-test="dialect-voice-button"]'
          )).toBe(voiceEntry.element)

          const voiceRule = cssRule(
            dialectAssistantSource,
            '.dialect-voice :deep(.voice-input__button)'
          )
          expect(
            declaredPixels(voiceRule, 'width'),
            'dialect voice target width'
          ).toBeGreaterThanOrEqual(64)
          expect(
            declaredPixels(voiceRule, 'height'),
            'dialect voice target height'
          ).toBeGreaterThanOrEqual(64)
        }

        if (name === 'policy-detail') {
          expect(wrapper.text()).not.toContain('浏览量：')
          expect(wrapper.text()).not.toContain('点击量：')
          expect(wrapper.text()).not.toMatch(
            /(?:浏览量|点击量)\s*[：:]?\s*\d+/
          )
          expect(
            wrapper.find('[data-test="policy-view-count"]').exists()
          ).toBe(false)
        }

        wrapper.unmount()
      }
    })
  }

  it.each(minimumTargets)(
    'declares the $label target at $pixels px or larger',
    contract => {
      const rule = cssRule(contract.source, contract.selector)
      const minimumHeight = declaredPixels(rule, 'min-height')
      expect(
        minimumHeight,
        `${contract.label} minimum height is missing`
      ).not.toBeNull()
      expect(minimumHeight ?? 0).toBeGreaterThanOrEqual(contract.pixels)
    }
  )

  it('keeps long Chinese copy on structural anti-orphan wrapping rules', () => {
    expect(longChinese.length).toBeGreaterThan(120)

    for (const contract of longCopyContracts) {
      expectCjkWrapping(
        contract.source,
        contract.selector,
        contract.label
      )
    }
  })

  it('keeps policy words intact with semantic nowrap segments', async () => {
    const wrapper = await mountView(
      'policy-detail',
      LocalResourcePolicyDetailView,
      320
    )
    const body = wrapper.get('[data-test="policy-body"]')
    const semanticText = body.get(
      '[data-test="semantic-chinese-text"]'
    )
    const words = semanticText
      .findAll('[data-segment="word"]')
      .map(segment => segment.text())

    expect(body.text()).toBe(semanticPolicyContent)
    expect(words).toEqual(expect.arrayContaining(['本地', '申请', '补贴']))

    wrapper.unmount()
  })

  it('keeps every 006 view on light tokens without unsupported decoration', () => {
    for (const [name] of views) {
      const css = viewSources[name]
      expect(css, `${name} light surface`).toContain(
        'background: var(--ark-surface-0)'
      )
      expect(css, `${name} hardcoded colors`).not.toMatch(
        /#[0-9a-f]{3,8}|rgba?\(|hsla?\(/i
      )
      expect(css, `${name} gradients`).not.toMatch(
        /linear-gradient|radial-gradient/i
      )
      expect(css, `${name} negative spacing`).not.toMatch(
        /letter-spacing:\s*-/
      )
      expect(css, `${name} viewport font scaling`).not.toMatch(
        /font-size:\s*[^;]*\d(?:vw|vmin|vmax)/i
      )
    }
  })
})
