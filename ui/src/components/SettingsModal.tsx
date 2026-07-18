import { useState, type FormEvent } from 'react'
import type { SidecarConfig } from '../types'

interface SettingsModalProps {
  config: SidecarConfig
  onClose: () => void
  onSave: (config: SidecarConfig) => Promise<void>
}

export function SettingsModal({ config, onClose, onSave }: SettingsModalProps) {
  const [draft, setDraft] = useState(config)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await onSave(draft)
      onClose()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '保存设置失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        aria-labelledby="settings-title"
        aria-modal="true"
        className="settings-modal"
        role="dialog"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <form onSubmit={(event) => void submit(event)}>
          <header className="settings-modal__header">
            <div>
              <h2 id="settings-title">转换设置</h2>
              <p>保存后将在下一批转换中生效。</p>
            </div>
            <button aria-label="关闭设置" className="icon-button" type="button" onClick={onClose}>
              ×
            </button>
          </header>
          <div className="settings-grid">
            <label>
              输出文件名
              <input
                value={String(draft.output_file_name ?? '')}
                onChange={(event) => setDraft({ ...draft, output_file_name: event.target.value })}
              />
            </label>
            <label>
              AES IV 模式
              <select
                value={String(draft.aes_iv_mode ?? 'auto')}
                onChange={(event) => setDraft({ ...draft, aes_iv_mode: event.target.value })}
              >
                <option value="auto">自动检测</option>
                <option value="prepended">前置 IV</option>
                <option value="hls">HLS 标准 IV</option>
              </select>
            </label>
            <label>
              同时转换数
              <input
                max="8"
                min="1"
                type="number"
                value={Number(draft.max_parallel_conversions ?? 2)}
                onChange={(event) =>
                  setDraft({ ...draft, max_parallel_conversions: Number(event.target.value) })
                }
              />
            </label>
            <label className="check-field">
              <input
                checked={Boolean(draft.skip_first_part)}
                type="checkbox"
                onChange={(event) => setDraft({ ...draft, skip_first_part: event.target.checked })}
              />
              跳过分段前第一段内容
            </label>
            <label className="check-field">
              <input
                checked={Boolean(draft.reset_decryption_if_part_changed)}
                type="checkbox"
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    reset_decryption_if_part_changed: event.target.checked,
                  })
                }
              />
              分段切换时重置解密器
            </label>
          </div>
          {error && <p className="form-error">{error}</p>}
          <footer className="settings-modal__footer">
            <button className="button button--secondary" type="button" onClick={onClose}>
              取消
            </button>
            <button className="button button--primary" disabled={saving} type="submit">
              {saving ? '保存中…' : '保存设置'}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}
