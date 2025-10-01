import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

export type ChatChip = { key: string; label: string; active: boolean };
export type ChatMessage = { role: "user"|"assistant"; content: string; actions?: { label: string; onClick: ()=>void }[] };

export function ChatPanel({
  chips,
  onToggleChip,
  messages,
  onSend,
  pending,
  autoFocus = true,
  prefillText,
}: {
  chips: ChatChip[];
  onToggleChip: (key:string)=>void;
  messages: ChatMessage[];
  onSend: (text:string)=>void;
  pending?: boolean;
  autoFocus?: boolean;
  prefillText?: string;
}) {
  const [text, setText] = React.useState("");
  const taRef = React.useRef<HTMLTextAreaElement|null>(null);
  React.useEffect(()=>{ if (autoFocus) setTimeout(()=> taRef.current?.focus(), 0); }, [autoFocus]);
  React.useEffect(()=>{ if (typeof prefillText === 'string') setText(prefillText); }, [prefillText]);

  const doSend = () => {
    const t = text.trim();
    if (!t) return;
    onSend(t);
    setText("");
  };

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex items-center gap-2 px-3 py-2">
        <div className="font-medium text-sm">Chat</div>
        <Separator orientation="vertical" className="mx-1" />
        <div className="flex gap-1 flex-wrap">
          {chips.map(c=> (
            <Badge
              key={c.key}
              variant={c.active ? "secondary" : "outline"}
              onClick={()=> onToggleChip(c.key)}
              className="cursor-pointer"
            >{c.label}</Badge>
          ))}
        </div>
      </div>
      <Separator />
      <ScrollArea className="flex-1 px-3 py-2">
        <div role="log" aria-live="polite" className="space-y-3">
          {messages.map((m,i)=> (
            <div key={i} className="text-sm">
              <div className="font-medium text-muted-foreground">{m.role === 'user' ? 'You' : 'Assistant'}</div>
              <div className="whitespace-pre-wrap">{m.content}</div>
              {!!m.actions?.length && (
                <div className="mt-1 flex gap-2 flex-wrap">
                  {m.actions.map((a,j)=> (
                    <Button key={j} size="sm" variant="outline" onClick={a.onClick}>{a.label}</Button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
      <div className="border-t p-2 flex items-end gap-2">
        <Textarea
          ref={taRef}
          value={text}
          onChange={e=>setText(e.target.value)}
          onKeyDown={e=>{ if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); doSend(); } }}
          placeholder="Ask about selection…"
          className="min-h-[44px]"
          aria-label="Chat message"
        />
        <Button onClick={doSend} disabled={pending || !text.trim()}>Send</Button>
      </div>
    </div>
  );
}
