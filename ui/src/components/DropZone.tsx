import { useState } from 'react'
import { isTauri } from '../api/startup'
import { pickDirectory, pickM3u8Files } from '../native/paths'

interface DropZoneProps {
  /** Only for transient busy state (e.g. scanning); not tied to conversion. */
  disabled?: boolean
  onAdd: (paths: string[]) => Promise<void>
}

export function DropZone({ disabled = false, onAdd }: DropZoneProps) {
  const [value, setValue] = useState('')
  const [isAdding, setIsAdding] = useState(false)
  const tauri = isTauri()

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

  const pickFiles = async () => {
    setIsAdding(true)
    try {
      const paths = await pickM3u8Files()
      if (paths.length > 0) await onAdd(paths)
    } finally {
      setIsAdding(false)
    }
  }

  const pickFolder = async () => {
    setIsAdding(true)
    try {
      const directory = await pickDirectory()
      if (directory) await onAdd([directory])
    } finally {
      setIsAdding(false)
    }
  }

  return (
    <section className="drop-zone">
      <div className="drop-zone__copy">
        <strong>添加 m3u8 文件或目录</strong>
        <span>
          {tauri
            ? '可拖放路径、选择文件/文件夹，或粘贴绝对路径'
            : '当前为浏览器模式，请粘贴绝对路径'}
        </span>
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
        {tauri && (
          <>
            <button
              className="button button--secondary"
              disabled={disabled || isAdding}
              type="button"
              onClick={() => void pickFiles()}
            >
              选择文件
            </button>
            <button
              className="button button--secondary"
              disabled={disabled || isAdding}
              type="button"
              onClick={() => void pickFolder()}
            >
              选择文件夹
            </button>
          </>
        )}
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
