import { renderHook } from '@testing-library/react'
import { useEventSource } from '../hooks/useEventSource'

class MockEventSource {
  url: string
  onopen: any
  onmessage: any
  onerror: any
  constructor(url: string) {
    this.url = url
    setTimeout(() => this.onopen?.({}), 0)
    setTimeout(() => this.onmessage?.({ data: JSON.stringify({ type: 'log', data: { message: 'hi' } }) }), 1)
  }
  close() {}
}
// @ts-ignore
global.EventSource = MockEventSource as any

test('useEventSource goes online and buffers messages', async () => {
  const { result } = renderHook(() => useEventSource('http://localhost/stream'))
  await new Promise(r => setTimeout(r, 5))
  expect(result.current.online).toBe(true)
  expect(result.current.messages.length).toBeGreaterThan(0)
})
