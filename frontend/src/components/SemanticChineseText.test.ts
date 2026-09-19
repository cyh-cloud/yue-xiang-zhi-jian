import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SemanticChineseText from './SemanticChineseText.vue'
import semanticChineseTextSource from './SemanticChineseText.vue?raw'
import { segmentChineseText } from '@/utils/chineseTypography'

describe('SemanticChineseText', () => {
  const source = '本地申请补贴。\n下一项 123'

  it('segments Chinese words while preserving every source character', () => {
    const segments = segmentChineseText(source)

    expect(segments.map(segment => segment.text).join('')).toBe(source)
    expect(
      segments
        .filter(segment => segment.wordLike)
        .map(segment => segment.text)
    ).toEqual(expect.arrayContaining(['本地', '申请', '补贴']))
  })

  it('renders each semantic word as an inline nowrap segment', () => {
    const wrapper = mount(SemanticChineseText, {
      props: { text: source }
    })

    expect(wrapper.get('[data-test="semantic-chinese-text"]').text()).toBe(
      source
    )
    expect(
      wrapper
        .findAll('[data-segment="word"]')
        .map(segment => segment.text())
    ).toEqual(expect.arrayContaining(['本地', '申请', '补贴']))
    expect(semanticChineseTextSource).toContain(
      '.semantic-chinese-text__segment.is-word'
    )
    expect(semanticChineseTextSource).toContain('display: inline-block')
    expect(semanticChineseTextSource).toContain('white-space: nowrap')
  })
})
