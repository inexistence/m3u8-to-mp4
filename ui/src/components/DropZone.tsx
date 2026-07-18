import { useState } from 'react'

interface DropZoneProps {
  disabled: boolean
  onAdd: (paths: string[]) => Promise<void>
}

export function DropZone({ disabled, onAdd }: DropZoneProps) {
  const [value, setValue] = useState('')
  const [isAdding, setIsAdding] = useState(false)

  const submit = async (paths: string[]) => {
    const cleanPaths = paths.map((path) => path.trim()).filter(Boolean)
    if (cleanPaths.length === 0) return
    setIsAdding(true)
    try {
      await onAdd(cleanPaths)
      setValue('')
    } finally {
      setIsAdding(false)
    }
  }

  return (
    <section className="drop-zone">
      <div className="drop-zone__copy">
        <strong>添加 m3u8 文件或目录</strong>
        <span>桌面版将支持拖放与原生选文件；当前请粘贴绝对路径</span>
      </div>
      <textarea
        aria-label="路径列表"
        disabled={disabled || isAdding}
        placeholder={'每行一个文件或目录路径\n例如：C:\\Videos\\episode-01'}
        rows={3}
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
      <div className="drop-zone__actions">
        <button
          className="button button--primary"
          disabled={disabled || isAdding || !value.trim()}
          type="button"
          onClick={() => void submit(value.split(/\r?\n/))}
        >
          {isAdding ? '正在扫描…' : '添加到队列'}
        </button>
      </div>
    </section>
  )
}
