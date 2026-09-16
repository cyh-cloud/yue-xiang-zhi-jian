import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError, apiFetch, apiStream } from '@/api/client'
import AgriSkillsNav from '@/components/AgriSkillsNav.vue'
import AppHeader from '@/components/AppHeader.vue'
import VoiceInputButton from '@/components/VoiceInputButton.vue'
import { useAgriQaStore } from '@/stores/agriQa'

import AgriQaView from './AgriQaView.vue'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch: vi.fn(),
    apiStream: vi.fn()
  }
})

const mockedApiFetch = vi.mocked(apiFetch)
const mockedApiStream = vi.mocked(apiStream)

function createTestRouter() {
  const paths = [
    '/',
    '/login',
    '/register',
    '/messages',
    '/student',
    '/student/agri-skills',
    '/student/agri-skills/calendar',
    '/student/agri-skills/qa',
    '/student/agri-skills/diagnosis',
    '/student/agri-skills/courses'
  ]

  return createRouter({
    history: createMemoryHistory(),
    routes: paths.map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}

function mountView() {
  const pinia = createPinia()
  const wrapper = mount(AgriQaView, {
    global: {
      plugins: [pinia, createTestRouter()]
    }
  })
  return { pinia, wrapper }
}

describe('AgriQaView', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    mockedApiStream.mockReset()
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/qa/conversations') {
        return { success: true, conversations: [] } as never
      }
      throw new Error(`Unexpected request: ${path}`)
    })
  })

  it('renders the shared shell, editable text input, and live streaming region', async () => {
    const { wrapper } = mountView()
    await flushPromises()

    expect(wrapper.findComponent(AppHeader).exists()).toBe(true)
    expect(wrapper.findComponent(AgriSkillsNav).exists()).toBe(true)
    expect(wrapper.get('[data-test="question-input"]').element).toBeInstanceOf(
      HTMLTextAreaElement
    )
    expect(wrapper.get('[data-test="streaming-answer"]').attributes('aria-live')).toBe(
      'polite'
    )
  })

  it('clicking a suggestion asks it as a new question', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    const store = useAgriQaStore(pinia)
    store.suggestions = ['如何判断蒂蛀虫', '如何施肥', '如何排水']
    const ask = vi.spyOn(store, 'ask').mockResolvedValue(true)
    await wrapper.vm.$nextTick()

    await wrapper.get('[data-test="suggestion-0"]').trigger('click')
    await flushPromises()

    expect(ask).toHaveBeenCalledWith('如何判断蒂蛀虫', 'text')
  })

  it('styles local answers and does not show suggestions for them', async () => {
    const { pinia, wrapper } = mountView()
    const store = useAgriQaStore(pinia)
    store.turns = [
      {
        id: 1,
        question: '荔枝蒂蛀虫',
        answer: '离线知识库回答\n荔枝蒂蛀虫：及时清理落果',
        input_mode: 'text',
        answer_mode: 'local_kb',
        suggestions: [],
        created_at: '2026-09-16T01:00:00+00:00'
      }
    ]
    store.answerMode = 'local_kb'
    await wrapper.vm.$nextTick()

    expect(wrapper.get('[data-test="local-answer"]').text()).toContain(
      '离线知识库回答'
    )
    expect(wrapper.find('[data-test="suggestion-0"]').exists()).toBe(false)
  })

  it('inserts recognized text for editing and never auto-submits it', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    const store = useAgriQaStore(pinia)
    const transcribe = vi
      .spyOn(store, 'transcribe')
      .mockResolvedValue('荔枝蒂蛀虫怎么防')
    const ask = vi.spyOn(store, 'ask').mockResolvedValue(true)

    wrapper.findComponent(VoiceInputButton).vm.$emit(
      'recorded',
      new Blob(['audio'], { type: 'audio/webm' }),
      'question.webm'
    )
    await flushPromises()

    expect(transcribe).toHaveBeenCalledWith(expect.any(Blob), 'question.webm')
    expect(
      (wrapper.get('[data-test="question-input"]').element as HTMLTextAreaElement)
        .value
    ).toBe('荔枝蒂蛀虫怎么防')
    expect(ask).not.toHaveBeenCalled()
  })

  it('records a MediaRecorder blob with a MIME-based filename', async () => {
    class FakeMediaRecorder {
      static isTypeSupported() {
        return true
      }

      readonly mimeType: string
      state: RecordingState = 'inactive'
      private readonly listeners = new Map<string, Array<(event: BlobEvent) => void>>()

      constructor(_stream: MediaStream, options?: MediaRecorderOptions) {
        this.mimeType = options?.mimeType ?? 'audio/webm'
      }

      addEventListener(type: string, listener: (event: BlobEvent) => void) {
        this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener])
      }

      start() {
        this.state = 'recording'
      }

      stop() {
        this.state = 'inactive'
        this.listeners.get('dataavailable')?.forEach(listener => {
          listener({
            data: new Blob(['audio'], { type: this.mimeType })
          } as BlobEvent)
        })
        this.listeners.get('stop')?.forEach(listener => {
          listener({} as BlobEvent)
        })
      }
    }

    const stopTrack = vi.fn()
    vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: stopTrack }]
        })
      }
    })
    const wrapper = mount(VoiceInputButton, {
      props: { recording: false }
    })

    await wrapper.get('button').trigger('click')
    await flushPromises()
    await wrapper.setProps({ recording: true })
    await wrapper.get('button').trigger('click')

    const recorded = wrapper.emitted('recorded')?.[0]
    expect(recorded?.[0]).toBeInstanceOf(Blob)
    expect(recorded?.[1]).toBe('question.webm')
    expect(stopTrack).toHaveBeenCalled()
    vi.unstubAllGlobals()
  })

  it('keeps visible text after recognition failure and creates no turn', async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    const store = useAgriQaStore(pinia)
    const input = wrapper.get('[data-test="question-input"]')
    await input.setValue('我已经输入的问题')
    mockedApiFetch.mockImplementation(async path => {
      if (path === '/api/agri-skills/qa/conversations') {
        return { success: true, conversations: [] } as never
      }
      if (path === '/api/agri-skills/speech/transcriptions') {
        throw new ApiError('未能识别，请重试或改用文字输入', 422)
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    wrapper.findComponent(VoiceInputButton).vm.$emit(
      'recorded',
      new Blob(['audio'], { type: 'audio/webm' }),
      'question.webm'
    )
    await flushPromises()

    expect((input.element as HTMLTextAreaElement).value).toBe('我已经输入的问题')
    expect(wrapper.get('[role="alert"]').text()).toContain(
      '未能识别，请重试或改用文字输入'
    )
    expect(store.turns).toHaveLength(0)
    expect(mockedApiStream).not.toHaveBeenCalled()
  })
})
