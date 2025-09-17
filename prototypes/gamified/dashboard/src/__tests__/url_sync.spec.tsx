import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import App from '../App'

class FakeES { onopen:any; onerror:any; onmessage:any; constructor(public url:string){ setTimeout(()=>this.onopen&&this.onopen({}),0)} close(){} }

describe('URL sync for filters', () => {
  beforeEach(() => {
    ;(global as any).EventSource = FakeES as any
    ;(global as any).fetch = vi.fn(async (url: string) => {
      return new Response(JSON.stringify({ ok: true, items: [] }))
    })
  })

  it('updates search params when filters change', async () => {
    render(<App />)
    const logsTab = await screen.findByRole('tab', { name: /logs/i })
    fireEvent.click(logsTab)
    const search = await screen.findByPlaceholderText('Search logs')
    fireEvent.change(search, { target: { value: 'error spike' }})
    expect(decodeURIComponent(window.location.search)).toContain('tab=logs')
    expect(decodeURIComponent(window.location.search)).toContain('q=error spike')
  })
})

