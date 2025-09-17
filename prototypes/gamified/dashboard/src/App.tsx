import React from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from './components/ui/card'
import { Button } from './components/ui/button'
import { Input } from './components/ui/input'
import { useEventSource } from './hooks/useEventSource'
import { CommandPalette } from './components/CommandPalette'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetBody } from './components/ui/sheet'
import { Virtuoso } from 'react-virtuoso'
import Fuse from 'fuse.js'
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from './components/ui/tooltip'
import { Share2 } from 'lucide-react'

type ScoreItem = { variant: string; total_points?: number; last_score?: number; details?: any }
type Episode = { ts: number; run_id: string; variant?: string; episode_id?: string; score?: number; error_count?: number }
type LogRow = { ts: number; run_id: string; variant?: string; source?: string; stream?: string; message: string }

const apiBase = (import.meta.env.VITE_API_BASE as string) || ''

export default function App(){
  const [tab, setTab] = React.useState<'status'|'episodes'|'logs'>('status')
  const [runId, setRunId] = React.useState<string>('')
  const [logsFilter, setLogsFilter] = React.useState({ runId: '', variant: '', source: '', stream: '', limit: 50 })
  const [scoreboard, setScoreboard] = React.useState<ScoreItem[]>([])
  const [episodes, setEpisodes] = React.useState<Episode[]>([])
  const [logs, setLogs] = React.useState<LogRow[]>([])
  const [logsSearch, setLogsSearch] = React.useState('')
  const [selected, setSelected] = React.useState<LogRow | null>(null)
  const { online, messages } = useEventSource(apiBase ? apiBase.replace(/\/$/, '') + '/stream' : null)
  const [openCmd, setOpenCmd] = React.useState(false)
  const [openSheet, setOpenSheet] = React.useState(false)
  const [openHelp, setOpenHelp] = React.useState(false)
  const [openOpt, setOpenOpt] = React.useState(false)
  const [optDiff, setOptDiff] = React.useState<string>('')
  const [optLoading, setOptLoading] = React.useState<boolean>(false)
  const [shareCopied, setShareCopied] = React.useState(false)
  const [shareCopiedLogs, setShareCopiedLogs] = React.useState(false)
  const [recent, setRecent] = React.useState<{ url: string; ts: number }[]>([])
  const [runNotes, setRunNotes] = React.useState<string>('')
  const [savingNotes, setSavingNotes] = React.useState<boolean>(false)
  const [toasts, setToasts] = React.useState<{ id: number; msg: string }[]>([])
  const [openRunMenu, setOpenRunMenu] = React.useState(false)
  const runInputRef = React.useRef<HTMLInputElement>(null)
  const [research, setResearch] = React.useState<any[]>([])
  const [loadingResearch, setLoadingResearch] = React.useState(false)
  const [explains, setExplains] = React.useState<Record<string, { why?: string; path?: string }>>({})
  const [suggestions, setSuggestions] = React.useState<{ title: string; why?: string; key?: string }[]>([])
  const memorySuggestions = React.useMemo(() => {
    // Parse the last "[memory] Suggestions:" block from runNotes
    try {
      const lines = (runNotes || '').split('\n')
      let lastIdx = -1
      for (let i=0;i<lines.length;i++){
        if (lines[i].toLowerCase().includes('[memory] suggestions')) lastIdx = i
      }
      if (lastIdx === -1) return [] as string[]
      const out: string[] = []
      for (let i = lastIdx+1; i<lines.length; i++){
        const ln = lines[i].trim()
        if (!ln) continue
        if (ln.startsWith('- ')) out.push(ln.substring(2).trim())
        else if (ln.startsWith('[')) break
      }
      return out.slice(0,3)
    } catch { return [] as string[] }
  }, [runNotes])

  const fetchJSON = async <T,>(path: string): Promise<T | null> => {
    try {
      const res = await fetch((apiBase || '') + path)
      const js = await res.json()
      return js as T
    } catch { return null }
  }

  async function refreshScoreboard(){
    const qs = runId ? ('?run_id=' + encodeURIComponent(runId)) : ''
    const js = await fetchJSON<{ ok: boolean; items: any[] }>(`/scoreboard${qs}`)
    if (js?.ok) setScoreboard(js.items as any)
  }

  async function loadRunNotes(){
    if (!runId) { setRunNotes(''); return }
    const js = await fetchJSON<{ ok: boolean; notes?: string }>(`/runs/${encodeURIComponent(runId)}/notes`)
    if (js?.ok) setRunNotes(js.notes || '')
  }

  async function saveRunNotes(){
    if (!runId) return
    try {
      setSavingNotes(true)
      await fetch((apiBase || '') + `/runs/${encodeURIComponent(runId)}/notes`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ notes: runNotes || '' })
      })
      pushToast('Notes saved')
    } finally { setSavingNotes(false) }
  }

  async function refreshResearch(){
    try {
      setLoadingResearch(true)
      const res = await fetch((apiBase||'') + `/memory/research?scope=research&limit=3`)
      const js = await res.json()
      if (js?.ok && Array.isArray(js.items)) setResearch(js.items)
    } catch {}
    finally { setLoadingResearch(false) }
  }

  React.useEffect(() => { refreshResearch() }, [])

  async function fetchExplain(key: string){
    try {
      const js = await fetch((apiBase||'') + `/memory/explain?key=${encodeURIComponent(`lessons/${key}`)}`).then(r=>r.json()).catch(()=>null)
      const item = js?.result?.items?.[0]
      if (item){
        setExplains(prev => ({ ...prev, [key]: { why: item.why || '', path: item.path || '' } }))
      }
    } catch {}
  }

  React.useEffect(() => {
    // Load fresh memory suggestions for current run
    (async () => {
      try {
        if (!runId) { setSuggestions([]); return }
        const js = await fetch((apiBase||'') + `/memory/suggestions?run_id=${encodeURIComponent(runId)}&k=3`).then(r=>r.json()).catch(()=>null)
        if (js?.ok && Array.isArray(js.items)) setSuggestions(js.items)
      } catch { setSuggestions([]) }
    })()
  }, [runId, messages])

  async function optimizeAndShow(){
    try {
      setOptLoading(true)
      const res = await fetch((apiBase||'') + '/optimize_from_spec')
      if (!res.ok){
        pushToast('Optimize failed — try CLI optimize for details')
        return
      }
      const js = await res.json()
      if (js?.ok) {
        setOptDiff(js.diff || '')
        setOpenOpt(true)
        pushToast('Optimize diff loaded')
      } else {
        pushToast('Optimize failed — check constraints and approaches')
      }
    } catch {
      pushToast('Optimize failed — backend offline?')
    } finally { setOptLoading(false) }
  }

  async function runAgain(fast=false){
    // Show toast immediately for responsive UX; attempt fetch but don't block
    pushToast(fast ? 'Fast run started' : 'Run started')
    const body = { spec_path: 'gamified.yaml', fast }
    try {
      await fetch((apiBase||'') + '/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    } catch {}
  }

  async function refreshEpisodes(){
    const p = new URLSearchParams()
    if (runId) p.set('run_id', runId)
    const js = await fetchJSON<{ ok: boolean; items: any[] }>(`/episodes?${p.toString()}`)
    if (js?.ok) setEpisodes(js.items as any)
  }

  async function refreshLogs(){
    const p = new URLSearchParams()
    if (logsFilter.runId) p.set('run_id', logsFilter.runId)
    if (logsFilter.variant) p.set('variant', logsFilter.variant)
    if (logsFilter.source) p.set('source', logsFilter.source)
    if (logsFilter.stream) p.set('stream', logsFilter.stream)
    p.set('limit', String(logsFilter.limit || 50))
    const js = await fetchJSON<{ ok: boolean; items: any[] }>(`/logs?${p.toString()}`)
    if (js?.ok) setLogs(js.items as any)
  }

  function pushToast(msg: string){
    const id = Date.now() + Math.floor(Math.random()*1000)
    setToasts(ts => [...ts, { id, msg }])
    setTimeout(() => setToasts(ts => ts.filter(t => t.id !== id)), 2000)
  }

  // Initialize from URL
  React.useEffect(() => {
    try {
      const sp = new URLSearchParams(window.location.search)
      const t = sp.get('tab') as any
      if (t === 'episodes' || t === 'logs' || t === 'status') setTab(t)
      const r = sp.get('run'); if (r) setRunId(r)
      setLogsFilter(v => ({
        ...v,
        runId: sp.get('run') || v.runId,
        variant: sp.get('variant') || v.variant,
        source: sp.get('source') || v.source,
        stream: sp.get('stream') || v.stream,
        limit: Number(sp.get('limit') || v.limit) || v.limit,
      }))
      setLogsSearch(sp.get('q') || '')
      // load recent
      try { const saved = JSON.parse(localStorage.getItem('recentViews') || '[]'); if (Array.isArray(saved)) setRecent(saved) } catch {}
    } catch {}
    refreshScoreboard(); refreshEpisodes(); loadRunNotes();
  }, [])

  // Keyboard shortcuts (avoid when typing)
  React.useEffect(() => {
    function isTypingTarget(el: any){
      if (!el) return false
      const tag = (el.tagName || '').toLowerCase()
      const editable = el.isContentEditable
      return tag === 'input' || tag === 'textarea' || editable
    }
    function onKey(e: KeyboardEvent){
      if (isTypingTarget(e.target)) return
      if (e.key === 'r'){ e.preventDefault(); runAgain(false) }
      if (e.key === 'f'){ e.preventDefault(); runAgain(true) }
      if (e.key === 'o'){ e.preventDefault(); optimizeAndShow() }
      if (e.key === '/'){
        e.preventDefault(); try { runInputRef.current?.focus() } catch {}
      }
      if (e.key === '?'){ e.preventDefault(); setOpenHelp(true) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Persist filters to URL (shareable link)
  React.useEffect(() => {
    const sp = new URLSearchParams(window.location.search)
    sp.set('tab', tab)
    if (runId) sp.set('run', runId); else sp.delete('run')
    const { runId: lrun, variant, source, stream, limit } = logsFilter
    if (lrun) sp.set('run', lrun)
    if (variant) sp.set('variant', variant); else sp.delete('variant')
    if (source) sp.set('source', source); else sp.delete('source')
    if (stream) sp.set('stream', stream); else sp.delete('stream')
    if (limit) sp.set('limit', String(limit))
    if (logsSearch) sp.set('q', logsSearch); else sp.delete('q')
    const url = new URL(window.location.href)
    url.search = sp.toString()
    window.history.replaceState({}, '', url)
    // Persist recent views (dedupe by full URL)
    try {
      const key = url.toString()
      setRecent(prev => {
        const exists = prev.find(v => v.url === key)
        const next = exists ? prev : [{ url: key, ts: Date.now() }, ...prev].slice(0, 10)
        localStorage.setItem('recentViews', JSON.stringify(next))
        return next
      })
    } catch {}
  }, [tab, runId, logsFilter.runId, logsFilter.variant, logsFilter.source, logsFilter.stream, logsFilter.limit, logsSearch])
  React.useEffect(() => {
    // lightweight wire-up: if an incoming SSE mentions type keys, refresh the relevant section
    const last = messages[messages.length - 1]
    if (!last) return
    if (last.type === 'score' || last.type === 'status') refreshScoreboard()
    if (last.type === 'episode') refreshEpisodes()
    if (last.type === 'log') refreshLogs()
  }, [messages])

  function applyFromUrl(u: string){
    try {
      const url = new URL(u, window.location.origin)
      const sp = url.searchParams
      const t = sp.get('tab') as any
      if (t === 'episodes' || t === 'logs' || t === 'status') setTab(t)
      const r = sp.get('run')
      setRunId(r || '')
      setLogsFilter(v => ({
        ...v,
        runId: r || '',
        variant: sp.get('variant') || '',
        source: sp.get('source') || '',
        stream: sp.get('stream') || '',
        limit: Number(sp.get('limit') || v.limit) || v.limit,
      }))
      setLogsSearch(sp.get('q') || '')
      window.history.replaceState({}, '', url)
    } catch {}
  }

  const items = [
    { id: 'refresh-score', label: 'Refresh Scoreboard', onSelect: refreshScoreboard },
    { id: 'refresh-episodes', label: 'Refresh Episodes', onSelect: refreshEpisodes },
    { id: 'refresh-logs', label: 'Refresh Logs', onSelect: refreshLogs },
    { id: 'copy-share-url', label: 'Copy Share URL', hint: 'Copy current filters', onSelect: async () => {
        try { await navigator.clipboard.writeText(window.location.href) } catch {}
      } },
    { id: 'load-demo-logs', label: 'Load Demo Logs (5000)', hint: 'Virtualization & search', onSelect: () => {
        const demo: LogRow[] = Array.from({ length: 5000 }).map((_, i) => ({
          ts: Math.floor(Date.now()/1000) - (5000 - i),
          run_id: 'demo-run',
          variant: ['alpha','beta','gamma'][i % 3],
          source: i % 10 === 0 ? 'codex' : 'app',
          stream: i % 2 === 0 ? 'stdout' : 'app',
          message: `demo-item-${String(i).padStart(5,'0')} ${i % 10 === 0 ? 'error spike' : 'ok'}`
        }))
        setLogs(demo)
      }
    },
    { id: 'clear-logs', label: 'Clear Logs', onSelect: () => setLogs([]) },
    { id: 'toggle-dark', label: 'Toggle Dark Mode', onSelect: () => {
        const c = document.documentElement.classList
        c.toggle('dark')
      } },
    // Recent views
    ...recent.slice(0,5).map((v, idx) => ({
      id: `recent-${idx}`,
      label: `Recent: ${new URL(v.url).search}`,
      hint: new Date(v.ts).toLocaleTimeString(),
      onSelect: () => applyFromUrl(v.url)
    })),
  ]

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 w-full border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="text-sm text-muted-foreground">Gamified</div>
            <div className="text-sm">Dashboard</div>
          </div>
          <div className="flex items-center gap-2">
            <div className="text-xs text-muted-foreground">{apiBase || '/'}{online ? ' • online' : ' • offline'}</div>
            <Button variant="secondary" title="Open command palette" onClick={() => setOpenCmd(true)}>Ctrl/Cmd+K</Button>
            <Button variant="outline" title="About & Happy Path" onClick={() => setOpenHelp(true)}>Help</Button>
          </div>
        </div>
      </header>

      <main className="container py-4">
        <Tabs value={tab} onValueChange={(v)=>setTab(v as any)}>
          <TabsList>
            <TabsTrigger value="status">Status</TabsTrigger>
            <TabsTrigger value="episodes">Episodes</TabsTrigger>
            <TabsTrigger value="logs">Logs</TabsTrigger>
          </TabsList>

          <TabsContent value="status">
            <Card>
              <CardHeader>
                <CardTitle>Scoreboard</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-xs text-muted-foreground pb-1">New here? <button className="underline hover:text-foreground" onClick={()=>setOpenHelp(true)}>Open the Happy Path guide</button> (press ?)</div>
                <TooltipProvider>
                  <div className="flex items-center gap-2 pb-3">
                    <Input ref={runInputRef} placeholder="Run ID filter" title="Filter scoreboard by run" value={runId} onChange={(e) => setRunId(e.target.value)} />
                    <Button onClick={refreshScoreboard} title="Apply run filter">Apply</Button>
                    <div className="relative inline-flex">
                      <Button variant="secondary" onClick={()=>{ setOpenRunMenu(false); runAgain(false) }} title="Run Again">Run Again</Button>
                      <Button variant="outline" className="ml-1" onClick={()=>setOpenRunMenu(v=>!v)} aria-label="More run options">▾</Button>
                      {openRunMenu && (
                        <div className="absolute right-0 mt-9 w-48 rounded border bg-background shadow">
                          <button className="w-full text-left px-3 py-2 hover:bg-accent" onClick={()=>{ setOpenRunMenu(false); runAgain(true) }}>Run Again (fast)</button>
                        </div>
                      )}
                    </div>
                    <Button onClick={optimizeAndShow} disabled={optLoading} title="Optimize prompt and run">{optLoading ? 'Optimizing…' : 'Optimize + Run'}</Button>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button variant="outline" aria-label="Share" onClick={async () => { try { await navigator.clipboard.writeText(window.location.href); setShareCopied(true); setTimeout(()=>setShareCopied(false), 1200) } catch {} }}>
                          <Share2 className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>{shareCopied ? 'Copied!' : 'Copy share URL'}</TooltipContent>
                    </Tooltip>
                    <a href={(apiBase||'') + '/memory/help'} target="_blank" rel="noreferrer" className="ml-2 text-sm underline">Memory Docs</a>
                  </div>
                </TooltipProvider>
                {runId && (
                  <div className="pb-4">
                    <div className="text-sm text-muted-foreground pb-1">Run Notes</div>
                    <textarea
                      className="w-full h-24 p-2 rounded border bg-background"
                      placeholder="Notes for this run (shared via link)"
                      value={runNotes}
                      onChange={e => setRunNotes(e.target.value)}
                    />
                    <div className="pt-2 flex gap-2">
                      <Button variant="secondary" onClick={saveRunNotes} disabled={savingNotes}>{savingNotes ? 'Saving…' : 'Save Notes'}</Button>
                    </div>
                    {(memorySuggestions.length > 0 || suggestions.length > 0) && (
                      <div className="pt-3">
                        <div className="text-sm text-muted-foreground">Latest Memory Suggestions</div>
                        {suggestions.length > 0 ? (
                          <ul className="list-disc ml-5 text-xs text-muted-foreground">
                            {suggestions.map((s, i) => (
                              <li key={i}>
                                <span className="font-medium">{s.title}</span>
                                {s.why ? <span className="ml-1 text-muted-foreground">({s.why})</span> : null}
                                {s.key ? <Button size="sm" variant="ghost" className="ml-2" onClick={()=>fetchExplain(String(s.key))}>Explain</Button> : null}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <ul className="list-disc ml-5 text-xs text-muted-foreground">
                            {memorySuggestions.map((s, i) => (<li key={i}>{s}</li>))}
                          </ul>
                        )}
                      </div>
                    )}
                    {/* Optional: Research ideas panel (operator); shows arXiv-derived lessons */}
                    <div className="pt-6">
                      <div className="flex items-center gap-2 pb-2">
                        <div className="text-sm text-muted-foreground">New Research Ideas</div>
                        <Button variant="ghost" onClick={refreshResearch} disabled={loadingResearch}>{loadingResearch ? '…' : 'Refresh'}</Button>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {research.map((it, idx) => (
                          <Card key={it._key || idx} className="border-muted">
                            <CardContent className="p-3">
                              <div className="font-medium text-sm pb-1 truncate" title={it.title}>{it.title}</div>
                              {(it.chunks && it.chunks.length > 0) ? (
                                <ul className="list-disc ml-5 text-xs text-muted-foreground">
                                  {(it.chunks as string[]).slice(0,2).map((c, i) => (<li key={i}>{c}</li>))}
                                </ul>
                              ) : (
                                <div className="text-xs text-muted-foreground">(no extracted ideas)</div>
                              )}
                              <div className="pt-2 flex gap-2 items-center">
                                {it.pdf_url ? <a className="text-xs underline" href={it.pdf_url} target="_blank" rel="noreferrer">PDF</a> : null}
                                <Button size="sm" variant="ghost" onClick={()=>fetchExplain(String(it._key))}>Explain</Button>
                                <Button size="sm" variant="outline" onClick={async ()=>{
                                  try { await fetch((apiBase||'') + '/memory/feedback', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ lesson_title: it.title, lesson_scope: 'research', helpful: true }) }) } catch {}
                                }}>Helpful</Button>
                                <Button size="sm" variant="ghost" onClick={async ()=>{
                                  try { await fetch((apiBase||'') + '/memory/feedback', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ lesson_title: it.title, lesson_scope: 'research', helpful: false }) }) } catch {}
                                }}>Not helpful</Button>
                              </div>
                              {explains[String(it._key)] && (
                                <div className="pt-2 text-xs text-muted-foreground">
                                  <div><span className="font-medium">Why:</span> {explains[String(it._key)].why || ''}</div>
                                  <div className="truncate"><span className="font-medium">Path:</span> {explains[String(it._key)].path || ''}</div>
                                </div>
                              )}
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {scoreboard.map((s, idx) => (
                    <Card key={idx} className="border-muted">
                      <CardHeader className="pb-2"><CardTitle className="text-base">{s.variant || 'variant'}</CardTitle></CardHeader>
                      <CardContent>
                        <div className="text-sm text-muted-foreground">Total</div>
                        <div className="text-2xl font-semibold">{Number((s.total_points ?? s.last_score ?? 0)).toFixed(2)}</div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="episodes">
            <Card>
              <CardHeader><CardTitle>Recent Episodes</CardTitle></CardHeader>
              <CardContent>
                <div className="overflow-auto">
                  <table className="w-full text-sm">
                    <thead className="text-muted-foreground"><tr><th className="text-left p-2">Time</th><th className="text-left p-2">Run</th><th className="text-left p-2">Variant</th><th className="text-left p-2">Episode</th><th className="text-left p-2">Score</th><th className="text-left p-2">Errors</th></tr></thead>
                    <tbody>
                      {episodes.map((e, i) => (
                        <tr key={i} className="border-t cursor-pointer hover:bg-accent" onClick={()=>{ if (e.run_id){ setRunId(e.run_id); setTab('status') } }}>
                          <td className="p-2">{new Date((e.ts||0)*1000).toLocaleString()}</td>
                          <td className="p-2">{e.run_id}</td>
                          <td className="p-2">{e.variant||''}</td>
                          <td className="p-2">{e.episode_id||''}</td>
                          <td className="p-2">{e.score != null ? Number(e.score).toFixed(2) : ''}</td>
                          <td className="p-2">{e.error_count || 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="logs">
            <Card>
              <CardHeader><CardTitle>Logs</CardTitle></CardHeader>
              <CardContent>
                <TooltipProvider>
                  <div className="flex flex-wrap items-center gap-2 pb-3">
                    <Input placeholder="Run" value={logsFilter.runId} onChange={e => setLogsFilter(v => ({...v, runId: e.target.value}))} />
                    <Input placeholder="Variant" value={logsFilter.variant} onChange={e => setLogsFilter(v => ({...v, variant: e.target.value}))} />
                    <Input placeholder="Source" value={logsFilter.source} onChange={e => setLogsFilter(v => ({...v, source: e.target.value}))} />
                    <Input placeholder="Stream" value={logsFilter.stream} onChange={e => setLogsFilter(v => ({...v, stream: e.target.value}))} />
                    <Input placeholder="Limit" value={String(logsFilter.limit)} onChange={e => setLogsFilter(v => ({...v, limit: Number(e.target.value)||50}))} />
                    <Button onClick={refreshLogs}>Apply</Button>
                    <Input placeholder="Search logs" value={logsSearch} onChange={e => setLogsSearch(e.target.value)} />
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button variant="outline" aria-label="Share" onClick={async () => { try { await navigator.clipboard.writeText(window.location.href); setShareCopiedLogs(true); setTimeout(()=>setShareCopiedLogs(false), 1200) } catch {} }}>
                          <Share2 className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>{shareCopiedLogs ? 'Copied!' : 'Copy share URL'}</TooltipContent>
                    </Tooltip>
                  </div>
                </TooltipProvider>
                {runId && (
                  <div className="pb-4">
                    <div className="text-sm text-muted-foreground pb-1">Run Notes</div>
                    <textarea
                      className="w-full h-24 p-2 rounded border bg-background"
                      placeholder="Notes for this run (shared via link)"
                      value={runNotes}
                      onChange={e => setRunNotes(e.target.value)}
                    />
                    <div className="pt-2 flex gap-2">
                      <Button variant="secondary" onClick={saveRunNotes} disabled={savingNotes}>{savingNotes ? 'Saving…' : 'Save Notes'}</Button>
                    </div>
                  </div>
                )}
                <div className="h-[60vh] w-full">
                  <div className="grid grid-cols-[180px_1fr_1fr_1fr_1fr_1fr] text-sm text-muted-foreground px-2">
                    <div className="p-2">Time</div>
                    <div className="p-2">Run</div>
                    <div className="p-2">Variant</div>
                    <div className="p-2">Source</div>
                    <div className="p-2">Stream</div>
                    <div className="p-2">Message</div>
                  </div>
                  <hr className="border-muted" />
                  <Virtuoso
                    data={React.useMemo(() => {
                      if (!logsSearch) return logs
                      try {
                        const f = new Fuse(logs, { keys: ['message','source','variant','stream'], ignoreLocation: true, threshold: 0.35 })
                        return f.search(logsSearch).map(r => r.item)
                      } catch { return logs }
                    }, [logs, logsSearch])}
                    itemContent={(index, l) => (
                      <div
                        role="row"
                        className="grid grid-cols-[180px_1fr_1fr_1fr_1fr_1fr] border-b hover:bg-accent cursor-pointer"
                        onClick={() => { setSelected(l); setOpenSheet(true) }}
                      >
                        <div className="p-2 whitespace-nowrap">{new Date((l.ts||0)*1000).toLocaleString()}</div>
                        <div className="p-2">{l.run_id}</div>
                        <div className="p-2">{l.variant||''}</div>
                        <div className="p-2">{l.source||''}</div>
                        <div className="p-2">{l.stream||''}</div>
                        <div className="p-2 max-w-[800px] truncate" title={l.message}>{l.message}</div>
                      </div>
                    )}
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>

      <CommandPalette open={openCmd} onOpenChange={setOpenCmd} items={items} />

      <Sheet open={openSheet} onOpenChange={setOpenSheet}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Log Details</SheetTitle>
          </SheetHeader>
          <SheetBody>
            {selected ? (
              <>
                <div className="pb-2"><Button onClick={()=>{ if (selected?.run_id){ setRunId(selected.run_id); setTab('status') } }}>View in Status</Button></div>
                <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(selected, null, 2)}</pre>
              </>
            ) : (
              <div className="text-sm text-muted-foreground">No log selected</div>
            )}
          </SheetBody>
        </SheetContent>
      </Sheet>

      <Sheet open={openHelp} onOpenChange={setOpenHelp}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>About &amp; Help</SheetTitle>
          </SheetHeader>
          <SheetBody>
            <div className="text-sm text-muted-foreground pb-2">Happy Path (minimal surface):</div>
            <ol className="list-decimal ml-5 text-sm">
              <li>Init a spec: <code>python -m prototypes.gamified.cli init</code></li>
              <li>Run: <code>python -m prototypes.gamified.cli run --spec gamified.yaml</code></li>
              <li>Open dashboard: <code>python -m prototypes.gamified.cli open</code></li>
              <li>Replay: <code>python -m prototypes.gamified.cli replay &lt;run_id&gt;</code></li>
            </ol>
            <div className="pt-3 text-sm">Guide (in repo): <code>docs/03_guides/HAPPYPATH_GUIDE.md</code></div>
          </SheetBody>
        </SheetContent>
      </Sheet>

      <Sheet open={openOpt} onOpenChange={setOpenOpt}>
        <SheetContent>
          <SheetHeader><SheetTitle>Optimize Diff</SheetTitle></SheetHeader>
          <SheetBody>
            <div className="text-sm text-muted-foreground pb-2">Why Optimize + Run? Ensures your prompt is unambiguous and scored fairly (normalized weights, required constraints). Accepting applies improvements, then runs.</div>
            {optDiff ? (
              <pre className="text-xs whitespace-pre-wrap">{optDiff}</pre>
            ) : (
              <div className="text-sm text-muted-foreground">No diff</div>
            )}
            <div className="pt-3">
              <Button onClick={()=>{ setOpenOpt(false); pushToast('Run started'); runAgain(false) }}>Accept + Run</Button>
            </div>
          </SheetBody>
        </SheetContent>
      </Sheet>

      {/* Keyboard hints footer */}
      <div className="fixed bottom-2 left-3 z-40 text-xs text-muted-foreground bg-background/70 backdrop-blur px-2 py-1 rounded border">
        ? Help • r Run Again • f Fast • o Optimize • / Focus filter
      </div>

      {/* Toasts */}
      <div className="fixed bottom-3 right-3 space-y-2 z-50">
        {toasts.map(t => (
          <div key={t.id} className="rounded bg-foreground text-background px-3 py-2 text-sm shadow">{t.msg}</div>
        ))}
      </div>
    </div>
  )
}
