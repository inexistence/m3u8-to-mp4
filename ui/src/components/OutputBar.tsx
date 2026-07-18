import { useEffect, useState } from 'react'

interface OutputBarProps {
  outputDirectory?: string | null
  disabled: boolean
  onChange: (directory: string | null) => void
}

export function OutputBar({ outputDirectory, disabled, onChange }: OutputBarProps) {
  const custom = outputDirectory !== null && outputDirectory !== undefined
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
          onClick={() => onChange(null)}
        >
          源目录
        </button>
        <button
          className={custom ? 'segmented__active' : ''}
          disabled={disabled}
          type="button"
          onClick={() => onChange(outputDirectory || '')}
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
          if (custom && draft !== outputDirectory) onChange(draft)
        }}
        onChange={(event) => setDraft(event.target.value)}
      />
    </section>
  )
}
