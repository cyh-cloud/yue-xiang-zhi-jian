export interface ChineseTextSegment {
  index: number
  text: string
  wordLike: boolean
}

interface SegmenterSegment {
  segment: string
  isWordLike?: boolean
}

interface SegmenterInstance {
  segment(input: string): Iterable<SegmenterSegment>
}

interface SegmenterConstructor {
  new (
    locales?: string | string[],
    options?: { granularity: 'word' }
  ): SegmenterInstance
}

const Segmenter = (
  Intl as unknown as { Segmenter?: SegmenterConstructor }
).Segmenter

export function segmentChineseText(text: string): ChineseTextSegment[] {
  if (!text) {
    return []
  }

  if (!Segmenter) {
    return [{ index: 0, text, wordLike: false }]
  }

  const segmenter = new Segmenter('zh-CN', { granularity: 'word' })
  return Array.from(segmenter.segment(text), (segment, index) => ({
    index,
    text: segment.segment,
    wordLike: segment.isWordLike === true
  }))
}
