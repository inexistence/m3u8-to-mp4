import type { QueueTask } from '../types'
import { TaskRow } from './TaskRow'

interface TaskListProps {
  tasks: QueueTask[]
  isConverting: boolean
  activeBatchIds: string[]
  onToggle: (taskId: string) => void
  onStreamChange: (taskId: string, index: number) => void
  onCancel: (taskId: string) => void
}

export function TaskList({
  tasks,
  isConverting,
  activeBatchIds,
  onToggle,
  onStreamChange,
  onCancel,
}: TaskListProps) {
  if (tasks.length === 0) {
    return <div className="empty-state">队列为空，请粘贴路径或选择 .m3u8 文件添加任务</div>
  }

  return (
    <section className="task-list" aria-label="转换队列">
      {tasks.map((task) => (
        <TaskRow
          key={task.id}
          cancellable={
            isConverting &&
            activeBatchIds.includes(task.id) &&
            (task.status === 'pending' || task.status === 'running')
          }
          disabled={isConverting}
          task={task}
          onCancel={() => onCancel(task.id)}
          onStreamChange={(index) => onStreamChange(task.id, index)}
          onToggle={() => onToggle(task.id)}
        />
      ))}
    </section>
  )
}
