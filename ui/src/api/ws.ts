import type { SidecarEvent } from '../types'

type EventListener = (event: SidecarEvent) => void

class SidecarWebSocket {
  private socket: WebSocket | null = null
  private readonly listeners = new Set<EventListener>()

  connect(): void {
    if (
      this.socket?.readyState === WebSocket.OPEN ||
      this.socket?.readyState === WebSocket.CONNECTING
    ) {
      return
    }

    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    this.socket = new WebSocket(`${protocol}://${location.host}/ws`)
    this.socket.onmessage = (message) => {
      const event = JSON.parse(String(message.data)) as SidecarEvent
      for (const listener of this.listeners) {
        listener(event)
      }
    }
    this.socket.onclose = () => {
      this.socket = null
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
}

export const ws = new SidecarWebSocket()
