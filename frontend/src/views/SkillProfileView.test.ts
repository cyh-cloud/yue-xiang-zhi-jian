import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { SkillProfile } from '@/api/types'
import { useJobMatchingStore } from '@/stores/jobMatching'

import SkillProfileView from './SkillProfileView.vue'

const profileFixture: SkillProfile = {
  items: [
    {
      item_id: 'ecommerce:live_script:1',
      category: 'live_script',
      source_module: 'ecommerce',
      source_type: 'live_script',
      title: '荔枝直播话术脚本',
      summary: '完成产品卖点与互动话术整理',
      score: null,
      is_formal: false,
      occurred_at: '2026-09-19T10:00:00+08:00',
      source_available: true,
      visible: false
    },
    {
      item_id: 'ecommerce:simulation_training:2',
      category: 'simulation_training',
      source_module: 'ecommerce',
      source_type: 'simulation_training',
      title: '农产品售后模拟训练',
      summary: '完成退款沟通与问题记录',
      score: 82,
      is_formal: true,
      occurred_at: '2026-09-19T11:00:00+08:00',
      source_available: true,
      visible: false
    },
    {
      item_id: 'agriculture:course_quiz:3',
      category: 'quiz_score',
      source_module: 'agriculture',
      source_type: 'course_quiz',
      title: '荔枝种植课后测验',
      summary: '果树管理课程正式测验',
      score: 91,
      is_formal: true,
      occurred_at: '2026-09-19T12:00:00+08:00',
      source_available: true,
      visible: false
    },
    {
      item_id: 'handcraft:course_view:4',
      category: 'learning_record',
      source_module: 'handcraft',
      source_type: 'course_view',
      title: '广绣基础课程学习记录',
      summary: '完成课程内容浏览与学习记录',
      score: null,
      is_formal: false,
      occurred_at: '2026-09-19T13:00:00+08:00',
      source_available: false,
      visible: false
    }
  ],
  visible_item_ids: [],
  summary: {
    live_script: 1,
    simulation_training: 1,
    quiz_score: 1,
    learning_record: 1
  }
}

function mountProfile(profile: SkillProfile = profileFixture) {
  const pinia = createPinia()
  const store = useJobMatchingStore(pinia)
  store.skillProfile = profile
  const wrapper = mount(SkillProfileView, {
    global: { plugins: [pinia] }
  })
  return { store, wrapper }
}

describe('SkillProfileView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders four categories and defaults every item to hidden', () => {
    const { wrapper } = mountProfile()

    expect(wrapper.findAll('[data-test="skill-category"]')).toHaveLength(4)
    expect(wrapper.findAll('[data-test="skill-visible"]')).toHaveLength(0)
    expect(wrapper.text()).toContain('仅自己可见')
    expect(wrapper.text()).toContain('直播话术脚本')
    expect(wrapper.text()).toContain('模拟训练评分')
    expect(wrapper.text()).toContain('课后测验成绩')
    expect(wrapper.text()).toContain('学习记录与课程完成')
  })

  it('saves only checked item IDs', async () => {
    const { store, wrapper } = mountProfile()
    const saveVisibility = vi
      .spyOn(store, 'saveSkillVisibility')
      .mockResolvedValue(profileFixture)

    await wrapper
      .get('[data-test="visibility-ecommerce:live_script:1"]')
      .setValue(true)
    await wrapper.get('[data-test="save-visibility"]').trigger('click')
    await flushPromises()

    expect(saveVisibility).toHaveBeenCalledWith([
      'ecommerce:live_script:1'
    ])
  })

  it('renders outcome details and stable distinct source-module labels', () => {
    const { wrapper } = mountProfile()
    const renderedText = wrapper.text()

    expect(renderedText).toContain('荔枝直播话术脚本')
    expect(renderedText).toContain('完成产品卖点与互动话术整理')
    expect(renderedText).toContain('82 分')
    expect(renderedText).toContain('正式成果')
    expect(renderedText).toContain('03 · 农业技能')
    expect(renderedText).toContain('04 · 电商训练')
    expect(renderedText).toContain('05 · 非遗手工')
    expect(renderedText).toContain('来源可用')
    expect(renderedText).toContain('2026')
    expect(renderedText).toContain('10:00')
  })

  it('shows an explicit enterprise-visible marker for visible items', () => {
    const { wrapper } = mountProfile({
      ...profileFixture,
      items: profileFixture.items.map(item =>
        item.item_id === 'agriculture:course_quiz:3'
          ? { ...item, visible: true }
          : item
      ),
      visible_item_ids: ['agriculture:course_quiz:3']
    })

    expect(wrapper.findAll('[data-test="skill-visible"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('企业可见')
  })

  it('saves the complete current visible set without partial patches', async () => {
    const profileWithVisibleItems: SkillProfile = {
      ...profileFixture,
      items: profileFixture.items.map(item =>
        item.item_id === 'ecommerce:simulation_training:2'
          ? { ...item, visible: true }
          : item
      ),
      visible_item_ids: ['ecommerce:simulation_training:2']
    }
    const { store, wrapper } = mountProfile(profileWithVisibleItems)
    const saveVisibility = vi
      .spyOn(store, 'saveSkillVisibility')
      .mockResolvedValue(profileWithVisibleItems)

    await wrapper
      .get('[data-test="visibility-ecommerce:live_script:1"]')
      .setValue(true)
    await wrapper.get('[data-test="save-visibility"]').trigger('click')
    await flushPromises()

    expect(saveVisibility).toHaveBeenCalledWith([
      'ecommerce:live_script:1',
      'ecommerce:simulation_training:2'
    ])
    expect(JSON.stringify(saveVisibility.mock.calls)).not.toContain(
      '荔枝直播话术脚本'
    )
    expect(JSON.stringify(saveVisibility.mock.calls)).not.toContain(
      '完成产品卖点与互动话术整理'
    )
  })

  it('removes an unchecked visible item from the marker and saved set', async () => {
    const profileWithVisibleItem: SkillProfile = {
      ...profileFixture,
      items: profileFixture.items.map(item =>
        item.item_id === 'agriculture:course_quiz:3'
          ? { ...item, visible: true }
          : item
      ),
      visible_item_ids: ['agriculture:course_quiz:3']
    }
    const { store, wrapper } = mountProfile(profileWithVisibleItem)
    const saveVisibility = vi
      .spyOn(store, 'saveSkillVisibility')
      .mockResolvedValue(profileWithVisibleItem)

    await wrapper
      .get('[data-test="visibility-agriculture:course_quiz:3"]')
      .setValue(false)

    expect(wrapper.findAll('[data-test="skill-visible"]')).toHaveLength(0)
    expect(wrapper.text()).toContain('仅自己可见')

    await wrapper.get('[data-test="save-visibility"]').trigger('click')
    await flushPromises()

    expect(saveVisibility).toHaveBeenCalledWith([])
  })

  it('marks unavailable sources and excludes them from the saved set', async () => {
    const profileWithUnavailableVisibleItem: SkillProfile = {
      ...profileFixture,
      items: profileFixture.items.map(item =>
        item.item_id === 'handcraft:course_view:4'
          ? { ...item, visible: true }
          : item
      ),
      visible_item_ids: ['handcraft:course_view:4']
    }
    const { store, wrapper } = mountProfile(
      profileWithUnavailableVisibleItem
    )
    const unavailableCheckbox = wrapper.get(
      '[data-test="visibility-handcraft:course_view:4"]'
    )
    const saveVisibility = vi
      .spyOn(store, 'saveSkillVisibility')
      .mockResolvedValue(profileWithUnavailableVisibleItem)

    expect(wrapper.text()).toContain('来源暂不可用')
    expect(unavailableCheckbox.attributes('disabled')).toBeDefined()
    expect(unavailableCheckbox.attributes('checked')).toBeUndefined()

    await unavailableCheckbox.setValue(true)
    await wrapper.get('[data-test="save-visibility"]').trigger('click')
    await flushPromises()

    expect(saveVisibility).toHaveBeenCalledWith([])
  })

  it('shows a useful empty state while retaining all four groups', () => {
    const { wrapper } = mountProfile({
      items: [],
      visible_item_ids: [],
      summary: {
        live_script: 0,
        simulation_training: 0,
        quiz_score: 0,
        learning_record: 0
      }
    })

    expect(wrapper.findAll('[data-test="skill-category"]')).toHaveLength(4)
    expect(wrapper.get('[data-test="skill-empty"]').text()).toContain(
      '暂无可展示的技能成果'
    )
    expect(wrapper.get('[data-test="skill-empty"]').text()).toContain(
      '完成课程学习、模拟训练或课后测验后'
    )
  })

  it('does not expose company or application data', () => {
    const profileWithUnrelatedFields = {
      ...profileFixture,
      items: [
        {
          ...profileFixture.items[0],
          company_name: '示例企业不应展示',
          application_id: 'APPLICATION-SECRET-1'
        }
      ],
      visible_item_ids: ['ecommerce:live_script:1']
    } as unknown as SkillProfile
    const { wrapper } = mountProfile(profileWithUnrelatedFields)

    expect(wrapper.text()).not.toContain('示例企业不应展示')
    expect(wrapper.text()).not.toContain('APPLICATION-SECRET-1')
  })
})
