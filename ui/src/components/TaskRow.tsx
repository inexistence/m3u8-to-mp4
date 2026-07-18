import type { QueueTask } from '../types'

interface TaskRowProps {
  task: QueueTask
  disabled: boolean
  cancellable: boolean
  cancelling: boolean
  onToggle: () => void
  onStreamChange: (index: number) => void
  onCancel: () => void
  onToggleError: () => void
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
  cancelling,
  onToggle,
  onStreamChange,
  onCancel,
  onToggleError,
}: TaskRowProps) {
  const hasError = task.status === 'error' && Boolean(task.errorMessage)

  return (
    <article className={`task-row task-row--${task.status}`}>
      <input
        aria-label={`选择 ${task.name}`}
        checked={task.selected}
        disabled={disabled}
        type="checkbox"
        onChange={onToggle}
      />
      <div
        aria-expanded={hasError ? task.errorExpanded : undefined}
        className={`task-row__main${hasError ? ' task-row__main--expandable' : ''}`}
        role={hasError ? 'button' : undefined}
        tabIndex={hasError ? 0 : undefined}
        onClick={hasError ? onToggleError : undefined}
        onKeyDown={
          hasError
            ? (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onToggleError()
                }
              }
            : undefined
        }
      >
        <div className="task-row__title">
          <strong title={task.path}>{task.name}</strong>
          <span className={`status-pill status-pill--${task.status}`}>{statusText[task.status]}</span>
        </div>
        <span className="task-row__directory">{task.directory || task.path}</span>
        {task.progressMessage && <span className="task-row__message">{task.progressMessage}</span>}
        {hasError && task.errorExpanded && (
          <div className="task-row__error-details">
            <pre className="task-row__error">{task.errorMessage}</pre>
            <button
              className="button button--secondary button--small"
              type="button"
              onClick={(event) => {
                event.stopPropagation()
                void navigator.clipboard.writeText(task.errorMessage)
              }}
            >
              复制错误
            </button>
          </div>
        )}
        {task.progressPercent !== null && (
          <div
            aria-valuemax={100}
            aria-valuemin={0}
            aria-valuenow={task.progressPercent}
            className="task-row__progress"
            role="progressbar"
          >
            <div
              className="task-row__progress-fill"
              style={{
                width: `${task.progressPercent}%`,
                transition: 'width 160ms linear',
              }}
            />
          </div>
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
          <button
            className="button button--danger button--small"
            disabled={cancelling}
            type="button"
            onClick={onCancel}
          >
            {cancelling ? '正在取消…' : '取消'}
          </button>
        )}
      </div>
    </article>
  )
}
