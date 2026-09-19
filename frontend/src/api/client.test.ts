import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiFetch, apiStream } from '@/api/client'

describe('api client error parsing', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('preserves the top-level branch code from apiFetch', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: false,
            code: 'resume_required',
            message: '请先创建并保存简历',
            errors: { resume: '请先创建并保存简历' }
          }),
          {
            status: 409,
            headers: { 'content-type': 'application/json' }
          }
        )
      )
    )

    await expect(apiFetch('/api/job-matching/resume')).rejects.toMatchObject({
      status: 409,
      message: '请先创建并保存简历',
      code: 'resume_required',
      errors: { resume: '请先创建并保存简历' }
    })
  })

  it('preserves the top-level branch code from apiStream', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: false,
            code: 'resume_required',
            message: '请先创建并保存简历',
            errors: {}
          }),
          {
            status: 409,
            headers: { 'content-type': 'application/json' }
          }
        )
      )
    )

    await expect(
      apiStream('/api/job-matching/resume', {}, vi.fn())
    ).rejects.toMatchObject({
      status: 409,
      message: '请先创建并保存简历',
      code: 'resume_required'
    })
  })
})
