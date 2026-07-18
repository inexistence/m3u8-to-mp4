import { useEffect, useState } from 'react'

interface OutputBarProps {
  outputDirectory?: string | null
  outputMode: 'source' | 'custom'
  disabled: boolean
  onDirectoryChange: (directory: string) => void
  onModeChange: (mode: 'source' | 'custom') => void
}

export function OutputBar({
  outputDirectory,
  outputMode,
  disabled,
  onDirectoryChange,
  onModeChange,
}: OutputBarProps) {
  const custom = outputMode === 'custom'
  const [draft, setDraft] = useState(outputDirectory ?? '')

  useEffect(() => {
    setDraft(outputDirectory ?? '')
  }, [outputDirectory])

  return (
    <section className="output-bar" aria-label="输出设置">
      <strong>输出到</strong>
      <div className="segmented">
        <button
          className={!custom ? 'segmented__active' : ''}
          disabled={disabled}
          type="button"
          onClick={() => onModeChange('source')}
        >
          源目录
        </button>
        <button
          className={custom ? 'segmented__active' : ''}
          disabled={disabled}
          type="button"
          onClick={() => onModeChange('custom')}
        >
          指定目录
        </button>
      </div>
      <input
        aria-label="输出目录"
        disabled={disabled || !custom}
        placeholder={custom ? '输入输出目录' : '每个源文件所在目录'}
        value={draft}
        onBlur={() => {
          if (custom && draft.trim() && draft !== outputDirectory) onDirectoryChange(draft)
        }}
        onChange={(event) => setDraft(event.target.value)}
      />
    </section>
  )
}
