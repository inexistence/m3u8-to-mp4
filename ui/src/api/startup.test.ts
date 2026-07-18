import { describe, expect, it, vi } from 'vitest'
import { resolveSidecarBase, waitForHealth } from './startup'

describe('sidecar startup', () => {
  it('uses relative URLs in a regular browser', async () => {
    const invoke = vi.fn()

    expect(await resolveSidecarBase(false, invoke)).toBe('')
    expect(invoke).not.toHaveBeenCalled()
  })

  it('asks Tauri for the loopback base URL', async () => {
    const invoke = vi.fn().mockResolvedValue('http://127.0.0.1:8765')

    expect(await resolveSidecarBase(true, invoke)).toBe('http://127.0.0.1:8765')
    expect(invoke).toHaveBeenCalledWith('get_sidecar_base')
  })

  it('retries health checks until the sidecar is ready', async () => {
    const health = vi
      .fn()
      .mockRejectedValueOnce(new Error('not listening'))
      .mockResolvedValueOnce({ ok: true })

    await waitForHealth({ health }, { attempts: 2, intervalMs: 0 })

    expect(health).toHaveBeenCalledTimes(2)
  })

  it('reports failure when the health deadline expires', async () => {
    const health = vi.fn().mockRejectedValue(new Error('not listening'))

    await expect(
      waitForHealth({ health }, { attempts: 2, intervalMs: 0 }),
    ).rejects.toThrow('sidecar health check timed out')
  })
})
