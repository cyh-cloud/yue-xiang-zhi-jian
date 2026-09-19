import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { defineComponent } from 'vue'

import router from '@/router'
import { useDialectAssistantStore } from '@/stores/dialectAssistant'
import { useLocalResourcesStore } from '@/stores/localResources'

import DialectAssistantView from './DialectAssistantView.vue'
import LocalResourceNewsView from './LocalResourceNewsView.vue'
import LocalResourcePoliciesView from './LocalResourcePoliciesView.vue'

describe('local resources acceptance', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('registers all exact routes', () => {
    const expected = [
      'local-resources-home',
      'local-resources-dialect',
      'local-resources-cases',
      'local-resources-case-detail',
      'local-resources-policies',
      'local-resources-policy-detail',
      'local-resources-news',
      'local-resources-news-detail'
    ]
    expect(
      router.getRoutes()
        .map(route => route.name)
        .filter(name => typeof name === 'string' && name.startsWith('local-resources-'))
    ).toEqual(expect.arrayContaining(expected))
  })

  it('renders seven policies and exactly three news categories', () => {
    const resourceStore = useLocalResourcesStore()
    resourceStore.subscriptions = {
      categories: [
        'subsidy',
        'ecommerce',
        'heritage',
        'training',
        'certification',
        'general',
        'entrepreneurship'
      ].map(code => ({
        code,
        label: code,
        subscribed: false,
        recommended: false
      })) as never,
      recommended_category_codes: []
    }
    const policies = mount(LocalResourcePoliciesView, {
      global: { stubs: { AppHeader: true, LocalResourcesNav: true } }
    })
    const news = mount(LocalResourceNewsView, {
      global: { stubs: { AppHeader: true, LocalResourcesNav: true } }
    })
    expect(policies.findAll('[data-test="policy-category"]')).toHaveLength(7)
    expect(news.findAll('[data-test="news-category"]')).toHaveLength(3)
    expect(news.text()).not.toContain('下架')
    expect(news.text()).not.toContain('重新上架')
  })

  it('renders the enlarged voice entry and exact failure copy', async () => {
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
    expect(wrapper.text()).toContain('语音提问')
    expect(wrapper.text()).toContain('未能识别，请重说或改用文字')
    expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
    store.error = 'AI 服务暂时不可用'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('AI 服务暂时不可用')
  })

  it('maps browser permission denial to the exact recognition copy', async () => {
    const VoiceStub = defineComponent({
      emits: ['permission-denied'],
      template: `
        <button
          data-test="permission-denied"
          @click="$emit('permission-denied')"
        >
          语音
        </button>
      `
    })
    const store = useDialectAssistantStore()
    const wrapper = mount(DialectAssistantView, {
      global: {
        stubs: {
          AppHeader: true,
          LocalResourcesNav: true,
          VoiceInputButton: VoiceStub
        }
      }
    })
    await wrapper.get('[data-test="permission-denied"]').trigger('click')
    expect(store.error).toBe('未能识别，请重说或改用文字')
  })
})
