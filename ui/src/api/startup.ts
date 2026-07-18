import { invoke } from '@tauri-apps/api/core'

type Invoke = (command: string) => Promise<unknown>
type HealthApi = { health: () => Promise<{ ok: boolean }> }

export function isTauri(): boolean {
  return '__TAURI_INTERNALS__' in window
}

export async function resolveSidecarBase(
  tauri = isTauri(),
  invokeCommand: Invoke = invoke,
): Promise<string> {
  return tauri ? String(await invokeCommand('get_sidecar_base')) : ''
}

export async function waitForHealth(
  api: HealthApi,
  options: { attempts?: number; intervalMs?: number } = {},
): Promise<void> {
  const attempts = options.attempts ?? 20
  const intervalMs = options.intervalMs ?? 500

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      if ((await api.health()).ok) return
    } catch {
      // The process may still be binding its socket.
    }
    if (attempt + 1 < attempts && intervalMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, intervalMs))
    }
  }

  throw new Error('sidecar health check timed out')
}
