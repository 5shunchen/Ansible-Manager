/** WebSocket 客户端封装：token 走 query、自动重连、心跳。 */
export class WsClient {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private closed = false

  constructor(
    private url: string,
    private onMessage: (data: any) => void,
    private onOpen?: () => void,
    private onClose?: () => void,
  ) {}

  connect() {
    const token = localStorage.getItem('token') || ''
    const sep = this.url.includes('?') ? '&' : '?'
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${proto}://${location.host}${this.url}${sep}token=${encodeURIComponent(token)}`
    this.ws = new WebSocket(url)
    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this.onOpen?.()
    }
    this.ws.onmessage = (ev) => {
      try {
        this.onMessage(JSON.parse(ev.data))
      } catch { /* ignore */ }
    }
    this.ws.onclose = () => {
      if (this.closed) return
      this.onClose?.()
      // 指数退避重连（最多 5 次）
      if (this.reconnectAttempts < 5) {
        this.reconnectAttempts++
        setTimeout(() => this.connect(), 1000 * this.reconnectAttempts)
      }
    }
  }

  send(data: any) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(data))
  }

  close() {
    this.closed = true
    this.ws?.close()
  }
}
