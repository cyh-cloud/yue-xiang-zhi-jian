import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import VoiceInputButton from '@/components/VoiceInputButton.vue'
import { useDialectAssistantStore } from '@/stores/dialectAssistant'

import DialectAssistantView from './DialectAssistantView.vue'

const completedTurn = {
  id: 'dialect-1',
  dialect_code: 'yue',
  dialect_label: '粤语',
  recognized_text: '几时种荔枝？',
  dialect_answer: '春天种。',
  mandarin_answer: '春天种植。',
  status: 'completed',
  created_at: '2026-09-19T10:00:00+08:00'
} as const

describe('DialectAssistantView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('shows all three dialect choices and an enlarged labelled voice control', () => {
    const wrapper = mount(DialectAssistantView, {
      global: {
        stubs: {
          AppHeader: true,
          LocalResourcesNav: true
        }
      }
    })

    const dialectOptions = wrapper.findAll('option')
    expect(dialectOptions.map(option => option.element.value)).toEqual([
      'yue',
      'hak',
      'nan'
    ])
    expect(dialectOptions.map(option => option.text())).toEqual([
      '粤语',
      '客家话',
      '潮汕话'
    ])
    expect(wrapper.text()).toContain('语音提问')
    const voiceEntry = wrapper.get('[data-test="dialect-voice-button"]')
    expect(voiceEntry.find('button[type="button"]').exists()).toBe(true)
    expect(voiceEntry.find('button').attributes('tabindex')).not.toBe('-1')
  })

  it('submits edited recognized text and renders dialect plus Mandarin answer', async () => {
    const store = useDialectAssistantStore()
    store.dialectCode = 'yue'
    store.recognizedText = '几时种荔枝？'
    store.lastTurn = completedTurn
    store.audioUrl = 'blob:audio-1'
    const submit = vi.spyOn(store, 'submitTurn').mockResolvedValue(true)
    const play = vi
      .spyOn(HTMLMediaElement.prototype, 'play')
      .mockRejectedValue(new DOMException('Autoplay blocked', 'NotAllowedError'))
    const wrapper = mount(DialectAssistantView, {
      global: {
        stubs: {
          AppHeader: true,
          LocalResourcesNav: true,
          VoiceInputButton: true
        }
      }
    })

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(submit).toHaveBeenCalledWith('几时种荔枝？')
    expect(wrapper.get('[data-test="dialect-answer"]').text()).toContain('春天种。')
    expect(wrapper.get('[data-test="mandarin-answer"]').text()).toContain('春天种植。')
    const audio = wrapper.get('audio')
    expect(audio.attributes('src')).toBe('blob:audio-1')
    expect(audio.attributes('controls')).toBeDefined()
    expect(play).toHaveBeenCalledTimes(1)

    await audio.trigger('play')
    expect(submit).toHaveBeenCalledTimes(1)
  })

  it('shows exact ASR and AI failure copy from the store', async () => {
    const store = useDialectAssistantStore()
    store.error = '未能识别，请重说或改用文字'
    const wrapper = mount(DialectAssistantView, {
      global: {
        stubs: {
          AppHeader: true,
          LocalResourcesNav: true
        }
      }
    })
    expect(wrapper.text()).toContain('未能识别，请重说或改用文字')
    store.error = 'AI 服务暂时不可用'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('AI 服务暂时不可用')
  })

  it('puts recognized speech into the editable text and does not auto-submit', async () => {
    const store = useDialectAssistantStore()
    const transcribe = vi
      .spyOn(store, 'transcribe')
      .mockResolvedValue('几时种荔枝？')
    const submit = vi.spyOn(store, 'submitTurn').mockResolvedValue(true)
    const wrapper = mount(DialectAssistantView, {
      global: {
        stubs: {
          AppHeader: true,
          LocalResourcesNav: true
        }
      }
    })

    wrapper.findComponent(VoiceInputButton).vm.$emit(
      'recorded',
      new Blob(['audio'], { type: 'audio/webm' }),
      'question.webm'
    )
    await flushPromises()

    expect(transcribe).toHaveBeenCalledWith(expect.any(Blob), 'question.webm')
    expect(store.recognizedText).toBe('几时种荔枝？')
    expect(
      (wrapper.get('#recognized-question').element as HTMLTextAreaElement).value
    ).toBe('几时种荔枝？')
    expect(submit).not.toHaveBeenCalled()
  })

  it('keeps existing text and uses the exact copy when permission is denied', async () => {
    const store = useDialectAssistantStore()
    store.recognizedText = '保留的文字'
    const wrapper = mount(DialectAssistantView, {
      global: {
        stubs: {
          AppHeader: true,
          LocalResourcesNav: true
        }
      }
    })

    wrapper.findComponent(VoiceInputButton).vm.$emit('permission-denied')
    await wrapper.vm.$nextTick()

    expect(store.error).toBe('未能识别，请重说或改用文字')
    expect(store.recognizedText).toBe('保留的文字')
    expect(
      (wrapper.get('#recognized-question').element as HTMLTextAreaElement).value
    ).toBe('保留的文字')
  })

  it('does not submit a blank question and submits later edits', async () => {
    const store = useDialectAssistantStore()
    store.recognizedText = '   '
    const submit = vi.spyOn(store, 'submitTurn').mockResolvedValue(false)
    const wrapper = mount(DialectAssistantView, {
      global: {
        stubs: {
          AppHeader: true,
          LocalResourcesNav: true,
          VoiceInputButton: true
        }
      }
    })

    await wrapper.get('form').trigger('submit')
    expect(submit).not.toHaveBeenCalled()

    await wrapper.get('#recognized-question').setValue('修改后的问题')
    await wrapper.get('form').trigger('submit')
    expect(submit).toHaveBeenCalledWith('修改后的问题')
  })
})
