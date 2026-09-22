import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import AdminConsoleNav from '@/components/AdminConsoleNav.vue'

import AdminContentManagementView from './AdminContentManagementView.vue'
import AdminModerationView from './AdminModerationView.vue'
import AdminPresetsView from './AdminPresetsView.vue'
import AdminReviewView from './AdminReviewView.vue'
import contentViewSource from './AdminContentManagementView.vue?raw'
import moderationViewSource from './AdminModerationView.vue?raw'
import presetsViewSource from './AdminPresetsView.vue?raw'
import reviewViewSource from './AdminReviewView.vue?raw'

vi.mock('@/api/client', () => {
  class MockApiError extends Error {
    readonly status: number
    readonly code: string
    readonly errors: Record<string, string>

    constructor(
      message: string,
      status = 400,
      errors: Record<string, string> = {},
      _redirect?: string,
      code = ''
    ) {
      super(message)
      this.name = 'ApiError'
      this.status = status
      this.code = code
      this.errors = errors
    }
  }

  return { ApiError: MockApiError, apiFetch: vi.fn() }
})

const apiFetchMock = vi.mocked(apiFetch)

// Each admin screen mounts by fetching its own read surface. A benign empty
// answer lets every one render its full layout (header, filters, table region)
// so the geometry probe below can measure the real responsive constraints.
function installBenignFetch() {
  apiFetchMock.mockImplementation(async (path: string) => {
    if (path.startsWith('/api/admin/review')) {
      return { success: true, items: [], counts: {} }
    }
    return { success: true, items: [], count: 0 }
  })
}

async function mountConsoleView(component: unknown) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore(pinia)
  auth.sessionState = 'active'
  auth.user = {
    id: 1,
    username: 'super-admin',
    name: '超级管理员',
    role: 'super_admin'
  }
  const wrapper = mount(component as never, {
    global: { plugins: [pinia] }
  })
  await flushPromises()
  return { pinia, wrapper }
}

const geometryViews = [
  {
    name: 'AdminReviewView',
    component: AdminReviewView,
    source: reviewViewSource,
    testId: 'admin-review'
  },
  {
    name: 'AdminPresetsView',
    component: AdminPresetsView,
    source: presetsViewSource,
    testId: 'admin-presets'
  },
  {
    name: 'AdminContentManagementView',
    component: AdminContentManagementView,
    source: contentViewSource,
    testId: 'admin-content'
  },
  {
    name: 'AdminModerationView',
    component: AdminModerationView,
    source: moderationViewSource,
    testId: 'admin-moderation'
  }
]

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

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      '/admin',
      '/admin/dashboard',
      '/admin/review',
      '/admin/moderation',
      '/admin/presets',
      '/admin/rewards',
      '/admin/redemptions',
      '/admin/accounts',
      '/admin/points-policy',
      '/admin/content',
      '/admin/announcements',
      '/login'
    ].map(path => ({ path, component: { template: '<div />' } }))
  })
}

async function mountNav(role: 'admin' | 'super_admin') {
  const test = testRouter()
  await test.push('/admin')
  await test.isReady()
  const wrapper = mount(AdminConsoleNav, {
    props: { role },
    global: {
      plugins: [test],
      stubs: { RouterLink: RouterLinkStub }
    }
  })
  return { test, wrapper }
}

describe('admin console role navigation', () => {
  it('shows ordinary admins the read-only set that includes data management', async () => {
    const { wrapper } = await mountNav('admin')

    const visible = [
      'dashboard',
      'review',
      'moderation',
      'presets',
      'rewards',
      'redemptions',
      'content'
    ]
    for (const testId of visible) {
      expect(
        wrapper.find(`[data-test="admin-nav-${testId}"]`).exists(),
        `admin visible: ${testId}`
      ).toBe(true)
    }

    // 账号管理、积分规则、系统公告为超管专属，普通管理员一律看不到。
    for (const testId of ['accounts', 'points-policy', 'announcements']) {
      expect(
        wrapper.find(`[data-test="admin-nav-${testId}"]`).exists(),
        `admin hidden: ${testId}`
      ).toBe(false)
    }
  })

  it('shows super admins every console entry', async () => {
    const { wrapper } = await mountNav('super_admin')
    const expected = [
      'dashboard',
      'review',
      'moderation',
      'presets',
      'rewards',
      'redemptions',
      'accounts',
      'points-policy',
      'content',
      'announcements'
    ]
    for (const testId of expected) {
      expect(
        wrapper.find(`[data-test="admin-nav-${testId}"]`).exists()
      ).toBe(true)
    }
  })
})

describe('admin console navigation and route guards agree', () => {
  it('keeps data management a double-role route so the nav cannot hide it from admins', () => {
    const content = router
      .getRoutes()
      .find(record => record.path === '/admin/content')

    expect(content?.meta.requiresAuth).toBe(true)
    expect(content?.meta.roles).toEqual(['super_admin', 'admin'])

    // 导航会把 /admin/content 显示给普通管理员，因此路由绝不能把它标成超管专属，
    // 否则点进去会被 authGuard 挡下——三方门禁由此对齐。
    const superAdminOnly = router
      .getRoutes()
      .filter(record =>
        (record.meta.roles as string[] | undefined)?.includes('super_admin') &&
        !(record.meta.roles as string[] | undefined)?.includes('admin')
      )
    expect(superAdminOnly.map(record => record.path).sort()).toEqual([
      '/admin/accounts',
      '/admin/announcements',
      '/admin/points-policy'
    ])
  })
})

describe('admin console responsive geometry', () => {
  beforeEach(() => {
    installBenignFetch()
  })

  it('detects overflowing content so the geometry assertions are not vacuous', () => {
    const host = mount({
      template:
        '<div class="probe"><span class="probe-run">粤乡智匠后台长文本溢出探针字符串</span></div>'
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

  for (const view of geometryViews) {
    for (const width of [320, 375, 1280] as const) {
      it(`renders ${view.name} without horizontal overflow at ${width}px`, async () => {
        const { wrapper } = await mountConsoleView(view.component)
        const root = wrapper.get(`[data-test="${view.testId}"]`)
          .element as HTMLElement
        installGeometry(root, view.source, width)

        expect(root.clientWidth).toBe(root.scrollWidth)
        wrapper.unmount()
      })
    }
  }
})
