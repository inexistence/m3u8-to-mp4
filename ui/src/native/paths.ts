import { open } from '@tauri-apps/plugin-dialog'

export async function pickM3u8Files(): Promise<string[]> {
  const selected = await open({
    multiple: true,
    filters: [{ name: 'm3u8', extensions: ['m3u8'] }],
  })
  if (selected === null) return []
  return Array.isArray(selected) ? selected : [selected]
}

export async function pickDirectory(): Promise<string | null> {
  const selected = await open({ directory: true, multiple: false })
  return typeof selected === 'string' ? selected : null
}
