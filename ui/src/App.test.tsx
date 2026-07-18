import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { api } from './api/client'
import { ws } from './api/ws'

describe('App sidecar wiring', () => {
  beforeEach(() => {
    vi.spyOn(api, 'health').mockResolvedValue({ ok: true })
    vi.spyOn(api, 'getConfig').mockResolvedValue({
      output_directory: null,
      max_parallel_conversions: 2,
    })
    vi.spyOn(api, 'ffmpegStatus').mockResolvedValue({
      available: true,
      message: 'ffmpeg ready',
    })
    vi.spyOn(api, 'batch').mockResolvedValue({
      is_converting: false,
      tasks: [],
    })
    vi.spyOn(ws, 'connect').mockImplementation(() => undefined)
    vi.spyOn(ws, 'disconnect').mockImplementation(() => undefined)
    vi.spyOn(ws, 'onEvent').mockReturnValue(() => undefined)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('scans pasted paths and converts selected entries using sidecar ids', async () => {
    vi.spyOn(api, 'scan').mockResolvedValue({
      entries: [
        {
          task_id: 'sidecar-task-1',
          path: 'C:\\videos\\master.m3u8',
          is_master_playlist: true,
          stream_labels: ['1080p', '720p'],
          selected_stream_index: 0,
        },
      ],
      added: 1,
      duplicates: 0,
      unparseable: 0,
      message: '已添加 1 个任务',
    })
    const convert = vi.spyOn(api, 'convert').mockResolvedValue({ ok: true })

    render(<App />)

    fireEvent.change(screen.getByLabelText('路径列表'), {
      target: { value: 'C:\\videos\\master.m3u8' },
    })
    fireEvent.click(screen.getByRole('button', { name: '添加到队列' }))

    expect(await screen.findByText('master.m3u8')).toBeTruthy()
    expect(screen.getByRole('option', { name: '1080p' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '开始转换' }))

    await waitFor(() => {
      expect(convert).toHaveBeenCalledWith([
        {
          task_id: 'sidecar-task-1',
          path: 'C:\\videos\\master.m3u8',
          selected_stream_index: 0,
          is_master_playlist: true,
        },
      ])
    })
  })

  it('saves edited settings through the config endpoint', async () => {
    const putConfig = vi.spyOn(api, 'putConfig').mockImplementation(async (config) => config)

    render(<App />)

    await waitFor(() => expect(api.getConfig).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: '设置' }))
    fireEvent.change(screen.getByLabelText('同时转换数'), {
      target: { value: '4' },
    })
    fireEvent.click(screen.getByRole('button', { name: '保存设置' }))

    await waitFor(() => {
      expect(putConfig).toHaveBeenCalledWith(
        expect.objectContaining({ max_parallel_conversions: 4 }),
      )
    })
  })
})
