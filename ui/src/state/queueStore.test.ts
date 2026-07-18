import { describe, expect, it } from 'vitest'
import { initialQueueState, queueReducer, type QueueTask } from './queueStore'

function task(partial: Partial<QueueTask> & Pick<QueueTask, 'id' | 'path'>): QueueTask {
  return {
    name: 'index.m3u8',
    directory: 'C:/v',
    selected: true,
    isMasterPlaylist: false,
    streamLabels: [],
    selectedStreamIndex: 0,
    status: 'pending',
    errorMessage: '',
    progressPercent: null,
    progressPhase: '',
    progressMessage: '',
    errorExpanded: false,
    ...partial,
  }
}

describe('queueReducer', () => {
  it('adds entries with stable ids and dedupes by path', () => {
    const a = task({ id: '1', path: 'C:/a/index.m3u8' })
    let state = queueReducer(initialQueueState, {
      type: 'ADD_ENTRIES',
      entries: [a],
      feedback: 'ok',
    })
    state = queueReducer(state, {
      type: 'ADD_ENTRIES',
      entries: [task({ id: '2', path: 'C:/a/index.m3u8' })],
      feedback: 'dup',
    })
    expect(state.tasks).toHaveLength(1)
    expect(state.tasks[0].id).toBe('1')
  })

  it('maps a scanned entry task_id to the queue task id', () => {
    const state = queueReducer(initialQueueState, {
      type: 'ADD_ENTRIES',
      entries: [
        {
          task_id: 'sidecar-id',
          path: 'C:/a/index.m3u8',
          is_master_playlist: true,
          stream_labels: ['1080p'],
          selected_stream_index: 0,
        },
      ],
      feedback: '',
    })

    expect(state.tasks[0]).toMatchObject({
      id: 'sidecar-id',
      isMasterPlaylist: true,
      streamLabels: ['1080p'],
    })
  })

  it('patches a single task by id without replacing others', () => {
    let state = queueReducer(initialQueueState, {
      type: 'ADD_ENTRIES',
      entries: [
        task({ id: '1', path: 'C:/a/index.m3u8' }),
        task({ id: '2', path: 'C:/b/index.m3u8' }),
      ],
      feedback: '',
    })
    const beforeSecond = state.tasks[1]
    state = queueReducer(state, {
      type: 'PATCH_TASK',
      taskId: '1',
      patch: { status: 'running', progressPercent: 40 },
    })
    expect(state.tasks[0].progressPercent).toBe(40)
    expect(state.tasks[1]).toBe(beforeSecond)
  })

  it('freezes selected ids on START_BATCH', () => {
    let state = queueReducer(initialQueueState, {
      type: 'ADD_ENTRIES',
      entries: [
        task({ id: '1', path: 'C:/a/index.m3u8', selected: true }),
        task({ id: '2', path: 'C:/b/index.m3u8', selected: false }),
      ],
      feedback: '',
    })
    state = queueReducer(state, { type: 'START_BATCH' })
    expect(state.isConverting).toBe(true)
    expect(state.activeBatchIds).toEqual(['1'])
  })
})
