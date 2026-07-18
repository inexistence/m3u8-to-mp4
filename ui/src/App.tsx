import { useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { api } from './api/client'
import { ws } from './api/ws'
import { DropZone } from './components/DropZone'
import { OutputBar } from './components/OutputBar'
import { SettingsModal } from './components/SettingsModal'
import { TaskList } from './components/TaskList'
import { Toolbar } from './components/Toolbar'
import { TopBar } from './components/TopBar'
import { batchFeedback } from './queueMessages'
import { initialQueueState, queueReducer } from './state/queueStore'
import type { QueueTask, ScanEntry, SidecarConfig, SidecarEvent } from './types'
import './App.css'

function splitPath(path: string) {
  const separator = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'))
  return {
    name: separator < 0 ? path : path.slice(separator + 1),
    directory: separator < 0 ? '' : path.slice(0, separator),
  }
}

function queueTaskFromScan(entry: ScanEntry): QueueTask {
  return {
    id: entry.task_id,
    path: entry.path,
    ...splitPath(entry.path),
    selected: true,
    isMasterPlaylist: entry.is_master_playlist,
    streamLabels: entry.stream_labels,
    selectedStreamIndex: entry.selected_stream_index,
    status: 'pending',
    errorMessage: '',
    progressPercent: null,
    progressPhase: '',
    progressMessage: '',
    errorExpanded: false,
  }
}

export function patchFromEvent(event: SidecarEvent): Partial<QueueTask> {
  const patch: Partial<QueueTask> = {
    progressMessage: event.message,
    progressPercent: event.progress_percent,
    progressPhase: event.progress_phase,
  }
  if (event.status) patch.status = event.status
  if (event.error_message !== undefined) {
    patch.errorMessage = event.error_message
  } else if (event.status === 'done' || event.status === 'pending') {
    patch.errorMessage = ''
  }
  return patch
}

function App() {
  const [state, dispatch] = useReducer(queueReducer, initialQueueState)
  const [sidecarReady, setSidecarReady] = useState(false)
  const [ffmpegAvailable, setFfmpegAvailable] = useState(false)
  const [ffmpegMessage, setFfmpegMessage] = useState('')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [outputMode, setOutputMode] = useState<'source' | 'custom'>('source')
  const [cancellingAll, setCancellingAll] = useState(false)
  const [cancellingTaskIds, setCancellingTaskIds] = useState<Set<string>>(
    () => new Set(),
  )
  const batchStatuses = useRef(new Map<string, QueueTask['status']>())
  const snapshotGen = useRef(0)
  const batchFinishedSnapshotGen = useRef(-1)

  useEffect(() => {
    let active = true
    void api
      .health()
      .then((result) => active && setSidecarReady(result.ok))
      .catch(() => active && setSidecarReady(false))
    void api
      .getConfig()
      .then((config) => {
        if (!active) return
        dispatch({ type: 'HYDRATE_CONFIG', config })
        setOutputMode(config.output_directory ? 'custom' : 'source')
      })
      .catch((error: unknown) => {
        if (active) dispatch({ type: 'SET_FEEDBACK', feedback: `读取设置失败：${String(error)}` })
      })
    void api
      .ffmpegStatus()
      .then((result) => {
        if (!active) return
        setFfmpegAvailable(result.available)
        setFfmpegMessage(result.message)
      })
      .catch((error: unknown) => {
        if (!active) return
        setFfmpegAvailable(false)
        setFfmpegMessage(String(error))
      })
    const gen = ++snapshotGen.current
    void api
      .batch()
      .then((batch) => {
        if (
          !active ||
          gen !== snapshotGen.current ||
          batchFinishedSnapshotGen.current === gen
        ) {
          return
        }
        dispatch({ type: 'SET_CONVERTING', isConverting: batch.is_converting })
        for (const task of batch.tasks) {
          batchStatuses.current.set(task.task_id, task.status)
          dispatch({
            type: 'PATCH_TASK',
            taskId: task.task_id,
            patch: {
              status: task.status,
              errorMessage: task.error_message,
              progressPercent: task.progress_percent,
              progressPhase: task.progress_phase,
              progressMessage: task.message,
            },
          })
        }
      })
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined

    const unsubscribe = ws.onEvent((event) => {
      if (event.type === 'batch_finished') {
        batchFinishedSnapshotGen.current = snapshotGen.current
        const statuses = [...batchStatuses.current.values()]
        const success = statuses.filter((status) => status === 'done').length
        const failed = statuses.filter((status) => status === 'error').length
        const cancelled = statuses.filter((status) => status === 'skipped').length
        const feedback = batchFeedback(success, failed, cancelled)
        dispatch({ type: 'BATCH_FINISHED', feedback })
        batchStatuses.current.clear()
        setCancellingAll(false)
        setCancellingTaskIds(new Set())
        return
      }
      if (event.task_id) {
        if (event.status) {
          batchStatuses.current.set(event.task_id, event.status)
        }
        dispatch({
          type: 'PATCH_TASK',
          taskId: event.task_id,
          patch: patchFromEvent(event),
        })
        if (event.status === 'done' || event.status === 'error' || event.status === 'skipped') {
          setCancellingTaskIds((current) => {
            if (!current.has(event.task_id)) return current
            const next = new Set(current)
            next.delete(event.task_id)
            return next
          })
        }
      }
      if (event.type === 'batch_progress') {
        dispatch({
          type: 'SET_FEEDBACK',
          feedback: `转换进度：${event.done_count} / ${event.total_count}`,
        })
      }
    })
    const unsubscribeClose = ws.onClose(() => {
      if (reconnectTimer !== undefined) clearTimeout(reconnectTimer)
      reconnectTimer = setTimeout(() => {
        ws.connect()
        const gen = ++snapshotGen.current
        void api
          .batch()
          .then((batch) => {
            if (
              gen !== snapshotGen.current ||
              batchFinishedSnapshotGen.current === gen
            ) {
              return
            }
            dispatch({ type: 'SET_CONVERTING', isConverting: batch.is_converting })
            for (const task of batch.tasks) {
              batchStatuses.current.set(task.task_id, task.status)
              dispatch({
                type: 'PATCH_TASK',
                taskId: task.task_id,
                patch: {
                  status: task.status,
                  errorMessage: task.error_message,
                  progressPercent: task.progress_percent,
                  progressPhase: task.progress_phase,
                  progressMessage: task.message,
                },
              })
            }
            if (!batch.is_converting) {
              setCancellingAll(false)
              setCancellingTaskIds(new Set())
            }
          })
          .catch(() => undefined)
      }, 1000)
    })
    ws.connect()
    return () => {
      if (reconnectTimer !== undefined) clearTimeout(reconnectTimer)
      unsubscribe()
      unsubscribeClose()
      ws.disconnect()
    }
  }, [])

  const selectedTasks = useMemo(
    () => state.tasks.filter((task) => task.selected),
    [state.tasks],
  )

  const addPaths = async (paths: string[]) => {
    try {
      const result = await api.scan(paths, state.tasks.map((task) => task.path))
      dispatch({
        type: 'ADD_ENTRIES',
        entries: result.entries.map(queueTaskFromScan),
        feedback: result.message,
      })
    } catch (error) {
      dispatch({ type: 'SET_FEEDBACK', feedback: `扫描失败：${String(error)}` })
    }
  }

  const startConversion = async () => {
    const activeTasks = selectedTasks
    dispatch({ type: 'START_BATCH' })
    batchStatuses.current = new Map(
      activeTasks.map((task) => [task.id, 'pending' as const]),
    )
    setCancellingAll(false)
    setCancellingTaskIds(new Set())
    try {
      await api.convert(
        activeTasks.map((task) => ({
          task_id: task.id,
          path: task.path,
          selected_stream_index: task.selectedStreamIndex,
          is_master_playlist: task.isMasterPlaylist,
        })),
      )
      dispatch({ type: 'SET_FEEDBACK', feedback: `已开始转换 ${activeTasks.length} 个任务` })
    } catch (error) {
      batchStatuses.current.clear()
      dispatch({ type: 'BATCH_FINISHED', feedback: `启动转换失败：${String(error)}` })
    }
  }

  const cancelAll = async () => {
    setCancellingAll(true)
    try {
      await api.cancelAll()
    } catch (error) {
      setCancellingAll(false)
      dispatch({ type: 'SET_FEEDBACK', feedback: `取消失败：${String(error)}` })
    }
  }

  const cancelTask = async (taskId: string) => {
    setCancellingTaskIds((current) => new Set(current).add(taskId))
    try {
      await api.cancelTask(taskId)
    } catch (error) {
      setCancellingTaskIds((current) => {
        const next = new Set(current)
        next.delete(taskId)
        return next
      })
      dispatch({ type: 'SET_FEEDBACK', feedback: `取消任务失败：${String(error)}` })
    }
  }

  const saveConfig = async (config: SidecarConfig) => {
    const saved = await api.putConfig(config)
    dispatch({ type: 'HYDRATE_CONFIG', config: saved })
    dispatch({ type: 'SET_FEEDBACK', feedback: '设置已保存' })
  }

  const changeOutputDirectory = async (outputDirectory: string | null) => {
    const config = { ...state.config, output_directory: outputDirectory }
    dispatch({ type: 'HYDRATE_CONFIG', config })
    try {
      const saved = await api.putConfig(config)
      dispatch({ type: 'HYDRATE_CONFIG', config: saved })
    } catch (error) {
      dispatch({ type: 'SET_FEEDBACK', feedback: `保存输出目录失败：${String(error)}` })
    }
  }

  const changeOutputMode = (mode: 'source' | 'custom') => {
    setOutputMode(mode)
    if (mode === 'source') {
      void changeOutputDirectory(null)
    }
  }

  return (
    <main className="app-shell">
      <TopBar
        ffmpegAvailable={ffmpegAvailable}
        ffmpegMessage={ffmpegMessage}
        sidecarReady={sidecarReady}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <OutputBar
        disabled={state.isConverting}
        outputDirectory={state.config.output_directory as string | null | undefined}
        outputMode={outputMode}
        onDirectoryChange={(directory) => void changeOutputDirectory(directory)}
        onModeChange={changeOutputMode}
      />
      <Toolbar
        canStart={selectedTasks.length > 0 && !state.isConverting && ffmpegAvailable}
        feedback={state.feedback}
        isCancelling={cancellingAll}
        isConverting={state.isConverting}
        selected={selectedTasks.length}
        total={state.tasks.length}
        onCancelAll={() => void cancelAll()}
        onClear={() => dispatch({ type: 'CLEAR' })}
        onSelectAll={() => dispatch({ type: 'SELECT_ALL' })}
        onStart={() => void startConversion()}
      />
      <DropZone disabled={state.isConverting} onAdd={addPaths} />
      <TaskList
        activeBatchIds={state.activeBatchIds}
        cancellingAll={cancellingAll}
        cancellingTaskIds={cancellingTaskIds}
        isConverting={state.isConverting}
        tasks={state.tasks}
        onCancel={(taskId) => void cancelTask(taskId)}
        onStreamChange={(taskId, streamIndex) =>
          dispatch({ type: 'SET_STREAM', taskId, streamIndex })
        }
        onToggle={(taskId) => dispatch({ type: 'TOGGLE_TASK', taskId })}
      />
      {settingsOpen && (
        <SettingsModal
          config={state.config}
          onClose={() => setSettingsOpen(false)}
          onSave={saveConfig}
        />
      )}
    </main>
  )
}

export default App
