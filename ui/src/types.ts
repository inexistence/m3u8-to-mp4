export type TaskStatus = 'pending' | 'running' | 'done' | 'error' | 'skipped'

export interface QueueTask {
  id: string
  path: string
  name: string
  directory: string
  selected: boolean
  isMasterPlaylist: boolean
  streamLabels: string[]
  selectedStreamIndex: number
  status: TaskStatus
  errorMessage: string
  progressPercent: number | null
  progressPhase: string
  progressMessage: string
  errorExpanded: boolean
}

export interface ScanEntry {
  task_id: string
  path: string
  is_master_playlist: boolean
  stream_labels: string[]
  selected_stream_index: number
}

export interface ScanResult {
  entries: ScanEntry[]
  added: number
  duplicates: number
  unparseable: number
  message: string
}

export interface ConvertTaskInput {
  task_id: string
  path: string
  selected_stream_index: number
  is_master_playlist: boolean
}

export interface SidecarConfig {
  skip_first_part?: boolean
  output_file_name?: string
  output_directory?: string
  reset_decryption_if_part_changed?: boolean
  aes_iv_mode?: string
  max_parallel_conversions?: number
  [key: string]: unknown
}

export interface BatchTaskSnapshot {
  task_id: string
  status: TaskStatus
  error_message: string
  progress_percent: number | null
  progress_phase: string
  message: string
}

export interface BatchSnapshot {
  is_converting: boolean
  tasks: BatchTaskSnapshot[]
}

export interface SidecarEvent {
  type: string
  task_id: string
  message: string
  done_count: number
  total_count: number
  progress_percent: number | null
  progress_phase: string
  status: TaskStatus | ''
  error_message: string
}
