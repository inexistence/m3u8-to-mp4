import type {
  BatchSnapshot,
  ConvertTaskInput,
  ScanResult,
  SidecarConfig,
} from '../types'

async function json<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(input, { ...init, headers })
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => json<{ ok: boolean }>('/api/health'),
  getConfig: () => json<SidecarConfig>('/api/config'),
  putConfig: (body: SidecarConfig) =>
    json<SidecarConfig>('/api/config', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  scan: (paths: string[], knownPaths: string[]) =>
    json<ScanResult>('/api/scan', {
      method: 'POST',
      body: JSON.stringify({ paths, known_paths: knownPaths }),
    }),
  convert: (tasks: ConvertTaskInput[]) =>
    json<{ ok: boolean }>('/api/convert', {
      method: 'POST',
      body: JSON.stringify({ tasks }),
    }),
  cancelAll: () =>
    json<{ ok: boolean }>('/api/cancel', {
      method: 'POST',
      body: '{}',
    }),
  cancelTask: (taskId: string) =>
    json<{ ok: boolean }>(`/api/cancel/${encodeURIComponent(taskId)}`, {
      method: 'POST',
      body: '{}',
    }),
  batch: () => json<BatchSnapshot>('/api/batch'),
  ffmpegStatus: () =>
    json<{ available: boolean; message: string }>('/api/ffmpeg-status'),
}
