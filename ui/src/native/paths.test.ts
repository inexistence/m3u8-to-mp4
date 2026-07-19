import { beforeEach, describe, expect, it, vi } from 'vitest'

const open = vi.hoisted(() => vi.fn())

vi.mock('@tauri-apps/plugin-dialog', () => ({
  open,
}))

import { pickDirectory, pickM3u8Files } from './paths'

describe('native path pickers', () => {
  beforeEach(() => {
    open.mockReset()
  })

  it('returns multiple m3u8 paths from the open dialog', async () => {
    open.mockResolvedValue(['C:\\a.m3u8', 'C:\\b.m3u8'])
    await expect(pickM3u8Files()).resolves.toEqual(['C:\\a.m3u8', 'C:\\b.m3u8'])
    expect(open).toHaveBeenCalledWith({
      multiple: true,
      filters: [{ name: 'm3u8', extensions: ['m3u8'] }],
    })
  })

  it('normalizes a single selected file and empty cancel', async () => {
    open.mockResolvedValueOnce('C:\\only.m3u8')
    await expect(pickM3u8Files()).resolves.toEqual(['C:\\only.m3u8'])
    open.mockResolvedValueOnce(null)
    await expect(pickM3u8Files()).resolves.toEqual([])
  })

  it('picks a directory or null when cancelled', async () => {
    open.mockResolvedValueOnce('C:\\Videos')
    await expect(pickDirectory()).resolves.toBe('C:\\Videos')
    expect(open).toHaveBeenCalledWith({ directory: true, multiple: false })
    open.mockResolvedValueOnce(null)
    await expect(pickDirectory()).resolves.toBeNull()
  })
})
