import type { QueueTask } from '../types'

interface TaskRowProps {
  task: QueueTask
  disabled: boolean
  cancellable: boolean
  onToggle: () => void
  onStreamChange: (index: number) => void
  onCancel: () => void
}

const statusText: Record<QueueTask['status'], string> = {
  pending: '等待中',
  running: '转换中',
  done: '已完成',
  error: '失败',
  skipped: '已跳过',
}

export function TaskRow({
  task,
  disabled,
  cancellable,
  onToggle,
  onStreamChange,
  onCancel,
}: TaskRowProps) {
  return (
    <article className={`task-row task-row--${task.status}`}>
      <input
        aria-label={`选择 ${task.name}`}
        checked={task.selected}
        disabled={disabled}
        type="checkbox"
        onChange={onToggle}
      />
      <div className="task-row__main">
        <div className="task-row__title">
          <strong title={task.path}>{task.name}</strong>
          <span className={`status-pill status-pill--${task.status}`}>{statusText[task.status]}</span>
        </div>
        <span className="task-row__directory">{task.directory || task.path}</span>
        {task.progressMessage && <span className="task-row__message">{task.progressMessage}</span>}
        {task.errorMessage && <pre className="task-row__error">{task.errorMessage}</pre>}
        {task.progressPercent !== null && (
          <progress max="100" value={task.progressPercent}>
            {task.progressPercent}%
          </progress>
        )}
      </div>
      <div className="task-row__options">
        {task.isMasterPlaylist && task.streamLabels.length > 0 && (
          <select
            aria-label={`${task.name} 码流`}
            disabled={disabled}
            value={task.selectedStreamIndex}
            onChange={(event) => onStreamChange(Number(event.target.value))}
          >
            {task.streamLabels.map((label, index) => (
              <option key={`${label}-${index}`} value={index}>
                {label}
              </option>
            ))}
          </select>
        )}
        {cancellable && (
          <button className="button button--danger button--small" type="button" onClick={onCancel}>
            取消
          </button>
        )}
      </div>
    </article>
  )
}
