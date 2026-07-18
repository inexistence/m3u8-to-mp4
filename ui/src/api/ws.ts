import type { SidecarEvent } from '../types'

type EventListener = (event: SidecarEvent) => void
type CloseListener = () => void

class SidecarWebSocket {
  private socket: WebSocket | null = null
  private baseUrl = ''
  private readonly listeners = new Set<EventListener>()
  private readonly closeListeners = new Set<CloseListener>()

  setBaseUrl(baseUrl: string): void {
    this.baseUrl = baseUrl.replace(/\/$/, '')
  }

  connect(): void {
    if (
      this.socket?.readyState === WebSocket.OPEN ||
      this.socket?.readyState === WebSocket.CONNECTING
    ) {
      return
    }

    const source = this.baseUrl ? new URL(this.baseUrl) : location
    const protocol = source.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${protocol}://${source.host}/ws`)
    this.socket = socket
    socket.onmessage = (message) => {
      const event = JSON.parse(String(message.data)) as SidecarEvent
      for (const listener of this.listeners) {
        listener(event)
      }
    }
    socket.onclose = (event) => {
      if (event.target === this.socket) {
        this.socket = null
        for (const listener of this.closeListeners) {
          listener()
        }
      }
    }
  }

  disconnect(): void {
    const socket = this.socket
    this.socket = null
    if (socket) {
      socket.onclose = null
      socket.close()
    }
  }

  onEvent(listener: EventListener): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  onClose(listener: CloseListener): () => void {
    this.closeListeners.add(listener)
    return () => {
      this.closeListeners.delete(listener)
    }
  }
}

export const ws = new SidecarWebSocket()
