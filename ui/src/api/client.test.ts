import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApi } from './client'

describe('createApi', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('prefixes sidecar requests with the supplied base URL', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await createApi('http://127.0.0.1:8765').health()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8765/api/health',
      expect.any(Object),
    )
  })

  it('keeps relative API paths when no base URL is supplied', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await createApi().health()

    expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.any(Object))
  })
})
