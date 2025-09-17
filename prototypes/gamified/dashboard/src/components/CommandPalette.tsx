import React from 'react'
import { Command } from 'cmdk'
import { cn } from '../lib/utils'

type Item = { id: string; label: string; hint?: string; onSelect: () => void }

export function CommandPalette({ open, onOpenChange, items }: { open: boolean; onOpenChange: (b: boolean) => void; items: Item[] }){
  const [value, setValue] = React.useState('')
  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k'){
        e.preventDefault()
        onOpenChange(!open)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open])

  return (
    <div className={cn("fixed inset-0 z-50 items-start justify-center bg-black/20 backdrop-blur-sm p-4", open ? 'flex' : 'hidden')} onClick={() => onOpenChange(false)}>
      <Command label="Command Menu" className="w-full max-w-xl rounded-lg border bg-background text-foreground shadow-lg" onKeyDown={(e) => e.stopPropagation()} onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b px-3">
          <Command.Input value={value} onValueChange={setValue} placeholder="Search actions…" className="h-11 flex-1 bg-transparent outline-none" />
        </div>
        <Command.List className="max-h-80 overflow-auto p-1">
          {items.map((it) => (
            <Command.Item key={it.id} value={it.label} onSelect={() => { it.onSelect(); onOpenChange(false) }} className="flex items-center justify-between rounded-md px-3 py-2 aria-selected:bg-accent">
              <span>{it.label}</span>
              {it.hint && <span className="text-xs text-muted-foreground">{it.hint}</span>}
            </Command.Item>
          ))}
        </Command.List>
      </Command>
    </div>
  )
}
