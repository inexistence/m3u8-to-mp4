import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App, { patchFromEvent } from './App'
import { api } from './api/client'
import { ws } from './api/ws'

describe('App sidecar wiring', () => {
  let emitEvent: Parameters<typeof ws.onEvent>[0]
  let emitClose: () => void

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
    vi.spyOn(ws, 'onEvent').mockImplementation((listener) => {
      emitEvent = listener
      return () => undefined
    })
    vi.spyOn(ws, 'onClose').mockImplementation((listener) => {
      emitClose = listener
      return () => undefined
    })
  })

  afterEach(() => {
    vi.useRealTimers()
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

  it('shows local cancelling state for task and batch cancellation', async () => {
    vi.spyOn(api, 'scan').mockResolvedValue({
      entries: [
        {
          task_id: 'task-1',
          path: 'C:\\videos\\one.m3u8',
          is_master_playlist: false,
          stream_labels: [],
          selected_stream_index: 0,
        },
      ],
      added: 1,
      duplicates: 0,
      unparseable: 0,
      message: '已添加 1 个任务',
    })
    vi.spyOn(api, 'convert').mockResolvedValue({ ok: true })
    const cancelTask = vi.spyOn(api, 'cancelTask').mockResolvedValue({ ok: true })
    const cancelAll = vi.spyOn(api, 'cancelAll').mockResolvedValue({ ok: true })

    render(<App />)
    fireEvent.change(screen.getByLabelText('路径列表'), {
      target: { value: 'C:\\videos\\one.m3u8' },
    })
    fireEvent.click(screen.getByRole('button', { name: '添加到队列' }))
    expect(await screen.findByText('one.m3u8')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '开始转换' }))

    fireEvent.click(await screen.findByRole('button', { name: '取消' }))
    expect(cancelTask).toHaveBeenCalledWith('task-1')
    expect(screen.getByRole('button', { name: '正在取消…' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '取消全部' }))
    expect(cancelAll).toHaveBeenCalled()
    expect(screen.getAllByRole('button', { name: '正在取消…' })).toHaveLength(2)
  })

  it('summarizes successful, failed, and cancelled tasks when a batch finishes', async () => {
    vi.spyOn(api, 'scan').mockResolvedValue({
      entries: ['done', 'error', 'skipped'].map((suffix) => ({
        task_id: `task-${suffix}`,
        path: `C:\\videos\\${suffix}.m3u8`,
        is_master_playlist: false,
        stream_labels: [],
        selected_stream_index: 0,
      })),
      added: 3,
      duplicates: 0,
      unparseable: 0,
      message: '已添加 3 个任务',
    })
    vi.spyOn(api, 'convert').mockResolvedValue({ ok: true })

    render(<App />)
    fireEvent.change(screen.getByLabelText('路径列表'), {
      target: { value: 'C:\\videos' },
    })
    fireEvent.click(screen.getByRole('button', { name: '添加到队列' }))
    expect(await screen.findByText('done.m3u8')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '开始转换' }))

    act(() => {
      for (const status of ['done', 'error', 'skipped'] as const) {
        emitEvent({
          type: `task_${status}`,
          task_id: `task-${status}`,
          message: '',
          done_count: 0,
          total_count: 3,
          progress_percent: null,
          progress_phase: '',
          status,
          error_message: '',
        })
      }
      emitEvent({
        type: 'batch_finished',
        task_id: '',
        message: '',
        done_count: 3,
        total_count: 3,
        progress_percent: null,
        progress_phase: '',
        status: '',
        error_message: '',
      })
    })

    expect(await screen.findByText('本批完成：成功 1，失败 1，取消 1')).toBeTruthy()
  })

  it('reconnects after a close and merges the batch snapshot', async () => {
    vi.spyOn(api, 'batch')
      .mockResolvedValueOnce({ is_converting: false, tasks: [] })
      .mockResolvedValueOnce({
        is_converting: false,
        tasks: [
          {
            task_id: 'task-1',
            status: 'done',
            error_message: '',
            progress_percent: 100,
            progress_phase: 'done',
            message: '完成',
          },
        ],
      })
    vi.spyOn(api, 'scan').mockResolvedValue({
      entries: [
        {
          task_id: 'task-1',
          path: 'C:\\videos\\one.m3u8',
          is_master_playlist: false,
          stream_labels: [],
          selected_stream_index: 0,
        },
      ],
      added: 1,
      duplicates: 0,
      unparseable: 0,
      message: '已添加 1 个任务',
    })

    render(<App />)
    fireEvent.change(screen.getByLabelText('路径列表'), {
      target: { value: 'C:\\videos\\one.m3u8' },
    })
    fireEvent.click(screen.getByRole('button', { name: '添加到队列' }))
    expect(await screen.findByText('one.m3u8')).toBeTruthy()

    vi.useFakeTimers()
    act(() => emitClose())
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })

    expect(api.batch).toHaveBeenCalledTimes(2)
    expect(ws.connect).toHaveBeenCalledTimes(2)
    expect(screen.getByText('已完成')).toBeTruthy()
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

  it('keeps custom output mode active until a path is entered', async () => {
    const putConfig = vi.spyOn(api, 'putConfig').mockImplementation(async (config) => config)

    render(<App />)

    await waitFor(() => expect(api.getConfig).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: '指定目录' }))

    const input = screen.getByLabelText('输出目录') as HTMLInputElement
    expect(input.disabled).toBe(false)
    expect(putConfig).not.toHaveBeenCalled()

    fireEvent.change(input, { target: { value: 'D:\\converted' } })
    fireEvent.blur(input)

    await waitFor(() => {
      expect(putConfig).toHaveBeenCalledWith(
        expect.objectContaining({ output_directory: 'D:\\converted' }),
      )
    })
    expect(screen.getByRole('button', { name: '指定目录' }).className).toContain(
      'segmented__active',
    )
  })
})

describe('patchFromEvent', () => {
  const event = {
    type: 'task_progress',
    task_id: 'task-1',
    message: '',
    done_count: 0,
    total_count: 1,
    progress_percent: null,
    progress_phase: '',
    status: 'done' as const,
    error_message: '',
  }

  it('clears an error when an event carries an empty error message', () => {
    expect(patchFromEvent(event).errorMessage).toBe('')
  })

  it('clears an error for a done event without an error field', () => {
    const withoutError = { ...event } as Partial<typeof event>
    delete withoutError.error_message
    expect(patchFromEvent(withoutError as typeof event).errorMessage).toBe('')
  })
})
