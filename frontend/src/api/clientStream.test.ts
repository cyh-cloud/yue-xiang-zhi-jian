import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiStream, setSessionExpiredHandler } from '@/api/client'

describe('apiStream', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('parses SSE events and preserves redirect on 401', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('event: chunk\ndata: {"content":"荔"}\n\n', {
          status: 200,
          headers: { 'Content-Type': 'text/event-stream' }
        })
      )
    )
    const events: Array<{ event: string; data: unknown }> = []

    await apiStream('/stream', { method: 'POST' }, event => events.push(event))

    expect(events).toEqual([{ event: 'chunk', data: { content: '荔' } }])
  })

  it('forwards 401 redirects to the shared session handler', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: false,
            message: '未登录或会话已过期',
            redirect: '/login?redirect=%2Fstudent%2Fagri-skills'
          }),
          {
            status: 401,
            headers: { 'Content-Type': 'application/json' }
          }
        )
      )
    )
    const seen: Array<string | undefined> = []
    const remove = setSessionExpiredHandler(error => {
      seen.push(error.redirect)
    })

    await expect(
      apiStream('/stream', {}, () => undefined)
    ).rejects.toMatchObject({
      status: 401,
      redirect: '/login?redirect=%2Fstudent%2Fagri-skills'
    })
    expect(seen).toEqual(['/login?redirect=%2Fstudent%2Fagri-skills'])
    remove()
  })
})
