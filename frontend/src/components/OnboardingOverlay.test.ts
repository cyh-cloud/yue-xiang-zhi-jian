import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import OnboardingOverlay from './OnboardingOverlay.vue'

const steps = [
  {
    selector: '#student-courses',
    title: '课程',
    description: '浏览课程'
  },
  {
    selector: '#student-profile',
    title: '资料',
    description: '维护资料'
  }
]

describe('OnboardingOverlay', () => {
  it('emits complete only after the final step', async () => {
    const wrapper = mount(OnboardingOverlay, {
      props: { title: '学员入口', steps }
    })

    await wrapper.get('[data-test="next-step"]').trigger('click')
    expect(wrapper.emitted('complete')).toBeUndefined()

    await wrapper.get('[data-test="finish"]').trigger('click')
    expect(wrapper.emitted('complete')).toHaveLength(1)
  })

  it('emits skipped without emitting complete', async () => {
    const wrapper = mount(OnboardingOverlay, {
      props: {
        title: '学员入口',
        steps
      }
    })

    await wrapper.get('[data-test="skip"]').trigger('click')

    expect(wrapper.emitted('skipped')).toHaveLength(1)
    expect(wrapper.emitted('complete')).toBeUndefined()
  })

  it('emits close without recording completion', async () => {
    const wrapper = mount(OnboardingOverlay, {
      props: { title: '学员入口', steps }
    })

    await wrapper.get('[data-test="close"]').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('complete')).toBeUndefined()
    expect(wrapper.emitted('skipped')).toBeUndefined()
  })
})
