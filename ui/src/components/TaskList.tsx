import { AnimatePresence, motion } from 'framer-motion'
import type { QueueTask } from '../types'
import { TaskRow } from './TaskRow'

interface TaskListProps {
  tasks: QueueTask[]
  isConverting: boolean
  activeBatchIds: string[]
  cancellingAll: boolean
  cancellingTaskIds: Set<string>
  onToggle: (taskId: string) => void
  onStreamChange: (taskId: string, index: number) => void
  onCancel: (taskId: string) => void
}

export function TaskList({
  tasks,
  isConverting,
  activeBatchIds,
  cancellingAll,
  cancellingTaskIds,
  onToggle,
  onStreamChange,
  onCancel,
}: TaskListProps) {
  if (tasks.length === 0) {
    return <div className="empty-state">队列为空，请粘贴路径或选择 .m3u8 文件添加任务</div>
  }

  return (
    <section className="task-list" aria-label="转换队列">
      <AnimatePresence initial={false}>
        {tasks.map((task) => (
          <motion.div
            key={task.id}
            layout
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
          >
            <TaskRow
              cancelling={cancellingAll || cancellingTaskIds.has(task.id)}
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
          </motion.div>
        ))}
      </AnimatePresence>
    </section>
  )
}
