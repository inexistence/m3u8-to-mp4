import type { QueueTask, ScanEntry, SidecarConfig } from '../types'

export type { QueueTask } from '../types'

export interface QueueState {
  tasks: QueueTask[]
  config: SidecarConfig
  feedback: string
  isConverting: boolean
  activeBatchIds: string[]
}

export type QueueAction =
  | { type: 'HYDRATE_CONFIG'; config: SidecarConfig }
  | {
      type: 'ADD_ENTRIES'
      entries: Array<QueueTask | ScanEntry>
      feedback: string
    }
  | { type: 'TOGGLE_TASK'; taskId: string }
  | { type: 'SET_STREAM'; taskId: string; streamIndex: number }
  | { type: 'TOGGLE_ERROR_EXPANDED'; taskId: string }
  | { type: 'SELECT_ALL'; selected?: boolean }
  | { type: 'CLEAR' }
  | { type: 'START_BATCH' }
  | { type: 'PATCH_TASK'; taskId: string; patch: Partial<QueueTask> }
  | { type: 'BATCH_FINISHED'; feedback?: string }
  | { type: 'SET_FEEDBACK'; feedback: string }
  | { type: 'SET_CONVERTING'; isConverting: boolean }

export const initialQueueState: QueueState = {
  tasks: [],
  config: {},
  feedback: '',
  isConverting: false,
  activeBatchIds: [],
}

function splitPath(path: string): { name: string; directory: string } {
  const separatorIndex = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'))
  if (separatorIndex === -1) {
    return { name: path, directory: '' }
  }
  return {
    name: path.slice(separatorIndex + 1),
    directory: path.slice(0, separatorIndex),
  }
}

function isQueueTask(entry: QueueTask | ScanEntry): entry is QueueTask {
  return 'id' in entry
}

function toQueueTask(entry: QueueTask | ScanEntry): QueueTask {
  if (isQueueTask(entry)) {
    return entry
  }

  const { name, directory } = splitPath(entry.path)
  return {
    id: entry.task_id || crypto.randomUUID(),
    path: entry.path,
    name,
    directory,
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

function patchTask(
  tasks: QueueTask[],
  taskId: string,
  patch: Partial<QueueTask>,
): QueueTask[] {
  return tasks.map((task) => (task.id === taskId ? { ...task, ...patch } : task))
}

export function queueReducer(state: QueueState, action: QueueAction): QueueState {
  switch (action.type) {
    case 'HYDRATE_CONFIG':
      return { ...state, config: action.config }
    case 'ADD_ENTRIES': {
      const knownPaths = new Set(state.tasks.map((task) => task.path))
      const additions: QueueTask[] = []
      for (const entry of action.entries) {
        if (knownPaths.has(entry.path)) {
          continue
        }
        knownPaths.add(entry.path)
        additions.push(toQueueTask(entry))
      }
      return {
        ...state,
        tasks: [...state.tasks, ...additions],
        feedback: action.feedback,
      }
    }
    case 'TOGGLE_TASK': {
      if (state.isConverting) {
        return state
      }
      const task = state.tasks.find((item) => item.id === action.taskId)
      return task
        ? {
            ...state,
            tasks: patchTask(state.tasks, action.taskId, {
              selected: !task.selected,
            }),
          }
        : state
    }
    case 'SET_STREAM':
      return {
        ...state,
        tasks: patchTask(state.tasks, action.taskId, {
          selectedStreamIndex: action.streamIndex,
        }),
      }
    case 'TOGGLE_ERROR_EXPANDED': {
      const task = state.tasks.find((item) => item.id === action.taskId)
      if (!task?.errorMessage) return state
      return {
        ...state,
        tasks: patchTask(state.tasks, action.taskId, {
          errorExpanded: !task.errorExpanded,
        }),
      }
    }
    case 'SELECT_ALL': {
      if (state.isConverting) {
        return state
      }
      const selected =
        action.selected ?? state.tasks.some((task) => !task.selected)
      return {
        ...state,
        tasks: state.tasks.map((task) => ({ ...task, selected })),
      }
    }
    case 'CLEAR':
      return state.isConverting
        ? state
        : { ...state, tasks: [], activeBatchIds: [], feedback: '' }
    case 'START_BATCH':
      return {
        ...state,
        isConverting: true,
        tasks: state.tasks.map((task) =>
          task.selected
            ? {
                ...task,
                status: 'pending',
                errorMessage: '',
                errorExpanded: false,
                progressPercent: null,
                progressPhase: '',
                progressMessage: '',
              }
            : task,
        ),
        activeBatchIds: state.tasks
          .filter((task) => task.selected)
          .map((task) => task.id),
      }
    case 'PATCH_TASK':
      return {
        ...state,
        tasks: patchTask(state.tasks, action.taskId, action.patch),
      }
    case 'BATCH_FINISHED':
      return {
        ...state,
        isConverting: false,
        activeBatchIds: [],
        feedback: action.feedback ?? state.feedback,
      }
    case 'SET_FEEDBACK':
      return { ...state, feedback: action.feedback }
    case 'SET_CONVERTING':
      return {
        ...state,
        isConverting: action.isConverting,
        activeBatchIds: action.isConverting ? state.activeBatchIds : [],
      }
  }
}
