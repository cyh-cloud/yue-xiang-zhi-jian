import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError, apiFetch } from '@/api/client'
import type {
  HandcraftCraft,
  HandcraftProgress,
  HandcraftVideo
} from '@/api/types'
import handcraftNavSource from '@/components/HandcraftInheritanceNav.vue?raw'
import handcraftCraftLearningSource from '@/components/HandcraftCraftLearning.vue?raw'
import { useHandcraftInheritanceStore } from '@/stores/handcraftInheritance'

import HandcraftCraftView from './HandcraftCraftView.vue'
import handcraftCraftViewSource from './HandcraftCraftView.vue?raw'
import handcraftCoursesViewSource from './HandcraftCoursesView.vue?raw'
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

function step(stepNo: number) {
  return {
    step_key: `step-${stepNo}`,
    step_no: stepNo,
    title: `第 ${stepNo} 步`,
    description: `第 ${stepNo} 步操作说明`,
    tips: [`第 ${stepNo} 步技巧`]
  }
}

function craft(
  available = true,
  steps = Array.from({ length: 6 }, (_, index) => step(index + 1))
): HandcraftCraft {
  return {
    craft_key: 'guangxiu',
    name: '广绣',
    sort_order: 1,
    introduction: '广绣以细密针法和鲜明色彩见长。',
    is_demo: true,
    source_available: available,
    status: available ? 'available' : 'unavailable',
    available,
    unavailable_reason: available ? null : '预置内容不足六个有效步骤',
    steps,
    material_guide: [
      {
        name: '桑蚕丝线',
        reference_price: '每束 18 元',
        purchase_channel: '本地绣材店',
        precautions: '按作品色系分批采购',
        taobao_keyword: '广绣桑蚕丝线'
      }
    ]
  }
}

function progress(completedSteps = [1, 2]): HandcraftProgress {
  return {
    user_id: 1,
    craft_key: 'guangxiu',
    status: 'available',
    available: true,
    unavailable_reason: null,
    completed_steps: completedSteps,
    completed_step_count: completedSteps.length,
    resume_step_no: completedSteps.length + 1,
    is_completed: completedSteps.length === 6,
    updated_at: '2026-09-18T10:00:00+08:00'
  }
}

function video(
  videoId: string,
  patch: Partial<HandcraftVideo> = {}
): HandcraftVideo {
  return {
    video_id: videoId,
    craft_key: 'guangxiu',
    title: '广绣基础针法',
    review_status: 'approved',
    source_available: true,
    media_url: 'https://example.test/guangxiu.mp4',
    playback_url: 'https://example.test/guangxiu.mp4',
    version: 1,
    is_demo: true,
    available: true,
    status: 'available',
    unavailable_reason: null,
    ...patch
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

async function mountAtCraft(pinia = createPinia()) {
  const router = testRouter()
  await router.push('/student/handcraft-inheritance/crafts/guangxiu')
  await router.isReady()
  const wrapper = mount(HandcraftCraftView, {
    global: {
      plugins: [pinia, router]
    }
  })
  await flushPromises()
  return wrapper
}

describe('HandcraftCraftView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders six ordered steps, completed count, resume point and material guide', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/handcraft-inheritance/crafts/guangxiu') {
        return { success: true, craft: craft() } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/crafts/guangxiu/progress'
      ) {
        return { success: true, progress: progress() } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/videos?craft_key=guangxiu'
      ) {
        return { success: true, videos: [video('approved')] } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = await mountAtCraft()

    const steps = wrapper.findAll('[data-test="craft-step"]')
    expect(steps).toHaveLength(6)
    expect(steps.map(item => item.get('h3').text())).toEqual([
      '第 1 步',
      '第 2 步',
      '第 3 步',
      '第 4 步',
      '第 5 步',
      '第 6 步'
    ])
    expect(wrapper.get('[data-test="completed-count"]').text()).toContain(
      '已完成 2 / 6'
    )
    expect(wrapper.get('[data-test="resume-point"]').text()).toContain(
      '从第 3 步继续'
    )

    const material = wrapper.get('[data-test="material-item"]')
    expect(material.text()).toContain('桑蚕丝线')
    expect(material.text()).toContain('参考价格')
    expect(material.text()).toContain('每束 18 元')
    expect(material.text()).toContain('购买渠道')
    expect(material.text()).toContain('本地绣材店')
    expect(material.text()).toContain('注意事项')
    expect(material.text()).toContain('按作品色系分批采购')
    expect(material.text()).toContain('淘宝搜索关键词')
    expect(material.text()).toContain('广绣桑蚕丝线')
    expect(
      wrapper.get('[data-test="handcraft-course-link"]').attributes('href')
    ).toBe('/student/handcraft-inheritance/courses')
  })

  it('shows an explicit unavailable state instead of partial learning content', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/handcraft-inheritance/crafts/guangxiu') {
        return {
          success: true,
          craft: craft(false, [step(1), step(2)])
        } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/crafts/guangxiu/progress'
      ) {
        return { success: true, progress: progress([]) } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/videos?craft_key=guangxiu'
      ) {
        return { success: true, videos: [] } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = await mountAtCraft()

    expect(wrapper.get('[data-test="craft-unavailable"]').text()).toContain(
      '预置内容不足六个有效步骤'
    )
    expect(wrapper.findAll('[data-test="craft-step"]')).toHaveLength(0)
    expect(wrapper.find('[data-test="ar-form"]').exists()).toBe(false)
  })

  it('renders only approved playable videos and shows an empty video state otherwise', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/handcraft-inheritance/crafts/guangxiu') {
        return { success: true, craft: craft() } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/crafts/guangxiu/progress'
      ) {
        return { success: true, progress: progress([]) } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/videos?craft_key=guangxiu'
      ) {
        return {
          success: true,
          videos: [
            video('approved'),
            video('pending', {
              review_status: 'pending',
              available: false,
              status: 'pending'
            }),
            video('missing-media', {
              playback_url: null,
              media_url: null,
              available: false,
              status: 'unavailable'
            })
          ]
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = await mountAtCraft()

    const videos = wrapper.findAll('[data-test="craft-video"]')
    expect(videos).toHaveLength(1)
    expect(videos[0].get('source').attributes('src')).toBe(
      'https://example.test/guangxiu.mp4'
    )
    expect(wrapper.text()).toContain('已审核')

    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/handcraft-inheritance/crafts/guangxiu') {
        return { success: true, craft: craft() } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/crafts/guangxiu/progress'
      ) {
        return { success: true, progress: progress([]) } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/videos?craft_key=guangxiu'
      ) {
        return {
          success: true,
          videos: [
            video('pending', {
              review_status: 'pending',
              available: false,
              status: 'pending'
            })
          ]
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const emptyWrapper = await mountAtCraft()
    expect(emptyWrapper.findAll('[data-test="craft-video"]')).toHaveLength(0)
    expect(
      emptyWrapper.get('[data-test="video-empty"]').text()
    ).toContain('暂无已审核且可播放的教学视频')
  })

  it('keeps the AR project and manual steps when AI guidance fails', async () => {
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/handcraft-inheritance/crafts/guangxiu') {
        return { success: true, craft: craft() } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/crafts/guangxiu/progress'
      ) {
        return { success: true, progress: progress([]) } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/videos?craft_key=guangxiu'
      ) {
        return { success: true, videos: [] } as never
      }
      if (path === '/api/handcraft-inheritance/ar-guidance') {
        throw new ApiError('provider timeout', 503)
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = await mountAtCraft()
    const projectLabel = wrapper.get<HTMLInputElement>(
      '[data-test="ar-project-label"]'
    )
    await projectLabel.setValue('绣制花瓣')
    await wrapper.get('[data-test="ar-form"]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-test="ar-error"]').text()).toBe(
      'AI 服务暂时不可用'
    )
    expect(projectLabel.element.value).toBe('绣制花瓣')
    expect(wrapper.findAll('[data-test="craft-step"]')).toHaveLength(6)
  })

  it('shows sequential feedback and preserves progress when a step is rejected', async () => {
    const pinia = createPinia()
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === '/api/handcraft-inheritance/crafts/guangxiu') {
        return { success: true, craft: craft() } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/crafts/guangxiu/progress'
      ) {
        return { success: true, progress: progress([]) } as never
      }
      if (
        path ===
        '/api/handcraft-inheritance/videos?craft_key=guangxiu'
      ) {
        return { success: true, videos: [] } as never
      }
      if (
        path ===
          '/api/handcraft-inheritance/crafts/guangxiu/steps/4/complete' &&
        options?.method === 'POST'
      ) {
        return {
          success: true,
          progress: {
            ...progress([]),
            accepted: false,
            reason: '请先完成步骤 1',
            step_no: 4,
            points_source_event_id: null,
            points_event: null,
            points_status: 'not_enqueued'
          }
        } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    const wrapper = await mountAtCraft(pinia)
    const store = useHandcraftInheritanceStore(pinia)
    await wrapper.get('[data-test="complete-step-4"]').trigger('click')
    await flushPromises()

    expect(
      wrapper.get('[data-test="step-completion-error-4"]').text()
    ).toContain('请先完成步骤 1')
    expect(wrapper.get('[data-test="completed-count"]').text()).toContain(
      '已完成 0 / 6'
    )
    expect(wrapper.get('[data-test="resume-point"]').text()).toContain(
      '从第 1 步继续'
    )
    expect(store.progressByCraft.guangxiu.completed_steps).toEqual([])
    expect(
      wrapper.get('[data-test="complete-step-1"]').attributes('disabled')
    ).toBeUndefined()
  })

  it('declares CJK-safe wrapping for steps, materials and AR guidance', () => {
    const heading = cssRule(
      handcraftCraftLearningSource,
      '.craft-learning__heading p'
    )
    const stepDescription = cssRule(
      handcraftCraftLearningSource,
      '.step-item__description'
    )
    const guidance = cssRule(
      handcraftCraftLearningSource,
      '.ar-output li'
    )
    const materialValue = cssRule(
      handcraftCraftLearningSource,
      '.material-item dd'
    )

    expect(heading).toContain('line-break: strict')
    expect(heading).toContain('overflow-wrap: anywhere')
    expect(heading).toContain('text-wrap: pretty')
    expect(heading).toContain('word-break: keep-all')
    expect(stepDescription).toContain('overflow-wrap: anywhere')
    expect(stepDescription).toContain('line-break: strict')
    expect(guidance).toContain('overflow-wrap: anywhere')
    expect(materialValue).toContain('overflow-wrap: anywhere')
    expect(handcraftCraftLearningSource).not.toContain(
      'white-space: nowrap'
    )
    expect(handcraftCraftLearningSource).not.toMatch(
      /#[0-9a-f]{3,8}|rgba?\(/i
    )
  })

  it('keeps Task 16 CSS tokenized, motion-safe, portrait-ready and focus-visible', () => {
    const sources = [
      handcraftNavSource,
      handcraftCraftLearningSource,
      handcraftHomeSource,
      handcraftCraftViewSource,
      handcraftCoursesViewSource
    ]

    sources.forEach(source => {
      expect(source).not.toMatch(/#[0-9a-f]{3,8}|rgba?\(|hsla?\(/i)
      expect(source).not.toMatch(
        /(?:color|background|border(?:-[a-z]+)?):\s*(?:#[0-9a-f]{3,8}|rgba?\(|hsla?\(|\b(?:white|black|red|blue|green|yellow|cyan|lime)\b)/i
      )
    })

    expect(handcraftCraftLearningSource).not.toContain('border-left: 3px')
    expect(handcraftCraftLearningSource).toContain(
      '@media (prefers-reduced-motion: reduce)'
    )
    expect(handcraftCraftLearningSource).toContain(
      '@media (max-width: 760px), (orientation: portrait)'
    )
    expect(
      cssRule(
        handcraftCraftLearningSource,
        '.craft-learning :is(a, button, input):focus-visible'
      )
    ).toContain('outline: 2px solid var(--ark-focus)')
  })
})
