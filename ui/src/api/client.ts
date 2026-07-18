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

export function createApi(base = '') {
  const url = (path: string) => `${base.replace(/\/$/, '')}${path}`

  return {
    health: () => json<{ ok: boolean }>(url('/api/health')),
    getConfig: () => json<SidecarConfig>(url('/api/config')),
    putConfig: (body: SidecarConfig) =>
      json<SidecarConfig>(url('/api/config'), {
        method: 'PUT',
        body: JSON.stringify(body),
      }),
    scan: (paths: string[], knownPaths: string[]) =>
      json<ScanResult>(url('/api/scan'), {
        method: 'POST',
        body: JSON.stringify({ paths, known_paths: knownPaths }),
      }),
    convert: (tasks: ConvertTaskInput[]) =>
      json<{ ok: boolean }>(url('/api/convert'), {
        method: 'POST',
        body: JSON.stringify({ tasks }),
      }),
    cancelAll: () =>
      json<{ ok: boolean }>(url('/api/cancel'), {
        method: 'POST',
        body: '{}',
      }),
    cancelTask: (taskId: string) =>
      json<{ ok: boolean }>(url(`/api/cancel/${encodeURIComponent(taskId)}`), {
        method: 'POST',
        body: '{}',
      }),
    batch: () => json<BatchSnapshot>(url('/api/batch')),
    ffmpegStatus: () =>
      json<{ available: boolean; message: string }>(url('/api/ffmpeg-status')),
  }
}

export type ApiClient = ReturnType<typeof createApi>

export const api = createApi()
