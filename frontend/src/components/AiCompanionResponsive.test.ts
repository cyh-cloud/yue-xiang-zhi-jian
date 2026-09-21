import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type { UserRole } from '@/api/types'

import { useAuthStore } from '@/stores/auth'

import AiCompanionLauncher from './AiCompanionLauncher.vue'
// jsdom 既不注入 scoped 样式，也不解析 min()/calc()/svh，响应式契约只能从
// 样式源码里逐条读取，因此四个组件都以 ?raw 形式引入。
import historySource from './AiCompanionHistory.vue?raw'
import launcherSource from './AiCompanionLauncher.vue?raw'
import messageSource from './AiCompanionMessage.vue?raw'
import panelSource from './AiCompanionPanel.vue?raw'

const ROUTES = [
  { path: '/', component: { template: '<div />' } },
  {
    path: '/student',
    component: { template: '<div />' },
    meta: { roles: ['student'] }
  }
]

// 取出 <style> 段：?raw 拿到的是整个 .vue 文件，脚本与模板里同名字符串不能
// 参与 CSS 断言。
function styleSource(source: string): string {
  const styleStart = source.indexOf('<style')
  if (styleStart === -1) {
    return ''
  }
  const open = source.indexOf('>', styleStart)
  if (open === -1) {
    return ''
  }
  const close = source.indexOf('</style>', open)
  const styleBody = source.slice(open + 1, close === -1 ? undefined : close)
  // 注释里的声明不是真实规则：去掉注释后，overflow-wrap/min-width 等断言
  // 才不会在真实声明被注释掉、只剩注释文本时仍然通过。
  return styleBody.replace(/\/\*[\s\S]*?\*\//g, '')
}

function escapeSelector(selector: string): string {
  return selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// 返回某个选择器的声明块；同名选择器取第一次出现，即媒体查询之前的基础规则，
// 基础规则就是移动端（≤640px）上下文。
function cssRule(source: string, selector: string): string {
  const css = styleSource(source)
  const pattern = new RegExp(`(?:^|\\n)\\s*${escapeSelector(selector)}\\s*\\{`)
  const match = pattern.exec(css)
  if (!match) {
    return ''
  }
  const open = css.indexOf('{', match.index)
  const close = css.indexOf('}', open)
  if (open === -1 || close === -1) {
    return ''
  }
  return css.slice(open + 1, close)
}

// 返回指定断点的整个 @media 块内容，按花括号配平截断，内部嵌套规则一并带回。
function mediaBlock(source: string, breakpoint: number): string {
  const css = styleSource(source)
  const start = css.indexOf(`@media (min-width: ${breakpoint}px)`)
  if (start === -1) {
    return ''
  }
  const open = css.indexOf('{', start)
  if (open === -1) {
    return ''
  }
  let depth = 0
  for (let index = open; index < css.length; index += 1) {
    if (css[index] === '{') {
      depth += 1
    } else if (css[index] === '}') {
      depth -= 1
      if (depth === 0) {
        return css.slice(open + 1, index)
      }
    }
  }
  return ''
}

// 与 AiCompanionLauncher.test.ts 同一套脚手架：pinia + 内存路由 + 已登录学员，
// 但固定挂到 document.body，焦点归属断言才有意义。
function mountCompanion(role: UserRole = 'student') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.sessionState = 'active'
  auth.user = { id: 1, username: role, name: role, role }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ROUTES
  })
  return mount(AiCompanionLauncher, {
    attachTo: document.body,
    global: { plugins: [pinia, router] }
  })
}

describe('AiCompanion responsive CSS contract', () => {
  // FR-012：桌面端靠近右侧锚定且不超出视口，移动端在安全区内展开。
  describe('launcher', () => {
    it('floats above page content on every viewport', () => {
      const base = cssRule(launcherSource, '.ai-companion-launcher')
      expect(base).toContain('position: fixed')
      expect(base).toContain('z-index: 40')
    })

    it('keeps the mobile inset inside the safe area', () => {
      const base = cssRule(launcherSource, '.ai-companion-launcher')
      expect(base).toContain('right: 16px')
      expect(base).toContain('bottom: 16px')
      expect(base).toContain('height: 56px')
    })

    it('widens the inset and the target above 640px', () => {
      const desktop = mediaBlock(launcherSource, 641)
      expect(desktop).toContain('right: 24px')
      expect(desktop).toContain('bottom: 24px')
      expect(desktop).toContain('height: 60px')
    })

    // FR-011：触控目标至少 44px，移动端与桌面端两档都要满足。
    it('keeps both launcher heights at or above the 44px touch target', () => {
      const base = cssRule(launcherSource, '.ai-companion-launcher')
      const desktop = mediaBlock(launcherSource, 641)
      expect(base).toContain('height: 56px')
      expect(desktop).toContain('height: 60px')
      expect(56).toBeGreaterThanOrEqual(44)
      expect(60).toBeGreaterThanOrEqual(44)
    })
  })

  describe('panel', () => {
    it('anchors to the right edge without overflowing the viewport', () => {
      const base = cssRule(panelSource, '.ai-companion-panel')
      expect(base).toContain('position: fixed')
      expect(base).toContain('z-index: 40')
      expect(base).toContain('width: min(420px, calc(100vw - 32px))')
    })

    // 旧 Safari 不识别 svh：vh 兜底必须写在 svh 之前。
    it('declares the vh height fallback before the svh value', () => {
      const base = cssRule(panelSource, '.ai-companion-panel')
      const fallbackIndex = base.indexOf(
        'height: min(680px, calc(100vh - 96px))'
      )
      const svhIndex = base.indexOf(
        'height: min(680px, calc(100svh - 96px))'
      )
      expect(fallbackIndex).toBeGreaterThan(-1)
      expect(svhIndex).toBeGreaterThan(fallbackIndex)
    })

    // 只允许消息列表滚动，面板根节点自己滚动会让头部与输入区被顶出视口。
    it('makes the message list the only vertical scroll container', () => {
      expect(cssRule(panelSource, '.ai-companion-panel-scroll')).toContain(
        'overflow-y: auto'
      )
      const root = cssRule(panelSource, '.ai-companion-panel')
      expect(root).not.toContain('overflow-y: auto')
      expect(root).not.toContain('overflow-y: scroll')
    })

    it('lets message and history text wrap and shrink', () => {
      // 只认 <style> 段里的声明：脚本、模板或注释里同样的字符串不算数。
      const messageCss = styleSource(messageSource)
      const historyCss = styleSource(historySource)
      expect(messageCss).toContain('overflow-wrap: anywhere')
      expect(messageCss).toContain('min-width: 0')
      expect(historyCss).toContain('overflow-wrap: anywhere')
      expect(historyCss).toContain('min-width: 0')
    })

    // 浏览器验收被占用端口阻塞，桌面端贴边偏移目前只有这里能守住。
    it('widens the desktop inset to match the launcher', () => {
      const desktop = mediaBlock(panelSource, 641)
      expect(desktop).toContain('right: 24px')
      expect(desktop).toContain('bottom: 96px')
    })

    // 输入区固定高度，可压缩的只有消息区，避免输入区被长内容挤出面板。
    it('pins the composer and lets only the body shrink', () => {
      expect(cssRule(panelSource, '.ai-companion-panel-composer')).toContain(
        'flex: 0 0 auto'
      )
      const body = cssRule(panelSource, '.ai-companion-panel-body')
      expect(body).toContain('flex: 1 1 auto')
      expect(body).toContain('min-height: 0')
    })
  })
})

describe('AiCompanion launcher ARIA contract', () => {
  // 挂到 document.body 的用例在这里统一清理，残留节点不能让后续用例的
  // activeElement 判断蒙混过关。
  afterEach(() => {
    document.body.innerHTML = ''
    sessionStorage.clear()
  })

  it('exposes the launcher as a labelled button', () => {
    const wrapper = mountCompanion()
    const launcher = wrapper.get('[data-test="ai-companion-launcher"]')
    expect(launcher.element.tagName).toBe('BUTTON')
    expect(launcher.attributes('aria-label')).toBe('打开 AI 学伴')
    expect(launcher.attributes('aria-expanded')).toBe('false')
  })

  it('reports the expanded state while the panel is open', async () => {
    const wrapper = mountCompanion()
    await wrapper.get('[data-test="ai-companion-launcher"]').trigger('click')
    expect(wrapper.find('[data-test="ai-companion-panel"]').exists()).toBe(true)
    expect(
      wrapper.get('[data-test="ai-companion-launcher"]').attributes('aria-expanded')
    ).toBe('true')
  })

  // Escape 关闭后焦点必须回到悬浮球，键盘用户才不会丢失位置。
  it('closes the panel with Escape and returns focus to the launcher', async () => {
    const wrapper = mountCompanion()
    await wrapper.get('[data-test="ai-companion-launcher"]').trigger('click')
    await wrapper.get('[data-test="ai-companion-panel"]').trigger('keydown', {
      key: 'Escape'
    })
    expect(wrapper.find('[data-test="ai-companion-panel"]').exists()).toBe(false)
    expect(document.activeElement).toBe(
      wrapper.get('[data-test="ai-companion-launcher"]').element
    )
  })

  it('keeps the composer controls reachable while the panel is open', async () => {
    const wrapper = mountCompanion()
    await wrapper.get('[data-test="ai-companion-launcher"]').trigger('click')
    expect(wrapper.find('[data-test="ai-companion-submit"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="ai-companion-draft"]').exists()).toBe(true)
  })
})
