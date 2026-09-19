import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  ResumeOptimizationOffer,
  StudentResume
} from '@/api/types'
import { useJobMatchingStore } from '@/stores/jobMatching'

import ResumeEditorView from './ResumeEditorView.vue'
import resumeEditorSource from './ResumeEditorView.vue?raw'
import resumeSectionEditorSource from '@/components/ResumeSectionEditor.vue?raw'

const emptyResume: StudentResume = {
  education_experiences: [],
  work_experiences: [],
  skills: [],
  version: 1,
  saved_at: null,
  has_saved_resume: false
}

const savedResume: StudentResume = {
  education_experiences: [
    {
      school: '广东职业学院',
      major: '电子商务',
      degree: '专科',
      start_date: '2022-09',
      end_date: '2025-06'
    }
  ],
  work_experiences: [],
  skills: ['直播运营'],
  version: 1,
  saved_at: '2026-09-20T10:00:00+08:00',
  has_saved_resume: true
}

const offerFixture: ResumeOptimizationOffer = {
  offer_id: 'offer-1',
  base_version: 1,
  suggestions: ['补充量化成果'],
  rewritten_resume: {
    education_experiences: [
      {
        school: '广东职业学院',
        major: '电子商务',
        degree: '专科',
        start_date: '2022-09',
        end_date: '2025-06'
      }
    ],
    work_experiences: [
      {
        company: '示范农场',
        role: '运营助理',
        start_date: '2025-07',
        end_date: '',
        description: '直播转化率提升 20%。'
      }
    ],
    skills: ['直播运营', '数据分析']
  },
  status: 'offered',
  created_at: '2026-09-20T10:05:00+08:00'
}

function mountEditor(resume: StudentResume = savedResume) {
  const pinia = createPinia()
  const store = useJobMatchingStore(pinia)
  store.resume = resume
  vi.spyOn(store, 'loadResume').mockResolvedValue(resume)
  const wrapper = mount(ResumeEditorView, {
    global: { plugins: [pinia] }
  })
  return { store, wrapper }
}

describe('ResumeEditorView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('blocks saving when all three structured sections are empty', async () => {
    const { store, wrapper } = mountEditor(emptyResume)
    const saveResume = vi.spyOn(store, 'saveResume')

    await wrapper.get('[data-test="resume-form"]').trigger('submit')
    await flushPromises()

    expect(saveResume).not.toHaveBeenCalled()
    expect(wrapper.get('[data-test="resume-empty-error"]').text()).toContain(
      '至少填写一个简历区块'
    )
  })

  it('saves all structured sections with the current version', async () => {
    const { store, wrapper } = mountEditor(emptyResume)
    const saveResume = vi.spyOn(store, 'saveResume').mockResolvedValue({
      ...savedResume,
      version: 2
    })

    await wrapper.get('[data-test="add-education"]').trigger('click')
    await wrapper
      .get('[data-test="education-school-0"]')
      .setValue('广东职业学院')
    await wrapper
      .get('[data-test="education-major-0"]')
      .setValue('电子商务')
    await wrapper
      .get('[data-test="education-degree-0"]')
      .setValue('专科')
    await wrapper
      .get('[data-test="education-start-0"]')
      .setValue('2022-09')
    await wrapper
      .get('[data-test="education-end-0"]')
      .setValue('2025-06')

    await wrapper.get('[data-test="add-work"]').trigger('click')
    await wrapper.get('[data-test="work-company-0"]').setValue('示范农场')
    await wrapper.get('[data-test="work-role-0"]').setValue('运营助理')
    await wrapper.get('[data-test="work-start-0"]').setValue('2025-07')
    await wrapper.get('[data-test="work-end-0"]').setValue('')
    await wrapper
      .get('[data-test="work-description-0"]')
      .setValue('负责直播数据记录。')

    await wrapper.get('[data-test="add-skill"]').trigger('click')
    await wrapper.get('[data-test="resume-skill"]').setValue('客户沟通')

    await wrapper.get('[data-test="resume-form"]').trigger('submit')
    await flushPromises()

    expect(saveResume).toHaveBeenCalledWith({
      expected_version: 1,
      education_experiences: [
        {
          school: '广东职业学院',
          major: '电子商务',
          degree: '专科',
          start_date: '2022-09',
          end_date: '2025-06'
        }
      ],
      work_experiences: [
        {
          company: '示范农场',
          role: '运营助理',
          start_date: '2025-07',
          end_date: '',
          description: '负责直播数据记录。'
        }
      ],
      skills: ['客户沟通']
    })
  })

  it('adds and removes education and work entries', async () => {
    const { wrapper } = mountEditor(emptyResume)

    await wrapper.get('[data-test="add-education"]').trigger('click')
    await wrapper.get('[data-test="add-education"]').trigger('click')
    await wrapper.get('[data-test="education-school-0"]').setValue('第一学校')
    await wrapper.get('[data-test="education-school-1"]').setValue('第二学校')
    await wrapper.get('[data-test="remove-education-0"]').trigger('click')

    expect(wrapper.find('[data-test="education-school-0"]').exists()).toBe(true)
    expect(
      (wrapper.get('[data-test="education-school-0"]').element as HTMLInputElement)
        .value
    ).toBe('第二学校')

    await wrapper.get('[data-test="add-work"]').trigger('click')
    await wrapper.get('[data-test="add-work"]').trigger('click')
    await wrapper.get('[data-test="work-company-0"]').setValue('第一公司')
    await wrapper.get('[data-test="work-company-1"]').setValue('第二公司')
    await wrapper.get('[data-test="remove-work-1"]').trigger('click')

    expect(wrapper.find('[data-test="work-company-1"]').exists()).toBe(false)
    expect(
      (wrapper.get('[data-test="work-company-0"]').element as HTMLInputElement)
        .value
    ).toBe('第一公司')
  })

  it('adds and removes skill entries', async () => {
    const { wrapper } = mountEditor(emptyResume)

    await wrapper.get('[data-test="add-skill"]').trigger('click')
    await wrapper.get('[data-test="add-skill"]').trigger('click')
    await wrapper.findAll('[data-test="resume-skill"]')[0]?.setValue('直播运营')
    await wrapper.findAll('[data-test="resume-skill"]')[1]?.setValue('数据分析')
    await wrapper.get('[data-test="remove-skill-0"]').trigger('click')

    const skills = wrapper.findAll('[data-test="resume-skill"]')
    expect(skills).toHaveLength(1)
    expect((skills[0]?.element as HTMLInputElement).value).toBe('数据分析')
  })

  it('keeps entered values and shows field errors after validation failure', async () => {
    const { store, wrapper } = mountEditor(emptyResume)
    vi.spyOn(store, 'saveResume').mockImplementation(async () => {
      store.error = '简历校验失败'
      store.fieldErrors = {
        'education_experiences.school': '学校不能为空'
      }
      return null
    })

    await wrapper.get('[data-test="add-education"]').trigger('click')
    await wrapper
      .get('[data-test="education-school-0"]')
      .setValue('不会丢失的学校')
    await wrapper.get('[data-test="resume-form"]').trigger('submit')
    await flushPromises()

    expect(
      (wrapper.get('[data-test="education-school-0"]')
        .element as HTMLInputElement).value
    ).toBe('不会丢失的学校')
    expect(
      wrapper.get('[data-test="education-school-error-0"]').text()
    ).toContain('学校不能为空')
  })

  it('shows exact AI unavailable copy while manual controls stay enabled', async () => {
    const { store, wrapper } = mountEditor()
    const optimizeResume = vi
      .spyOn(store, 'optimizeResume')
      .mockImplementation(async () => {
        store.error = 'AI 服务暂时不可用'
        store.errorCode = 'ai_unavailable'
        return null
      })

    await wrapper.get('[data-test="optimize-resume"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="ai-unavailable"]').text()).toBe(
      'AI 服务暂时不可用'
    )
    expect(
      wrapper.get('[data-test="education-school-0"]').attributes('disabled')
    ).toBeUndefined()
    expect(
      wrapper.get('[data-test="add-education"]').attributes('disabled')
    ).toBeUndefined()
    expect(
      wrapper.get('[data-test="resume-save"]').attributes('disabled')
    ).toBeUndefined()
    expect(optimizeResume).toHaveBeenCalledWith(1)
  })

  it('adopts with the offer ID and current resume version', async () => {
    const { store, wrapper } = mountEditor({ ...savedResume, version: 2 })
    store.optimizationOffer = offerFixture
    const adoptOptimization = vi
      .spyOn(store, 'adoptOptimization')
      .mockResolvedValue({ ...savedResume, version: 3 })
    await wrapper.vm.$nextTick()

    await wrapper.get('[data-test="adopt-optimization"]').trigger('click')
    await flushPromises()

    expect(adoptOptimization).toHaveBeenCalledWith('offer-1', 2)
  })

  it('shows rewritten sections in the AI preview', async () => {
    const { store, wrapper } = mountEditor()
    store.optimizationOffer = offerFixture
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('补充量化成果')
    expect(wrapper.text()).toContain('示范农场')
    expect(wrapper.text()).toContain('数据分析')
    expect(wrapper.get('[data-test="adopt-optimization"]').text()).toContain(
      '采纳改写'
    )
  })

  it('does not offer automatic adoption for a suggestion-only result', async () => {
    const { store, wrapper } = mountEditor()
    store.optimizationOffer = {
      ...offerFixture,
      rewritten_resume: null
    }
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="adopt-optimization"]').exists()).toBe(false)
    expect(wrapper.get('[data-test="discard-optimization"]').text()).toContain(
      '放弃'
    )
    expect(wrapper.text()).toContain('补充量化成果')
  })

  it('discards an offer without changing the saved resume', async () => {
    const { store, wrapper } = mountEditor()
    store.optimizationOffer = offerFixture
    const discardOptimization = vi
      .spyOn(store, 'discardOptimization')
      .mockImplementation(async () => {
        store.optimizationOffer = {
          ...offerFixture,
          status: 'discarded'
        }
        return store.optimizationOffer
      })
    await wrapper.vm.$nextTick()

    await wrapper.get('[data-test="discard-optimization"]').trigger('click')
    await flushPromises()

    expect(discardOptimization).toHaveBeenCalledWith('offer-1')
    expect(store.resume?.skills).toEqual(['直播运营'])
    expect(wrapper.find('[data-test="optimization-preview"]').exists()).toBe(
      false
    )
  })

  it('uses bounded responsive tracks, strict CJK wrapping, and token colors', () => {
    for (const source of [resumeEditorSource, resumeSectionEditorSource]) {
      expect(source).toContain('min-width: 0')
      expect(source).toContain('overflow-wrap: anywhere')
      expect(source).toContain('word-break: normal')
      expect(source).toContain('@media (max-width: 720px)')
      expect(source).not.toContain('white-space: nowrap')
      expect(source).not.toMatch(
        /#[0-9a-f]{3,8}|rgba?\(|hsla?\(|linear-gradient|radial-gradient/i
      )
    }

    expect(resumeEditorSource).toContain(
      'grid-template-columns: minmax(0, 1fr)'
    )
    expect(resumeSectionEditorSource).toContain(
      'grid-template-columns: repeat(2, minmax(0, 1fr))'
    )
  })
})
