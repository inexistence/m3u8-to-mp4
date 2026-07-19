interface TopBarProps {
  sidecarReady: boolean
  ffmpegAvailable: boolean
  ffmpegMessage: string
  settingsDisabled?: boolean
  onOpenSettings: () => void
}

export function TopBar({
  sidecarReady,
  ffmpegAvailable,
  ffmpegMessage,
  settingsDisabled = false,
  onOpenSettings,
}: TopBarProps) {
  return (
    <header className="top-bar">
      <div>
        <h1>m3u8 → mp4</h1>
        <p>本地视频转换队列</p>
      </div>
      <div className="top-bar__actions">
        <span className={sidecarReady ? 'status status--ok' : 'status status--error'}>
          {sidecarReady ? 'Sidecar 已连接' : 'Sidecar 未连接'}
        </span>
        <span
          className={ffmpegAvailable ? 'status status--ok' : 'status status--error'}
          title={ffmpegMessage}
        >
          {ffmpegAvailable ? 'FFmpeg 可用' : 'FFmpeg 不可用'}
        </span>
        <button
          className="button button--secondary"
          disabled={settingsDisabled}
          type="button"
          onClick={onOpenSettings}
        >
          设置
        </button>
      </div>
    </header>
  )
}
