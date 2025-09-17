import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import App from '../App'

class FakeES { onopen:any; onerror:any; onmessage:any; constructor(public url:string){ setTimeout(()=>this.onopen&&this.onopen({}),0)} close(){} }

function makeLogs(n:number){
  return Array.from({length:n}).map((_,i)=>({
    ts: Math.floor(Date.now()/1000) - (n-i),
    run_id: 'demo-run',
    variant: ['alpha','beta','gamma'][i%3],
    source: i%10===0?'codex':'app',
    stream: i%2===0?'stdout':'app',
    message: `demo-item-${String(i).padStart(5,'0')} ${i%10===0?'error spike':'ok'}`
  }))
}

describe('Logs virtualization and search', () => {
  beforeEach(() => {
    ;(global as any).EventSource = FakeES as any
    ;(global as any).fetch = vi.fn(async (url: string) => {
      if (url.includes('/scoreboard')) return new Response(JSON.stringify({ ok: true, items: [] }))
      if (url.includes('/episodes')) return new Response(JSON.stringify({ ok: true, items: [] }))
      if (url.includes('/logs')) return new Response(JSON.stringify({ ok: true, items: makeLogs(1000) }))
      return new Response(JSON.stringify({ ok: true }))
    })
  })

  it('renders virtualized rows and filters via fuzzy search', async () => {
    render(<App />)
    // Open logs tab
    const logsTab = await screen.findByRole('tab', { name: /logs/i })
    fireEvent.click(logsTab)

    // Apply to fetch
    const applyBtn = await screen.findByRole('button', { name: /apply/i })
    fireEvent.click(applyBtn)

    // Wait for some row content
    const messageHeader = await screen.findByText('Message')
    expect(messageHeader).toBeInTheDocument()

    // Fuzzy search
    const search = screen.getByPlaceholderText('Search logs')
    fireEvent.change(search, { target: { value: 'error spike' }})

    // Virtualized list shows some matching row
    const anyRow = await screen.findByText(/error spike/i)
    expect(anyRow).toBeInTheDocument()
  })
})

