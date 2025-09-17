import { useEffect, useRef, useState } from 'react'

export type SSEMessage = any

export function useEventSource(url: string | null, { paused = false } = {}) {
  const [online, setOnline] = useState(false)
  const [messages, setMessages] = useState<SSEMessage[]>([])
  const esRef = useRef<EventSource | null>(null)
  const backoffRef = useRef(1000)
  const pausedRef = useRef(paused)

  useEffect(() => { pausedRef.current = paused }, [paused])

  useEffect(() => {
    let cancelled = false
    if (!url) return

    const connect = () => {
      if (cancelled || pausedRef.current) return
      try {
        const es = new EventSource(url)
        esRef.current = es
        es.onopen = () => { setOnline(true); backoffRef.current = 1000 }
        es.onerror = () => { setOnline(false); es.close(); scheduleReconnect() }
        es.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data)
            setMessages((m) => [...m.slice(-999), data])
          } catch {
            // ignore
          }
        }
      } catch {
        scheduleReconnect()
      }
    }

    const scheduleReconnect = () => {
      if (cancelled) return
      const t = setTimeout(() => connect(), backoffRef.current)
      backoffRef.current = Math.min(backoffRef.current * 2, 15000)
      return () => clearTimeout(t)
    }

    connect()
    return () => {
      cancelled = true
      try { esRef.current?.close() } catch {}
    }
  }, [url])

  return { online, messages }
}

