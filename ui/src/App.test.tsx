import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App, { patchFromEvent } from './App'
import { api } from './api/client'
import { ws } from './api/ws'

async function renderReadyApp() {
  render(<App />)
  await screen.findByLabelText('路径列表')
}

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

  it('gates the queue until health succeeds and offers retry after timeout', async () => {
    vi.useFakeTimers()
    vi.mocked(api.health).mockRejectedValue(new Error('connection refused'))

    render(<App />)
    expect(screen.getByText('正在启动转换服务…')).toBeTruthy()
    expect(screen.queryByLabelText('路径列表')).toBeNull()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(9_500)
    })
    expect(screen.getByText('转换服务启动失败')).toBeTruthy()

    vi.mocked(api.health).mockResolvedValue({ ok: true })
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(screen.getByLabelText('路径列表')).toBeTruthy()
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

    await renderReadyApp()

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

    await renderReadyApp()
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

    await renderReadyApp()
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

    expect(
      await screen.findByText(
        '本批完成：成功 1，失败 1，取消 1；点击失败任务可查看详情',
      ),
    ).toBeTruthy()
  })

  it('expands and copies failed task error details', async () => {
    vi.spyOn(api, 'scan').mockResolvedValue({
      entries: [
        {
          task_id: 'task-error',
          path: 'C:\\videos\\error.m3u8',
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
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })

    await renderReadyApp()
    fireEvent.change(screen.getByLabelText('路径列表'), {
      target: { value: 'C:\\videos\\error.m3u8' },
    })
    fireEvent.click(screen.getByRole('button', { name: '添加到队列' }))
    expect(await screen.findByText('error.m3u8')).toBeTruthy()

    act(() => {
      emitEvent({
        type: 'task_error',
        task_id: 'task-error',
        message: '转换失败',
        done_count: 1,
        total_count: 1,
        progress_percent: null,
        progress_phase: '',
        status: 'error',
        error_message: 'ffmpeg exited with code 1',
      })
    })

    expect(screen.queryByText('ffmpeg exited with code 1')).toBeNull()
    fireEvent.click(screen.getByText('error.m3u8'))
    expect(screen.getByText('ffmpeg exited with code 1')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '复制错误' }))
    expect(writeText).toHaveBeenCalledWith('ffmpeg exited with code 1')
    fireEvent.click(screen.getByText('error.m3u8'))
    expect(screen.queryByText('ffmpeg exited with code 1')).toBeNull()
  })

  it('uses absolute path paste without misleading browser picker buttons', async () => {
    await renderReadyApp()

    expect(screen.getByText('当前为浏览器模式，请粘贴绝对路径')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '选择文件' })).toBeNull()
    expect(screen.queryByRole('button', { name: '选择文件夹' })).toBeNull()
    expect(screen.queryByRole('button', { name: '浏览…' })).toBeNull()
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

    await renderReadyApp()
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

  it('ignores a stale reconnect snapshot after the batch finishes', async () => {
    let resolveReconnectSnapshot!: (value: {
      is_converting: boolean
      tasks: []
    }) => void
    const reconnectSnapshot = new Promise<{
      is_converting: boolean
      tasks: []
    }>((resolve) => {
      resolveReconnectSnapshot = resolve
    })
    vi.spyOn(api, 'batch')
      .mockResolvedValueOnce({ is_converting: false, tasks: [] })
      .mockReturnValueOnce(reconnectSnapshot)

    await renderReadyApp()
    await waitFor(() => expect(api.batch).toHaveBeenCalledTimes(1))

    vi.useFakeTimers()
    act(() => emitClose())
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(api.batch).toHaveBeenCalledTimes(2)

    act(() => {
      emitEvent({
        type: 'batch_finished',
        task_id: '',
        message: '',
        done_count: 0,
        total_count: 0,
        progress_percent: null,
        progress_phase: '',
        status: '',
        error_message: '',
      })
      resolveReconnectSnapshot({ is_converting: true, tasks: [] })
    })
    await act(async () => {
      await reconnectSnapshot
    })

    expect(screen.queryByRole('button', { name: '取消全部' })).toBeNull()
  })

  it('saves edited settings through the config endpoint', async () => {
    const putConfig = vi.spyOn(api, 'putConfig').mockImplementation(async (config) => config)

    await renderReadyApp()

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

  it('keeps import enabled and locks settings while converting', async () => {
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

    await renderReadyApp()
    fireEvent.change(screen.getByLabelText('路径列表'), {
      target: { value: 'C:\\videos\\one.m3u8' },
    })
    fireEvent.click(screen.getByRole('button', { name: '添加到队列' }))
    expect(await screen.findByText('one.m3u8')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '开始转换' }))

    await screen.findByRole('button', { name: '取消全部' })

    const pathInput = screen.getByLabelText('路径列表') as HTMLTextAreaElement
    const settingsButton = screen.getByRole('button', { name: '设置' }) as HTMLButtonElement
    const clearButton = screen.getByRole('button', { name: '清空列表' }) as HTMLButtonElement
    expect(pathInput.disabled).toBe(false)
    expect(settingsButton.disabled).toBe(true)
    expect(clearButton.disabled).toBe(true)
  })

  it('keeps custom output mode active until a path is entered', async () => {
    const putConfig = vi.spyOn(api, 'putConfig').mockImplementation(async (config) => config)

    await renderReadyApp()

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

  it('rolls back the output directory when saving fails', async () => {
    vi.spyOn(api, 'putConfig').mockRejectedValue(new Error('disk full'))

    await renderReadyApp()
    await waitFor(() => expect(api.getConfig).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: '指定目录' }))
    const input = screen.getByLabelText('输出目录') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'D:\\converted' } })
    fireEvent.blur(input)

    await screen.findByText(/保存输出目录失败/)
    expect(input.value).toBe('')
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
