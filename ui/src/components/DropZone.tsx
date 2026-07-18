import { useRef, useState, type ChangeEvent } from 'react'

interface DropZoneProps {
  disabled: boolean
  onAdd: (paths: string[]) => Promise<void>
}

interface PathFile extends File {
  path?: string
  webkitRelativePath: string
}

function pathsFromFiles(files: FileList | null): string[] {
  return Array.from(files ?? [], (file) => {
    const pathFile = file as PathFile
    return pathFile.path || pathFile.webkitRelativePath || pathFile.name
  })
}

export function DropZone({ disabled, onAdd }: DropZoneProps) {
  const [value, setValue] = useState('')
  const [isAdding, setIsAdding] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)

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

  const selectFiles = (event: ChangeEvent<HTMLInputElement>) => {
    void submit(pathsFromFiles(event.target.files))
    event.target.value = ''
  }

  return (
    <section className="drop-zone">
      <div className="drop-zone__copy">
        <strong>添加 m3u8 文件或目录</strong>
        <span>桌面版将在 Phase 3 支持系统拖放；当前可粘贴本机绝对路径。</span>
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
        <button
          className="button button--secondary"
          disabled={disabled || isAdding}
          type="button"
          onClick={() => fileInput.current?.click()}
        >
          选择文件
        </button>
        <button
          className="button button--secondary"
          disabled={disabled || isAdding}
          type="button"
          onClick={() => folderInput.current?.click()}
        >
          选择文件夹
        </button>
        <input
          ref={fileInput}
          className="visually-hidden"
          accept=".m3u8,application/vnd.apple.mpegurl"
          multiple
          type="file"
          onChange={selectFiles}
        />
        <input
          ref={folderInput}
          className="visually-hidden"
          multiple
          type="file"
          {...({ webkitdirectory: '' } as Record<string, string>)}
          onChange={selectFiles}
        />
      </div>
    </section>
  )
}
