import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import type { AdminConsoleRole, AdminDashboardSnapshot } from '@/api/types'
import router from '@/router'
import { useAdminConsoleStore } from '@/stores/adminConsole'
import { useAuthStore } from '@/stores/auth'

import AdminDashboardView from './AdminDashboardView.vue'
import dashboardViewSource from './AdminDashboardView.vue?raw'

vi.mock('@/api/client', () => {
  class MockApiError extends Error {
    readonly status: number
    readonly errors: Record<string, string>
    readonly redirect?: string
    readonly code?: string

    constructor(
      message: string,
      status = 400,
      errors: Record<string, string> = {},
      redirect?: string,
      code?: string
    ) {
      super(message)
      this.name = 'ApiError'
      this.status = status
      this.errors = errors
      this.redirect = redirect
      this.code = code
    }
  }

  return { ApiError: MockApiError, apiFetch: vi.fn() }
})

const apiFetchMock = vi.mocked(apiFetch)

// FR-102 forbids these keys anywhere in the ordinary-admin dashboard, at any
// nesting depth, so the scan below walks the whole DTO instead of the surface.
const FORBIDDEN_DASHBOARD_KEYS: readonly string[] = [
  'total_users',
  'role_distribution',
  'student_total',
  'student_count',
  'user_details',
  'average_progress',
  'completion_rate',
  'quiz_attempt_count',
  'quiz_average_score',
  'training_progress',
  'learning_behavior_count'
]

function collectKeys(value: unknown, into: Set<string> = new Set()): Set<string> {
  if (Array.isArray(value)) {
    for (const item of value) {
      collectKeys(item, into)
    }
    return into
  }
  if (typeof value === 'object' && value !== null) {
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      into.add(key)
      collectKeys(child, into)
    }
  }
  return into
}

function unavailableMetric() {
  return { available: false as const, value: null }
}

function contentOperationsDashboard(): AdminDashboardSnapshot {
  return {
    pending_review: {
      course_video: 4,
      job_position: 2,
      handcraft_teaching_video: 1
    },
    published_course_count: 12,
    active_job_count: 7,
    comment_processed_count: 5,
    report_processed_count: 3,
    feedback_processed_count: 6,
    reward_stock: 88,
    pending_fulfillment_count: 2
  }
}

function platformDashboard(): AdminDashboardSnapshot {
  return {
    ...contentOperationsDashboard(),
    total_users: 24,
    role_distribution: {
      student: 12,
      teacher: 3,
      enterprise: 4,
      government: 2,
      admin: 2,
      super_admin: 1
    },
    student_count: 12,
    policy_count: 5,
    policy_view_count: 88,
    news_count: 4,
    news_view_count: 61,
    points_issued: 1250,
    redemption_count: 9
  }
}

let dashboardPayload: AdminDashboardSnapshot = platformDashboard()
let dashboardFailure: Error | null = null

function dashboardResponse(path: string): unknown {
  if (
    path === '/api/admin/dashboard' ||
    path === '/api/admin/content-dashboard'
  ) {
    if (dashboardFailure) {
      throw dashboardFailure
    }
    return { success: true, dashboard: dashboardPayload }
  }
  return { success: true }
}

async function mountView(role: AdminConsoleRole = 'super_admin') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore(pinia)
  auth.sessionState = 'active'
  auth.user = {
    id: 1,
    username: 'super-admin',
    name: '超级管理员',
    role
  }
  const wrapper = mount(AdminDashboardView, {
    global: { plugins: [pinia] },
    attachTo: document.body
  })
  await flushPromises()
  return { wrapper, pinia, store: useAdminConsoleStore(pinia) }
}

describe('AdminDashboardView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiFetchMock.mockImplementation(async (path: string) =>
      dashboardResponse(path)
    )
    dashboardPayload = platformDashboard()
    dashboardFailure = null
    document.body.innerHTML = ''
  })

  it('registers the dashboard child route for both admin roles', () => {
    const route = router
      .getRoutes()
      .find(record => record.path === '/admin/dashboard')

    expect(route?.name).toBe('admin-dashboard')
    expect(route?.meta.requiresAuth).toBe(true)
    expect(route?.meta.roles).toEqual(['super_admin', 'admin'])
  })

  // The plan's Step-1 case, adapted to the Task 4 AdminMetricGroup selector.
  // The payload is deliberately the contaminated platform snapshot, so the
  // exclusion assertions below run against keys the response really carries.
  it('ordinary admin renders only content operations metrics', async () => {
    dashboardPayload = platformDashboard()
    const { wrapper } = await mountView('admin')

    expect(apiFetchMock).toHaveBeenCalledWith('/api/admin/content-dashboard')
    expect(apiFetchMock).not.toHaveBeenCalledWith('/api/admin/dashboard')
    expect(
      wrapper.find('[data-test="admin-metric-pending-review-course-video"]')
        .exists()
    ).toBe(true)
    expect(
      wrapper.find('[data-test="admin-metric-published-course-count"]').exists()
    ).toBe(true)
    expect(
      wrapper.find('[data-test="admin-metric-pending-fulfillment-count"]')
        .exists()
    ).toBe(true)
    expect(wrapper.find('[data-test="dashboard-group-users"]').exists()).toBe(
      false
    )

    expect(wrapper.text()).not.toContain('总用户数')
    expect(wrapper.text()).not.toContain('完成率')
    expect(wrapper.text()).not.toContain('学员数')

    for (const key of FORBIDDEN_DASHBOARD_KEYS) {
      expect(wrapper.html(), `rendered markup leaks ${key}`).not.toContain(key)
    }
  })

  // FR-102/FR-103 defence in depth: the exclusion must also hold when the
  // response body carries the platform-only keys, so a mis-scoped payload
  // still cannot surface a forbidden metric in the ordinary-admin view.
  it('surfaces no forbidden metric from a contaminated payload', async () => {
    dashboardPayload = platformDashboard()
    const { wrapper, store } = await mountView('admin')

    // Guard: the contamination really reached the store, so the assertions
    // below cannot pass against a clean payload.
    const receivedKeys = [...collectKeys(store.dashboard)]
    const contaminated = FORBIDDEN_DASHBOARD_KEYS.filter(key =>
      receivedKeys.includes(key)
    )
    expect(contaminated).toEqual([
      'total_users',
      'role_distribution',
      'student_count'
    ])

    for (const key of FORBIDDEN_DASHBOARD_KEYS) {
      expect(wrapper.html(), `rendered markup leaks ${key}`).not.toContain(key)
      expect(
        wrapper.find(`[data-metric-key="${key}"]`).exists(),
        `rendered tile leaks ${key}`
      ).toBe(false)
    }

    expect(wrapper.find('[data-test="dashboard-group-users"]').exists()).toBe(
      false
    )
    expect(wrapper.text()).not.toContain('账户分布')
    expect(wrapper.text()).not.toContain('总用户数')
    expect(wrapper.text()).not.toContain('学员数')
    expect(wrapper.text()).toContain('内容审核')
  })

  it('super admin renders the full metric set', async () => {
    const { wrapper } = await mountView('super_admin')

    expect(apiFetchMock).toHaveBeenCalledWith('/api/admin/dashboard')
    for (const testId of [
      'admin-metric-pending-review-course-video',
      'admin-metric-pending-review-job-position',
      'admin-metric-pending-review-handcraft-teaching-video',
      'admin-metric-published-course-count',
      'admin-metric-active-job-count',
      'admin-metric-comment-processed-count',
      'admin-metric-report-processed-count',
      'admin-metric-feedback-processed-count',
      'admin-metric-reward-stock',
      'admin-metric-pending-fulfillment-count',
      'admin-metric-total-users',
      'admin-metric-student-count',
      'admin-metric-role-distribution-student',
      'admin-metric-role-distribution-teacher',
      'admin-metric-role-distribution-enterprise',
      'admin-metric-role-distribution-government',
      'admin-metric-role-distribution-admin',
      'admin-metric-role-distribution-super-admin',
      'admin-metric-policy-count',
      'admin-metric-policy-view-count',
      'admin-metric-news-count',
      'admin-metric-news-view-count',
      'admin-metric-points-issued',
      'admin-metric-redemption-count'
    ]) {
      expect(wrapper.find(`[data-test="${testId}"]`).exists()).toBe(true)
    }

    for (const group of ['review', 'content', 'moderation', 'rewards', 'users']) {
      expect(wrapper.find(`[data-test="dashboard-group-${group}"]`).exists())
        .toBe(true)
    }

    expect(wrapper.get('[data-test="admin-metric-total-users"]').text()).toContain(
      '总用户数'
    )
    expect(wrapper.get('[data-test="admin-metric-total-users"]').text()).toContain(
      '24'
    )
  })

  it('marks an unavailable source instead of faking a zero', async () => {
    dashboardPayload = {
      ...contentOperationsDashboard(),
      active_job_count: unavailableMetric()
    }
    const { wrapper } = await mountView('super_admin')

    const marker = wrapper.get(
      '[data-test="dashboard-unavailable-active-job-count"]'
    )
    expect(marker.text()).toContain('数据源不可用')
    expect(marker.text()).not.toContain('0')
    expect(
      wrapper.find('[data-test="admin-metric-active-job-count"]').exists()
    ).toBe(false)
  })

  it('shows the loading state before the dashboard resolves', async () => {
    apiFetchMock.mockImplementation(() => new Promise(() => {}))
    const { wrapper } = await mountView('super_admin')

    expect(wrapper.find('[data-test="dashboard-loading"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="dashboard-group-review"]').exists()).toBe(
      false
    )
  })

  it('shows an empty state when the dashboard carries no metric', async () => {
    dashboardPayload = {} as AdminDashboardSnapshot
    const { wrapper } = await mountView('super_admin')

    expect(wrapper.find('[data-test="dashboard-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="dashboard-group-review"]').exists()).toBe(
      false
    )
  })

  it('surfaces the load failure and retries on demand', async () => {
    dashboardPayload = platformDashboard()
    dashboardFailure = new ApiError('看板指标来源不可用', 503)
    const { wrapper } = await mountView('super_admin')

    expect(wrapper.get('[data-test="dashboard-error"]').text()).toContain(
      '看板指标来源不可用'
    )

    dashboardFailure = null
    await wrapper.get('[data-test="dashboard-retry"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="dashboard-error"]').exists()).toBe(false)
    expect(
      wrapper.find('[data-test="dashboard-group-review"]').exists()
    ).toBe(true)
  })
})

describe('AdminDashboardView geometry', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiFetchMock.mockImplementation(async (path: string) =>
      dashboardResponse(path)
    )
    dashboardPayload = platformDashboard()
    dashboardFailure = null
    document.body.innerHTML = ''
  })

  it('keeps the screen root unclipped so the geometry assertion has teeth', () => {
    const rootRule = cssRule(dashboardViewSource, '.admin-dashboard')
    expect(rootRule).toContain('min-width: 0')
    expect(rootRule).not.toContain('overflow-x')
  })

  it('collapses fixed-format regions with responsive constraints', () => {
    expect(cssRule(dashboardViewSource, '.dashboard-header')).toContain(
      'grid-template-columns: minmax(0, 1fr) minmax(0, 0.62fr)'
    )
    expect(cssRule(dashboardViewSource, '.dashboard-header', 900)).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(cssRule(dashboardViewSource, '.dashboard-header__summary')).toContain(
      'grid-template-columns: repeat(2, minmax(0, 1fr))'
    )
    expect(cssRule(dashboardViewSource, '.dashboard-group__heading')).toContain(
      'flex-wrap: wrap'
    )
    expect(cssRule(dashboardViewSource, '.dashboard-unavailable li')).toContain(
      'grid-template-columns: auto minmax(0, 1fr) auto'
    )
    expect(
      cssRule(dashboardViewSource, '.dashboard-unavailable li', 520)
    ).toContain('grid-template-columns: auto minmax(0, 1fr)')
  })

  it('wraps long Chinese text without mid-word breaks', () => {
    for (const selector of [
      '.dashboard-header__identity p',
      '.dashboard-header__summary dt',
      '.dashboard-error span',
      '.dashboard-group__heading span',
      '.dashboard-unavailable li span'
    ]) {
      const rule = cssRule(dashboardViewSource, selector)
      expect(rule, `${selector} line-break`).toContain('line-break: strict')
      expect(rule, `${selector} overflow-wrap`).toContain(
        'overflow-wrap: anywhere'
      )
      expect(rule, `${selector} word-break`).toContain('word-break: keep-all')
    }
  })

  for (const width of [320, 375, 1280] as const) {
    it(`has no horizontal overflow at ${width}px with long Chinese content`, async () => {
      const { wrapper } = await mountView('super_admin')
      expect(wrapper.text()).toContain('非遗教学视频待审核')
      const root = wrapper.get('[data-test="admin-dashboard"]')
        .element as HTMLElement
      installGeometry(root, dashboardViewSource, width)

      expect(root.clientWidth).toBe(root.scrollWidth)
      wrapper.unmount()
    })
  }

  it('detects overflowing content so the geometry assertion is not vacuous', () => {
    const host = mount({
      template:
        '<div class="probe"><span class="probe-run">粤乡智匠管理后台长文本探针</span></div>'
    })
    const root = host.get('.probe').element as HTMLElement
    installGeometry(
      root,
      '<style>.probe { width: 120px; } .probe-run { white-space: nowrap; }</style>',
      320
    )

    expect(root.clientWidth).toBe(120)
    expect(root.scrollWidth).toBeGreaterThan(root.clientWidth)
    host.unmount()
  })
})

interface StyleRule {
  media: number | null
  selector: string
  declarations: Record<string, string>
}

interface Sides {
  top: number
  right: number
  bottom: number
  left: number
}

interface TextContext {
  fontSize: number
  nowrap: boolean
  anywhere: boolean
  breakAll: boolean
}

interface Measurement {
  min: number
  max: number
  used: number
  extent: number
  boxExtent: number
  client: number
  scroll: number
}

interface GridTrack {
  min: number
  fr: number | null
  px: number | null
  percent: number | null
}

type ChildEntry =
  | {
      kind: 'text'
      text: string
      min: number
      max: number
      margin: Sides
    }
  | {
      kind: 'element'
      element: Element
      min: number
      max: number
      margin: Sides
      boxExtent: number
    }

const INLINE_TAGS = new Set([
  'a',
  'abbr',
  'b',
  'big',
  'cite',
  'code',
  'data',
  'em',
  'i',
  'label',
  'mark',
  'output',
  'q',
  's',
  'small',
  'span',
  'strong',
  'sub',
  'sup',
  'time',
  'tt',
  'u'
])

const ROOT_FONT_SIZE = 16
const CONSOLE_MAX_WIDTH = 1320

let measureRules: StyleRule[] = []
let measureViewport = 1280

function firstLength(value: string): number | null {
  for (const part of value.split(/\s+/)) {
    const px = /^(-?[\d.]+)px$/.exec(part)
    if (px) return Number(px[1])
    const rem = /^(-?[\d.]+)rem$/.exec(part)
    if (rem) return Number(rem[1]) * ROOT_FONT_SIZE
    if (part === '0') return 0
  }
  return null
}

function expandBox(value: string): [number, number, number, number] | null {
  const lengths = value
    .split(/\s+/)
    .map(firstLength)
    .filter((entry): entry is number => entry !== null)
  if (lengths.length === 0) return null
  const [top, right = top, bottom = top, left = right] = lengths
  return [top, right, bottom, left]
}

function boxSides(
  declarations: Record<string, string>,
  property: string
): Sides {
  const sides: Sides = { top: 0, right: 0, bottom: 0, left: 0 }
  const shorthand = declarations[property]
  if (shorthand) {
    const box = expandBox(shorthand)
    if (box) {
      sides.top = box[0]
      sides.right = box[1]
      sides.bottom = box[2]
      sides.left = box[3]
    }
  }
  for (const side of ['top', 'right', 'bottom', 'left'] as const) {
    const longhand = declarations[`${property}-${side}`]
    if (longhand !== undefined) {
      sides[side] = firstLength(longhand) ?? sides[side]
    }
  }
  const inline = declarations[`${property}-inline`]
  if (inline !== undefined) {
    const value = firstLength(inline)
    if (value !== null) {
      sides.left = value
      sides.right = value
    }
  }
  return sides
}

function gapValue(
  declarations: Record<string, string>,
  axis: 'column' | 'row'
): number {
  const shorthand = declarations.gap
  if (shorthand) {
    const parts = shorthand.split(/\s+/).map(firstLength)
    if (parts.length >= 2 && parts[0] !== null && parts[1] !== null) {
      return axis === 'column' ? parts[1] : parts[0]
    }
    if (parts.length === 1 && parts[0] !== null) return parts[0]
  }
  const specific = declarations[axis === 'column' ? 'column-gap' : 'row-gap']
  return specific ? (firstLength(specific) ?? 0) : 0
}

function parseDeclarations(body: string): Record<string, string> {
  const declarations: Record<string, string> = {}
  for (const chunk of body.split(';')) {
    const colon = chunk.indexOf(':')
    if (colon === -1) continue
    const property = chunk.slice(0, colon).trim()
    const value = chunk.slice(colon + 1).trim()
    if (property && value) declarations[property] = value
  }
  return declarations
}

function parseRules(css: string, media: number | null): StyleRule[] {
  const rules: StyleRule[] = []
  let index = 0
  while (index < css.length) {
    const open = css.indexOf('{', index)
    if (open === -1) break
    const prelude = css.slice(index, open).trim()
    let depth = 1
    let cursor = open + 1
    while (cursor < css.length && depth > 0) {
      if (css[cursor] === '{') depth += 1
      else if (css[cursor] === '}') depth -= 1
      cursor += 1
    }
    const body = css.slice(open + 1, cursor - 1)
    index = cursor
    if (prelude.startsWith('@media')) {
      const match = /max-width:\s*(\d+)px/.exec(prelude)
      if (match) rules.push(...parseRules(body, Number(match[1])))
      continue
    }
    if (prelude.startsWith('@')) continue
    for (const selector of prelude
      .split(',')
      .map(value => value.trim())
      .filter(Boolean)) {
      rules.push({ media, selector, declarations: parseDeclarations(body) })
    }
  }
  return rules
}

function parseStyleBlocks(source: string): StyleRule[] {
  const blocks = [...source.matchAll(/<style(?:\s[^>]*)?>([\s\S]*?)<\/style>/g)]
    .map(match => match[1] ?? '')
    .join('\n')
  return parseRules(blocks, null)
}

function cssRule(
  source: string,
  selector: string,
  media: number | null = null
): string {
  const declarations: string[] = []
  for (const rule of parseStyleBlocks(source)) {
    if (rule.selector !== selector) continue
    if (rule.media === null || (media !== null && rule.media >= media)) {
      declarations.push(
        Object.entries(rule.declarations)
          .map(([property, value]) => `${property}: ${value}`)
          .join('; ')
      )
    }
  }
  expect(declarations, `Missing CSS rule for ${selector}`).not.toHaveLength(0)
  return declarations.join('; ')
}

function resolveStyle(
  element: Element,
  rules: StyleRule[]
): Record<string, string> {
  const declarations: Record<string, string> = {}
  for (const rule of rules) {
    if (rule.media !== null && measureViewport > rule.media) continue
    let matched = false
    try {
      matched = element.matches(rule.selector)
    } catch {
      matched = false
    }
    if (matched) Object.assign(declarations, rule.declarations)
  }
  return declarations
}

function defaultDisplay(element: Element): string {
  return INLINE_TAGS.has(element.tagName.toLowerCase()) ? 'inline' : 'block'
}

function textContextFor(
  declarations: Record<string, string>,
  parent: TextContext
): TextContext {
  const fontSize = declarations['font-size']
    ? remToPixels(declarations['font-size'])
    : parent.fontSize
  const whiteSpace = declarations['white-space'] ?? (parent.nowrap ? 'nowrap' : 'normal')
  const overflowWrap =
    declarations['overflow-wrap'] ?? (parent.anywhere ? 'anywhere' : 'normal')
  const wordBreak =
    declarations['word-break'] ?? (parent.breakAll ? 'break-all' : 'normal')
  return {
    fontSize,
    nowrap: whiteSpace === 'nowrap' || whiteSpace === 'pre',
    anywhere: overflowWrap === 'anywhere' || overflowWrap === 'break-word',
    breakAll: wordBreak === 'break-all'
  }
}

function remToPixels(value: string): number {
  const px = /^([\d.]+)px$/.exec(value.trim())
  if (px) return Number(px[1])
  const rem = /^([\d.]+)rem$/.exec(value.trim())
  if (rem) return Number(rem[1]) * ROOT_FONT_SIZE
  return ROOT_FONT_SIZE
}

function isCjk(char: string): boolean {
  const code = char.codePointAt(0) ?? 0
  return (
    (code >= 0x2e80 && code <= 0x9fff) ||
    (code >= 0x3000 && code <= 0x303f) ||
    (code >= 0xac00 && code <= 0xd7af) ||
    (code >= 0xf900 && code <= 0xfaff) ||
    (code >= 0xff00 && code <= 0xff60) ||
    (code >= 0xffe0 && code <= 0xffe6)
  )
}

function charWidth(char: string, fontSize: number): number {
  const code = char.codePointAt(0) ?? 0
  if (char === ' ') return 0.28 * fontSize
  if (char === '\t') return 1.6 * fontSize
  if (isCjk(char)) return fontSize
  if ('iljtIfr.,:;\'"`|!()[]{}'.includes(char)) return 0.34 * fontSize
  if ('mwMW@%&'.includes(char)) return 0.86 * fontSize
  if (char >= '0' && char <= '9') return 0.56 * fontSize
  if (char >= 'A' && char <= 'Z') return 0.66 * fontSize
  if (code < 0x20) return 0
  return 0.55 * fontSize
}

function textExtent(
  text: string,
  context: TextContext
): { min: number; max: number } {
  let max = 0
  let unit = 0
  let min = 0
  for (const char of text) {
    const width = charWidth(char, context.fontSize)
    max += width
    const breakable =
      char === ' ' ||
      char === '\t' ||
      char === '\n' ||
      isCjk(char) ||
      context.anywhere ||
      context.breakAll
    if (breakable) {
      min = Math.max(min, unit + width)
      unit = 0
    } else {
      unit += width
    }
  }
  min = Math.max(min, unit)
  return { min: context.nowrap ? max : min, max }
}

function textMeasurement(text: string, context: TextContext): Measurement {
  const extent = textExtent(text, context)
  return {
    min: extent.min,
    max: extent.max,
    used: extent.max,
    extent: extent.max,
    boxExtent: extent.max,
    client: extent.max,
    scroll: extent.max
  }
}

function atomicWidth(element: Element): number {
  const width = Number(element.getAttribute('width'))
  if (Number.isFinite(width) && width > 0) return width
  const height = Number(element.getAttribute('height'))
  if (Number.isFinite(height) && height > 0) return height
  return 24
}

function expandRepeat(value: string): string {
  let result = value
  const pattern = /repeat\(\s*(\d+)\s*,/g
  let match = pattern.exec(result)
  while (match) {
    const start = match.index
    const bodyStart = start + match[0].length
    let depth = 1
    let cursor = bodyStart
    while (cursor < result.length && depth > 0) {
      if (result[cursor] === '(') depth += 1
      else if (result[cursor] === ')') depth -= 1
      cursor += 1
    }
    const body = result.slice(bodyStart, cursor - 1)
    const expanded = Array.from({ length: Number(match[1]) }, () => body).join(' ')
    result = result.slice(0, start) + expanded + result.slice(cursor)
    pattern.lastIndex = start + expanded.length
    match = pattern.exec(result)
  }
  return result
}

function splitTopLevel(value: string): string[] {
  const parts: string[] = []
  let depth = 0
  let current = ''
  for (const char of value) {
    if (char === '(') depth += 1
    if (char === ')') depth -= 1
    if (char === ' ' && depth === 0) {
      if (current) parts.push(current)
      current = ''
      continue
    }
    current += char
  }
  if (current) parts.push(current)
  return parts
}

function parseTracks(value: string | undefined): GridTrack[] | null {
  if (!value || value === 'none') return null
  const tokens = splitTopLevel(expandRepeat(value))
  const tracks: GridTrack[] = []
  for (const token of tokens) {
    const minmax = /^minmax\(\s*([^,]+?)\s*,\s*(.+?)\s*\)$/.exec(token)
    if (minmax) {
      const fr = /^([\d.]+)fr$/.exec(minmax[2].trim())
      tracks.push({
        min: firstLength(minmax[1]) ?? 0,
        fr: fr ? Number(fr[1]) : null,
        px: fr ? null : firstLength(minmax[2]),
        percent: fr ? null : parsePercent(minmax[2])
      })
      continue
    }
    const fr = /^([\d.]+)fr$/.exec(token)
    if (fr) {
      tracks.push({ min: 0, fr: Number(fr[1]), px: null, percent: null })
      continue
    }
    const px = firstLength(token)
    if (px !== null) {
      tracks.push({ min: px, fr: null, px, percent: null })
      continue
    }
    const percent = parsePercent(token)
    if (percent !== null) {
      tracks.push({ min: 0, fr: null, px: null, percent })
      continue
    }
    if (token === 'auto') {
      tracks.push({ min: 0, fr: null, px: null, percent: null })
      continue
    }
    return null
  }
  return tracks.length > 0 ? tracks : null
}

function parsePercent(value: string): number | null {
  const match = /^(-?[\d.]+)%$/.exec(value.trim())
  return match ? Number(match[1]) / 100 : null
}

function layoutGrid(
  tracks: GridTrack[],
  contentBox: number,
  gap: number,
  items: ChildEntry[]
): number[] {
  const gaps = gap * Math.max(0, tracks.length - 1)
  const available = Math.max(0, contentBox - gaps)
  let fixed = 0
  let frTotal = 0
  const autoIndices: number[] = []
  tracks.forEach((track, index) => {
    if (track.fr !== null) frTotal += track.fr
    else if (track.percent !== null) fixed += track.percent * contentBox
    else if (track.px !== null) fixed += track.px
    else autoIndices.push(index)
  })
  const autoMax = autoIndices.map(index => items[index]?.max ?? 0)
  const autoTotal = autoMax.reduce((sum, value) => sum + value, 0)
  const remaining = Math.max(0, available - fixed)
  const autoBudget = Math.min(autoTotal, remaining)
  const frSpace = Math.max(0, remaining - autoBudget)
  return tracks.map((track, index) => {
    if (track.fr !== null) return frTotal > 0 ? (frSpace * track.fr) / frTotal : 0
    if (track.percent !== null) return track.percent * contentBox
    if (track.px !== null) return track.px
    const autoIndex = autoIndices.indexOf(index)
    return autoTotal > 0 ? (autoBudget * autoMax[autoIndex]) / autoTotal : 0
  })
}

function flexValues(declarations: Record<string, string>): {
  grow: number
  shrink: number
  basis: string
} {
  const raw = declarations.flex
  if (!raw) return { grow: 0, shrink: 1, basis: 'auto' }
  const parts = raw.split(/\s+/).filter(Boolean)
  if (parts.length === 1) {
    if (parts[0] === 'none') return { grow: 0, shrink: 0, basis: 'auto' }
    if (parts[0] === 'auto') return { grow: 1, shrink: 1, basis: 'auto' }
    if (/^\d+$/.test(parts[0])) {
      return { grow: Number(parts[0]), shrink: 1, basis: '0%' }
    }
    return { grow: 1, shrink: 1, basis: parts[0] }
  }
  if (parts.length === 2) {
    if (/^\d+$/.test(parts[0]) && /^\d+$/.test(parts[1])) {
      return { grow: Number(parts[0]), shrink: Number(parts[1]), basis: '0%' }
    }
    return { grow: numeric(parts[0], 1), shrink: 1, basis: parts[1] }
  }
  return {
    grow: numeric(parts[0], 0),
    shrink: numeric(parts[1], 1),
    basis: parts[2] ?? 'auto'
  }
}

function numeric(value: string | undefined, fallback: number): number {
  const parsed = Number.parseFloat(value ?? '')
  return Number.isFinite(parsed) ? parsed : fallback
}

function resolveBasis(basis: string, maxContent: number, contentBox: number): number {
  if (basis === 'auto' || basis === '') return maxContent
  const percent = parsePercent(basis)
  if (percent !== null) return percent * contentBox
  return firstLength(basis) ?? maxContent
}

function resolveDefiniteWidth(
  declarations: Record<string, string>,
  available: number
): number | null {
  const raw = declarations.width
  if (!raw) return null
  const value = raw.trim()
  if (['auto', 'max-content', 'min-content', 'fit-content'].includes(value)) {
    return null
  }
  const percent = parsePercent(value)
  if (percent !== null) return percent * available
  return firstLength(value)
}

function collectChildren(
  element: Element,
  contentBox: number,
  context: TextContext
): ChildEntry[] {
  const children: ChildEntry[] = []
  for (const node of Array.from(element.childNodes)) {
    if (node.nodeType === 3) {
      const text = node.textContent ?? ''
      if (text.trim().length > 0) {
        const extent = textExtent(text, context)
        children.push({
          kind: 'text',
          text,
          min: extent.min,
          max: extent.max,
          margin: { top: 0, right: 0, bottom: 0, left: 0 }
        })
      }
      continue
    }
    if (node.nodeType !== 1) continue
    const child = node as Element
    const declarations = resolveStyle(child, measureRules)
    const position = declarations.position ?? 'static'
    if (position === 'absolute' || position === 'fixed') continue
    const margin = boxSides(declarations, 'margin')
    const measured = measureElement(
      child,
      Math.max(0, contentBox - margin.left - margin.right),
      context
    )
    if (!measured) continue
    children.push({
      kind: 'element',
      element: child,
      min: measured.min,
      max: measured.max,
      margin,
      boxExtent: measured.boxExtent
    })
  }
  return children
}

function remeasure(
  child: ChildEntry,
  assigned: number,
  context: TextContext
): Measurement {
  if (child.kind === 'text') return textMeasurement(child.text, context)
  return (
    measureElement(
      child.element,
      Math.max(0, assigned + child.margin.left + child.margin.right),
      context
    ) ?? textMeasurement('', context)
  )
}

function measureElement(
  element: Element,
  available: number,
  context: TextContext
): Measurement | null {
  const declarations = resolveStyle(element, measureRules)
  const display = declarations.display ?? defaultDisplay(element)
  if (display === 'none') return null

  const tag = element.tagName.toLowerCase()
  if (tag === 'svg' || tag === 'img') {
    const width = atomicWidth(element)
    return {
      min: width,
      max: width,
      used: width,
      extent: width,
      boxExtent: width,
      client: width,
      scroll: width
    }
  }
  if (tag === 'input' || tag === 'select' || tag === 'textarea') {
    return {
      min: 0,
      max: 0,
      used: 0,
      extent: 0,
      boxExtent: 0,
      client: 0,
      scroll: 0
    }
  }

  const padding = boxSides(declarations, 'padding')
  const border = boxSides(declarations, 'border')
  const margin = boxSides(declarations, 'margin')
  const childContext = textContextFor(declarations, context)
  const outer = Math.max(0, available - margin.left - margin.right)
  const contentBox = Math.max(
    0,
    outer - padding.left - padding.right - border.left - border.right
  )

  const children = collectChildren(element, contentBox, childContext)
  const gap = gapValue(declarations, 'column')

  let min = 0
  let max = 0
  let extent = 0

  if (display.startsWith('grid')) {
    const tracks = parseTracks(declarations['grid-template-columns']) ?? [
      { min: 0, fr: 1, px: null, percent: null }
    ]
    const sizes = layoutGrid(tracks, contentBox, gap, children)
    min = tracks.reduce((sum, track) => sum + track.min, 0)
    max = min
    let rowOffset = 0
    let right = 0
    children.forEach((child, index) => {
      const column = index % tracks.length
      if (column === 0) rowOffset = 0
      const trackSize = sizes[column] ?? 0
      const measured = remeasure(
        child,
        Math.max(0, trackSize - child.margin.left - child.margin.right),
        childContext
      )
      rowOffset += child.margin.left + measured.boxExtent + child.margin.right
      if (column < tracks.length - 1) rowOffset += gap
      right = Math.max(right, rowOffset)
    })
    extent = right
  } else if (display === 'flex' || display === 'inline-flex') {
    if ((declarations['flex-direction'] ?? 'row') === 'column') {
      let width = 0
      for (const child of children) {
        width = Math.max(
          width,
          child.max + child.margin.left + child.margin.right
        )
      }
      min = width
      max = width
      extent = width
    } else {
      const wrap = (declarations['flex-wrap'] ?? 'nowrap') !== 'nowrap'
      const gaps = gap * Math.max(0, children.length - 1)
      const items = children.map(child => {
        const flex = flexValues(
          child.kind === 'element' ? resolveStyle(child.element, measureRules) : {}
        )
        return {
          child,
          grow: flex.grow,
          shrink: flex.shrink,
          basis: resolveBasis(flex.basis, child.max, contentBox)
        }
      })
      const total = items.reduce((sum, item) => sum + item.basis, 0) + gaps
      const widths: number[] = []
      if (total <= contentBox) {
        const free = contentBox - total
        const totalGrow = items.reduce((sum, item) => sum + item.grow, 0)
        for (const item of items) {
          widths.push(
            totalGrow > 0 ? item.basis + (free * item.grow) / totalGrow : item.basis
          )
        }
      } else {
        const deficit = total - contentBox
        const totalShrink = items.reduce(
          (sum, item) => sum + item.shrink * Math.max(item.basis, 0.001),
          0
        )
        for (const item of items) {
          const scaled =
            totalShrink > 0
              ? (deficit * item.shrink * Math.max(item.basis, 0.001)) / totalShrink
              : 0
          widths.push(Math.max(item.child.min, item.basis - scaled))
        }
      }
      let offset = 0
      let right = 0
      items.forEach((item, index) => {
        if (index > 0) offset += gap
        offset += item.child.margin.left
        const measured = remeasure(
          item.child,
          Math.max(0, widths[index] - item.child.margin.left - item.child.margin.right),
          childContext
        )
        offset += measured.boxExtent
        right = Math.max(right, offset)
        offset += item.child.margin.right
      })
      extent = right
      min = wrap
        ? children.reduce((sum, child) => Math.max(sum, child.min), 0)
        : items.reduce(
            (sum, item) => sum + (item.shrink === 0 ? item.child.max : item.child.min),
            0
          ) + gaps
      max = children.reduce((sum, child) => sum + child.max, 0) + gaps
    }
  } else if (display === 'table' || display === 'inline-table') {
    const rows: Element[] = []
    for (const section of Array.from(element.children)) {
      const sectionTag = section.tagName.toLowerCase()
      if (sectionTag === 'tr') rows.push(section)
      else if (sectionTag === 'thead' || sectionTag === 'tbody') {
        rows.push(
          ...Array.from(section.children).filter(
            row => row.tagName.toLowerCase() === 'tr'
          )
        )
      }
    }
    const fixed = (declarations['table-layout'] ?? 'auto') === 'fixed'
    const firstCells = rows.length > 0 ? Array.from(rows[0].children) : []
    const cellWidths = firstCells.map(cell => {
      const cellDeclarations = resolveStyle(cell, measureRules)
      return resolveDefiniteWidth(cellDeclarations, contentBox)
    })
    const known = cellWidths.reduce<number>((sum, width) => sum + (width ?? 0), 0)
    const unknown = cellWidths.filter(width => width === null).length
    const remainder = Math.max(0, contentBox - known)
    const tracks = cellWidths.map(width =>
      width ?? (unknown > 0 ? remainder / unknown : 0)
    )
    let widest = 0
    for (const row of rows) {
      let rowWidth = 0
      Array.from(row.children).forEach((cell, index) => {
        const trackSize = tracks[index] ?? 0
        const measured = measureElement(cell, trackSize, childContext)
        rowWidth += measured?.boxExtent ?? trackSize
      })
      widest = Math.max(widest, rowWidth)
    }
    extent = Math.max(contentBox, widest)
    min = fixed ? 0 : widest
    max = extent
  } else {
    let runMin = 0
    let runMax = 0
    const flushRun = () => {
      min = Math.max(min, runMin)
      max = Math.max(max, runMax)
      extent = Math.max(extent, runMin)
      runMin = 0
      runMax = 0
    }
    for (const child of children) {
      if (child.kind === 'text') {
        runMin = Math.max(runMin, child.min)
        runMax += child.max
        continue
      }
      const childDeclarations = resolveStyle(child.element, measureRules)
      const childDisplay =
        childDeclarations.display ?? defaultDisplay(child.element)
      if (childDisplay.startsWith('inline')) {
        runMin = Math.max(runMin, child.min)
        runMax += child.max
        continue
      }
      flushRun()
      min = Math.max(min, child.min + child.margin.left + child.margin.right)
      max = Math.max(max, child.max + child.margin.left + child.margin.right)
      extent = Math.max(
        extent,
        child.boxExtent + child.margin.left + child.margin.right
      )
    }
    flushRun()
  }

  const definite = resolveDefiniteWidth(declarations, outer)
  let used = definite ?? outer
  const minWidth = firstLength(declarations['min-width'] ?? '')
  if (minWidth !== null) used = Math.max(used, minWidth)
  const maxWidth = firstLength(declarations['max-width'] ?? '')
  if (maxWidth !== null) used = Math.min(used, maxWidth)

  const client = Math.max(0, used - border.left - border.right)
  const scroll = Math.max(client, extent + padding.left + padding.right)
  const scrollContainer = (declarations['overflow-x'] ?? 'visible') !== 'visible'
  const boxExtent = scrollContainer
    ? used
    : Math.max(used, scroll + border.left + border.right)

  return { min, max, used, extent, boxExtent, client, scroll }
}

function roundMetrics(value: number): number {
  return Math.round(value * 1000) / 1000
}

function installGeometry(
  root: HTMLElement,
  source: string,
  viewport: number
): void {
  measureRules = parseStyleBlocks(source)
  measureViewport = viewport
  const padding = viewport <= 720 ? 28 : 48
  const available = Math.max(
    0,
    Math.min(viewport, CONSOLE_MAX_WIDTH) - padding
  )
  const measured = measureElement(
    root,
    available,
    { fontSize: ROOT_FONT_SIZE, nowrap: false, anywhere: false, breakAll: false }
  )
  Object.defineProperty(root, 'clientWidth', {
    configurable: true,
    get: () => (measured ? roundMetrics(measured.client) : 0)
  })
  Object.defineProperty(root, 'scrollWidth', {
    configurable: true,
    get: () => (measured ? roundMetrics(measured.scroll) : 0)
  })
}
