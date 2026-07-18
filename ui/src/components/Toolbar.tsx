interface ToolbarProps {
  total: number
  selected: number
  feedback: string
  isConverting: boolean
  canStart: boolean
  onSelectAll: () => void
  onClear: () => void
  onStart: () => void
  onCancelAll: () => void
}

export function Toolbar({
  total,
  selected,
  feedback,
  isConverting,
  canStart,
  onSelectAll,
  onClear,
  onStart,
  onCancelAll,
}: ToolbarProps) {
  return (
    <section className="toolbar" aria-label="队列操作">
      <label>
        <input
          checked={total > 0 && selected === total}
          disabled={isConverting || total === 0}
          type="checkbox"
          onChange={onSelectAll}
        />
        全选
      </label>
      <span className="muted">已选 {selected} / 共 {total}</span>
      <span className="toolbar__feedback">{feedback}</span>
      <div className="toolbar__actions">
        {isConverting ? (
          <button className="button button--danger" type="button" onClick={onCancelAll}>
            取消全部
          </button>
        ) : (
          <button className="button button--primary" disabled={!canStart} type="button" onClick={onStart}>
            开始转换
          </button>
        )}
        <button
          className="button button--ghost"
          disabled={isConverting || total === 0}
          type="button"
          onClick={onClear}
        >
          清空列表
        </button>
      </div>
    </section>
  )
}
