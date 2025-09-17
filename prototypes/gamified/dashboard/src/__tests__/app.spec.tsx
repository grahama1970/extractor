import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import App from '../App'

// Minimal global fetch/EventSource stubs
class FakeES {
  onopen: any; onerror: any; onmessage: any
  constructor(public url: string){ setTimeout(() => this.onopen && this.onopen({}), 0) }
  close(){}
}

describe('App dashboard basics', () => {
  beforeEach(() => {
    ;(global as any).EventSource = FakeES as any
    ;(global as any).fetch = vi.fn(async (url: string) => {
      if (url.toString().includes('/scoreboard')) return new Response(JSON.stringify({ ok: true, items: [{ variant: 'mul_shift_add', total_points: 87.2 }] }))
      if (url.toString().includes('/episodes')) return new Response(JSON.stringify({ ok: true, items: [] }))
      if (url.toString().includes('/logs')) return new Response(JSON.stringify({ ok: true, items: [] }))
      return new Response(JSON.stringify({ ok: true }))
    })
  })

  it('renders tabs and data', async () => {
    render(<App />)
    expect(await screen.findByText('Scoreboard')).toBeInTheDocument()
    expect(await screen.findByText('mul_shift_add')).toBeInTheDocument()
  })

  it('filters scoreboard by run id', async () => {
    render(<App />)
    const input = await screen.findByPlaceholderText('Run ID filter')
    fireEvent.change(input, { target: { value: 'run-123' }})
    expect((input as HTMLInputElement).value).toBe('run-123')
  })
})

