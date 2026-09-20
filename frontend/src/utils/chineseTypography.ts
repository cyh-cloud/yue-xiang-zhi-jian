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

const TRAILING_PUNCTUATION = new Set([
  '，',
  '。',
  '！',
  '？',
  '；',
  '：',
  '、',
  '）',
  '》',
  '】',
  '〕',
  '〉',
  '」',
  '』',
  '”',
  '’',
  '…',
  '—',
  '～',
  '·',
  ',',
  '.',
  ';',
  ':',
  '!',
  '?',
  ')',
  ']',
  '}'
])

function isTrailingPunctuation(text: string): boolean {
  return (
    text.length > 0 &&
    Array.from(text).every(character => TRAILING_PUNCTUATION.has(character))
  )
}

function groupSegmenterOutput(
  segments: SegmenterSegment[]
): Array<{ text: string; wordLike: boolean }> {
  const grouped: Array<{ text: string; wordLike: boolean }> = []

  for (const segment of segments) {
    if (
      !segment.isWordLike &&
      isTrailingPunctuation(segment.segment) &&
      grouped.length > 0
    ) {
      let previousIndex = grouped.length - 1
      while (
        previousIndex >= 0 &&
        /^\s+$/.test(grouped[previousIndex]?.text ?? '')
      ) {
        previousIndex -= 1
      }

      if (previousIndex >= 0) {
        const target = grouped[previousIndex]
        if (target) {
          target.text +=
            grouped
              .slice(previousIndex + 1)
              .map(item => item.text)
              .join('') + segment.segment
          target.wordLike = true
          grouped.length = previousIndex + 1
          continue
        }
      }
    }

    grouped.push({
      text: segment.segment,
      wordLike: segment.isWordLike === true
    })
  }

  return grouped
}

export function segmentChineseText(text: string): ChineseTextSegment[] {
  if (!text) {
    return []
  }

  if (!Segmenter) {
    return [{ index: 0, text, wordLike: false }]
  }

  const segmenter = new Segmenter('zh-CN', { granularity: 'word' })
  return groupSegmenterOutput(Array.from(segmenter.segment(text))).map(
    (segment, index) => ({
      index,
      text: segment.text,
      wordLike: segment.wordLike
    })
  )
}
